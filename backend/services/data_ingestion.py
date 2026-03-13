import logging

from sqlalchemy.orm import Session

from config import get_settings
from models import Creator
from services.alerts import generate_alerts
from services.health_score import compute_health_scores
from services.kaggle_loader import load_campaigns
from services.linker import link_campaigns_to_creators
from services.youtube import DEFAULT_SEGMENTS, fetch_youtube_creators

logger = logging.getLogger(__name__)


def run_ingestion(db: Session) -> dict:
    """Orchestrate the full data pipeline and return a summary stats dict.

    Pipeline stages (in order):
      1.  Load campaigns from Kaggle CSV
      2.  Bulk insert campaigns (creator_id = None at this stage)
      3.  Fetch YouTube creators
          [TWITCH EXTENSION POINT — see comment below]
      4.  Bulk insert creators
      5.  Link campaigns to creators (mutates creator_id in place)
      6.  Commit updated campaigns
      7.  Compute health scores (mutates health_score in place)
      8.  Commit updated creators
      9.  Generate alerts
      10. Bulk insert alerts

    Partial failure strategy:
      - Kaggle load or insert fails  → raise (unrecoverable — CSV is load-bearing)
      - YouTube fetch or insert fails → log, set skipped_youtube=True, continue
      - Linker fails                  → log, continue (campaigns stay unlinked)
      - Health score fails            → log, continue (health_score stays None)
      - Alert generation fails        → log, continue (no alerts inserted)

    ⚠️  RE-INGESTION WARNING:
    Running this twice against the same DB will corrupt analytics — duplicate
    rows and conflicting creator_id assignments from weighted-random linking.
    Always wipe the DB before re-running:
        from database import Base, engine
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

    ⚠️  SESSION OWNERSHIP:
    This function receives the session but never closes it — the caller owns
    the session lifecycle and is responsible for closing it after this returns.

    Args:
        db: Active SQLAlchemy Session (must have expire_on_commit=False —
            set on SessionLocal in database.py).

    Returns:
        dict with keys:
            campaigns_loaded    (int)
            creators_loaded     (int)
            campaigns_linked    (int)
            alerts_generated    (int)
            skipped_youtube     (bool)
            errors              (list[str])
    """
    settings        = get_settings()
    summary: dict   = {
        "campaigns_loaded":  0,
        "creators_loaded":   0,
        "campaigns_linked":  0,
        "alerts_generated":  0,
        "skipped_youtube":   False,
        "errors":            [],
    }

    # -------------------------------------------------------------------------
    # Stage 1 — Load campaigns from Kaggle CSV
    # Raises on missing file, malformed CSV, or missing columns — unrecoverable.
    # -------------------------------------------------------------------------
    logger.info("Stage 1: loading Kaggle CSV from %s", settings.KAGGLE_CSV_PATH)
    campaigns = load_campaigns(settings.KAGGLE_CSV_PATH)

    if not campaigns:
        raise RuntimeError(
            f"Kaggle CSV at '{settings.KAGGLE_CSV_PATH}' produced 0 campaigns — "
            "check the file path and contents before proceeding."
        )

    # -------------------------------------------------------------------------
    # Stage 2 — Bulk insert campaigns (creator_id = None)
    # -------------------------------------------------------------------------
    logger.info("Stage 2: inserting %d campaigns", len(campaigns))
    db.add_all(campaigns)
    db.commit()
    summary["campaigns_loaded"] = len(campaigns)
    logger.info("Stage 2 complete — %d campaigns committed", len(campaigns))

    # -------------------------------------------------------------------------
    # Stage 3 — Fetch creators from external APIs
    #
    # TWITCH EXTENSION POINT:
    # To add Twitch creators, import and call the Twitch service here:
    #
    #   from services.twitch import fetch_twitch_creators
    #   twitch_creators = fetch_twitch_creators(
    #       settings.TWITCH_CLIENT_ID,
    #       settings.TWITCH_CLIENT_SECRET,
    #   )
    #   creator_dicts = youtube_creators + twitch_creators
    #
    # No other changes needed in this file.
    # -------------------------------------------------------------------------
    logger.info("Stage 3: fetching YouTube creators")
    youtube_creators: list[dict] = []
    try:
        youtube_creators = fetch_youtube_creators(
            api_key  = settings.YOUTUBE_API_KEY,
            segments = DEFAULT_SEGMENTS,
        )
        logger.info("Stage 3: %d YouTube creators fetched", len(youtube_creators))
    except Exception as exc:
        msg = f"YouTube fetch failed: {exc}"
        logger.error(msg)
        summary["skipped_youtube"] = True
        summary["errors"].append(msg)

    # Merge platform lists — extend here when Twitch is added
    creator_dicts = youtube_creators

    # -------------------------------------------------------------------------
    # Stage 4 — Bulk insert creators
    # -------------------------------------------------------------------------
    creators: list[Creator] = []
    if creator_dicts:
        logger.info("Stage 4: inserting %d creators", len(creator_dicts))
        try:
            creators = [Creator(**d) for d in creator_dicts]
            db.add_all(creators)
            db.commit()
            summary["creators_loaded"] = len(creators)
            logger.info("Stage 4 complete — %d creators committed", len(creators))
        except Exception as exc:
            msg = f"Creator DB insert failed: {exc}"
            logger.error(msg)
            summary["skipped_youtube"] = True   # data fetched but lost
            summary["errors"].append(msg)
            db.rollback()
            creators = []   # pipeline continues with no creators
    else:
        logger.warning("Stage 4: no creators to insert — YouTube was skipped or returned empty")

    # -------------------------------------------------------------------------
    # Stage 5+6 — Link campaigns to creators, then commit
    # -------------------------------------------------------------------------
    if creators:
        logger.info("Stage 5: linking campaigns to creators")
        try:
            campaigns = link_campaigns_to_creators(creators, campaigns)
            linked = sum(1 for c in campaigns if c.creator_id is not None)
            summary["campaigns_linked"] = linked

            # Re-attach mutated campaigns and commit creator_id changes
            for campaign in campaigns:
                db.add(campaign)
            db.commit()
            logger.info("Stage 6 complete — %d campaigns linked and committed", linked)
        except Exception as exc:
            msg = f"Linker failed: {exc}"
            logger.error(msg)
            summary["errors"].append(msg)
            db.rollback()
            # After rollback, any campaign objects added to the session are
            # expired. Stages 7+9 will reload attributes from DB where
            # creator_id = NULL (the linker mutation was never committed).
            # This is correct — do not attempt to cache in-memory mutations
            # after a failed commit.
    else:
        logger.warning("Stage 5: skipped — no creators available to link against")

    # -------------------------------------------------------------------------
    # Stage 7+8 — Compute health scores, then commit
    # -------------------------------------------------------------------------
    if creators:
        logger.info("Stage 7: computing health scores for %d creators", len(creators))
        try:
            creators = compute_health_scores(creators, campaigns)

            # Re-attach mutated creators and commit health_score changes
            for creator in creators:
                db.add(creator)
            db.commit()
            logger.info("Stage 8 complete — health scores committed")
        except Exception as exc:
            msg = f"Health score computation failed: {exc}"
            logger.error(msg)
            summary["errors"].append(msg)
            db.rollback()
            # creators stay with health_score = None
    else:
        logger.warning("Stage 7: skipped — no creators to score")

    # -------------------------------------------------------------------------
    # Stage 9+10 — Generate and insert alerts
    # -------------------------------------------------------------------------
    logger.info("Stage 9: generating alerts")
    try:
        alert_objs = generate_alerts(creators, campaigns)
        if alert_objs:
            db.add_all(alert_objs)
            db.commit()
        summary["alerts_generated"] = len(alert_objs)
        logger.info("Stage 10 complete — %d alerts committed", len(alert_objs))
    except Exception as exc:
        msg = f"Alert generation failed: {exc}"
        logger.error(msg)
        summary["errors"].append(msg)
        db.rollback()

    # -------------------------------------------------------------------------
    # Done
    # -------------------------------------------------------------------------
    logger.info(
        "Ingestion complete — campaigns: %d, creators: %d, linked: %d, alerts: %d, errors: %d",
        summary["campaigns_loaded"],
        summary["creators_loaded"],
        summary["campaigns_linked"],
        summary["alerts_generated"],
        len(summary["errors"]),
    )
    return summary