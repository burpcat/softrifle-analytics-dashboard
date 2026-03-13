import logging
import random

from models import Campaign, Creator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RNG — seeded for reproducible dev/test runs.
# To get non-deterministic production behaviour, change seed to None:
#   RNG = random.Random(None)
# Re-running ingestion with the same seed produces identical creator_id
# assignments — different seeds will re-assign and overwrite existing links.
# ---------------------------------------------------------------------------

RNG = random.Random(42)

# Campaigns are only linked to creators when channel_used is one of these.
# Instagram and Facebook are included in the filter spec but have no creator
# data yet — they will always fall through to "no pool" and stay unlinked
# until their respective creator services are added. See Flag 5 note below.
LINKABLE_CHANNELS = {"YouTube", "Instagram", "Facebook"}

# Platforms with no creator data yet — logged at DEBUG to avoid drowning
# out real warnings. Promote to WARNING once a creator service is added.
KNOWN_MISSING_PLATFORMS = {"Instagram", "Facebook"}

MAX_CAMPAIGNS_PER_CREATOR = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_segment_map(
    creators: list[Creator],
) -> dict[str, list[Creator]]:
    """Group creators by normalised category key.

    Normalisation (.strip().lower()) is applied at comparison time only —
    the original Creator.category value in the DB is not mutated. This
    guards against casing/whitespace drift between CSV customer_segment
    values and the category strings set by youtube.py.
    """
    seg_map: dict[str, list[Creator]] = {}
    for c in creators:
        key = (c.category or "").strip().lower()
        if key:
            seg_map.setdefault(key, []).append(c)
    return seg_map


def _weighted_choice(
    creators: list[Creator],
) -> Creator:
    """Pick one creator using followers as a probability weight.

    Fallback to uniform random when all weights are None or zero —
    ensures creators with hidden/zero follower counts are still reachable.
    """
    weights = [c.followers for c in creators]

    if all(w is None or w == 0 for w in weights):
        return RNG.choice(creators)

    safe_weights = [w or 0 for w in weights]
    return RNG.choices(creators, weights=safe_weights, k=1)[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def link_campaigns_to_creators(
    creators:  list[Creator],
    campaigns: list[Campaign],
) -> list[Campaign]:
    """Assign creator_id to eligible influencer campaigns in place.

    Eligibility criteria:
      - campaign_type == "Influencer"
      - channel_used in LINKABLE_CHANNELS

    Matching strategy:
      - campaign.customer_segment → creator.category (normalised comparison)
      - Weighted random selection by followers within matched segment pool
      - Each creator capped at MAX_CAMPAIGNS_PER_CREATOR (default 5)
      - Campaigns with no matching pool stay creator_id = None

    ⚠️  KNOWN BEHAVIOUR:
    Instagram and Facebook campaigns pass the channel filter but have no
    creator data — they will always remain unlinked until those services
    are added. These cases are logged at DEBUG, not WARNING.

    ⚠️  PERSISTENCE:
    Campaigns are mutated in place. Caller must re-attach and commit:
        for campaign in campaigns:
            db.add(campaign)
        db.commit()

    ⚠️  REPRODUCIBILITY:
    Assignment uses RNG (seeded at 42 by default). Re-running ingestion
    with the same seed produces identical assignments. Different seeds
    will re-assign and overwrite existing creator_id links.

    Args:
        creators:  Full Creator list — must have id populated (post-insert).
        campaigns: Full Campaign list — creator_id will be mutated in place.

    Returns:
        The same campaign list with creator_id set on eligible rows.
    """
    if not creators:
        logger.warning("link_campaigns_to_creators: no creators provided — all campaigns stay unlinked")
        return campaigns

    seg_map = _build_segment_map(creators)

    # Per-creator assignment counter — enforces the 5-campaign cap
    assignment_counts: dict[str, int] = {c.id: 0 for c in creators}

    # Mutable per-segment pools — creators are removed when they hit the cap
    # We take a shallow copy of each list so seg_map itself isn't mutated
    pools: dict[str, list[Creator]] = {k: list(v) for k, v in seg_map.items()}

    eligible   = 0
    linked     = 0
    unlinked   = 0

    for campaign in campaigns:
        # --- Filter: only influencer campaigns on linkable channels ---
        if campaign.campaign_type != "Influencer":
            continue
        if campaign.channel_used not in LINKABLE_CHANNELS:
            continue

        eligible += 1

        segment_key = (campaign.customer_segment or "").strip().lower()
        pool = pools.get(segment_key, [])

        if not pool:
            # Distinguish known-missing platforms from genuine gaps
            if campaign.channel_used in KNOWN_MISSING_PLATFORMS:
                logger.debug(
                    "No creators for channel '%s' (not yet ingested) — "
                    "campaign %s stays unlinked",
                    campaign.channel_used, campaign.id,
                )
            else:
                logger.warning(
                    "No creator pool for segment '%s' (channel: %s) — "
                    "campaign %s stays unlinked",
                    campaign.customer_segment, campaign.channel_used, campaign.id,
                )
            unlinked += 1
            continue

        creator = _weighted_choice(pool)
        campaign.creator_id = creator.id
        linked += 1

        # Update cap counter and evict creator if limit reached.
        # Uses ID-based filtering instead of pool.remove(creator) —
        # list.remove() relies on object identity (is), which breaks after
        # db.commit() refreshes ORM instances. Filtering by .id is safe
        # regardless of object reference state.
        assignment_counts[creator.id] += 1
        if assignment_counts[creator.id] >= MAX_CAMPAIGNS_PER_CREATOR:
            pools[segment_key] = [c for c in pools[segment_key] if c.id != creator.id]
            logger.debug(
                "Creator %s (%s) hit cap of %d — removed from segment pool '%s'",
                creator.id, creator.username, MAX_CAMPAIGNS_PER_CREATOR, segment_key,
            )
            # Pool may now be empty — next iteration's `if not pool` guard handles it

    logger.info(
        "Linking complete — eligible: %d, linked: %d, unlinked: %d",
        eligible, linked, unlinked,
    )
    return campaigns