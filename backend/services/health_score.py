import logging

from models import Campaign, Creator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base weights — must sum to 1.0
# Any metric that is None for a creator has its weight redistributed
# proportionally across whichever metrics ARE present (including roi).
# ---------------------------------------------------------------------------

BASE_WEIGHTS: dict[str, float] = {
    "engagement":   0.35,
    "reach":        0.25,
    "consistency":  0.20,
    "roi":          0.20,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _min_max_normalize(values: list[float | None]) -> list[float | None]:
    """Min-max scale a list to [0.0, 1.0], preserving None positions.

    Edge cases:
    - All None      → all None (no data to normalize)
    - All identical → all 1.0 (every creator equally ranked on this metric)
    - Normal range  → standard (v - min) / (max - min)
    """
    non_null = [v for v in values if v is not None]
    if not non_null:
        return [None] * len(values)

    lo, hi = min(non_null), max(non_null)
    if lo == hi:
        # Uniform metric — all creators equally ranked, assign full score
        return [1.0 if v is not None else None for v in values]

    return [
        (v - lo) / (hi - lo) if v is not None else None
        for v in values
    ]


def _redistribute_weights(
    metric_scores: dict[str, float | None],
) -> float | None:
    """Compute a weighted score with proportional weight redistribution.

    Any metric whose value is None is dropped and its weight is redistributed
    proportionally across the remaining present metrics. This applies uniformly
    to all four metrics (engagement, reach, consistency, roi) — there is no
    special-casing for missing ROI vs missing raw metrics.

    Returns None if no metrics are present (all None).

    Example:
        If reach=None, its 0.25 weight is split across engagement (0.35),
        consistency (0.20), roi (0.20) in proportion → new weights sum to 1.0.
    """
    present = {k: v for k, v in metric_scores.items() if v is not None}
    if not present:
        return None

    total_weight = sum(BASE_WEIGHTS[k] for k in present)
    score = sum(
        v * (BASE_WEIGHTS[k] / total_weight)
        for k, v in present.items()
    )
    return score


def _avg_campaign_roi(
    campaigns: list[Campaign],
    creator_id: str,
) -> float | None:
    """Return the mean ROI across all campaigns linked to creator_id.
    Returns None if the creator has no linked campaigns or all ROI values
    are None — callers treat None as a missing metric, not a zero."""
    linked = [
        c.roi for c in campaigns
        if c.creator_id == creator_id and c.roi is not None
    ]
    if not linked:
        return None
    return sum(linked) / len(linked)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_health_scores(
    creators:  list[Creator],
    campaigns: list[Campaign],
) -> list[Creator]:
    """Compute and set health_score (0–100) on each Creator in place.

    Scoring formula (before weight redistribution):
        health_score = (engagement * 0.35 + reach * 0.25
                        + consistency * 0.20 + roi * 0.20) * 100

    Missing metrics (None) have their weight redistributed proportionally
    across whichever metrics ARE present — no metric is defaulted to 0.
    If ALL metrics are None for a creator, health_score is set to None.

    ⚠️  NORMALIZATION CONSTRAINT:
    This function MUST receive the full creator pool on every call.
    Min-max normalization is computed globally — passing a subset produces
    scores that are incomparable to existing scores in the DB.
    If new creators are added later, re-run this function over all creators.

    ⚠️  PERSISTENCE:
    Creators are mutated in place but may be detached from the DB session.
    The caller (data_ingestion.py) must re-attach and commit:
        for creator in creators:
            db.add(creator)
        db.commit()

    Args:
        creators:  Full list of Creator ORM objects (id must be populated).
        campaigns: Full list of Campaign ORM objects (used for avg ROI lookup).

    Returns:
        The same creator list with health_score set on each object.
    """
    if not creators:
        logger.warning("compute_health_scores called with empty creator list")
        return creators

    # --- Step 1: extract raw metric vectors (one value per creator, in order) ---
    raw_engagement  = [c.engagement_rate  for c in creators]
    raw_reach       = [c.avg_views        for c in creators]
    raw_consistency = [c.posts_per_week   for c in creators]
    raw_roi         = [_avg_campaign_roi(campaigns, c.id) for c in creators]

    # --- Step 2: normalize each vector globally ---
    norm_engagement  = _min_max_normalize(raw_engagement)
    norm_reach       = _min_max_normalize(raw_reach)
    norm_consistency = _min_max_normalize(raw_consistency)
    norm_roi         = _min_max_normalize(raw_roi)

    logger.info(
        "Scoring %d creators — engagement non-null: %d, reach: %d, "
        "consistency: %d, roi: %d",
        len(creators),
        sum(1 for v in raw_engagement  if v is not None),
        sum(1 for v in raw_reach       if v is not None),
        sum(1 for v in raw_consistency if v is not None),
        sum(1 for v in raw_roi         if v is not None),
    )

    # --- Step 3: score each creator ---
    scored = 0
    nulled = 0

    for i, creator in enumerate(creators):
        metric_scores = {
            "engagement":  norm_engagement[i],
            "reach":       norm_reach[i],
            "consistency": norm_consistency[i],
            "roi":         norm_roi[i],
        }

        raw_score = _redistribute_weights(metric_scores)

        if raw_score is None:
            creator.health_score = None
            nulled += 1
        else:
            # Scale to 0–100 and clamp (floating point can nudge past bounds)
            creator.health_score = round(max(0.0, min(100.0, raw_score * 100)), 2)
            scored += 1

    logger.info(
        "Health score complete: %d scored, %d set to None (all metrics missing)",
        scored, nulled,
    )
    return creators