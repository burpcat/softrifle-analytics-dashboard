import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from config import get_settings
from database import get_db
from models import Campaign, Creator
from schemas import CreatorListResponse, CreatorResponse
from services.health_score import compute_health_scores
from services.youtube import DEFAULT_SEGMENTS, _fetch_creators_for_segment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/creators", tags=["creators"])
settings = get_settings()

# ---------------------------------------------------------------------------
# Sort column map — explicit dict, no getattr.
# Defense-in-depth: even if a value slips past the Query validator,
# an unmapped key returns None and raises 400 before touching the query.
# ---------------------------------------------------------------------------

SORT_COLUMNS = {
    "health_score":     Creator.health_score,
    "followers":        Creator.followers,
    "engagement_rate":  Creator.engagement_rate,
    "avg_views":        Creator.avg_views,
    "posts_per_week":   Creator.posts_per_week,
}


# ---------------------------------------------------------------------------
# GET /api/creators
# ---------------------------------------------------------------------------

@router.get("", response_model=CreatorListResponse)
def get_creators(
    platform:         Optional[str] = Query(default=None),
    category:         Optional[str] = Query(default=None),
    min_health_score: Optional[float] = Query(default=None, ge=0, le=100),
    max_health_score: Optional[float] = Query(default=None, ge=0, le=100),
    search:           Optional[str] = Query(default=None, min_length=1, max_length=100),
    sort_by:          str  = Query(default="health_score"),
    sort_order:       str  = Query(default="desc", pattern="^(asc|desc)$"),
    page:             int  = Query(default=1, ge=1),
    page_size:        int  = Query(default=20, ge=1, le=100),
    db:               Session = Depends(get_db),
) -> CreatorListResponse:
    """List creators with optional filtering, sorting, and pagination.

    NULL health_score creators appear in unfiltered results but are excluded
    when min_health_score or max_health_score filters are active — standard
    SQL NULL comparison behaviour. Frontend should surface this if the filtered
    count is significantly lower than the unfiltered count.
    """
    # --- Validate sort_by against explicit allowlist ---
    order_col = SORT_COLUMNS.get(sort_by)
    if order_col is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by value '{sort_by}'. "
                   f"Allowed: {sorted(SORT_COLUMNS.keys())}",
        )

    q = db.query(Creator)

    # --- Filters ---
    if platform:
        try:
            from models import DataSource
            DataSource(platform)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform '{platform}'. "
                       f"Allowed: {[e.value for e in DataSource]}",
            )
        q = q.filter(Creator.platform == platform)

    if category:
        q = q.filter(func.lower(Creator.category) == category.strip().lower())

    if min_health_score is not None:
        q = q.filter(Creator.health_score >= min_health_score)

    if max_health_score is not None:
        q = q.filter(Creator.health_score <= max_health_score)

    if search:
        term = search.strip().lower()
        q = q.filter(
            func.lower(Creator.username).contains(term)
            | func.lower(Creator.display_name).contains(term)
        )

    # --- Sorting ---
    ordered = (
        q.order_by(order_col.desc())
        if sort_order == "desc"
        else q.order_by(order_col.asc())
    )

    # --- Pagination ---
    total   = q.count()
    offset  = (page - 1) * page_size
    results = ordered.offset(offset).limit(page_size).all()

    return CreatorListResponse(
        total     = total,
        page      = page,
        page_size = page_size,
        results   = [CreatorResponse.model_validate(c) for c in results],
    )


# ---------------------------------------------------------------------------
# GET /api/creators/{creator_id}
# ---------------------------------------------------------------------------

@router.get("/{creator_id}", response_model=CreatorResponse)
def get_creator(
    creator_id: str,
    db: Session = Depends(get_db),
) -> CreatorResponse:
    """Fetch a single creator by ID with their linked campaigns eagerly loaded.

    joinedload(Creator.campaigns) fetches all linked campaigns in one query.
    Campaigns are capped at 5 per creator by linker.py — payload size is bounded.
    """
    creator = (
        db.query(Creator)
        .options(joinedload(Creator.campaigns))
        .filter(Creator.id == creator_id)
        .first()
    )

    if creator is None:
        raise HTTPException(
            status_code=404,
            detail=f"Creator '{creator_id}' not found.",
        )

    return CreatorResponse.model_validate(creator)


# ---------------------------------------------------------------------------
# Ingest models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    category: str
    keywords: list[str] = []
    max_results: int = Field(default=10, ge=1, le=30)


class IngestCreator(BaseModel):
    id: str
    display_name: str | None
    username: str
    category: str | None
    followers: int
    health_score: float | None


class IngestResponse(BaseModel):
    status: str
    new_creators_added: int
    duplicates_skipped: int
    total_creators_now: int
    creators: list[IngestCreator]


# ---------------------------------------------------------------------------
# POST /api/creators/ingest
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=IngestResponse)
def ingest_creators(request: IngestRequest, db: Session = Depends(get_db)):
    """Fetch new YouTube creators for a category and insert them into the DB.

    After insert, health scores are recomputed across the full creator pool —
    min-max normalization is global so adding new creators can shift everyone's
    scores. Deduplicates by platform_id before inserting.
    """
    # --- Guard: YouTube API key ---
    if not settings.YOUTUBE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="YouTube API key not configured — YOUTUBE_API_KEY not set",
        )

    # --- Keyword resolution ---
    keywords = request.keywords if request.keywords else (
        DEFAULT_SEGMENTS.get(request.category) or [request.category]
    )
    max_per_keyword = max(1, request.max_results // len(keywords))

    # --- Fetch from YouTube ---
    try:
        fetched = _fetch_creators_for_segment(
            api_key=settings.YOUTUBE_API_KEY,
            segment=request.category,
            keywords=keywords,
            max_per_keyword=max_per_keyword,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"YouTube API temporarily unavailable: {exc}",
        )

    # --- Deduplication ---
    existing_platform_ids = {
        row[0] for row in db.query(Creator.platform_id).all()
    }

    new_dicts: list[dict] = []
    duplicates_skipped = 0
    for c in fetched:
        if c["platform_id"] in existing_platform_ids:
            duplicates_skipped += 1
        else:
            existing_platform_ids.add(c["platform_id"])  # guard within-batch dupes
            new_dicts.append(c)

    # --- Early return: nothing new ---
    if not new_dicts:
        total = db.query(Creator).count()
        return IngestResponse(
            status="success",
            new_creators_added=0,
            duplicates_skipped=duplicates_skipped,
            total_creators_now=total,
            creators=[],
        )

    # --- Insert new creators ---
    now = datetime.now(timezone.utc)
    new_creators = [
        Creator(
            id=str(uuid.uuid4()),
            platform=c["platform"],
            platform_id=c["platform_id"],
            username=c["username"],
            display_name=c["display_name"],
            avatar_url=c["avatar_url"],
            followers=c["followers"],
            avg_views=c["avg_views"],
            engagement_rate=c["engagement_rate"],
            posts_per_week=c["posts_per_week"],
            category=c["category"],
            country=c["country"],
            health_score=None,
            created_at=now,
            last_updated=now,
        )
        for c in new_dicts
    ]
    db.add_all(new_creators)
    db.flush()  # write to session so full pool query below includes new rows

    # --- Health score recomputation over full pool ---
    all_creators = db.query(Creator).all()
    all_campaigns = db.query(Campaign).all()
    compute_health_scores(all_creators, all_campaigns)

    for creator in all_creators:
        db.add(creator)
    db.commit()

    for creator in new_creators:
        db.refresh(creator)

    return IngestResponse(
        status="success",
        new_creators_added=len(new_creators),
        duplicates_skipped=duplicates_skipped,
        total_creators_now=len(all_creators),
        creators=[
            IngestCreator(
                id=c.id,
                display_name=c.display_name,
                username=c.username,
                category=c.category,
                followers=c.followers,
                health_score=c.health_score,
            )
            for c in new_creators
        ],
    )