import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from database import get_db
from models import Campaign, Creator
from schemas import (
    AnalyticsSummaryResponse,
    ChannelComparisonItem,
    ChannelComparisonResponse,
    TopCreatorItem,
    TrendsBucket,
    TrendsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# GET /api/analytics/summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_summary(db: Session = Depends(get_db)) -> AnalyticsSummaryResponse:
    """Return high-level KPIs, breakdowns, and top creators.

    All 9 aggregation queries run inside a single read transaction to ensure
    a consistent snapshot — prevents internally inconsistent responses if a
    re-ingestion write occurs between queries.
    """
    with db.begin():
        # 1. Counts
        total_creators  = db.query(func.count(Creator.id)).scalar() or 0
        total_campaigns = db.query(func.count(Campaign.id)).scalar() or 0
        total_influencer = (
            db.query(func.count(Campaign.id))
            .filter(func.lower(Campaign.campaign_type) == "influencer")
            .scalar() or 0
        )

        # 2. Avg health score
        avg_health = db.query(func.avg(Creator.health_score)).scalar()

        # 3. Avg ROI by campaign type
        roi_by_type_rows = (
            db.query(Campaign.campaign_type, func.avg(Campaign.roi))
            .filter(Campaign.campaign_type.is_not(None))
            .group_by(Campaign.campaign_type)
            .all()
        )
        avg_roi_by_campaign_type = {row[0]: row[1] for row in roi_by_type_rows}

        # 4. Avg ROI by channel
        roi_by_channel_rows = (
            db.query(Campaign.channel_used, func.avg(Campaign.roi))
            .filter(Campaign.channel_used.is_not(None))
            .group_by(Campaign.channel_used)
            .all()
        )
        avg_roi_by_channel = {row[0]: row[1] for row in roi_by_channel_rows}

        # 5. Avg ROI by segment
        roi_by_segment_rows = (
            db.query(Campaign.customer_segment, func.avg(Campaign.roi))
            .filter(Campaign.customer_segment.is_not(None))
            .group_by(Campaign.customer_segment)
            .all()
        )
        avg_roi_by_segment = {row[0]: row[1] for row in roi_by_segment_rows}

        # 6. Top 5 creators by health_score
        # LEFT JOIN so creators with zero linked campaigns still appear.
        # avg_roi is None for unlinked creators — TopCreatorItem.avg_roi
        # is Optional[float] to accommodate this.
        top_rows = (
            db.query(
                Creator.id,
                Creator.username,
                Creator.platform,
                Creator.category,
                Creator.health_score,
                func.avg(Campaign.roi).label("avg_roi"),
            )
            .outerjoin(Campaign, Campaign.creator_id == Creator.id)
            .filter(Creator.health_score.is_not(None))
            .group_by(Creator.id)
            .order_by(Creator.health_score.desc())
            .limit(5)
            .all()
        )
        top_creators = [
            TopCreatorItem(
                id           = row.id,
                username     = row.username,
                platform     = row.platform,
                category     = row.category,
                health_score = row.health_score,
                avg_roi      = row.avg_roi,
            )
            for row in top_rows
        ]

        # 7. Platform breakdown (creator count by platform)
        platform_rows = (
            db.query(Creator.platform, func.count(Creator.id))
            .group_by(Creator.platform)
            .all()
        )
        platform_breakdown = {str(row[0].value): row[1] for row in platform_rows}

        # 8. Segment breakdown (campaign count by segment)
        segment_rows = (
            db.query(Campaign.customer_segment, func.count(Campaign.id))
            .filter(Campaign.customer_segment.is_not(None))
            .group_by(Campaign.customer_segment)
            .all()
        )
        segment_breakdown = {row[0]: row[1] for row in segment_rows}

    return AnalyticsSummaryResponse(
        total_creators              = total_creators,
        total_campaigns             = total_campaigns,
        total_influencer_campaigns  = total_influencer,
        avg_health_score            = avg_health,
        avg_roi_by_campaign_type    = avg_roi_by_campaign_type,
        avg_roi_by_channel          = avg_roi_by_channel,
        avg_roi_by_segment          = avg_roi_by_segment,
        top_creators                = top_creators,
        platform_breakdown          = platform_breakdown,
        segment_breakdown           = segment_breakdown,
    )


# ---------------------------------------------------------------------------
# GET /api/analytics/channel-comparison
# ---------------------------------------------------------------------------

@router.get("/channel-comparison", response_model=ChannelComparisonResponse)
def get_channel_comparison(
    db: Session = Depends(get_db),
) -> ChannelComparisonResponse:
    """For each channel, compare influencer vs non-influencer avg ROI and lift.

    Lift = (influencer_avg - non_influencer_avg) / non_influencer_avg.
    lift_percentage is None when either avg is missing OR non_influencer_avg
    is 0.0 — both cases make lift undefined/infinite.
    """
    rows = (
        db.query(
            Campaign.channel_used,
            # Influencer avg ROI and count
            func.avg(
                case((func.lower(Campaign.campaign_type) == "influencer", Campaign.roi))
            ).label("influencer_avg_roi"),
            func.count(
                case((func.lower(Campaign.campaign_type) == "influencer", Campaign.id))
            ).label("influencer_count"),
            # Non-influencer avg ROI and count
            func.avg(
                case((func.lower(Campaign.campaign_type) != "influencer", Campaign.roi))
            ).label("non_influencer_avg_roi"),
            func.count(
                case((func.lower(Campaign.campaign_type) != "influencer", Campaign.id))
            ).label("non_influencer_count"),
        )
        .filter(Campaign.channel_used.is_not(None))
        .group_by(Campaign.channel_used)
        .all()
    )

    items: list[ChannelComparisonItem] = []
    for row in rows:
        inf_avg     = row.influencer_avg_roi
        non_inf_avg = row.non_influencer_avg_roi

        # Guard against None and zero — both make lift undefined
        if not inf_avg or not non_inf_avg:
            lift = None
        else:
            lift = (inf_avg - non_inf_avg) / non_inf_avg

        items.append(ChannelComparisonItem(
            channel                = row.channel_used,
            influencer_avg_roi     = inf_avg,
            non_influencer_avg_roi = non_inf_avg,
            influencer_count       = row.influencer_count,
            non_influencer_count   = row.non_influencer_count,
            lift_percentage        = lift,
        ))

    return ChannelComparisonResponse(results=items)


# ---------------------------------------------------------------------------
# GET /api/analytics/trends
# ---------------------------------------------------------------------------

@router.get("/trends", response_model=TrendsResponse)
def get_trends(db: Session = Depends(get_db)) -> TrendsResponse:
    """Return monthly campaign performance buckets, split by campaign type.

    Campaigns with NULL dates are excluded — they cannot be bucketed.

    Month bucketing uses SQLite's strftime('%Y-%m', date).
    Postgres equivalent: DATE_TRUNC('month', Campaign.date)::text

    The flat query result is pivoted in Python — sparse months (where a
    campaign type has no campaigns) produce None values rather than missing
    keys, matching the TrendsBucket schema.
    """
    # strftime on a NULL date returns NULL — filter first to keep buckets clean
    rows = (
        db.query(
            func.strftime("%Y-%m", Campaign.date).label("month"),
            Campaign.campaign_type,
            func.count(Campaign.id).label("count"),
            func.avg(Campaign.roi).label("avg_roi"),
            func.avg(Campaign.conversion_rate).label("avg_conversion"),
        )
        .filter(Campaign.date.is_not(None))
        .filter(Campaign.campaign_type.is_not(None))
        .group_by("month", Campaign.campaign_type)
        .order_by("month")
        .all()
    )

    # --- Pivot flat rows into nested month buckets ---
    # Structure: month → { campaign_type → { count, avg_roi, avg_conversion } }
    pivot: dict[str, dict] = defaultdict(lambda: {
        "campaign_count_by_type": defaultdict(int),
        "avg_roi_by_type":        defaultdict(lambda: None),
        "avg_conversion_by_type": defaultdict(lambda: None),
    })

    all_campaign_types: set[str] = set()

    for row in rows:
        month = row.month
        ctype = row.campaign_type
        all_campaign_types.add(ctype)

        pivot[month]["campaign_count_by_type"][ctype] = row.count
        pivot[month]["avg_roi_by_type"][ctype]        = row.avg_roi
        pivot[month]["avg_conversion_by_type"][ctype] = row.avg_conversion

    # Build TrendsBucket list — use .get() for sparse safety
    buckets: list[TrendsBucket] = []
    for month in sorted(pivot.keys()):
        data = pivot[month]
        buckets.append(TrendsBucket(
            month                   = month,
            campaign_count_by_type  = {
                ct: data["campaign_count_by_type"].get(ct, 0)
                for ct in all_campaign_types
            },
            avg_roi_by_type         = {
                ct: data["avg_roi_by_type"].get(ct)
                for ct in all_campaign_types
            },
            avg_conversion_by_type  = {
                ct: data["avg_conversion_by_type"].get(ct)
                for ct in all_campaign_types
            },
        ))

    return TrendsResponse(results=buckets)