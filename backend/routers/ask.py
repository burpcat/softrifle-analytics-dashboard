import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from config import settings

router = APIRouter(prefix="/api", tags=["ask"])

# --- API key guard: checked once at module import, not per-request ---
_API_KEY_CONFIGURED = bool(settings.ANTHROPIC_API_KEY)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class AskResponse(BaseModel):
    answer: str
    model: str


# ---------------------------------------------------------------------------
# Prompt sanitisation
# ---------------------------------------------------------------------------

def safe_str(val) -> str:
    """Prevent curly-brace injection and coerce None to a display value."""
    if val is None:
        return "N/A"
    return str(val).replace("{", "(").replace("}", ")")


# ---------------------------------------------------------------------------
# Data snapshot
# ---------------------------------------------------------------------------

def _build_context_snapshot(db: Session) -> str:
    # 1. Overview counts
    overview = db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM creators)                                    AS total_creators,
            (SELECT COUNT(*) FROM campaigns)                                   AS total_campaigns,
            (SELECT COUNT(*) FROM campaigns WHERE type = 'Influencer')         AS influencer_campaigns
    """)).mappings().one()

    # 2. Top 10 creators by health score
    top_creators = db.execute(text("""
        SELECT
            c.name,
            c.category,
            c.health_score,
            c.followers,
            c.engagement_rate,
            ROUND(AVG(ca.roi), 2) AS avg_roi
        FROM creators c
        LEFT JOIN campaigns ca ON ca.creator_id = c.id
        GROUP BY c.id
        ORDER BY c.health_score DESC
        LIMIT 10
    """)).mappings().all()

    # 3. Avg ROI by campaign type
    roi_by_type = db.execute(text("""
        SELECT type, ROUND(AVG(roi), 2) AS avg_roi
        FROM campaigns
        GROUP BY type
        ORDER BY avg_roi DESC
    """)).mappings().all()

    # 4. Avg ROI by channel
    roi_by_channel = db.execute(text("""
        SELECT channel, ROUND(AVG(roi), 2) AS avg_roi
        FROM campaigns
        GROUP BY channel
        ORDER BY avg_roi DESC
    """)).mappings().all()

    # 5. Avg ROI by segment
    roi_by_segment = db.execute(text("""
        SELECT segment, ROUND(AVG(roi), 2) AS avg_roi
        FROM campaigns
        GROUP BY segment
        ORDER BY avg_roi DESC
    """)).mappings().all()

    # 6. Alert counts by severity
    alert_counts = db.execute(text("""
        SELECT severity, COUNT(*) AS count
        FROM alerts
        GROUP BY severity
        ORDER BY count DESC
    """)).mappings().all()

    # 7. Top 5 campaigns by ROI
    top_campaigns = db.execute(text("""
        SELECT company, type, channel, segment, ROUND(roi, 2) AS roi
        FROM campaigns
        ORDER BY roi DESC
        LIMIT 5
    """)).mappings().all()

    # 8. Bottom 5 campaigns by ROI
    bottom_campaigns = db.execute(text("""
        SELECT company, type, channel, segment, ROUND(roi, 2) AS roi
        FROM campaigns
        ORDER BY roi ASC
        LIMIT 5
    """)).mappings().all()

    # ---------------------------------------------------------------------------
    # Assemble prompt sections — safe_str() on every user-sourced field
    # ---------------------------------------------------------------------------

    overview_block = (
        f"Total creators: {overview['total_creators']}\n"
        f"Total campaigns: {overview['total_campaigns']}\n"
        f"Influencer campaigns: {overview['influencer_campaigns']}"
    )

    creators_lines = "\n".join(
        f"  {safe_str(r['name'])} | {safe_str(r['category'])} | "
        f"Health: {safe_str(r['health_score'])} | Followers: {safe_str(r['followers'])} | "
        f"Engagement: {safe_str(r['engagement_rate'])}% | Avg ROI: {safe_str(r['avg_roi'])}"
        for r in top_creators
    )

    type_lines    = "\n".join(f"  {safe_str(r['type'])}: {safe_str(r['avg_roi'])}" for r in roi_by_type)
    channel_lines = "\n".join(f"  {safe_str(r['channel'])}: {safe_str(r['avg_roi'])}" for r in roi_by_channel)
    segment_lines = "\n".join(f"  {safe_str(r['segment'])}: {safe_str(r['avg_roi'])}" for r in roi_by_segment)
    alert_lines   = "\n".join(f"  {safe_str(r['severity'])}: {r['count']}" for r in alert_counts)

    def campaign_line(r) -> str:
        return (
            f"  {safe_str(r['company'])} | {safe_str(r['type'])} | "
            f"{safe_str(r['channel'])} | {safe_str(r['segment'])} | ROI: {safe_str(r['roi'])}"
        )

    top_camp_lines    = "\n".join(campaign_line(r) for r in top_campaigns)
    bottom_camp_lines = "\n".join(campaign_line(r) for r in bottom_campaigns)

    return f"""=== OVERVIEW ===
{overview_block}

=== TOP CREATORS BY HEALTH SCORE ===
{creators_lines}

=== CAMPAIGN PERFORMANCE ===
Avg ROI by Type:
{type_lines}

Avg ROI by Channel:
{channel_lines}

Avg ROI by Segment:
{segment_lines}

=== ALERTS ===
{alert_lines}

=== BEST CAMPAIGNS (Top 5 by ROI) ===
{top_camp_lines}

=== WORST CAMPAIGNS (Bottom 5 by ROI) ===
{bottom_camp_lines}"""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest, db: Session = Depends(get_db)):
    # Guard: checked against module-level flag — no DB work wasted
    if not _API_KEY_CONFIGURED:
        raise HTTPException(
            status_code=503,
            detail="AI assistant not configured — ANTHROPIC_API_KEY not set",
        )

    context = _build_context_snapshot(db)

    system_prompt = f"""You are HardScope Analytics Assistant — an AI that helps brand partnerships teams \
understand creator and campaign performance data.

You have access to the following data snapshot from the HardScope platform:

{context}

Answer the user's question based on this data. Be concise, specific, and reference \
actual numbers. If the data doesn't contain enough information to answer, say so. \
Format responses with short paragraphs — no bullet point walls. If recommending \
creators, explain why based on their metrics."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": request.question}],
                },
            )
            resp.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="AI service timed out")
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=502, detail="AI service temporarily unavailable")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="AI service temporarily unavailable")

    data = resp.json()
    content = data.get("content", [])
    answer = next(
        (block["text"] for block in content if block.get("type") == "text"),
        "No response generated.",
    )
    model = data.get("model", "claude-haiku-4-5-20251001")

    return AskResponse(answer=answer, model=model)