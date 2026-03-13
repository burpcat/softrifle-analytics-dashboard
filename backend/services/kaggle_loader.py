import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from models import Campaign

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = {
    "Campaign_ID", "Company", "Campaign_Type", "Target_Audience",
    "Duration", "Channel_Used", "Conversion_Rate", "Acquisition_Cost",
    "ROI", "Location", "Language", "Clicks", "Impressions",
    "Engagement_Score", "Customer_Segment", "Date",
}

NUMERIC_COLUMNS = [
    "Conversion_Rate", "Acquisition_Cost", "ROI",
    "Clicks", "Impressions", "Engagement_Score",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
#     """Strip whitespace from column names and title-case them to match
#     EXPECTED_COLUMNS exactly. Handles CSVs exported with leading/trailing
#     spaces or inconsistent casing."""
#     df.columns = [c.strip().title().replace(" ", "_") for c in df.columns]
#     # Title-case produces e.g. "Roi" — fix the known acronym cases
#     rename_map = {"Roi": "ROI", "Id": "ID"}
#     df.columns = [rename_map.get(c, c) for c in df.columns]
#     return df

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from column names. Minimal transformation to avoid
    mangling already-correct names."""
    df.columns = [c.strip() for c in df.columns]
    return df


def _validate_columns(df: pd.DataFrame) -> None:
    """Raise ValueError if any expected column is missing after normalization."""
    missing = EXPECTED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Kaggle CSV is missing expected columns: {sorted(missing)}"
        )


def _coerce_numerics(df: pd.DataFrame) -> pd.DataFrame:
    """Force all numeric columns to proper numeric dtype, coercing bad values
    (empty strings, 'N/A', etc.) to NaN. NaN is then converted to None in the
    row mapper — ensuring no NaN survives into the ORM layer."""
    df[NUMERIC_COLUMNS] = df[NUMERIC_COLUMNS].apply(
        pd.to_numeric, errors="coerce"
    )
    return df


def _parse_date(val: str) -> date | None:
    """Parse a date string to a Python date. Returns None on failure rather
    than aborting the whole load — date is nullable in the Campaign model."""
    if pd.isna(val) or not str(val).strip():
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    logger.warning("Could not parse date value: %r — setting to None", val)
    return None


def _safe_int(val) -> int | None:
    if pd.isna(val):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_str(val) -> str | None:
    if pd.isna(val) if not isinstance(val, str) else not val.strip():
        return None
    return str(val).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_campaigns(csv_path: str) -> list[Campaign]:
    """Load the Kaggle marketing CSV and return a list of unsaved Campaign ORM
    objects ready for bulk insertion.

    ⚠️  CONTRACT — detached objects:
    Returned Campaign instances are NOT attached to any SQLAlchemy session.
    The caller (data_ingestion.py) must call db.add_all() and db.commit()
    before accessing any relationship (e.g. campaign.creator) — doing so on
    a detached instance will raise DetachedInstanceError or silently return None.

    All creator_id fields are set to None. linker.py populates them after
    creators have been inserted.

    Args:
        csv_path: Path to the Kaggle campaigns CSV file.

    Returns:
        list[Campaign]: Detached ORM objects, one per valid CSV row.

    Raises:
        FileNotFoundError: If the CSV file does not exist at csv_path.
        ValueError: If any expected columns are missing from the CSV.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Kaggle CSV not found at: {path.resolve()}")

    logger.info("Loading Kaggle CSV from %s", path.resolve())

    df = pd.read_csv(path, dtype=str)  # read everything as str — we coerce below

    df = _normalize_columns(df)
    _validate_columns(df)
    df = _coerce_numerics(df)

    if df.empty:
        logger.warning("Kaggle CSV loaded but contains 0 rows — returning empty list")
        return []

    logger.info("CSV loaded: %d rows, %d columns", len(df), len(df.columns))

    campaigns: list[Campaign] = []
    skipped = 0

    for idx, row in df.iterrows():
        try:
            campaign = Campaign(
                campaign_id_orig  = _safe_str(row["Campaign_ID"]),
                creator_id        = None,  # populated later by linker.py
                company           = _safe_str(row["Company"]),
                campaign_type     = _safe_str(row["Campaign_Type"]),
                target_audience   = _safe_str(row["Target_Audience"]),
                duration          = _safe_str(row["Duration"]),
                channel_used      = _safe_str(row["Channel_Used"]),
                conversion_rate   = _safe_float(row["Conversion_Rate"]),
                acquisition_cost  = _safe_float(row["Acquisition_Cost"]),
                roi               = _safe_float(row["ROI"]),
                location          = _safe_str(row["Location"]),
                language          = _safe_str(row["Language"]),
                clicks            = _safe_int(row["Clicks"]),
                impressions       = _safe_int(row["Impressions"]),
                engagement_score  = _safe_int(row["Engagement_Score"]),
                customer_segment  = _safe_str(row["Customer_Segment"]),
                date              = _parse_date(row["Date"]),
            )
            campaigns.append(campaign)
        except Exception as exc:
            logger.warning("Skipping row %d due to unexpected error: %s", idx, exc)
            skipped += 1

    logger.info(
        "Campaign mapping complete: %d loaded, %d skipped",
        len(campaigns), skipped,
    )
    return campaigns