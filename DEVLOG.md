# SynthRare DEVLOG

## Session 1 — 2026-03-07

### Completed
- [PHASE-0] Created TODO.md with all phase tasks across phases 0-8
- [PHASE-0] Created docker-compose.yml (postgres, redis, backend, worker, frontend)
- [PHASE-0] Created .env.example with all documented env vars
- [PHASE-0] Created backend Dockerfile (Python 3.11-slim)
- [PHASE-0] Created backend app/main.py with FastAPI app and /health endpoint
- [PHASE-0] Created backend app/config.py (pydantic-settings)
- [PHASE-0] Created backend app/database.py (SQLAlchemy + session factory)
- [PHASE-0] Created backend requirements.txt
- [PHASE-0] Created backend alembic.ini + alembic/env.py scaffold
- [PHASE-0] Created backend tests/conftest.py + tests/test_health.py
- [PHASE-0] Created frontend Next.js 14 scaffold (package.json, tsconfig, layout, page)
- [PHASE-0] Created frontend Dockerfile
- [PHASE-0] Created infrastructure/scripts/health_check.sh
- [PHASE-0] Created infrastructure/scripts/deploy.sh
- [PHASE-0] Created infrastructure/digitalocean/app_spec.yaml
- [PHASE-0] Created infrastructure/digitalocean/gpu_droplet_setup.sh
- [PHASE-0] Created infrastructure/digitalocean/spaces_setup.sh
- [PHASE-1] Created User SQLAlchemy model (app/models/user.py) with UserRole enum
- [PHASE-1] Created Alembic migration 0001_create_users_table.py
- [PHASE-1] Created JWT auth service (app/services/auth.py) — bcrypt + python-jose
- [PHASE-1] Created auth router (app/routers/auth.py) — register, login, refresh
- [PHASE-1] Created auth schemas (app/schemas/auth.py)
- [PHASE-1] Created app/dependencies.py — get_current_user, require_admin
- [PHASE-1] Created tests/test_auth.py — 10 tests, all passing
- [PHASE-2] Created Domain + Dataset SQLAlchemy models with DatasetStatus enum
- [PHASE-2] Created Alembic migrations 0002_create_catalog_tables.py
- [PHASE-2] Created catalog router (GET /catalog, GET /catalog/{id}, POST /catalog, POST /catalog/{id}/download)
- [PHASE-2] Created catalog schemas (DatasetCreate, DatasetResponse)
- [PHASE-2] Created storage service (app/services/storage.py) — DO Spaces + local fallback
- [PHASE-2] Created seed service (app/services/seed.py) — seeded 3 domains + 6 datasets
- [PHASE-2] Created tests/test_catalog.py — 12 tests, all passing
- [PHASE-3] Created Job SQLAlchemy model with JobStatus enum
- [PHASE-3] Created Alembic migration 0003_create_jobs_table.py
- [PHASE-3] Created jobs router (POST /jobs, GET /jobs, GET /jobs/{id})
- [PHASE-3] Created RQ generation worker (app/workers/generation_worker.py) — Finance/Aviation/Healthcare engines
- [PHASE-3] Created jobs schemas (JobCreate, JobResponse)
- [PHASE-3] Created tests/test_jobs.py — 13 tests, all passing
- [PHASE-4] Created ValidationReport SQLAlchemy model with ReportStatus enum
- [PHASE-4] Created Alembic migration 0004_create_validation_reports.py
- [PHASE-4] Created validation service (app/services/validation.py) — KS test, Pearson correlation, coverage score
- [PHASE-4] Created validation router (GET /jobs/{id}/report)
- [PHASE-4] Created validation schemas (ValidationReportResponse with column_scores)
- [PHASE-4] Created tests/test_validation.py — 16 tests, all passing
- [PHASE-5] Created ApiKey SQLAlchemy model with hash + prefix storage
- [PHASE-5] Created Alembic migration 0005_create_api_keys_table.py
- [PHASE-5] Created api_keys router (POST /api-keys, GET /api-keys, DELETE /api-keys/{id})
- [PHASE-5] Created /api/v1/generate and /api/v1/jobs/{id} endpoints with API key auth
- [PHASE-5] Added rate limiting (10 req/min generation, 60 req/min status) via slowapi
- [PHASE-5] Created api_keys schemas (ApiKeyCreate, ApiKeyResponse)
- [PHASE-5] Created tests/test_api_keys.py — 12 tests, all passing
- [PHASE-6] Created frontend pages: landing, auth (login/register), catalog, dashboard, request
- [PHASE-6] Created Next.js API routes bridging frontend → FastAPI backend
- [PHASE-6] Configured Tailwind CSS + layout with nav/footer
- [PHASE-7] Created infrastructure/digitalocean/app_spec.yaml — DO App Platform spec
- [PHASE-7] Created infrastructure/digitalocean/gpu_droplet_setup.sh — L40S GPU setup
- [PHASE-7] Created infrastructure/digitalocean/spaces_setup.sh — Spaces bucket creation
- [PHASE-7] Created infrastructure/scripts/deploy.sh — one-command deploy via doctl
- [PHASE-7] Created docs/DEPLOYMENT.md — full deployment guide (Spaces → App Platform → GPU training)
- [PHASE-7] Created docs/API.md — complete API reference (all endpoints, schemas, errors)

### Blockers
- None

### DO Spend
- $0.00 (running total: $0.00 / $200)

---

## Session 2 — 2026-03-08

### Completed
- [PHASE-8] Created infrastructure/scripts/smoke_test.sh — full e2e smoke test script
  - Covers: health → register → login → refresh → catalog → job submit → poll → validation report → API key lifecycle → auth enforcement
  - Parameterised: `bash smoke_test.sh [BASE_URL]` (default: localhost:8000)
  - Color-coded PASS/FAIL output with final summary
- [PHASE-8] Confirmed all 62 pytest tests pass (`python -m pytest tests/ -q`)
- [PHASE-8] Fixed docker-compose.yml: backend now runs `alembic upgrade head` before uvicorn
- [PHASE-8] Created .env for local dev (gitignored, copied from .env.example with dev defaults)

### Outstanding (manual actions required)
- [PHASE-8] Production URL live on DO App Platform — requires `bash infrastructure/scripts/deploy.sh`
- [PHASE-8] Confirm DO spend under $100 — check billing in DO dashboard after deploy

### Notes
- All automated Phase 8 items are complete
- docker-compose up should now work out of the box with the .env file in place and migrations running automatically
- Smoke test exits non-zero on any failure — suitable for CI integration

### DO Spend
- $0.00 (running total: $0.00 / $200)
