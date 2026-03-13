# ============================================================
# HardScope — Makefile
# Run all targets from the repo root.
# All backend targets cd into backend/ first — never rely on
# CWD for module resolution or SQLite path.
# ============================================================

.PHONY: install dev seed reseed lint

# --- Setup ---

install:
	pip install -r backend/requirements.txt

# --- Development server ---
# Hot reload enabled. API available at http://localhost:8000
# Docs at http://localhost:8000/docs

dev:
	cd backend && uvicorn main:app --reload --port 8000

# --- Database seeding ---
# seed   — load data into existing DB (no-op if tables already exist)
# reseed — wipe DB and reload from scratch (CI-safe, no confirmation prompt)

seed:
	cd backend && python seed.py

reseed:
	cd backend && python seed.py --wipe --yes

# --- Linting (optional — requires: pip install ruff) ---

lint:
	cd backend && ruff check .