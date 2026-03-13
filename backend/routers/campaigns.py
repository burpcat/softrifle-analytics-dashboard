import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Campaign
from schemas import CampaignListResponse, CampaignResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])

# ---------------------------------------------------------------------------
# Sort column map — explicit dict, no getattr. Same pattern as creators.py.
# Note: engagement_score is a Campaign column (integer, from Kaggle CSV).
#       engagement_rate is a Creator column (float, from YouTube API).
#       These are distinct metrics — ensure frontend labels them differently.
# ---------------------------------------------------------------------------

SORT_COLUMNS = {
    "date":             Campaign.date,
    "roi":              Campaign.roi,
    "conversion_rate":  Campaign.conversion_rate,
    "acquisition_cost": Campaign.acquisition_cost,
    "impressions":      Campaign.impressions,
    "clicks":           Campaign.clicks,
    "engagement_score": Campaign.engagement_score,
}


# ---------------------------------------------------------------------------
# GET /api/campaigns
# ---------------------------------------------------------------------------

@router.get("", response_model=CampaignListResponse)
def get_campaigns(
    campaign_type:    Optional[str]  = Query(default=None),
    channel_used:     Optional[str]  = Query(default=None),
    customer_segment: Optional[str]  = Query(default=None),
    company:          Optional[str]  = Query(default=None),
    min_roi:          Optional[float] = Query(default=None),
    max_roi:          Optional[float] = Query(default=None),
    date_from:        Optional[date] = Query(default=None),
    date_to:          Optional[date] = Query(default=None),
    has_creator:      Optional[bool] = Query(default=None),
    sort_by:          str  = Query(default="date"),
    sort_order:       str  = Query(default="desc", pattern="^(asc|desc)$"),
    page:             int  = Query(default=1, ge=1),
    page_size:        int  = Query(default=20, ge=1, le=100),
    db:               Session = Depends(get_db),
) -> CampaignListResponse:
    """List campaigns with optional filtering, sorting, and pagination.

    String filters (campaign_type, channel_used, customer_segment, company)
    are case-insensitive exact matches. Kaggle CSV values are title-case
    (e.g. "Influencer", "Email") — frontend may send any casing.

    has_creator=False returns ALL campaigns with creator_id IS NULL, including
    non-influencer campaigns (Email, Display, etc.) that were never eligible
    for creator linking. To find influencer campaigns missing a creator,
    combine: has_creator=False&campaign_type=Influencer.

    NULL roi/date campaigns are excluded when the corresponding range filters
    are active — standard SQL NULL comparison behaviour.
    """
    # --- Validate sort_by ---
    order_col = SORT_COLUMNS.get(sort_by)
    if order_col is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by value '{sort_by}'. "
                   f"Allowed: {sorted(SORT_COLUMNS.keys())}",
        )

    # --- Validate date range ---
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from must be before or equal to date_to.",
        )

    q = db.query(Campaign)

    # --- String filters — both sides lowercased ---
    if campaign_type:
        q = q.filter(
            func.lower(Campaign.campaign_type) == campaign_type.strip().lower()
        )

    if channel_used:
        q = q.filter(
            func.lower(Campaign.channel_used) == channel_used.strip().lower()
        )

    if customer_segment:
        q = q.filter(
            func.lower(Campaign.customer_segment) == customer_segment.strip().lower()
        )

    if company:
        q = q.filter(
            func.lower(Campaign.company) == company.strip().lower()
        )

    # --- Numeric range filters ---
    if min_roi is not None:
        q = q.filter(Campaign.roi >= min_roi)

    if max_roi is not None:
        q = q.filter(Campaign.roi <= max_roi)

    # --- Date range filters ---
    if date_from is not None:
        q = q.filter(Campaign.date >= date_from)

    if date_to is not None:
        q = q.filter(Campaign.date <= date_to)

    # --- Creator presence filter ---
    if has_creator is True:
        q = q.filter(Campaign.creator_id.isnot(None))
    elif has_creator is False:
        q = q.filter(Campaign.creator_id.is_(None))

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

    return CampaignListResponse(
        total     = total,
        page      = page,
        page_size = page_size,
        results   = [CampaignResponse.model_validate(c) for c in results],
    )


# ---------------------------------------------------------------------------
# GET /api/campaigns/{campaign_id}
# ---------------------------------------------------------------------------

@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
) -> CampaignResponse:
    """Fetch a single campaign by ID with its linked creator eagerly loaded.

    creator will be None if the campaign is not linked to a creator
    (non-influencer campaigns, or influencer campaigns where no matching
    creator was found during ingestion).
    """
    campaign = (
        db.query(Campaign)
        .options(joinedload(Campaign.creator))
        .filter(Campaign.id == campaign_id)
        .first()
    )

    if campaign is None:
        raise HTTPException(
            status_code=404,
            detail=f"Campaign '{campaign_id}' not found.",
        )

    return CampaignResponse.model_validate(campaign)