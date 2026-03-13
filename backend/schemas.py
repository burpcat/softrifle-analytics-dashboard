from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from models import AlertSeverity, AlertType, DataSource


# ---------------------------------------------------------------------------
# Shared config — applied to every response model
# ---------------------------------------------------------------------------

_orm_config = ConfigDict(
    from_attributes=True,   # enables model_validate(orm_obj)
    use_enum_values=True,   # enums serialize as plain strings
)


# ---------------------------------------------------------------------------
# Creator
# ---------------------------------------------------------------------------

class CreatorResponse(BaseModel):
    id:              str
    platform:        DataSource
    platform_id:     str
    username:        str
    display_name:    Optional[str]
    avatar_url:      Optional[str]
    followers:       Optional[int]
    avg_views:       Optional[float]
    engagement_rate: Optional[float]
    posts_per_week:  Optional[float]
    category:        Optional[str]
    country:         Optional[str]
    health_score:    Optional[float]
    created_at:      datetime
    last_updated:    datetime

    # Only populated on GET /api/creators/{id} — None on list endpoints
    # to prevent lazy-load N+1 queries
    campaigns: Optional[list["CampaignResponse"]] = None

    model_config = _orm_config


class CreatorListResponse(BaseModel):
    total:     int
    page:      int
    page_size: int
    results:   list[CreatorResponse]


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------

class CampaignResponse(BaseModel):
    id:               str
    campaign_id_orig: Optional[str]
    creator_id:       Optional[str]
    company:          Optional[str]
    campaign_type:    Optional[str]
    target_audience:  Optional[str]
    duration:         Optional[str]
    channel_used:     Optional[str]
    conversion_rate:  Optional[float]
    acquisition_cost: Optional[float]
    roi:              Optional[float]
    location:         Optional[str]
    language:         Optional[str]
    clicks:           Optional[int]
    impressions:      Optional[int]
    engagement_score: Optional[int]
    customer_segment: Optional[str]
    date:             Optional[date]    # serializes as "YYYY-MM-DD"
    created_at:       datetime

    # Only populated on GET /api/campaigns/{id}
    creator: Optional["CreatorResponse"] = None

    model_config = _orm_config


class CampaignListResponse(BaseModel):
    total:     int
    page:      int
    page_size: int
    results:   list[CampaignResponse]


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    id:          str
    type:        AlertType
    severity:    AlertSeverity
    message:     str
    creator_id:  Optional[str]
    campaign_id: Optional[str]
    created_at:  datetime

    model_config = _orm_config


# ---------------------------------------------------------------------------
# Analytics — Summary
# ---------------------------------------------------------------------------

class TopCreatorItem(BaseModel):
    """Slim creator shape for the top-5 summary — populated from an aggregated
    query, not a full ORM fetch. Only includes fields the query actually returns.
    Using CreatorResponse here would risk attribute errors on unloaded fields."""
    id:           str
    username:     str
    platform:     DataSource
    category:     Optional[str]
    health_score: Optional[float]
    avg_roi:      float             # computed in analytics query

    model_config = _orm_config


class AnalyticsSummaryResponse(BaseModel):
    total_creators:            int
    total_campaigns:           int
    total_influencer_campaigns: int
    avg_health_score:          Optional[float]

    # dict[campaign_type | channel | segment → avg_roi]
    # Optional[float] because AVG() over a NULL-heavy column can return None
    avg_roi_by_campaign_type:  dict[str, Optional[float]]
    avg_roi_by_channel:        dict[str, Optional[float]]
    avg_roi_by_segment:        dict[str, Optional[float]]

    top_creators:              list[TopCreatorItem]

    # dict[platform | segment → count]
    platform_breakdown:        dict[str, int]
    segment_breakdown:         dict[str, int]


# ---------------------------------------------------------------------------
# Analytics — Channel Comparison
# ---------------------------------------------------------------------------

class ChannelComparisonItem(BaseModel):
    channel:                str
    influencer_avg_roi:     Optional[float]
    non_influencer_avg_roi: Optional[float]
    influencer_count:       int
    non_influencer_count:   int
    lift_percentage:        Optional[float]  # None if either avg is missing


class ChannelComparisonResponse(BaseModel):
    results: list[ChannelComparisonItem]


# ---------------------------------------------------------------------------
# Analytics — Trends
# ---------------------------------------------------------------------------

class TrendsBucket(BaseModel):
    # Format enforced here — router is responsible for producing "YYYY-MM"
    # but the validator catches anything malformed at the schema boundary.
    month: str

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m")
        except ValueError:
            raise ValueError(f"month must be in YYYY-MM format, got: {v!r}")
        return v

    # All dicts keyed by campaign_type string
    campaign_count_by_type: dict[str, int]
    avg_roi_by_type:        dict[str, Optional[float]]
    avg_conversion_by_type: dict[str, Optional[float]]


class TrendsResponse(BaseModel):
    results: list[TrendsBucket]


# ---------------------------------------------------------------------------
# model_rebuild() calls — MANDATORY.
# CreatorResponse and CampaignResponse reference each other (circular).
# Pydantic requires explicit rebuild after both classes are fully defined,
# otherwise you get a PydanticUserError at import time.
# ---------------------------------------------------------------------------

CreatorResponse.model_rebuild()
CampaignResponse.model_rebuild()