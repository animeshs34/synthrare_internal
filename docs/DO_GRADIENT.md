# DO Gradient Inference — SynthRare Integration Guide

## Overview

SynthRare uses **DigitalOcean Gradient Inference** (DO AI Model Serving) as the primary engine for generating synthetic data. Instead of training custom CTGAN/TimeGAN models for every deployment, the platform calls foundation LLMs hosted on DO Gradient via an OpenAI-compatible API.

This means:
- **No GPU required to run** — inference is serverless and managed by DO
- **Zero cold-start training** — usable immediately after deploy
- **Domain prompts** control the schema and realism of output
- **Custom trained models remain supported** as an optional upgrade path

---

## Architecture

```
User request (POST /jobs)
        │
        ▼
  RQ Worker (basic-m)
        │
        ├─── DO_GRADIENT_API_KEY set? ─── YES ──► DO Gradient API
        │                                         (llama3.1-8b-instruct etc.)
        │                                         ↓ parse CSV response
        │                                         ↓ calibrated stat. augmentation
        │                                         ↓ upload to DO Spaces
        │
        └─── NO / API failure ──────────► Statistical fallback
                                          (numpy distributions, always available)
                                          ↓ upload to DO Spaces / local storage
```

For row counts above `DO_GRADIENT_MAX_DIRECT_ROWS` (default 200):
- The LLM generates a **seed batch** (in chunks of 50 rows)
- The remaining rows are generated **statistically, calibrated to the seed** (matching mean/std)
- Results are concatenated and shuffled

---

## DO Gradient vs GPU Droplet Training — When to Use Each

| Scenario | Recommendation |
|---|---|
| Standard deployment | **DO Gradient** — zero setup, serverless |
| Need highest statistical fidelity for a specific domain | **GPU Droplet training** — train CTGAN on domain data |
| Budget-sensitive / prototype | **DO Gradient** or statistical fallback |
| Regulatory requirement for reproducible model | **GPU Droplet training** — model artifact stored on Spaces/HF |
| Both approaches | Set `DO_GRADIENT_API_KEY` for primary; `models/<domain>/model.pkl` for trained fallback |

---

## Available Models on DO Gradient

| Model ID | Context | Speed | Quality | Cost tier |
|---|---|---|---|---|
| `llama3.1-8b-instruct` | 128k | Fast | Good | Low |
| `llama3.1-70b-instruct` | 128k | Moderate | Excellent | Medium |
| `mistral-7b-instruct-v0-3` | 32k | Fast | Good | Low |

**Recommendation:** Start with `llama3.1-8b-instruct`. Upgrade to `llama3.1-70b-instruct` for higher-fidelity healthcare data (clinically realistic correlations).

---

## Setup

### 1. Get a DO API token

```
https://cloud.digitalocean.com/account/api/tokens
```

Create a token with **read + write** scope. This is your `DO_GRADIENT_API_KEY`.

### 2. Verify the Gradient inference endpoint

DO Gradient uses an OpenAI-compatible endpoint:

```
https://inference.do-ai.run/v1
```

Test it:

```bash
curl -X POST https://inference.do-ai.run/v1/chat/completions \
  -H "Authorization: Bearer $DO_GRADIENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1-8b-instruct",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 20
  }'
```

Expected: `{"choices": [{"message": {"content": "Hello! ..."}}]}`

### 3. Set environment variables

**Local dev** (`.env`):
```
DO_GRADIENT_API_KEY=dop_v1_...
DO_GRADIENT_INFERENCE_ENDPOINT=https://inference.do-ai.run/v1
DO_GRADIENT_MODEL_ID=llama3.1-8b-instruct
DO_GRADIENT_MAX_DIRECT_ROWS=200
```

**Production** (DO App Platform → Settings → Environment Variables):

| Key | Type | Value |
|---|---|---|
| `DO_GRADIENT_API_KEY` | SECRET | your DO token |
| `DO_GRADIENT_INFERENCE_ENDPOINT` | Plain | `https://inference.do-ai.run/v1` |
| `DO_GRADIENT_MODEL_ID` | Plain | `llama3.1-8b-instruct` |
| `DO_GRADIENT_MAX_DIRECT_ROWS` | Plain | `200` |

Or update `infrastructure/digitalocean/app_spec.yaml` — the worker service already has these keys defined.

---

## How Generation Works

### Domain prompts

Each domain has a hardcoded system prompt in `backend/app/services/gradient.py` that specifies:
- Column names and order
- Data types and ranges
- Domain-specific constraints (e.g. `high >= open` for OHLCV, `diastolic < systolic` for healthcare)
- Realism instructions (e.g. "clinically realistic correlations")

| Domain | Schema | Key constraints |
|---|---|---|
| `finance` | date, open, high, low, close, volume | high ≥ open, low ≤ open, S&P 500 price range |
| `aviation` | timestamp, altitude_ft, speed_kts, heading_deg, vertical_speed_fpm, latitude, longitude, flight_id | smooth cruise segment, realistic airspace bounds |
| `healthcare` | patient_id, age, gender, systolic_bp, diastolic_bp, bmi, glucose_mg_dl, cholesterol_mg_dl, diagnosis_code, los_days | diastolic < systolic, diabetics have higher glucose |

### Batching

The LLM is called in batches of **50 rows** to stay within token limits. A job requesting 500 rows makes:
- 4 × 50-row Gradient calls (200 rows total from LLM)
- 300 rows from statistical generation calibrated to the LLM seed

This keeps latency predictable (each batch ~3–8 seconds) and cost bounded.

### Fallback chain

```python
# backend/app/services/gradient.py — generate_for_domain()
if gradient_available():
    try:
        return _generate_via_gradient(slug, row_count)   # Gradient
    except:
        pass  # log + fall through

return _generate_statistical(slug, row_count)            # Statistical
```

If the Gradient API is unreachable or returns malformed CSV, the worker automatically falls back to the statistical generator. **No job will fail** due to Gradient unavailability.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DO_GRADIENT_API_KEY` | `""` | DO personal access token. If empty, Gradient is skipped. |
| `DO_GRADIENT_INFERENCE_ENDPOINT` | `""` | Base URL of the Gradient API (`https://inference.do-ai.run/v1`). |
| `DO_GRADIENT_MODEL_ID` | `llama3.1-8b-instruct` | Model to use for all domains. |
| `DO_GRADIENT_MAX_DIRECT_ROWS` | `200` | Max rows generated by LLM; rows beyond this use statistical augmentation. |

---

## Costs

DO Gradient Inference is billed per token:

| Model | Input | Output | 500-row finance job (est.) |
|---|---|---|---|
| `llama3.1-8b-instruct` | ~$0.10/M | ~$0.10/M | < $0.01 |
| `llama3.1-70b-instruct` | ~$0.90/M | ~$0.90/M | ~$0.05 |

A typical 1000-row job (4 Gradient batches) with `llama3.1-8b-instruct` costs **< $0.01**.

Compare to GPU Droplet (L40S): **~$3/hr**, minimum ~30 min for training = ~$1.50 per model, reusable thereafter.

---

## Testing the Integration Locally

With `DO_GRADIENT_API_KEY` set, start the backend and run the smoke test:

```bash
# Backend with Gradient enabled
DO_GRADIENT_API_KEY=dop_v1_... \
DO_GRADIENT_INFERENCE_ENDPOINT=https://inference.do-ai.run/v1 \
DATABASE_URL=sqlite:////tmp/synthrare_smoke.db \
SECRET_KEY=my-dev-secret-key-at-least-32-chars \
USE_LOCAL_STORAGE=true \
LOCAL_STORAGE_PATH=/tmp/synthrare_uploads \
uvicorn app.main:app --host 127.0.0.1 --port 8000 &

# Seed the DB, then run full smoke test
bash infrastructure/scripts/smoke_test.sh http://127.0.0.1:8000
```

Or test the Gradient service directly:

```python
from app.services.gradient import generate_for_domain
import os

os.environ["DO_GRADIENT_API_KEY"] = "dop_v1_..."
os.environ["DO_GRADIENT_INFERENCE_ENDPOINT"] = "https://inference.do-ai.run/v1"

df = generate_for_domain("finance", 50)
print(df.head())
print(df.dtypes)
```

---

## Upgrading to Custom Trained Models

If you need higher fidelity for a specific domain (e.g. a proprietary financial dataset), you can train a CTGAN model on a GPU Droplet and the worker will automatically prefer it:

**Priority order (worker):**
1. DO Gradient Inference (configured via env vars)
2. Local trained model at `models/<domain>/model.pkl` *(only in ml/ scripts, not worker)*
3. Statistical fallback

> **Note:** The RQ worker only uses DO Gradient + statistical fallback. To use a trained model in production, you need to serve it via DO Gradient Serverless Inference (deploy your `.pkl` as a custom endpoint) and point `DO_GRADIENT_INFERENCE_ENDPOINT` to it.

### Training workflow (for future improvements)

```bash
# 1. Provision GPU Droplet
doctl compute droplet create synthrare-gpu \
  --region nyc3 --image ubuntu-22-04-x64 \
  --size g-8vcpu-32gb-l40s --ssh-keys <KEY_ID>

# 2. Bootstrap
ssh root@<IP>
bash infrastructure/digitalocean/gpu_droplet_setup.sh

# 3. Train
python ml/training/finance_trainer.py \
  --data ml/seed_data/finance_seed.csv \
  --epochs 300 \
  --output models/finance/model.pkl

# 4. Upload to DO Spaces for use in inference
aws s3 cp models/finance/model.pkl \
  s3://synthrare-datasets/models/finance/model.pkl \
  --endpoint-url https://nyc3.digitaloceanspaces.com

# 5. Destroy droplet (stop billing)
doctl compute droplet delete synthrare-gpu
```

To serve the trained model via DO Gradient, follow the DO Gradient custom model deployment guide:
```
https://docs.digitalocean.com/products/ai-ml/gradient/
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Jobs stuck in `pending` | Worker not running | `docker-compose up worker` or check App Platform worker status |
| Jobs `failed` with "DO Gradient request failed" | Bad API key or endpoint | Check `DO_GRADIENT_API_KEY` and `DO_GRADIENT_INFERENCE_ENDPOINT` |
| Jobs complete but CSV has wrong schema | Model returned unexpected columns | Update domain prompt in `backend/app/services/gradient.py` |
| Statistical fallback always used | `DO_GRADIENT_API_KEY` empty | Set both `DO_GRADIENT_API_KEY` and `DO_GRADIENT_INFERENCE_ENDPOINT` |
| High latency for large row counts | Too many Gradient batches | Reduce `DO_GRADIENT_MAX_DIRECT_ROWS` or use statistical for large jobs |

### Check worker logs

```bash
# docker-compose
docker-compose logs -f worker

# DO App Platform
doctl apps logs <APP_ID> --component worker --follow
```
