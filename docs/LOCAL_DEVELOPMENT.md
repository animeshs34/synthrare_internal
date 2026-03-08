# Local Development Guide

## Stack overview

| Component | Tech | Local address |
|---|---|---|
| Backend API | FastAPI + uvicorn | `http://localhost:8000` |
| RQ Worker | Python (same image) | — |
| Frontend | Next.js dev server | `http://localhost:3000` |
| Database | PostgreSQL 15 | `localhost:5432` |
| Queue / Cache | Redis 7 | `localhost:6379` |
| File storage | Local filesystem | `./data/uploads/` |
| Synthetic data | Statistical fallback (no key needed) or DO Gradient | — |

---

## Option A — Docker Compose (recommended, fastest start)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 24+ (or Docker Engine + Compose plugin on Linux)
- Git

That's it. Python and Node are not required on your host.

### 1. Clone and copy env file

```bash
git clone https://github.com/your-org/synthrare.git
cd synthrare
cp .env.example .env
```

### 2. Set a real SECRET_KEY

```bash
# macOS / Linux
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Open `.env` and replace the `SECRET_KEY` placeholder with the output.

> All other defaults in `.env` work out of the box for Docker Compose.
> `USE_LOCAL_STORAGE=true` is already set so you don't need DO Spaces credentials.

### 3. Start all services

```bash
docker-compose up --build
```

First run takes 2–4 minutes (builds images, installs deps). Subsequent starts are instant.

What starts:

| Service | Container | Notes |
|---|---|---|
| `postgres` | postgres:15-alpine | Data persisted in `postgres_data` volume |
| `redis` | redis:7-alpine | In-memory, resets on restart |
| `backend` | python:3.11-slim | Runs `alembic upgrade head` then uvicorn --reload |
| `worker` | python:3.11-slim | RQ worker, hot-reloads via volume mount |
| `frontend` | node:20-alpine | Next.js dev server with hot-reload |

### 4. Seed the domain catalog

In a new terminal:

```bash
docker-compose exec backend python -c "
from app.database import SessionLocal
from app.services.seed import run_seed
db = SessionLocal()
run_seed(db)
db.close()
print('Seed complete')
"
```

### 5. Verify everything is working

```bash
# Backend health
curl http://localhost:8000/health
# Expected: {"status":"ok","env":"development"}

# API docs
open http://localhost:8000/docs

# Frontend
open http://localhost:3000
```

### 6. Create a test account and run a job

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"devpassword1","full_name":"Dev User"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"devpassword1"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# List domains
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/catalog/domains

# Get the domain id for finance (usually 1), then create a job
curl -X POST http://localhost:8000/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domain_id":1,"row_count":100}'
```

The worker picks up the job immediately. Poll `GET /jobs/<id>` to watch status change from `pending` → `running` → `completed`.

### 7. Download the result

```bash
# Get result_path from the completed job, then:
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/catalog/local/results/job_1/synthetic_100_rows.csv
```

Or browse `./data/uploads/results/` directly on your host (the volume is mounted).

### Stop / clean up

```bash
# Stop containers (keep data)
docker-compose down

# Stop and wipe the database volume
docker-compose down -v
```

---

## Option B — Bare-metal (without Docker)

Use this if you want finer control, prefer your own Postgres/Redis installs, or can't use Docker.

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | `brew install python@3.11` / [python.org](https://python.org) |
| Node.js | 20+ | `brew install node` / [nodejs.org](https://nodejs.org) |
| PostgreSQL | 14+ | `brew install postgresql@15` |
| Redis | 7+ | `brew install redis` |

### 1. Clone and set up env

```bash
git clone https://github.com/your-org/synthrare.git
cd synthrare
cp .env.example .env
```

Edit `.env`:

```ini
# Point to your local services (not the Docker hostnames)
DATABASE_URL=postgresql://synthrare:synthrare_dev@localhost:5432/synthrare
REDIS_URL=redis://localhost:6379/0
USE_LOCAL_STORAGE=true
LOCAL_STORAGE_PATH=./data/uploads
SECRET_KEY=<output of: python3 -c "import secrets; print(secrets.token_urlsafe(32))">
```

### 2. Create the database

```bash
# Start PostgreSQL (macOS Homebrew)
brew services start postgresql@15

psql postgres -c "CREATE USER synthrare WITH PASSWORD 'synthrare_dev';"
psql postgres -c "CREATE DATABASE synthrare OWNER synthrare;"
```

On Linux (Ubuntu/Debian):

```bash
sudo systemctl start postgresql
sudo -u postgres psql -c "CREATE USER synthrare WITH PASSWORD 'synthrare_dev';"
sudo -u postgres psql -c "CREATE DATABASE synthrare OWNER synthrare;"
```

### 3. Start Redis

```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis
```

### 4. Set up backend Python environment

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 5. Run migrations and seed

```bash
# Still in backend/ with .venv active
alembic upgrade head

python -c "
from app.database import SessionLocal
from app.services.seed import run_seed
db = SessionLocal()
run_seed(db)
db.close()
print('Seed complete')
"
```

### 6. Start the backend

```bash
# In backend/ with .venv active
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 7. Start the worker (new terminal)

```bash
cd backend
source .venv/bin/activate
rq worker --url redis://localhost:6379/0 generation
```

### 8. Set up and start the frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend starts at `http://localhost:3000`.

---

## Enabling DO Gradient locally (optional)

By default the worker uses the statistical fallback. To test real LLM-generated data:

```ini
# .env
DO_GRADIENT_API_KEY=dop_v1_...        # your DO personal access token
DO_GRADIENT_INFERENCE_ENDPOINT=https://inference.do-ai.run/v1
DO_GRADIENT_MODEL_ID=llama3.1-8b-instruct
DO_GRADIENT_MAX_DIRECT_ROWS=200
```

Restart the worker after editing `.env`. See [DO_GRADIENT.md](DO_GRADIENT.md) for full details.

---

## Running the test suite

```bash
cd backend
source .venv/bin/activate   # (or the Docker exec equivalent)
pytest tests/ -v
```

All 62 tests use an in-memory SQLite database and mock the RQ queue — no external services needed.

```bash
# Docker Compose variant
docker-compose exec backend pytest tests/ -v
```

---

## Common issues

| Symptom | Fix |
|---|---|
| `connection refused` on port 5432 | PostgreSQL not running — `brew services start postgresql@15` |
| `connection refused` on port 6379 | Redis not running — `brew services start redis` |
| `alembic upgrade head` fails | Check `DATABASE_URL` in `.env` matches your local Postgres |
| Worker shows `No module named app` | Run it from inside `backend/` with `.venv` active |
| Frontend `ECONNREFUSED` on API calls | Backend not running, or `NEXT_PUBLIC_API_URL` wrong in `.env` |
| Jobs stuck in `pending` | Worker not running — start `rq worker ...` in a separate terminal |
| Generated CSV is empty | Check worker logs; statistical fallback always produces data |

---

## Directory structure reference

```
synthrare/
├── backend/              # FastAPI app + RQ worker
│   ├── app/
│   │   ├── routers/      # HTTP endpoints (auth, jobs, catalog, …)
│   │   ├── services/     # Business logic (gradient.py, storage.py, …)
│   │   ├── workers/      # generation_worker.py (RQ task)
│   │   ├── models/       # SQLAlchemy ORM models
│   │   └── schemas/      # Pydantic request/response schemas
│   ├── tests/            # pytest suite
│   ├── alembic/          # DB migrations
│   └── requirements.txt
├── frontend/             # Next.js app
├── ml/
│   ├── inference/        # generator.py, gradient_client.py, validator.py
│   └── training/         # CTGAN trainers (optional GPU Droplet use)
├── infrastructure/
│   ├── digitalocean/     # app_spec.yaml, deploy scripts
│   └── scripts/          # smoke_test.sh, health_check.sh
├── docs/                 # This file and other guides
├── docker-compose.yml
└── .env.example
```
