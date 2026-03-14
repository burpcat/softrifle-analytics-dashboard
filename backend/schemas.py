import datetime as _dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from models import AlertSeverity, AlertType, DataSource


# ---------------------------------------------------------------------------
# Shared config — applied to every response model
# ---------------------------------------------------------------------------

_orm_config = ConfigDict(
    from_attributes=True,
    use_enum_values=True,
)


# ---------------------------------------------------------------------------
# Brief models — no nested relationships, used to break circular refs
# ---------------------------------------------------------------------------

class CampaignBrief(BaseModel):
    """Campaign without nested creator — used inside CreatorResponse."""
    model_config = _orm_config

    id:               str
    campaign_id_orig: Optional[str]      = None
    company:          Optional[str]      = None
    campaign_type:    Optional[str]      = None
    target_audience:  Optional[str]      = None
    duration:         Optional[str]      = None
    channel_used:     Optional[str]      = None
    conversion_rate:  Optional[float]    = None
    acquisition_cost: Optional[float]    = None
    roi:              Optional[float]    = None
    location:         Optional[str]      = None
    language:         Optional[str]      = None
    clicks:           Optional[int]      = None
    impressions:      Optional[int]      = None
    engagement_score: Optional[int]      = None
    customer_segment: Optional[str]      = None
    date:             Optional[_dt.date] = None
    created_at:       Optional[_dt.datetime] = None


class CreatorBrief(BaseModel):
    """Creator without nested campaigns — used inside CampaignResponse."""
    model_config = _orm_config

    id:           str
    platform:     DataSource
    platform_id:  str
    username:     str
    display_name: Optional[str]   = None
    avatar_url:   Optional[str]   = None
    followers:    Optional[int]   = None
    engagement_rate: Optional[float] = None
    avg_views:    Optional[float] = None
    posts_per_week: Optional[float] = None
    category:     Optional[str]   = None
    country:      Optional[str]   = None
    health_score: Optional[float] = None


# ---------------------------------------------------------------------------
# Creator
# ---------------------------------------------------------------------------

class CreatorResponse(BaseModel):
    model_config = _orm_config

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
    created_at:      _dt.datetime
    last_updated:    _dt.datetime

    campaigns: list[CampaignBrief] = []


class CreatorListResponse(BaseModel):
    total:     int
    page:      int
    page_size: int
    results:   list[CreatorResponse]


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------

class CampaignResponse(BaseModel):
    model_config = _orm_config

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
    date:             Optional[_dt.date]
    created_at:       _dt.datetime

    creator: Optional[CreatorBrief] = None


class CampaignListResponse(BaseModel):
    total:     int
    page:      int
    page_size: int
    results:   list[CampaignResponse]


# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    model_config = _orm_config

    id:          str
    type:        AlertType
    severity:    AlertSeverity
    message:     str
    creator_id:  Optional[str]
    campaign_id: Optional[str]
    created_at:  _dt.datetime


# ---------------------------------------------------------------------------
# Analytics — Summary
# ---------------------------------------------------------------------------

class TopCreatorItem(BaseModel):
    model_config = _orm_config

    id:           str
    username:     str
    platform:     DataSource
    category:     Optional[str]
    health_score: Optional[float]
    avg_roi:      Optional[float]


class AnalyticsSummaryResponse(BaseModel):
    total_creators:             int
    total_campaigns:            int
    total_influencer_campaigns: int
    avg_health_score:           Optional[float]

    avg_roi_by_campaign_type:   dict[str, Optional[float]]
    avg_roi_by_channel:         dict[str, Optional[float]]
    avg_roi_by_segment:         dict[str, Optional[float]]

    top_creators:               list[TopCreatorItem]

    platform_breakdown:         dict[str, int]
    segment_breakdown:          dict[str, int]


# ---------------------------------------------------------------------------
# Analytics — Channel Comparison
# ---------------------------------------------------------------------------

class ChannelComparisonItem(BaseModel):
    channel:                str
    influencer_avg_roi:     Optional[float]
    non_influencer_avg_roi: Optional[float]
    influencer_count:       int
    non_influencer_count:   int
    lift_percentage:        Optional[float]


class ChannelComparisonResponse(BaseModel):
    results: list[ChannelComparisonItem]


# ---------------------------------------------------------------------------
# Analytics — Trends
# ---------------------------------------------------------------------------

class TrendsBucket(BaseModel):
    month: str

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        try:
            _dt.datetime.strptime(v, "%Y-%m")
        except ValueError:
            raise ValueError(f"month must be in YYYY-MM format, got: {v!r}")
        return v

    campaign_count_by_type: dict[str, int]
    avg_roi_by_type:        dict[str, Optional[float]]
    avg_conversion_by_type: dict[str, Optional[float]]


class TrendsResponse(BaseModel):
    results: list[TrendsBucket]