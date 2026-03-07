# SynthRare API Reference

Base URL: `https://synthrare-backend.ondigitalocean.app`
Local dev: `http://localhost:8000`

All endpoints return JSON. Authenticated endpoints require either:
- **JWT Bearer token** (from `/auth/login`) — for user-facing endpoints
- **API Key Bearer token** (from `/api-keys`, prefix `sr_`) — for `/api/v1/*` endpoints

---

## Health

### `GET /health`

No auth required.

**Response 200**
```json
{"status": "ok", "env": "production"}
```

---

## Auth

### `POST /auth/register`

Create a new user account.

**Body**
```json
{
  "email": "user@example.com",
  "password": "minimum8chars",
  "full_name": "Jane Doe"
}
```

**Response 201**
```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "role": "user",
  "is_active": true,
  "credits": 10
}
```

**Errors:** `409` email already registered · `422` validation error

---

### `POST /auth/login`

**Body**
```json
{"email": "user@example.com", "password": "minimum8chars"}
```

**Response 200**
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
```

**Errors:** `401` invalid credentials

---

### `POST /auth/refresh`

Exchange a refresh token for new tokens.

**Body**
```json
{"refresh_token": "<jwt>"}
```

**Response 200** — same shape as `/auth/login`

**Errors:** `401` invalid or expired token

---

## Catalog

### `GET /catalog`

List active datasets. No auth required.

**Query params**
| Param | Type | Description |
|---|---|---|
| `domain_slug` | string | Filter by domain (`finance`, `aviation`, `healthcare`) |

**Response 200**
```json
[
  {
    "id": 1,
    "name": "Synthetic Stock Prices (S&P 500 style)",
    "description": "1,000 rows of OHLCV synthetic daily stock price data.",
    "domain": {"id": 1, "name": "Finance", "slug": "finance", "description": "..."},
    "row_count": 1000,
    "column_count": 6,
    "credit_cost": 1,
    "status": "active"
  }
]
```

---

### `GET /catalog/{dataset_id}`

Get a single dataset. No auth required.

**Response 200** — same shape as list item, plus `created_at`

**Errors:** `404` not found

---

### `POST /catalog` 🔒 Admin only

Create a catalog entry.

**Headers:** `Authorization: Bearer <jwt>`

**Body**
```json
{
  "name": "New Dataset",
  "description": "Description",
  "domain_id": 1,
  "storage_path": "datasets/finance/prices.csv",
  "row_count": 5000,
  "column_count": 8,
  "credit_cost": 2
}
```

**Response 201** — full `DatasetResponse`

**Errors:** `403` not admin · `404` domain not found

---

### `POST /catalog/{dataset_id}/download` 🔒

Request a download URL. Deducts `credit_cost` credits from the user.

**Headers:** `Authorization: Bearer <jwt>`

**Response 200**
```json
{
  "download_url": "https://synthrare-datasets.nyc3.digitaloceanspaces.com/...",
  "credits_remaining": "8"
}
```

**Errors:** `402` insufficient credits · `404` not found

---

## Jobs

### `POST /jobs` 🔒

Enqueue a synthetic data generation job.

**Headers:** `Authorization: Bearer <jwt>`

**Body**
```json
{
  "domain_id": 1,
  "dataset_id": null,
  "row_count": 1000,
  "parameters": {}
}
```

**Response 201**
```json
{
  "id": 42,
  "user_id": 7,
  "domain_id": 1,
  "dataset_id": null,
  "row_count": 1000,
  "parameters": {},
  "status": "pending",
  "rq_job_id": "abc123",
  "result_path": null,
  "error_message": null,
  "created_at": "2026-03-07T00:00:00Z",
  "updated_at": "2026-03-07T00:00:00Z"
}
```

**Errors:** `403` unauthenticated · `404` domain not found · `422` row_count out of range (1–1,000,000)

---

### `GET /jobs` 🔒

List the current user's jobs (newest first).

**Headers:** `Authorization: Bearer <jwt>`

**Response 200** — array of job objects

---

### `GET /jobs/{job_id}` 🔒

Get a specific job. Only accessible by the owning user.

**Headers:** `Authorization: Bearer <jwt>`

**Response 200** — job object

**Errors:** `404` not found or not owned

---

### `GET /jobs/{job_id}/report` 🔒

Get (or auto-generate) the fidelity validation report for a completed job.

**Headers:** `Authorization: Bearer <jwt>`

**Response 200**
```json
{
  "id": 5,
  "job_id": 42,
  "status": "completed",
  "overall_score": 0.8732,
  "ks_statistic": 0.0612,
  "correlation_delta": 0.0421,
  "coverage_score": 0.9418,
  "column_scores": [
    {"column": "feature_a", "score": 0.9312, "ks": 0.0688},
    {"column": "feature_b", "score": 0.8541, "ks": 0.1459},
    {"column": "feature_c", "score": 0.9112, "ks": 0.0888}
  ],
  "error_message": null,
  "created_at": "2026-03-07T00:00:00Z",
  "updated_at": "2026-03-07T00:00:00Z"
}
```

**Notes:**
- `overall_score` — composite fidelity: 0.0 (bad) to 1.0 (perfect)
- `ks_statistic` — average Kolmogorov-Smirnov statistic (lower = better)
- `correlation_delta` — mean |Δ Pearson correlation| (lower = better)
- `coverage_score` — fraction of real distribution's P5–P95 range covered (higher = better)
- `column_scores` — Recharts-ready array for per-column bar chart

**Errors:** `400` job not completed · `404` job not found

---

## API Keys

### `POST /api-keys` 🔒

Create a new API key. The `raw_key` is shown **once only**.

**Headers:** `Authorization: Bearer <jwt>`

**Body**
```json
{"name": "My Integration"}
```

**Response 201**
```json
{
  "id": 3,
  "name": "My Integration",
  "is_active": true,
  "last_used_at": null,
  "created_at": "2026-03-07T00:00:00Z",
  "raw_key": "sr_AbCdEf..."
}
```

---

### `GET /api-keys` 🔒

List active API keys for the current user (raw key not returned).

**Headers:** `Authorization: Bearer <jwt>`

**Response 200** — array of key objects (no `raw_key`)

---

### `DELETE /api-keys/{key_id}` 🔒

Revoke an API key.

**Headers:** `Authorization: Bearer <jwt>`

**Response 204** No content

**Errors:** `404` key not found

---

## Public API v1

Rate limits: **10 req/min** for generation, **60 req/min** for status.

Authentication: `Authorization: Bearer sr_<your_api_key>`

### `POST /api/v1/generate`

Enqueue a generation job via API key.

**Body** — same as `POST /jobs`

**Response 201** — job object

**Errors:** `401` invalid or missing key · `404` domain not found · `429` rate limit exceeded

---

### `GET /api/v1/jobs/{job_id}`

Get job status via API key. Only jobs belonging to the key's owner are accessible.

**Response 200** — job object

**Errors:** `401` invalid key · `404` not found · `429` rate limit exceeded

---

## Job Status Values

| Status | Meaning |
|---|---|
| `pending` | Queued, not yet started |
| `running` | Worker is generating data |
| `completed` | Data generated; `result_path` is set |
| `failed` | Generation failed; `error_message` is set |

---

## Fidelity Score Interpretation

| Score | Quality |
|---|---|
| 0.90 – 1.00 | Excellent — publication-grade synthetic data |
| 0.75 – 0.89 | Good — suitable for most ML tasks |
| 0.60 – 0.74 | Fair — use with caution |
| < 0.60 | Poor — retrain or adjust parameters |

---

## Error Format

All errors follow RFC 7807:

```json
{"detail": "Human-readable error message"}
```

Common status codes:

| Code | Meaning |
|---|---|
| `400` | Bad request (e.g. job not completed) |
| `401` | Missing or invalid credentials |
| `402` | Insufficient credits |
| `403` | Forbidden (wrong role or missing token) |
| `404` | Resource not found |
| `409` | Conflict (e.g. duplicate email) |
| `422` | Validation error (malformed body) |
| `429` | Rate limit exceeded |
| `500` | Internal server error |
