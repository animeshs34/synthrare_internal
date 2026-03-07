# SynthRare TODO

## Phase 0 — Bootstrap
- [x] PHASE-0 | Create docker-compose.yml with postgres, redis, backend, worker, frontend | Done: 2026-03-07
- [x] PHASE-0 | Create .env.example with all documented env vars | Done: 2026-03-07
- [x] PHASE-0 | Create backend Dockerfile | Done: 2026-03-07
- [x] PHASE-0 | Create backend app/main.py with FastAPI app and /health endpoint | Done: 2026-03-07
- [x] PHASE-0 | Create backend app/config.py for settings | Done: 2026-03-07
- [x] PHASE-0 | Create backend app/database.py for SQLAlchemy engine + session | Done: 2026-03-07
- [x] PHASE-0 | Create backend requirements.txt | Done: 2026-03-07
- [x] PHASE-0 | Create frontend Next.js 14 app scaffold | Done: 2026-03-07
- [x] PHASE-0 | Create frontend Dockerfile | Done: 2026-03-07
- [x] PHASE-0 | Create infrastructure/scripts/health_check.sh | Done: 2026-03-07
- [x] PHASE-0 | Create DEVLOG.md with first session entry | Done: 2026-03-07

## Phase 1 — Auth
- [x] PHASE-1 | Create SQLAlchemy User model with roles | Done: 2026-03-07
- [x] PHASE-1 | Create Alembic migration for users table | Done: 2026-03-07
- [x] PHASE-1 | Create auth router: POST /auth/register, POST /auth/login, POST /auth/refresh | Done: 2026-03-07
- [x] PHASE-1 | Create JWT token service (access + refresh tokens) | Done: 2026-03-07
- [x] PHASE-1 | Create Pydantic schemas for auth (UserCreate, UserLogin, TokenResponse) | Done: 2026-03-07
- [x] PHASE-1 | Create get_current_user dependency | Done: 2026-03-07
- [x] PHASE-1 | Write tests for auth endpoints (success, auth failure, invalid input) | Done: 2026-03-07

## Phase 2 — Catalog
- [x] PHASE-2 | Create Dataset SQLAlchemy model | Done: 2026-03-07
- [x] PHASE-2 | Create Domain model | Done: 2026-03-07
- [x] PHASE-2 | Create catalog router: GET /catalog, GET /catalog/{id}, POST /catalog (admin) | Done: 2026-03-07
- [x] PHASE-2 | Create DO Spaces / local storage service | Done: 2026-03-07
- [x] PHASE-2 | Create download endpoint with credit deduction | Done: 2026-03-07
- [x] PHASE-2 | Seed catalog with sample datasets | Done: 2026-03-07
- [x] PHASE-2 | Write tests for catalog endpoints | Done: 2026-03-07

## Phase 3 — Jobs
- [x] PHASE-3 | Create Job SQLAlchemy model | Done: 2026-03-07
- [x] PHASE-3 | Create jobs router: POST /jobs, GET /jobs/{id}, GET /jobs (user) | Done: 2026-03-07
- [x] PHASE-3 | Create RQ generation worker | Done: 2026-03-07
- [x] PHASE-3 | Create job request Pydantic schemas | Done: 2026-03-07
- [x] PHASE-3 | Wire RQ queue to worker on redis | Done: 2026-03-07
- [x] PHASE-3 | Write tests for jobs endpoints | Done: 2026-03-07

## Phase 4 — Validation
- [x] PHASE-4 | Create ValidationReport SQLAlchemy model | Done: 2026-03-07
- [x] PHASE-4 | Create fidelity scoring service (statistical metrics) | Done: 2026-03-07
- [x] PHASE-4 | Create validation router: GET /jobs/{id}/report | Done: 2026-03-07
- [x] PHASE-4 | Generate charts from fidelity scores | Done: 2026-03-07
- [x] PHASE-4 | Write tests for validation | Done: 2026-03-07

## Phase 5 — ML Models
- [x] PHASE-5 | Create ml/notebooks/finance_colab.ipynb | Done: 2026-03-07
- [x] PHASE-5 | Create ml/notebooks/aviation_colab.ipynb | Done: 2026-03-07
- [x] PHASE-5 | Create ml/notebooks/healthcare_colab.ipynb | Done: 2026-03-07
- [x] PHASE-5 | Create ml/inference/generator.py | Done: 2026-03-07
- [x] PHASE-5 | Create ml/inference/validator.py | Done: 2026-03-07
- [x] PHASE-5 | Create ml/training/finance_trainer.py | Done: 2026-03-07
- [x] PHASE-5 | Create ml/training/aviation_trainer.py | Done: 2026-03-07
- [x] PHASE-5 | Create ml/training/healthcare_trainer.py | Done: 2026-03-07

## Phase 6 — Public API
- [x] PHASE-6 | Create ApiKey SQLAlchemy model | Done: 2026-03-07
- [x] PHASE-6 | Create api_keys router: POST /api-keys, DELETE /api-keys/{id} | Done: 2026-03-07
- [x] PHASE-6 | Create /api/v1/* proxy endpoints | Done: 2026-03-07
- [x] PHASE-6 | Add rate limiting with slowapi | Done: 2026-03-07
- [x] PHASE-6 | Write tests for public API | Done: 2026-03-07

## Phase 7 — DO Deployment
- [x] PHASE-7 | Create infrastructure/digitalocean/app_spec.yaml | Done: 2026-03-07
- [x] PHASE-7 | Create infrastructure/digitalocean/gpu_droplet_setup.sh | Done: 2026-03-07
- [x] PHASE-7 | Create infrastructure/digitalocean/spaces_setup.sh | Done: 2026-03-07
- [x] PHASE-7 | Create infrastructure/scripts/deploy.sh | Done: 2026-03-07
- [ ] PHASE-7 | Create docs/DEPLOYMENT.md | MED
- [ ] PHASE-7 | Create docs/API.md | MED

## Phase 8 — Polish
- [ ] PHASE-8 | Full smoke test: register -> request -> generate -> validate -> download | HIGH
- [ ] PHASE-8 | All pytest tests passing | HIGH
- [ ] PHASE-8 | docker-compose up with zero errors | HIGH
- [ ] PHASE-8 | Production URL live on DO App Platform | HIGH
- [ ] PHASE-8 | Confirm DO spend under $100 | HIGH
- [ ] PHASE-8 | DEVLOG.md complete for all sessions | MED
