# SynthRare — Deployment Guide

## Overview

SynthRare is deployed on DigitalOcean using:

| Component | Service |
|---|---|
| Backend API | DO App Platform (basic-s) |
| Worker | DO App Platform (basic-m) |
| Frontend | DO App Platform (static site) |
| Database | DO Managed PostgreSQL 15 |
| Cache / Queue | DO Managed Valkey 7 |
| File Storage | DO Spaces (NYC3) |
| **Synthetic Data Generation** | **DO Gradient Inference (primary)** |
| Custom Model Training (optional) | DO GPU Droplet L40S (ephemeral) |

### Generation approach

The worker uses **DO Gradient Inference** (a managed LLM endpoint, OpenAI-compatible) as the primary generation engine. This means:

- No GPU setup required for a standard deployment
- Generation is available immediately after `doctl apps create`
- If `DO_GRADIENT_API_KEY` is not set, the worker falls back to fast statistical generation

For maximum fidelity on a specific domain, you can optionally train a CTGAN model on a GPU Droplet and serve it as a custom DO Gradient endpoint. See [DO_GRADIENT.md](DO_GRADIENT.md) for full details.

---

## Prerequisites

```bash
# Install doctl
brew install doctl          # macOS
snap install doctl          # Linux

# Authenticate
doctl auth init             # paste your DO API token

# Install GitHub CLI (for repo wiring)
brew install gh
```

---

## Step 1 — Set secrets

In the DO dashboard → App Platform → your app → Settings → Environment Variables, set the `SECRET` type vars:

```
SECRET_KEY                       # 32+ char random string: openssl rand -base64 32
DO_SPACES_KEY                    # Spaces access key
DO_SPACES_SECRET                 # Spaces secret
DO_GRADIENT_API_KEY              # DO personal access token (used for Gradient Inference)
```

Set the following as plain (non-secret) env vars on the **worker** service:

```
DO_GRADIENT_INFERENCE_ENDPOINT=https://inference.do-ai.run/v1
DO_GRADIENT_MODEL_ID=llama3.1-8b-instruct
DO_GRADIENT_MAX_DIRECT_ROWS=200
```

These are already present in `infrastructure/digitalocean/app_spec.yaml` — no manual step needed if you use `deploy.sh`.

> **Note:** `DO_GRADIENT_API_KEY` is your standard DigitalOcean personal access token — the same one used for `doctl`. No separate Gradient subscription is required.

See [docs/DO_GRADIENT.md](DO_GRADIENT.md) for full Gradient configuration options.

---

## Step 2 — Create DO Spaces bucket

```bash
bash infrastructure/digitalocean/spaces_setup.sh
```

This creates the `synthrare-datasets` bucket in `nyc3`.

Enable CDN on the bucket in the DO dashboard for fast dataset downloads.

---

## Step 3 — Deploy the app

Update `infrastructure/digitalocean/app_spec.yaml` with your GitHub repo path, then:

```bash
bash infrastructure/scripts/deploy.sh
```

Or manually:

```bash
doctl auth init
doctl apps create --spec infrastructure/digitalocean/app_spec.yaml
```

The App Platform will:
1. Provision Managed PostgreSQL (`synthrare-db`) and Managed Valkey (`synthrare-cache`)
2. Build and deploy `backend` (FastAPI uvicorn)
3. Deploy `worker` (RQ worker listening on `generation` queue)
4. Build and deploy `frontend` (Next.js static site)

---

## Step 4 — Run database migrations

After first deploy, shell into the backend service and run:

```bash
doctl apps exec <APP_ID> --component backend -- alembic upgrade head
```

Or via the App Platform console.

---

## Step 5 — Seed the catalog

```bash
doctl apps exec <APP_ID> --component backend -- python -c "
from app.database import SessionLocal
from app.services.seed import run_seed
db = SessionLocal()
run_seed(db)
db.close()
print('Seed complete')
"
```

---

## Step 6 — Verify health check

```bash
bash infrastructure/scripts/health_check.sh https://synthrare-backend.ondigitalocean.app
```

Expected output:
```
Health check passed: {"status": "ok", "env": "production"}
```

---

## ML Model Training (GPU Droplet) — Optional

> This section is **optional**. The platform works out of the box using DO Gradient Inference.
> Train a custom model only if you need higher fidelity on proprietary domain data.

> **Cost warning:** GPU Droplet L40S costs ~$2.99–3.44/GPU/hr. Destroy immediately after training.

### Provision the droplet

```bash
doctl compute droplet create synthrare-gpu \
  --region nyc3 \
  --image ubuntu-22-04-x64 \
  --size g-8vcpu-32gb-l40s \
  --ssh-keys <YOUR_SSH_KEY_ID>
```

### Bootstrap and train

```bash
ssh root@<DROPLET_IP>
curl -sSL https://raw.githubusercontent.com/YOUR_ORG/synthrare/main/infrastructure/digitalocean/gpu_droplet_setup.sh | bash

source /opt/synthrare-ml/bin/activate
git clone https://github.com/YOUR_ORG/synthrare.git
cd synthrare

# Finance
python ml/training/finance_trainer.py \
  --data ml/seed_data/finance_seed.csv \
  --epochs 300 \
  --output models/finance/model.pkl

# Aviation
python ml/training/aviation_trainer.py \
  --data ml/seed_data/aviation_seed.csv \
  --epochs 200 \
  --output models/aviation/model.pkl

# Healthcare
python ml/training/healthcare_trainer.py \
  --data ml/seed_data/healthcare_seed.csv \
  --epochs 300 \
  --output models/healthcare/model.pkl
```

### Destroy the droplet

```bash
doctl compute droplet delete synthrare-gpu
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | yes | `production` or `development` |
| `SECRET_KEY` | yes | JWT signing key (32+ chars) |
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `REDIS_URL` | yes | Valkey/Redis URL |
| `DO_SPACES_KEY` | yes | Spaces access key ID |
| `DO_SPACES_SECRET` | yes | Spaces secret access key |
| `DO_SPACES_BUCKET` | yes | Bucket name (`synthrare-datasets`) |
| `DO_GRADIENT_API_KEY` | no | For serverless inference |
| `HF_TOKEN` | no | For model upload/download |
| `USE_LOCAL_STORAGE` | dev only | `true` to skip Spaces |

---

## Scaling

- **Backend:** change `instance_size_slug` in `app_spec.yaml` to `basic-m` or `professional-s`
- **Worker:** scale concurrency with `rq worker --burst --concurrency 4`
- **Database:** upgrade to `db-s-1vcpu-2gb` in the DO dashboard
- **Multiple workers:** add replicas in App Platform → worker component → instance count

---

## Monitoring

- DO App Platform provides built-in metrics (CPU, memory, request count)
- Set a billing alert at $150 in the DO dashboard
- Application logs: `doctl apps logs <APP_ID> --component backend --follow`

---

## Rollback

```bash
# List deployments
doctl apps list-deployments <APP_ID>

# Roll back to a previous deployment
doctl apps create-deployment <APP_ID> --force-rebuild
```
