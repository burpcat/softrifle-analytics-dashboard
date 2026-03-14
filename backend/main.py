from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import create_tables
from routers import alerts, analytics, campaigns, creators, ask


# ---------------------------------------------------------------------------
# Lifespan — runs once on startup, once on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # models MUST be imported before create_tables() so SQLAlchemy's metadata
    # registry is populated. Belt-and-suspenders — same pattern as seed.py.
    import models  # noqa: F401

    create_tables()
    yield
    # Shutdown: SQLite handles connection cleanup automatically.
    # Add explicit teardown here if switching to Postgres + connection pooling.


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title       = "HardScope Analytics API",
    description = "Creator campaign analytics for HardScope's partnerships team.",
    version     = "0.1.0",
    lifespan    = lifespan,
)

# ---------------------------------------------------------------------------
# CORS
#
# allow_origins=["*"] is intentional for the 48hr open build.
# allow_credentials is explicitly False — browsers reject the combination of
# wildcard origin + credentials=True as a CORS spec violation. When auth is
# added, switch to:
#     allow_origins=["http://localhost:3000"]   (explicit origin)
#     allow_credentials=True
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = False,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(creators.router)
app.include_router(campaigns.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(ask.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    """Confirm the server is running. Used by load balancers and smoke tests."""
    return {"status": "ok"}