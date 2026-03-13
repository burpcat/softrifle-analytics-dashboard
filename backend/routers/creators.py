import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Creator
from schemas import CreatorListResponse, CreatorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/creators", tags=["creators"])

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
        # Validate platform value — invalid enum raises 400 not 500
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
    total     = q.count()
    offset    = (page - 1) * page_size
    results   = ordered.offset(offset).limit(page_size).all()

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