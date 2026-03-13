import argparse
import json
import logging
import sys

# --- models MUST be imported before create_tables() or wipe_db() so that
# SQLAlchemy's metadata registry is populated before create_all() runs.
# wipe_db() also imports models internally as a belt-and-suspenders guard.
import models  # noqa: F401

from database import Base, SessionLocal, create_tables, engine
from services.data_ingestion import run_ingestion

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wipe_db() -> None:
    """Drop and recreate all tables. Destroys all data — use with caution.

    Imports models internally to guarantee metadata is populated before
    create_all(), regardless of call-site import order.
    """
    import models  # noqa: F401 — populates Base.metadata before create_all

    logger.warning("Wiping database — all existing data will be permanently lost.")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    logger.info("Database wiped and recreated successfully.")


def _print_summary(summary: dict) -> None:
    """Print ingestion summary to stdout in a readable format."""
    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"  Campaigns loaded : {summary['campaigns_loaded']:,}")
    print(f"  Creators loaded  : {summary['creators_loaded']:,}")
    print(f"  Campaigns linked : {summary['campaigns_linked']:,}")
    print(f"  Alerts generated : {summary['alerts_generated']:,}")
    print(f"  YouTube skipped  : {summary['skipped_youtube']}")

    if summary["errors"]:
        print(f"\n  ⚠️  {len(summary['errors'])} error(s):")
        for err in summary["errors"]:
            print(f"    • {err}")
    else:
        print("\n  ✅ No errors.")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the HardScope database with Kaggle + YouTube data."
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        default=False,
        help="Drop and recreate all tables before seeding. Destroys all existing data.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Skip the --wipe confirmation prompt (for scripted/CI runs).",
    )
    args = parser.parse_args()

    # --- Handle --wipe ---
    if args.wipe:
        if not args.yes:
            try:
                confirm = input(
                    "\n⚠️  This will permanently destroy all data in the database.\n"
                    "Type 'yes' to continue, anything else to abort: "
                )
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                sys.exit(0)

            if confirm.strip().lower() != "yes":
                print("Aborted.")
                sys.exit(0)

        wipe_db()
    else:
        # No-op if tables already exist
        create_tables()

    # --- Run ingestion ---
    db = SessionLocal()
    try:
        logger.info("Starting ingestion run...")
        summary = run_ingestion(db)
        _print_summary(summary)

        if summary["errors"]:
            logger.warning(
                "Ingestion completed with %d error(s) — check summary above.",
                len(summary["errors"]),
            )
        else:
            logger.info("Ingestion completed successfully.")

    except Exception as exc:
        logger.error("Unrecoverable ingestion failure: %s", exc)
        sys.exit(1)   # SystemExit — finally block still fires, session closes cleanly

    finally:
        db.close()


if __name__ == "__main__":
    main()