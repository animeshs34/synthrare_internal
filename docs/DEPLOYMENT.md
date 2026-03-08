# DigitalOcean Deployment Guide

## Architecture

| Component | DO Service | Plan |
|---|---|---|
| Backend API | App Platform service | basic-s (1 vCPU, 512 MB) |
| RQ Worker | App Platform service | basic-m (1 vCPU, 1 GB) |
| Frontend | App Platform static site | Free |
| Database | Managed PostgreSQL 15 | db-s-1vcpu-1gb |
| Queue / Cache | Managed Valkey 7 | db-s-1vcpu-1gb |
| File storage | DO Spaces (S3-compatible) | $5/mo for 250 GB |
| **Synthetic data** | **DO Gradient Inference** | Per-token (< $0.01/job) |
| Custom model training | GPU Droplet L40S (ephemeral) | ~$3.20/hr, optional |

**Estimated monthly cost (baseline):** ~$60–80/mo (App Platform basic + Managed DB + Spaces)

---

## Prerequisites

### 1. Tools

```bash
# doctl (DigitalOcean CLI)
brew install doctl                  # macOS
snap install doctl                  # Linux
# Windows: https://docs.digitalocean.com/reference/doctl/how-to/install/

# GitHub CLI (for connecting your repo)
brew install gh
gh auth login
```

### 2. DigitalOcean account setup

1. Create a DO account at [cloud.digitalocean.com](https://cloud.digitalocean.com)
2. Go to **API → Tokens → Generate New Token** — give it Read + Write scope
3. Authenticate doctl:

```bash
doctl auth init
# paste your DO token when prompted
doctl account get   # verify it works
```

### 3. GitHub repo

The App Platform deploys from a GitHub repo with auto-deploy on push to `main`.

```bash
# If you haven't already:
gh repo create your-org/synthrare --private --source=. --push
```

Update the repo path in `infrastructure/digitalocean/app_spec.yaml`:

```yaml
# Replace "your-org/synthrare" with your actual GitHub path
github:
  repo: your-org/synthrare
```

---

## Step 1 — Create a DO Spaces bucket

Spaces is the S3-compatible object store where generated CSV files are saved.

```bash
# Create bucket (nyc3 region, private)
doctl spaces create synthrare-datasets --region nyc3
```

Or via dashboard: **Spaces → Create Space → name: `synthrare-datasets`, region: NYC3**

Create a **Spaces access key** (separate from your API token):

1. DO Dashboard → **API → Spaces Keys → Generate New Key**
2. Copy the **key ID** and **secret** — you'll need them in Step 3

---

## Step 2 — Deploy the app

### Option A — deploy script (one command)

```bash
bash infrastructure/scripts/deploy.sh
```

### Option B — manual

```bash
doctl apps create --spec infrastructure/digitalocean/app_spec.yaml
```

The App Platform will:
1. Provision Managed PostgreSQL (`synthrare-db`) and Valkey (`synthrare-cache`)
2. Build and deploy `backend` (FastAPI + uvicorn)
3. Deploy `worker` (RQ worker, `generation` queue)
4. Build and deploy `frontend` (Next.js static site)

Save the App ID from the output:

```bash
doctl apps list          # find your app
APP_ID=<your-app-id>
```

---

## Step 3 — Set secrets

In **DO Dashboard → App Platform → synthrare → Settings → Environment Variables**, add these as **Encrypted (Secret)** type:

| Variable | Value |
|---|---|
| `SECRET_KEY` | `openssl rand -base64 32` (run this and paste the output) |
| `DO_SPACES_KEY` | your Spaces key ID from Step 1 |
| `DO_SPACES_SECRET` | your Spaces secret from Step 1 |
| `DO_GRADIENT_API_KEY` | your DO API token (same one used for doctl) |

> **Note:** `DO_GRADIENT_API_KEY` is your standard DO personal access token — the same one used for `doctl auth init`. No separate Gradient subscription is required.

The following vars are already in `app_spec.yaml` as plain values and need no manual action:

| Variable | Default |
|---|---|
| `DO_GRADIENT_INFERENCE_ENDPOINT` | `https://inference.do-ai.run/v1` |
| `DO_GRADIENT_MODEL_ID` | `llama3.1-8b-instruct` |
| `DO_GRADIENT_MAX_DIRECT_ROWS` | `200` |
| `USE_LOCAL_STORAGE` | `false` |

---

## Step 4 — Run database migrations

Wait for the first deploy to finish (watch **Dashboard → Deployments**), then:

```bash
doctl apps exec $APP_ID --component backend -- alembic upgrade head
```

Or in the dashboard: **App Platform → synthrare → backend → Console** → run `alembic upgrade head`.

---

## Step 5 — Seed the domain catalog

```bash
doctl apps exec $APP_ID --component backend -- python -c "
from app.database import SessionLocal
from app.services.seed import run_seed
db = SessionLocal()
run_seed(db)
db.close()
print('Seed complete')
"
```

This inserts the finance, aviation, and healthcare domain records.

---

## Step 6 — Verify

```bash
# Get the live URL
APP_URL=$(doctl apps get $APP_ID --format LiveURL --no-header)
echo $APP_URL

# Health check
curl $APP_URL/health
# Expected: {"status":"ok","env":"production"}

# Or use the script
bash infrastructure/scripts/health_check.sh $APP_URL
```

---

## Step 7 — Test end-to-end

```bash
# Register
curl -X POST $APP_URL/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword1","full_name":"Your Name"}'

# Login
TOKEN=$(curl -s -X POST $APP_URL/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword1"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# List domains
curl -H "Authorization: Bearer $TOKEN" $APP_URL/catalog/domains

# Create a job (domain_id 1 = finance, 200 rows)
curl -X POST $APP_URL/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domain_id":1,"row_count":200}'

# Poll until status = completed (replace 1 with returned job id)
curl -H "Authorization: Bearer $TOKEN" $APP_URL/jobs/1
```

---

## Auto-deploy on git push

`deploy_on_push: true` is set in `app_spec.yaml` for `main`. Every push triggers a new deploy automatically. No extra action needed.

---

## Viewing logs

```bash
# Live backend logs
doctl apps logs $APP_ID --component backend --follow

# Live worker logs (generation activity shows here)
doctl apps logs $APP_ID --component worker --follow

# Frontend build logs
doctl apps logs $APP_ID --component frontend --type BUILD
```

---

## Rollback

```bash
doctl apps list-deployments $APP_ID
doctl apps create-deployment $APP_ID --force-rebuild
```

Or: **Dashboard → Deployments → select previous → Rollback**.

---

## Scaling

### More worker instances

In `app_spec.yaml`:

```yaml
- name: worker
  instance_count: 2
  instance_size_slug: basic-m
```

### Bigger instances

```yaml
instance_size_slug: basic-l    # 2 vCPU, 4 GB RAM
```

### Worker concurrency

```yaml
run_command: rq worker --url $REDIS_URL --concurrency 4 generation
```

Apply changes:

```bash
doctl apps update $APP_ID --spec infrastructure/digitalocean/app_spec.yaml
```

---

## Custom domain

1. **Dashboard → App Platform → synthrare → Settings → Domains → Add Domain**
2. Add a CNAME at your DNS provider pointing to the app's default `.ondigitalocean.app` domain
3. DO provisions a Let's Encrypt cert automatically

---

## Optional: ML Model Training (GPU Droplet)

> Skip this unless you need higher fidelity than DO Gradient provides.
> The platform works fully without this step using DO Gradient + statistical fallback.

**Cost: ~$3.20/hr (L40S GPU). Always destroy the droplet when done.**

```bash
# 1. Find your SSH key ID
doctl compute ssh-key list

# 2. Create GPU Droplet
doctl compute droplet create synthrare-gpu \
  --region nyc3 \
  --image ubuntu-22-04-x64 \
  --size g-8vcpu-32gb-l40s \
  --ssh-keys <YOUR_SSH_KEY_ID> \
  --wait

# 3. SSH in
DROPLET_IP=$(doctl compute droplet get synthrare-gpu --format PublicIPv4 --no-header)
ssh root@$DROPLET_IP

# 4. Bootstrap and train (on the droplet)
curl -sSL https://raw.githubusercontent.com/your-org/synthrare/main/infrastructure/digitalocean/gpu_droplet_setup.sh | bash
source /opt/synthrare-ml/bin/activate
git clone https://github.com/your-org/synthrare.git && cd synthrare

python ml/training/finance_trainer.py \
  --data ml/seed_data/finance_seed.csv --epochs 300 --output models/finance/model.pkl

python ml/training/healthcare_trainer.py \
  --data ml/seed_data/healthcare_seed.csv --epochs 300 --output models/healthcare/model.pkl

python ml/training/aviation_trainer.py \
  --data ml/seed_data/aviation_seed.csv --epochs 200 --output models/aviation/model.pkl

# 5. Upload to Spaces
aws s3 cp models/ s3://synthrare-datasets/models/ --recursive \
  --endpoint-url https://nyc3.digitaloceanspaces.com

# 6. DESTROY the droplet (critical — stops billing)
exit
doctl compute droplet delete synthrare-gpu
```

To serve a trained model in production, deploy it as a custom DO Gradient endpoint and update `DO_GRADIENT_INFERENCE_ENDPOINT` to point to it. See [DO_GRADIENT.md](DO_GRADIENT.md).

---

## Environment Variables Reference

| Variable | Required | Where set | Description |
|---|---|---|---|
| `APP_ENV` | yes | app_spec.yaml | `production` |
| `SECRET_KEY` | yes | Dashboard secret | JWT signing key, 32+ chars |
| `DATABASE_URL` | auto | App Platform | Injected from managed DB |
| `REDIS_URL` | auto | App Platform | Injected from managed cache |
| `DO_SPACES_KEY` | yes | Dashboard secret | Spaces access key ID |
| `DO_SPACES_SECRET` | yes | Dashboard secret | Spaces secret key |
| `DO_SPACES_BUCKET` | no | app_spec.yaml | Default: `synthrare-datasets` |
| `DO_GRADIENT_API_KEY` | recommended | Dashboard secret | DO token for LLM inference |
| `DO_GRADIENT_INFERENCE_ENDPOINT` | recommended | app_spec.yaml | Default: `https://inference.do-ai.run/v1` |
| `DO_GRADIENT_MODEL_ID` | no | app_spec.yaml | Default: `llama3.1-8b-instruct` |
| `DO_GRADIENT_MAX_DIRECT_ROWS` | no | app_spec.yaml | Default: `200` |
| `USE_LOCAL_STORAGE` | no | app_spec.yaml | `false` in production |

---

## Monitoring

- **Metrics:** App Platform → synthrare → Insights (CPU, memory, request rate)
- **Alerts:** Dashboard → Monitoring → Create Alert → pick backend or worker
- **Billing alert:** Billing → Alert Policies → set at $100 to catch runaway costs
- **Worker activity:** `doctl apps logs $APP_ID --component worker --follow`
