import logging
import time
from datetime import datetime, timezone

import requests

from models import DataSource

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Default segment → keyword mapping. Passed into fetch_youtube_creators()
# by data_ingestion.py — defined here as a convenience constant so callers
# don't have to redeclare it.
DEFAULT_SEGMENTS: dict[str, list[str]] = {
    "Foodies":             ["food review", "cooking", "recipe"],
    "Tech Enthusiasts":    ["tech review", "gadgets", "unboxing"],
    "Health & Wellness":   ["fitness", "workout", "wellness"],
    "Outdoor Adventurers": ["hiking", "outdoor adventure", "camping"],
    "Fashionistas":        ["fashion haul", "style", "outfit"],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get(url: str, params: dict) -> dict:
    """Thin wrapper around requests.get with consistent error handling.
    Raises ValueError on 401/403 (unrecoverable — bad API key).
    Returns {} on all other HTTP errors so callers can treat as empty."""
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code in (401, 403):
        raise ValueError(
            f"YouTube API auth error {resp.status_code} — check YOUTUBE_API_KEY"
        )
    if not resp.ok:
        logger.warning("YouTube API error %d for %s", resp.status_code, url)
        return {}
    return resp.json()


def _search_channel_ids(
    api_key: str,
    keyword: str,
    max_results: int = 10,
) -> list[str]:
    """Call search.list to discover channel IDs matching a keyword.
    Costs 100 quota units per call — keep max_results ≤ 10 to cap spend."""
    data = _get(
        f"{YOUTUBE_API_BASE}/search",
        params={
            "key":        api_key,
            "part":       "id",
            "type":       "channel",
            "q":          keyword,
            "maxResults": max_results,
        },
    )
    ids = [
        item["id"]["channelId"]
        for item in data.get("items", [])
        if item.get("id", {}).get("channelId")
    ]
    logger.debug("search '%s' → %d channel IDs", keyword, len(ids))
    return ids


def _fetch_channel_stats(
    api_key: str,
    channel_ids: list[str],
) -> dict[str, dict]:
    """Batch-fetch channel snippet + statistics + contentDetails.
    Processes in chunks of 50 (YouTube API limit).
    Returns dict[channel_id → raw channel data].

    contentDetails.relatedPlaylists.uploads gives the official uploads
    playlist ID — no UC→UU string hacking needed."""
    results: dict[str, dict] = {}

    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        data = _get(
            f"{YOUTUBE_API_BASE}/channels",
            params={
                "key":  api_key,
                "part": "snippet,statistics,contentDetails",
                "id":   ",".join(batch),
            },
        )
        for item in data.get("items", []):
            results[item["id"]] = item

    logger.debug("_fetch_channel_stats: %d/%d channels returned", len(results), len(channel_ids))
    return results


def _fetch_recent_video_metrics(
    api_key: str,
    uploads_playlist_id: str,
) -> dict:
    """Fetch the 20 most recent videos for a channel and derive:
      - engagement_rate: avg (likes + comments) / views across videos
      - avg_views: mean viewCount
      - posts_per_week: video count / elapsed weeks (oldest→newest publish date)

    Costs 2 quota units (1 playlistItems + 1 videos batch).
    Returns a dict with the three keys; any value may be None if data is
    unavailable (hidden stats, single-video window, etc.)."""

    # --- Step 1: get recent video IDs from uploads playlist ---
    pl_data = _get(
        f"{YOUTUBE_API_BASE}/playlistItems",
        params={
            "key":        api_key,
            "part":       "contentDetails,snippet",
            "playlistId": uploads_playlist_id,
            "maxResults": 20,
        },
    )
    items = pl_data.get("items", [])
    if not items:
        return {"engagement_rate": None, "avg_views": None, "posts_per_week": None}

    video_ids = [
        it["contentDetails"]["videoId"]
        for it in items
        if it.get("contentDetails", {}).get("videoId")
    ]
    if not video_ids:
        return {"engagement_rate": None, "avg_views": None, "posts_per_week": None}

    # Collect publish dates for posts_per_week window
    publish_dates: list[datetime] = []
    for it in items:
        raw = it.get("snippet", {}).get("publishedAt")
        if raw:
            try:
                publish_dates.append(
                    datetime.fromisoformat(raw.replace("Z", "+00:00"))
                )
            except ValueError:
                pass

    # --- Step 2: batch-fetch video statistics ---
    vid_data = _get(
        f"{YOUTUBE_API_BASE}/videos",
        params={
            "key":  api_key,
            "part": "statistics",
            "id":   ",".join(video_ids),
        },
    )
    video_items = vid_data.get("items", [])
    if not video_items:
        return {"engagement_rate": None, "avg_views": None, "posts_per_week": None}

    # --- Step 3: derive metrics ---
    engagement_rates: list[float] = []
    view_counts:      list[int]   = []

    for vid in video_items:
        stats = vid.get("statistics", {})
        views    = int(stats.get("viewCount",   0))
        likes    = int(stats.get("likeCount",   0))   # 0 when YouTube hides likes
        comments = int(stats.get("commentCount", 0))

        view_counts.append(views)
        if views > 0:
            engagement_rates.append((likes + comments) / views)
        # If views == 0, skip this video — including it would skew the average

    avg_views       = sum(view_counts) / len(view_counts) if view_counts else None
    engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else None

    # posts_per_week — requires at least 2 dated videos to define a window
    posts_per_week: float | None = None
    if len(publish_dates) >= 2:
        publish_dates.sort()
        window_days = (publish_dates[-1] - publish_dates[0]).days
        weeks = window_days / 7
        if weeks > 0:
            posts_per_week = len(video_ids) / weeks

    return {
        "engagement_rate": engagement_rate,
        "avg_views":       avg_views,
        "posts_per_week":  posts_per_week,
    }


# ---------------------------------------------------------------------------
# Per-segment fetcher
# ---------------------------------------------------------------------------

def _fetch_creators_for_segment(
    api_key:         str,
    segment:         str,
    keywords:        list[str],
    max_per_keyword: int = 10,
) -> list[dict]:
    """Discover and enrich YouTube creators for one Customer_Segment bucket.

    Flow:
      1. Search channel IDs for each keyword (100 units/call)
      2. Deduplicate channel IDs across keywords
      3. Batch-fetch channel stats + uploads playlist IDs
      4. Skip channels with hidden subscriber counts
      5. Fetch video metrics per channel (2 units each, 100ms between calls)
      6. Return normalized creator dicts

    Returns [] on total failure — caller logs and continues."""
    seen_ids:    set[str]   = set()
    channel_ids: list[str]  = []

    for keyword in keywords:
        try:
            ids = _search_channel_ids(api_key, keyword, max_per_keyword)
            for cid in ids:
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    channel_ids.append(cid)
        except Exception as exc:
            logger.warning("Search failed for keyword '%s': %s", keyword, exc)

    if not channel_ids:
        logger.warning("No channel IDs found for segment '%s'", segment)
        return []

    try:
        channels = _fetch_channel_stats(api_key, channel_ids)
    except ValueError:
        raise   # propagate auth errors — unrecoverable
    except Exception as exc:
        logger.error("channel stats fetch failed for segment '%s': %s", segment, exc)
        return []

    creators: list[dict] = []

    for ch_id, ch in channels.items():
        stats   = ch.get("statistics", {})
        snippet = ch.get("snippet",    {})

        # Skip channels with hidden subscriber counts — unusable for reach scoring
        if "subscriberCount" not in stats:
            logger.debug("Skipping %s — subscriberCount hidden", ch_id)
            continue

        uploads_playlist = (
            ch.get("contentDetails", {})
              .get("relatedPlaylists", {})
              .get("uploads")
        )

        # Derive video metrics — failures set metrics to None, don't skip creator
        metrics = {"engagement_rate": None, "avg_views": None, "posts_per_week": None}
        if uploads_playlist:
            try:
                metrics = _fetch_recent_video_metrics(api_key, uploads_playlist)
            except ValueError:
                raise   # auth error
            except Exception as exc:
                logger.warning("Video metrics failed for channel %s: %s", ch_id, exc)
        else:
            logger.warning("No uploads playlist for channel %s", ch_id)

        time.sleep(0.1)  # avoid burst throttling across rapid per-channel calls

        thumbnails = snippet.get("thumbnails", {})
        avatar_url = (
            thumbnails.get("high",    {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
        )

        creators.append({
            "platform":        DataSource.youtube,
            "platform_id":     ch_id,
            "username":        snippet.get("customUrl") or ch_id,
            "display_name":    snippet.get("title"),
            "avatar_url":      avatar_url,
            "followers":       int(stats["subscriberCount"]),
            "avg_views":       metrics["avg_views"],
            "engagement_rate": metrics["engagement_rate"],
            "posts_per_week":  metrics["posts_per_week"],
            "category":        segment,   # segment name → Creator.category
            "country":         snippet.get("country"),
            "health_score":    None,      # populated later by health_score.py
        })

    logger.info("Segment '%s': %d creators fetched", segment, len(creators))
    return creators


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_youtube_creators(
    api_key:  str,
    segments: dict[str, list[str]] = DEFAULT_SEGMENTS,
) -> list[dict]:
    """Fetch YouTube creators across all Customer_Segment buckets.

    Calls _fetch_creators_for_segment() for each segment, deduplicates
    globally by platform_id, and returns a flat list of creator dicts
    ready for Creator ORM construction in data_ingestion.py.

    Per-segment failures are logged and skipped — one bad segment will not
    abort the run.

    Args:
        api_key:  YouTube Data API v3 key.
        segments: Mapping of Customer_Segment → search keywords.
                  Defaults to DEFAULT_SEGMENTS.

    Returns:
        list[dict]: Normalized creator dicts. health_score is always None
                    here — health_score.py populates it after DB insert.

    Raises:
        ValueError: If the API key is invalid (401/403) — unrecoverable.
    """
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY is not set — cannot fetch creators")

    # Quota estimate: 100 units × (keywords per segment) × segments
    #   + ~2 units per discovered channel for stats + video metrics
    total_keywords = sum(len(kws) for kws in segments.values())
    logger.info(
        "Starting YouTube fetch — %d segments, %d total keywords. "
        "Estimated quota: ~%d search units + ~2 units per channel.",
        len(segments), total_keywords, total_keywords * 100,
    )

    all_creators:  list[dict] = []
    seen_platform_ids: set[str] = set()

    for segment, keywords in segments.items():
        try:
            batch = _fetch_creators_for_segment(api_key, segment, keywords)
        except ValueError:
            raise   # auth errors bubble up
        except Exception as exc:
            logger.error("Segment '%s' failed entirely: %s", segment, exc)
            continue

        for creator in batch:
            pid = creator["platform_id"]
            if pid not in seen_platform_ids:
                seen_platform_ids.add(pid)
                all_creators.append(creator)
            else:
                logger.debug("Dedup: skipping platform_id %s (already seen)", pid)

    logger.info(
        "YouTube fetch complete — %d unique creators across %d segments",
        len(all_creators), len(segments),
    )
    return all_creators