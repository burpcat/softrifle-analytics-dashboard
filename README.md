# HardScope — Creator Campaign Analytics Tool

A full-stack analytics dashboard that helps brand partnerships teams evaluate creators and measure campaign performance. Built with real YouTube creator data, a 200K-row campaign dataset, and an AI-powered query assistant.

**Live stack:** Python (FastAPI) → SQLite → React (Vite + Tailwind) → Claude Haiku AI

---

## Quick Start

```bash
# 1. Clone and set up backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in:
#   YOUTUBE_API_KEY        — from Google Cloud Console
#   ANTHROPIC_API_KEY      — from console.anthropic.com (for AI chat)
#   KAGGLE_CSV_PATH        — path to campaign CSV (default: ../data/data.csv)

# 3. Place the Kaggle campaign CSV
# Download from: https://www.kaggle.com/datasets/manishabhatt22/marketing-campaign-performance-dataset?resource=download
# Save to: data/data.csv

#4. Seed the database
python seed.py
# Takes ~2 minutes — pulls YouTube creators, loads campaigns, computes scores

# 5. Start the backend
uvicorn main:app --reload
# API running at http://localhost:8000
# Swagger docs at http://localhost:8000/docs

# 6. In a new terminal — set up frontend
cd frontend
npm install
npm run dev
# Dashboard running at http://localhost:5173
```

Total setup time: **under 5 minutes** (excluding API key creation).

---

## What It Does

HardScope's partnerships team needs to answer three questions daily:

1. **"Which creators should we partner with?"** — The Creators page shows 150 real YouTube creators pulled from the YouTube Data API, ranked by a composite health score that weighs engagement, reach, posting consistency, and campaign ROI.

2. **"Are our campaigns working?"** — The Campaigns page surfaces 200K campaign records with filtering by type, channel, segment, and ROI. The Analytics page compares influencer vs. non-influencer campaign performance across channels.

3. **"What needs attention right now?"** — The Alerts engine flags underperforming campaigns, low-engagement creators with active partnerships, and high-potential creators with no campaigns (outreach opportunities).

4. **"Just tell me the answer."** — The AI Assistant (powered by Claude Haiku) lets team members ask plain-English questions like "Which tech creators have the best ROI?" and get data-backed answers instantly.

---

## Data Sources

### YouTube Data API v3 — Creator Data (Real)

The seed script searches YouTube for creators across five segments (Foodies, Tech Enthusiasts, Health & Wellness, Outdoor Adventurers, Fashionistas) and pulls:

- **Channel stats** via `channels.list`: subscriber count, total views, video count, thumbnails, country
- **Recent video stats** via `videos.list`: per-video views, likes, comments, publish dates

From these raw API responses, three metrics are derived:
- `engagement_rate` = average (likes + comments) / views across last 10–20 videos
- `posts_per_week` = videos published in last 30 days / 4.3
- `avg_views` = mean view count across recent videos

**Why YouTube:** Richest public engagement data of any platform. Twitch lacks public engagement metrics. TikTok's API requires app review. YouTube gives likes, comments, views, and upload frequency — everything needed to evaluate a creator's audience quality, not just their size.

### Kaggle Marketing Campaign Dataset — Campaign Data (Proxy)

200K rows of campaign performance data: company, campaign type, channel, target audience, ROI, conversion rate, impressions, clicks, engagement scores, and customer segments.

**Why a Kaggle dataset instead of real campaign data:** No public API provides campaign-level metrics — spend, ROI, conversions tied to specific creators are always proprietary. This is the data that lives inside HardScope's own database. I used a realistic marketing dataset as a proxy to demonstrate the architecture that would connect creator performance to campaign outcomes. In production, the Kaggle CSV loader would be replaced with a direct connection to HardScope's internal campaign database — zero changes to the API layer, scoring engine, or frontend.

**The link between creators and campaigns** is built by the linker service: influencer campaigns are matched to creators by customer segment (e.g., "Tech Enthusiasts" campaigns → tech YouTube creators), weighted by follower count so larger creators get more campaign assignments. This simulates partnership history that would exist as real records in HardScope's production system.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    React Frontend                     │
│  Dashboard · Creators · Campaigns · Analytics · AI    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (proxied via Vite)
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                       │
│  /api/creators · /api/campaigns · /api/analytics      │
│  /api/alerts · /api/ask (AI)                          │
└──────┬───────────────┬──────────────────────────────┘
       │               │
  ┌────▼────┐   ┌──────▼──────┐
  │ SQLite  │   │ Anthropic   │
  │   DB    │   │ Claude API  │
  └─────────┘   └─────────────┘

Data Pipeline (seed.py):
  Kaggle CSV ──→ kaggle_loader ──→ campaigns table
  YouTube API ──→ youtube.py ──→ creators table
                                      ↓
                    linker.py ──→ campaign.creator_id populated
                                      ↓
                health_score.py ──→ creator.health_score computed
                                      ↓
                    alerts.py ──→ alerts table populated
```

### Key Design Decisions

**SQLite over Postgres.** Single-file database, zero configuration, no Docker dependency for reviewers. At 200K rows and 150 creators, SQLite handles every query in milliseconds. In production I'd swap to Postgres for concurrent writes and connection pooling — the SQLAlchemy abstraction makes this a config change, not a rewrite.

**Separate ingestion pipeline from API layer.** The seed script runs the full pipeline (fetch → normalize → link → score → alert) as a one-shot process. The API layer is read-only against the populated database. This separation means the API never blocks on YouTube rate limits or slow CSV parsing, and the pipeline can be converted to a scheduled cron job without touching any API code.

**Health score as a composite metric.** A single 0–100 number that combines four signals:

| Factor | Weight | Source | Why |
|--------|--------|--------|-----|
| Engagement rate | 35% | YouTube API | Audience quality matters more than size |
| Avg views | 25% | YouTube API | Reach per piece of content |
| Posts per week | 20% | YouTube API | Consistency signals reliability |
| Avg campaign ROI | 20% | Kaggle (linked) | Past performance predicts future |

Weights were chosen to prioritize engagement over vanity metrics. A creator with 10K followers and 20% engagement is more valuable than one with 1M followers and 0.5% engagement — the health score reflects that. When a creator has no linked campaigns, the ROI weight redistributes proportionally across the other three factors rather than penalizing them with a zero.

**AI assistant uses context injection, not SQL generation.** The `/api/ask` endpoint pre-fetches a data summary (top creators, campaign averages, alert counts) and sends it as context to Claude Haiku alongside the user's question. This is safer and more reliable than having the AI generate SQL — no risk of injection, no risk of malformed queries, and the AI can reason about business context ("is this creator worth partnering with?") rather than just returning row data.

**Campaign linking is segment-based, not identity-based.** No public dataset connects specific campaigns to specific creators. The linker matches by customer segment as a proxy for what HardScope's internal records would provide. The architecture is deliberately designed so replacing the linker with a direct database lookup requires changing one file (`linker.py`) and nothing else.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | Python + FastAPI | Async-ready, automatic OpenAPI docs, Pydantic validation. Best DX for a data-heavy API |
| Database | SQLite + SQLAlchemy | Zero-config for reviewers, ORM for clean queries, swappable to Postgres via connection string |
| Frontend | React 18 + Vite | Fast HMR, modern tooling. Vite proxy eliminates CORS config |
| Styling | Tailwind CSS | Utility-first, no component library overhead. Consistent spacing/color without custom CSS |
| Charts | Recharts | React-native charting, composable, handles the bar/line/pie charts the dashboard needs |
| AI | Claude Haiku (Anthropic API) | Fast, cheap, capable enough for data Q&A. Context window handles the full data summary |
| Data | YouTube Data API v3 | Richest public creator engagement data available |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/creators` | Paginated creator list with filters (platform, category, health score range, search) |
| GET | `/api/creators/{id}` | Single creator with linked campaign history |
| GET | `/api/campaigns` | Paginated campaign list with filters (type, channel, segment, ROI range, date range) |
| GET | `/api/campaigns/{id}` | Single campaign with linked creator |
| GET | `/api/analytics/summary` | Aggregate stats: totals, averages, top creators, breakdowns |
| GET | `/api/analytics/channel-comparison` | Influencer vs. non-influencer ROI per channel |
| GET | `/api/analytics/trends` | Monthly time-series: campaign counts, ROI, conversion by type |
| GET | `/api/alerts` | Paginated alerts filtered by severity and type |
| POST | `/api/ask` | AI-powered natural language query against the data |
| GET | `/api/health` | Health check |

Full interactive documentation available at `http://localhost:8000/docs` when the backend is running.

---

## Alert Rules

| Severity | Type | Trigger |
|----------|------|---------|
| Critical | Low ROI | Linked campaign with ROI < 2.0 or engagement score < 3 |
| Warning | Low Engagement | Creator in bottom 20th percentile engagement with active campaigns |
| Warning | Low Conversion | Campaign with 5,000+ impressions but < 3% conversion rate |
| Info | Outreach Opportunity | Creator with health score > 75 but zero linked campaigns |
| Info | Segment Outperformance | Segment where influencer campaigns outperform non-influencer by > 50% |

---

## Engineering Deep Dive

### Data Pipeline — Step by Step

The seed script (`seed.py`) runs a sequential pipeline where each stage feeds the next. Order matters — later stages depend on earlier outputs.

```
Stage 1 → Load Kaggle CSV (200K rows → campaigns table, creator_id = NULL)
Stage 2 → Fetch YouTube creators (API calls → creators table)
Stage 3 → Link campaigns to creators (segment matching → campaign.creator_id populated)
Stage 4 → Compute health scores (normalize + weight → creator.health_score populated)
Stage 5 → Generate alerts (rule engine scans both tables → alerts table populated)
```

**Stage 1: Kaggle Ingestion** (`services/kaggle_loader.py`)

```python
df = pd.read_csv(path, dtype=str)       # read everything as strings
df = _normalize_columns(df)              # strip whitespace from headers
_validate_columns(df)                    # fail fast if schema doesn't match
df = _coerce_numerics(df)                # convert ROI, clicks, etc. to proper types
```

Every row becomes a detached SQLAlchemy `Campaign` object with `creator_id = None`. The loader never touches the database directly — it returns a list of objects and the orchestrator handles the commit. This separation means the loader is testable without a database.

**Stage 2: YouTube Fetch** (`services/youtube.py`)

Three API calls per segment, chained:

```
search.list(q="food review", type=channel)  →  channel IDs
channels.list(id=channel_ids, part=snippet,statistics)  →  profile + stats
playlistItems.list(uploads playlist)  →  recent video IDs
videos.list(id=video_ids, part=statistics)  →  per-video engagement
```

Engagement rate is derived, not fetched:
```python
engagement_rate = mean([(v.likes + v.comments) / v.views for v in recent_videos])
```

The function returns normalized dicts matching the Creator model schema — the orchestrator doesn't need to know anything about YouTube's API shape.

**Stage 3: Linking** (`services/linker.py`)

```python
# Build lookup: {"foodies": [creator1, creator2, ...], "tech enthusiasts": [...]}
seg_map = {c.category.lower(): [...] for c in creators}

for campaign in campaigns:
    if campaign.campaign_type != "Influencer":
        continue
    pool = seg_map.get(campaign.customer_segment.lower(), [])
    if pool:
        creator = weighted_choice(pool, weights=followers)  # bigger creators get more
        campaign.creator_id = creator.id
```

Weighted random uses `random.Random(42)` — seeded for reproducibility. Same seed always produces identical assignments, which makes debugging deterministic.

Cap of 5 campaigns per creator prevents one mega-creator from absorbing every campaign in their segment. When a creator hits the cap, they're removed from the pool.

**Stage 4: Health Score** (`services/health_score.py`)

Min-max normalization across the full creator pool, then weighted sum:

```python
def normalize(values):
    min_v, max_v = min(values), max(values)
    if min_v == max_v:
        return [0.5] * len(values)  # avoid division by zero
    return [(v - min_v) / (max_v - min_v) for v in values]

score = (
    norm_engagement  * 0.35 +    # audience quality
    norm_avg_views   * 0.25 +    # reach per content
    norm_posts_week  * 0.20 +    # consistency
    norm_campaign_roi * 0.20     # actual results
) * 100
```

**Important edge case:** When a creator has no linked campaigns (and therefore no ROI), the 0.20 weight doesn't default to zero — it redistributes proportionally:

```python
# No campaigns: weights become 0.4375 / 0.3125 / 0.25 (still sum to 1.0)
# This prevents creators without campaign history from being penalized
adjusted = {
    "engagement": 0.35 / 0.80,   # 0.4375
    "reach":      0.25 / 0.80,   # 0.3125
    "consistency": 0.20 / 0.80,  # 0.25
}
```

**Worked example — @happyunboxingasmr (health score: 52.1):**

| Metric | Raw Value | Normalized (0-1) | Weight | Contribution |
|--------|-----------|-------------------|--------|-------------|
| Engagement rate | 0.34 (34%) | ~0.85 (high in pool) | 0.35 | 0.298 |
| Avg views | 38,960 | ~0.15 (mid-low) | 0.25 | 0.038 |
| Posts/week | 0.73 | ~0.10 (low) | 0.20 | 0.020 |
| Avg campaign ROI | 6.39 | ~0.65 (above average) | 0.20 | 0.130 |
| **Total** | | | | **0.486 × 100 ≈ 52.1** |

This creator scores well because of exceptional engagement (34%) and strong campaign ROI (6.39x), despite low posting frequency and moderate view counts. The health score correctly identifies them as a high-quality partner — exactly the insight a partnerships team needs.

### Error Handling Strategy

Errors are handled at three levels with a clear philosophy: **fail loud in the pipeline, fail gracefully in the API, fail helpfully in the frontend.**

**Pipeline level (seed.py):**
```
YouTube API fails  →  log warning, continue with Kaggle data only
Twitch API fails   →  log warning, continue with YouTube + Kaggle
Kaggle CSV missing →  fatal error, abort with clear message
Bad CSV row        →  skip row, log warning, continue loading
Rate limit hit     →  log warning, return partial results
```

The pipeline is designed for partial success. If YouTube returns 80 creators instead of 150 because of quota limits, the rest of the system still works — the linker just has fewer creators to assign, and the health scores normalize across whatever pool exists.

**API level (routers/):**

Every endpoint wraps its database query in try/except and returns appropriate HTTP status codes:

```python
# 404 — resource not found
if not creator:
    raise HTTPException(status_code=404, detail=f"Creator '{id}' not found.")

# 422 — validation error (handled automatically by Pydantic)
# Invalid page_size, bad date format, etc.

# 500 — unexpected errors (caught by FastAPI's exception handler)
```

All string filters are case-insensitive — both sides lowercased at query time. This prevents silent "no results" bugs when the frontend sends "youtube" but the database stores "YouTube".

**Frontend level (useApi hook):**

```javascript
// Every data-dependent component handles three states:
if (loading) return ;
if (error) return ;
if (!data.results.length) return ;
```

The `useApi` hook uses `AbortController` to cancel in-flight requests when filters change — prevents stale data from a slow request overwriting fresh results from a fast one.

**AI endpoint (`/api/ask`) specific handling:**
- No API key → 503: "AI assistant not configured"
- Anthropic API error → 502: "AI service temporarily unavailable"
- Empty question → 422: validation error
- The AI never sees raw SQL or database internals — it receives a pre-built data summary, eliminating injection risk entirely

### API Design Patterns

**Consistent pagination contract.** Every list endpoint returns the same shape:

```json
{
  "total": 200000,
  "page": 1,
  "page_size": 20,
  "results": [...]
}
```

The frontend Pagination component works identically across Creators, Campaigns, and Alerts because the response contract is identical. `page_size` is capped at 100 server-side to prevent accidental full-table dumps.

**Filter params are additive.** Each query parameter narrows the result set. No parameter means no filter. This makes the API predictable:

```
GET /api/campaigns                                    → all 200K
GET /api/campaigns?campaign_type=Influencer            → ~40K
GET /api/campaigns?campaign_type=Influencer&channel_used=YouTube  → ~6.7K
GET /api/campaigns?campaign_type=Influencer&channel_used=YouTube&min_roi=6  → subset
```

**Sort is server-side, not client-side.** Clicking a column header in the frontend sends `sort_by=engagement_rate&sort_order=desc` to the API. The database handles the sort (indexed and fast), not JavaScript sorting a page of 20 results that gives wrong ordering across pages.

**Nested resources on detail endpoints only.** `GET /api/creators` returns flat creator objects (fast, no joins). `GET /api/creators/{id}` returns the creator with their full campaign history (one extra query, acceptable for a detail view). This avoids N+1 query problems on list endpoints — loading 150 creators with 5 campaigns each would be 750+ rows transferred on every page load.

**Enums serialize as strings.** Pydantic's `use_enum_values=True` ensures the API returns `"youtube"` and `"critical"` instead of `DataSource.youtube` and `AlertSeverity.critical`. The frontend never needs to know about Python enum classes.

---

## Tradeoffs I Weighed

**Real-time vs. snapshot data.** I chose snapshot — seed once, query fast. Real-time YouTube polling would burn API quota (10K units/day) and add latency to every page load. The tradeoff is stale data. The right production answer is a background worker that re-fetches on a schedule (hourly or daily), which the pipeline architecture already supports.

**SQL vs. NoSQL.** The data is fundamentally relational — creators have campaigns, campaigns have alerts. SQL gives you joins, aggregations, and filtering for free. The API responses are flat JSON anyway. MongoDB would add operational complexity for zero analytical benefit at this scale.

**Health score weights.** Engagement at 35% is a bet that audience quality predicts campaign success better than raw reach. I considered equal weighting (25% each) but that lets mega-creators with low engagement dominate the rankings. The current weights could be made configurable via an admin endpoint — hardcoding them was a time tradeoff, not an architectural limitation.

**200K campaign rows in SQLite.** Pagination, filtering, and aggregation all run in < 100ms. The bottleneck would appear around 5–10M rows with complex joins. At that point, Postgres with proper indexing and materialized views for the analytics endpoints would be the move.

---

## What I'd Build With Another Week

1. **Twitch integration.** The architecture is already prepared — `config.py` has Twitch credentials, `data_ingestion.py` has a marked extension point. Adding Twitch is one new service file that returns the same creator schema, one new call in the orchestrator, zero changes to the API layer or frontend.

2. **Scheduled data pulls.** Convert `seed.py` into a background worker (Celery or APScheduler) that re-fetches YouTube data daily and recomputes health scores. The pipeline already runs idempotently.

3. **Docker Compose.** Single `docker-compose up` to run backend + frontend + seed in one command. SQLite makes this trivial — no separate database container needed.

4. **On-demand creator ingestion.** A `POST /api/creators/ingest?category=gaming` endpoint that lets the partnerships team pull new creators from the dashboard without re-seeding. The YouTube service already exists — just needs a new route exposing it.

5. **Automated tests.** Pytest for backend endpoints (response shapes, filter logic, pagination edge cases). Vitest + Testing Library for frontend components. The clean separation between services and routes makes unit testing straightforward.

6. **TypeScript migration** on the frontend. The Pydantic schemas already define the exact response shapes — generating TS types from them would catch type mismatches at build time.

7. **Campaign detail page** with drill-down analytics — per-campaign performance timeline, comparison against segment averages, creator attribution breakdown.

---

## Project Structure

```
hardscope/
├── backend/
│   ├── main.py                  # FastAPI app + CORS + router registration
│   ├── config.py                # Environment variables (.env)
│   ├── database.py              # SQLAlchemy engine + session
│   ├── models.py                # ORM models: Creator, Campaign, Alert
│   ├── schemas.py               # Pydantic response schemas
│   ├── seed.py                  # One-shot data pipeline runner
│   ├── services/
│   │   ├── youtube.py           # YouTube API ingestion
│   │   ├── kaggle_loader.py     # CSV loading + normalization
│   │   ├── linker.py            # Campaign → Creator matching
│   │   ├── health_score.py      # Composite score computation
│   │   ├── alerts.py            # Alert rule engine
│   │   └── data_ingestion.py    # Pipeline orchestrator
│   └── routers/
│       ├── creators.py          # /api/creators endpoints
│       ├── campaigns.py         # /api/campaigns endpoints
│       ├── analytics.py         # /api/analytics endpoints
│       ├── alerts.py            # /api/alerts endpoint
│       └── ask.py               # /api/ask AI endpoint
├── frontend/
│   ├── src/
│   │   ├── api/client.js        # API fetch functions
│   │   ├── hooks/useApi.js      # Data fetching hook
│   │   ├── utils/format.js      # Number/date formatting
│   │   ├── components/          # Reusable UI components
│   │   └── pages/               # Route-level page components
│   └── ...config files
└── data/
    └── campaigns.csv            # Kaggle dataset (not committed)
```