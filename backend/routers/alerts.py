import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from database import get_db
from models import Alert, AlertSeverity, AlertType
from schemas import AlertResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

# ---------------------------------------------------------------------------
# Severity sort order — critical first, info last.
# Compares against AlertSeverity enum members (not string literals) so
# SQLAlchemy translates correctly regardless of how the enum is stored.
# ---------------------------------------------------------------------------

SEVERITY_ORDER = case(
    (Alert.severity == AlertSeverity.critical, 0),
    (Alert.severity == AlertSeverity.warning,  1),
    (Alert.severity == AlertSeverity.info,     2),
    else_=3,
)


# ---------------------------------------------------------------------------
# GET /api/alerts
# ---------------------------------------------------------------------------

@router.get("", response_model=dict)
def get_alerts(
    severity:    Optional[AlertSeverity] = Query(default=None),
    type:        Optional[AlertType]     = Query(default=None, alias="type"),
    creator_id:  Optional[str]           = Query(default=None),
    campaign_id: Optional[str]           = Query(default=None),
    page:        int = Query(default=1, ge=1),
    page_size:   int = Query(default=20, ge=1, le=100),
    db:          Session = Depends(get_db),
) -> dict:
    """List alerts sorted by severity (critical → warning → info) then
    created_at descending within each tier.

    Sort order is fixed — alert priority is a product decision, not
    user-configurable. Exposing sort_by would allow info alerts to bury
    critical ones.

    Filters:
      severity    — FastAPI validates against AlertSeverity enum, returns 422
                    on invalid value (no manual validation needed)
      type        — FastAPI validates against AlertType enum, returns 422
                    on invalid value
      creator_id  — exact FK match, returns all alerts for a specific creator
      campaign_id — exact FK match, returns all alerts for a specific campaign
    """
    q = db.query(Alert)

    # --- Filters ---
    if severity is not None:
        q = q.filter(Alert.severity == severity)

    if type is not None:
        q = q.filter(Alert.type == type)

    if creator_id is not None:
        q = q.filter(Alert.creator_id == creator_id)

    if campaign_id is not None:
        q = q.filter(Alert.campaign_id == campaign_id)

    # --- Sort: severity tier first, then most recent within tier ---
    ordered = q.order_by(SEVERITY_ORDER, Alert.created_at.desc())

    # --- Pagination ---
    total   = q.count()
    offset  = (page - 1) * page_size
    results = ordered.offset(offset).limit(page_size).all()

    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "results":   [AlertResponse.model_validate(a) for a in results],
    }