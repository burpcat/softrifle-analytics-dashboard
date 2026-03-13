import logging
from collections import defaultdict

from models import Alert, AlertSeverity, AlertType, Campaign, Creator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alert rule thresholds — all magic numbers live here, nowhere else.
# ---------------------------------------------------------------------------

# Rule 1 — critical: bad campaign (OR condition — either alone is critical)
ROI_CRITICAL_THRESHOLD              = 2.0
ENGAGEMENT_SCORE_CRITICAL_THRESHOLD = 3

# Rule 2 — warning: low engagement creator
ENGAGEMENT_PERCENTILE_THRESHOLD     = 20.0   # bottom 20th percentile

# Rule 3 — warning: high impressions, low conversion
# conversion_rate is stored as a decimal (0.01–0.15 per dataset spec, where
# 0.03 = 3%). If the data source ever changes to percentage scale (3.0 = 3%),
# this threshold must be updated to 3.0.
CONVERSION_RATE_WARNING_THRESHOLD   = 0.03
IMPRESSION_WARNING_THRESHOLD        = 5000

# Rule 4 — info: outreach opportunity
# Tightened to zero linked campaigns — "we haven't used this creator yet"
# is a cleaner signal than "fewer than 2", which caught capped-out creators.
HEALTH_SCORE_OPPORTUNITY_THRESHOLD  = 75.0
OUTREACH_MAX_LINKED_CAMPAIGNS       = 0

# Rule 5 — info: segment outperformance
SEGMENT_OUTPERFORMANCE_LIFT         = 0.50   # influencer ROI > non-influencer by > 50%


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_bottom_percentile_threshold(
    values:     list[float | None],
    percentile: float = 20.0,
) -> float | None:
    """Return the value at the given percentile boundary of a distribution.

    Returns None if fewer than 2 non-null values exist — a single-point
    distribution has no meaningful percentile boundary.

    Index formula: idx = min(int(n * percentile / 100), n - 1)
    For percentile=20, n=10: idx=2 (3rd value) — the boundary below which
    the bottom 20% fall.
    """
    non_null = sorted(v for v in values if v is not None)
    if len(non_null) < 2:
        return None
    n   = len(non_null)
    idx = min(int(n * percentile / 100), n - 1)
    return non_null[idx]


def _make_alert(
    alert_type:  AlertType,
    severity:    AlertSeverity,
    message:     str,
    creator_id:  str | None = None,
    campaign_id: str | None = None,
) -> Alert:
    return Alert(
        type        = alert_type,
        severity    = severity,
        message     = message,
        creator_id  = creator_id,
        campaign_id = campaign_id,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_alerts(
    creators:  list[Creator],
    campaigns: list[Campaign],
) -> list[Alert]:
    """Apply all alert rules and return a deduplicated list of Alert objects.

    Rules applied (in order):
      1. critical  — low_roi:                roi < 2.0 OR engagement_score < 3
      2. warning   — low_engagement:         creator in bottom 20th percentile
                                             engagement AND ≥ 1 linked campaign
      3. warning   — low_conversion:         impressions > 5000 AND
                                             conversion_rate < 0.03
      4. info      — outreach_opportunity:   health_score > 75 AND
                                             zero linked campaigns
      5. info      — segment_outperformance: influencer avg ROI > non-influencer
                                             avg ROI by > 50% for a segment

    Dedup key: (alert_type, creator_id, campaign_id, segment_name)
    All four slots are always present — rules 1–4 use None for segment_name,
    Rule 5 uses None for creator_id and campaign_id. This prevents Rule 5
    from collapsing all segments onto the same key.

    ⚠️  Returns detached Alert ORM objects. Caller must insert and commit:
        db.add_all(alerts)
        db.commit()

    Args:
        creators:  Full Creator list (health_score must be populated).
        campaigns: Full Campaign list (creator_id must be populated by linker).

    Returns:
        list[Alert]: Deduplicated, unsaved Alert ORM objects.
    """
    alerts:    list[Alert]                      = []
    seen_keys: set[tuple]                       = set()

    def _add(alert: Alert, segment_name: str | None = None) -> None:
        """Dedup-check then append. Key is always a 4-tuple."""
        key = (alert.type, alert.creator_id, alert.campaign_id, segment_name)
        if key not in seen_keys:
            seen_keys.add(key)
            alerts.append(alert)

    # Pre-build lookup structures -----------------------------------------

    # creator_id → list of linked campaigns
    creator_campaigns: dict[str, list[Campaign]] = defaultdict(list)
    for c in campaigns:
        if c.creator_id:
            creator_campaigns[c.creator_id].append(c)

    creator_map: dict[str, Creator] = {c.id: c for c in creators}

    # -------------------------------------------------------------------------
    # Rule 1 — Critical: bad campaign
    # Fires if roi < threshold OR engagement_score < threshold (either alone
    # is critical — AND was too restrictive and missed genuinely bad campaigns)
    # -------------------------------------------------------------------------
    for campaign in campaigns:
        if campaign.creator_id is None:
            continue  # only flag linked influencer campaigns

        roi_bad  = campaign.roi            is not None and campaign.roi            < ROI_CRITICAL_THRESHOLD
        eng_bad  = campaign.engagement_score is not None and campaign.engagement_score < ENGAGEMENT_SCORE_CRITICAL_THRESHOLD

        if roi_bad or eng_bad:
            reasons = []
            if roi_bad: reasons.append(f"ROI {campaign.roi:.2f} < {ROI_CRITICAL_THRESHOLD}")
            if eng_bad: reasons.append(f"engagement score {campaign.engagement_score} < {ENGAGEMENT_SCORE_CRITICAL_THRESHOLD}")

            _add(_make_alert(
                alert_type  = AlertType.low_roi,
                severity    = AlertSeverity.critical,
                message     = f"Campaign {campaign.campaign_id_orig}: {' and '.join(reasons)}",
                creator_id  = campaign.creator_id,
                campaign_id = campaign.id,
            ))

    # -------------------------------------------------------------------------
    # Rule 2 — Warning: low engagement creator with active campaigns
    # -------------------------------------------------------------------------
    engagement_threshold = _get_bottom_percentile_threshold(
        [c.engagement_rate for c in creators],
        ENGAGEMENT_PERCENTILE_THRESHOLD,
    )

    if engagement_threshold is None:
        logger.warning("Rule 2: insufficient engagement_rate data — skipping low-engagement alerts")
    else:
        for creator in creators:
            if creator.engagement_rate is None:
                continue
            if creator.engagement_rate >= engagement_threshold:
                continue
            if not creator_campaigns.get(creator.id):
                continue  # no linked campaigns — not actionable

            _add(_make_alert(
                alert_type = AlertType.low_engagement,
                severity   = AlertSeverity.warning,
                message    = (
                    f"{creator.display_name or creator.username} has engagement rate "
                    f"{creator.engagement_rate:.4f} (bottom {ENGAGEMENT_PERCENTILE_THRESHOLD:.0f}th percentile) "
                    f"with {len(creator_campaigns[creator.id])} active campaign(s)"
                ),
                creator_id = creator.id,
            ))

    # -------------------------------------------------------------------------
    # Rule 3 — Warning: high impressions, low conversion
    # conversion_rate is decimal scale (0.01–0.15); threshold 0.03 = 3%
    # -------------------------------------------------------------------------
    for campaign in campaigns:
        if campaign.impressions is None or campaign.conversion_rate is None:
            continue
        if (
            campaign.impressions    >  IMPRESSION_WARNING_THRESHOLD
            and campaign.conversion_rate < CONVERSION_RATE_WARNING_THRESHOLD
        ):
            _add(_make_alert(
                alert_type  = AlertType.low_conversion,
                severity    = AlertSeverity.warning,
                message     = (
                    f"Campaign {campaign.campaign_id_orig}: "
                    f"{campaign.impressions:,} impressions but only "
                    f"{campaign.conversion_rate:.1%} conversion rate "
                    f"(threshold: {CONVERSION_RATE_WARNING_THRESHOLD:.0%})"
                ),
                creator_id  = campaign.creator_id,
                campaign_id = campaign.id,
            ))

    # -------------------------------------------------------------------------
    # Rule 4 — Info: outreach opportunity (high health, zero campaigns)
    # -------------------------------------------------------------------------
    for creator in creators:
        if creator.health_score is None:
            continue
        if creator.health_score <= HEALTH_SCORE_OPPORTUNITY_THRESHOLD:
            continue
        if creator_campaigns.get(creator.id):
            continue  # already has campaigns — not an outreach gap

        _add(_make_alert(
            alert_type = AlertType.outreach_opportunity,
            severity   = AlertSeverity.info,
            message    = (
                f"{creator.display_name or creator.username} has health score "
                f"{creator.health_score:.1f} but no linked campaigns — "
                f"strong outreach candidate"
            ),
            creator_id = creator.id,
        ))

    # -------------------------------------------------------------------------
    # Rule 5 — Info: segment outperformance
    # One alert per segment; creator_id and campaign_id are both None (intentional —
    # this is a segment-level signal, not tied to a specific creator or campaign).
    # Segment name used as 4th dedup key slot to prevent all segments collapsing
    # onto the same (segment_outperformance, None, None, None) key.
    # -------------------------------------------------------------------------

    # Build per-segment ROI buckets split by campaign type
    seg_influencer_roi:     dict[str, list[float]] = defaultdict(list)
    seg_non_influencer_roi: dict[str, list[float]] = defaultdict(list)

    for campaign in campaigns:
        if campaign.customer_segment is None or campaign.roi is None:
            continue
        seg = campaign.customer_segment
        if campaign.campaign_type == "Influencer":
            seg_influencer_roi[seg].append(campaign.roi)
        else:
            seg_non_influencer_roi[seg].append(campaign.roi)

    for segment, inf_rois in seg_influencer_roi.items():
        non_inf_rois = seg_non_influencer_roi.get(segment, [])
        if not inf_rois or not non_inf_rois:
            continue

        inf_avg     = sum(inf_rois)     / len(inf_rois)
        non_inf_avg = sum(non_inf_rois) / len(non_inf_rois)

        if non_inf_avg == 0:
            continue  # avoid division by zero; can't compute lift

        lift = (inf_avg - non_inf_avg) / non_inf_avg
        if lift > SEGMENT_OUTPERFORMANCE_LIFT:
            _add(
                _make_alert(
                    alert_type = AlertType.segment_outperformance,
                    severity   = AlertSeverity.info,
                    message    = (
                        f"Segment '{segment}': influencer avg ROI {inf_avg:.2f} "
                        f"vs non-influencer {non_inf_avg:.2f} "
                        f"(+{lift:.0%} lift — threshold: {SEGMENT_OUTPERFORMANCE_LIFT:.0%})"
                    ),
                ),
                segment_name=segment,
            )

    logger.info(
        "Alert generation complete — %d alerts: %d critical, %d warning, %d info",
        len(alerts),
        sum(1 for a in alerts if a.severity == AlertSeverity.critical),
        sum(1 for a in alerts if a.severity == AlertSeverity.warning),
        sum(1 for a in alerts if a.severity == AlertSeverity.info),
    )
    return alerts