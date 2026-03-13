import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from database import Base


# ---------------------------------------------------------------------------
# Enums — single source of truth for constrained string columns.
# Used by both the ORM (DB-level CHECK constraints) and the service layer.
# ---------------------------------------------------------------------------

class DataSource(str, enum.Enum):
    youtube = "youtube"
    twitch  = "twitch"      # reserved — wired up when Twitch service is added


class AlertSeverity(str, enum.Enum):
    critical = "critical"
    warning  = "warning"
    info     = "info"


class AlertType(str, enum.Enum):
    low_roi                 = "low_roi"
    low_engagement          = "low_engagement"
    low_conversion          = "low_conversion"
    outreach_opportunity    = "outreach_opportunity"
    segment_outperformance  = "segment_outperformance"


# ---------------------------------------------------------------------------
# Creator
# ---------------------------------------------------------------------------

class Creator(Base):
    __tablename__ = "creators"

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    platform        = Column(Enum(DataSource), nullable=False)
    platform_id     = Column(String, nullable=False, index=True)   # e.g. YouTube channel ID
    username        = Column(String, nullable=False)
    display_name    = Column(String, nullable=True)
    avatar_url      = Column(String, nullable=True)

    # --- Platform stats (raw, from API) ---
    followers       = Column(Integer, nullable=True)
    avg_views       = Column(Float,   nullable=True)
    engagement_rate = Column(Float,   nullable=True)
    posts_per_week  = Column(Float,   nullable=True)

    # --- Metadata ---
    category        = Column(String, nullable=True)   # maps to Customer_Segment buckets
    country         = Column(String, nullable=True)

    # --- Derived metric (populated by health_score.py) ---
    health_score    = Column(Float, nullable=True)

    # --- Timestamps ---
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # --- Relationships ---
    campaigns       = relationship("Campaign", back_populates="creator", lazy="select")
    alerts          = relationship("Alert",    back_populates="creator", lazy="select")


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------

class Campaign(Base):
    __tablename__ = "campaigns"

    id                = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id_orig  = Column(String, nullable=True, index=True)   # original CSV Campaign_ID

    # --- FK to creator (NULL for non-influencer campaigns) ---
    creator_id        = Column(
        String,
        ForeignKey("creators.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # --- Kaggle CSV columns ---
    company           = Column(String,  nullable=True)
    campaign_type     = Column(String,  nullable=True)   # Influencer | Email | Display | ...
    target_audience   = Column(String,  nullable=True)
    duration          = Column(String,  nullable=True)   # "30 days" etc. — kept as-is from CSV
    channel_used      = Column(String,  nullable=True)
    conversion_rate   = Column(Float,   nullable=True)
    acquisition_cost  = Column(Float,   nullable=True)
    roi               = Column(Float,   nullable=True)
    location          = Column(String,  nullable=True)
    language          = Column(String,  nullable=True)
    clicks            = Column(Integer, nullable=True)
    impressions       = Column(Integer, nullable=True)
    engagement_score  = Column(Integer, nullable=True)
    customer_segment  = Column(String,  nullable=True)
    date              = Column(Date,    nullable=True)

    # --- Timestamps ---
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- Relationships ---
    creator           = relationship("Creator", back_populates="campaigns")
    alerts            = relationship("Alert",   back_populates="campaign", lazy="select")


# ---------------------------------------------------------------------------
# Alert
#
# NOTE: Both creator_id and campaign_id are intentionally nullable.
# `segment_outperformance` alerts are segment-level and don't belong to a
# specific creator or campaign — this is a known valid state, not an oversight.
# All other alert types will have at least one FK populated by alerts.py.
# ---------------------------------------------------------------------------

class Alert(Base):
    __tablename__ = "alerts"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    type        = Column(Enum(AlertType),     nullable=False)
    severity    = Column(Enum(AlertSeverity), nullable=False)
    message     = Column(String,              nullable=False)

    # --- Optional FK links (SET NULL if parent is deleted) ---
    creator_id  = Column(
        String,
        ForeignKey("creators.id",  ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    campaign_id = Column(
        String,
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # --- Timestamp ---
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- Relationships ---
    creator     = relationship("Creator",  back_populates="alerts")
    campaign    = relationship("Campaign", back_populates="alerts")