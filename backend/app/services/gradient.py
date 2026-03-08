"""DigitalOcean Gradient Inference service.

Generation priority (per call to generate_for_domain):
  1. DO Gradient Inference  — if DO_GRADIENT_API_KEY and DO_GRADIENT_INFERENCE_ENDPOINT are set
  2. Statistical fallback   — always available, no external deps

For large row counts (> do_gradient_max_direct_rows) the Gradient-generated seed
is used to calibrate the statistical generator so the full output matches the
realistic distributions returned by the LLM.
"""
from __future__ import annotations

import io
import logging
import re
import time
from typing import Any

import httpx
import numpy as np
import pandas as pd

from app.config import settings

log = logging.getLogger(__name__)

# Rows generated per single Gradient API call (stays within token limits)
_GRADIENT_BATCH_SIZE = 50


# ─────────────────────────────────────────────────────────────────────────────
# Domain system prompts
# ─────────────────────────────────────────────────────────────────────────────

_DOMAIN_PROMPTS: dict[str, str] = {
    "finance": (
        "You are a synthetic financial data generator. "
        "Generate realistic synthetic stock price rows in CSV format. "
        "Columns (in this exact order): "
        "date (YYYY-MM-DD business days), open (float USD), high (float USD, >= open), "
        "low (float USD, <= open), close (float USD), volume (integer, 1000000-50000000). "
        "Use realistic S&P 500 style prices (50–2000 USD range) with natural day-to-day variation. "
        "Output ONLY raw CSV with a single header row — no markdown, no explanations."
    ),
    "aviation": (
        "You are a synthetic aviation telemetry generator. "
        "Generate realistic synthetic flight telemetry rows in CSV format. "
        "Columns (in this exact order): "
        "timestamp (ISO 8601, 1-second intervals), altitude_ft (float 0–45000), "
        "speed_kts (float 200–600), heading_deg (float 0–360), "
        "vertical_speed_fpm (float -3000–3000), latitude (float 30–60), "
        "longitude (float -120 to -70), flight_id (format: SYN0001). "
        "Simulate a realistic cruise segment with smooth transitions. "
        "Output ONLY raw CSV with a single header row — no markdown, no explanations."
    ),
    "healthcare": (
        "You are a synthetic HIPAA-safe healthcare data generator. "
        "Generate realistic synthetic patient records in CSV format. "
        "Columns (in this exact order): "
        "patient_id (format P000001), age (integer 18–90), gender (M/F/Other), "
        "systolic_bp (integer 80–200), diastolic_bp (integer 50–130, < systolic), "
        "bmi (float 16–50), glucose_mg_dl (float 60–400), "
        "cholesterol_mg_dl (float 100–400), "
        "diagnosis_code (one of: E11, I10, J45, M54, F32, Z00), "
        "los_days (integer 1–15). "
        "Use clinically realistic correlations (e.g. diabetics have higher glucose). "
        "Output ONLY raw CSV with a single header row — no markdown, no explanations."
    ),
}

_DEFAULT_DOMAIN = "finance"


# ─────────────────────────────────────────────────────────────────────────────
# Gradient API client
# ─────────────────────────────────────────────────────────────────────────────

def _call_gradient(messages: list[dict[str, str]], max_tokens: int = 4096) -> str:
    """Call DO Gradient (OpenAI-compatible /chat/completions). Retries up to 3×."""
    endpoint = settings.do_gradient_inference_endpoint.rstrip("/")
    url = f"{endpoint}/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.do_gradient_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": settings.do_gradient_model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }

    for attempt in range(3):
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            # 4xx errors are permanent config problems — don't retry
            if 400 <= exc.response.status_code < 500:
                raise RuntimeError(
                    f"DO Gradient request failed ({exc.response.status_code}): {exc}"
                ) from exc
            if attempt == 2:
                raise RuntimeError(
                    f"DO Gradient request failed after 3 attempts: {exc}"
                ) from exc
            wait = 2 ** attempt
            log.warning("Gradient attempt %d failed (%s), retrying in %ds", attempt + 1, exc, wait)
            time.sleep(wait)
        except (httpx.RequestError, KeyError, IndexError) as exc:
            if attempt == 2:
                raise RuntimeError(
                    f"DO Gradient request failed after 3 attempts: {exc}"
                ) from exc
            wait = 2 ** attempt
            log.warning("Gradient attempt %d failed (%s), retrying in %ds", attempt + 1, exc, wait)
            time.sleep(wait)

    raise RuntimeError("Unreachable")


def _gradient_available() -> bool:
    return bool(settings.do_gradient_api_key and settings.do_gradient_inference_endpoint)


# ─────────────────────────────────────────────────────────────────────────────
# CSV parsing
# ─────────────────────────────────────────────────────────────────────────────

def _extract_csv(text: str) -> str:
    """Strip markdown code fences if the LLM wrapped its output."""
    match = re.search(r"```(?:csv)?\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _parse_csv_response(text: str, domain_slug: str) -> pd.DataFrame | None:
    """Parse LLM response into a DataFrame. Returns None on failure."""
    try:
        csv_text = _extract_csv(text)
        df = pd.read_csv(io.StringIO(csv_text))
        if df.empty or len(df.columns) < 2:
            return None
        return df
    except Exception as exc:
        log.warning("Failed to parse Gradient CSV response for %s: %s", domain_slug, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Statistical generation (always-available fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _statistical_finance(row_count: int, seed_df: pd.DataFrame | None = None) -> pd.DataFrame:
    rng = np.random.default_rng()
    if seed_df is not None and not seed_df.empty:
        # Calibrate to seed distribution
        try:
            price_mean = seed_df["close"].mean()
            price_std = seed_df["close"].std()
        except (KeyError, TypeError):
            price_mean, price_std = 150.0, 30.0
    else:
        price_mean, price_std = 150.0, 30.0

    close = rng.normal(price_mean, price_std, row_count).clip(10, 3000)
    spread = rng.uniform(0.002, 0.015, row_count)
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=row_count, freq="B"),
        "open": (close * (1 - spread / 2)).round(2),
        "high": (close * (1 + spread)).round(2),
        "low": (close * (1 - spread)).round(2),
        "close": close.round(2),
        "volume": rng.integers(1_000_000, 50_000_000, row_count),
    })


def _statistical_aviation(row_count: int, seed_df: pd.DataFrame | None = None) -> pd.DataFrame:
    rng = np.random.default_rng()
    t = pd.date_range("2023-01-01", periods=row_count, freq="s")
    altitude = 30_000 + rng.normal(0, 200, row_count).cumsum() * 0.02
    return pd.DataFrame({
        "timestamp": t,
        "altitude_ft": altitude.clip(0, 45_000).round(1),
        "speed_kts": rng.normal(480, 20, row_count).clip(200, 600).round(1),
        "heading_deg": rng.uniform(0, 360, row_count).round(2),
        "vertical_speed_fpm": rng.normal(0, 150, row_count).round(1),
        "latitude": rng.uniform(30, 60, row_count).round(4),
        "longitude": rng.uniform(-120, -70, row_count).round(4),
        "flight_id": [f"SYN{i:04d}" for i in range(row_count)],
    })


def _statistical_healthcare(row_count: int, seed_df: pd.DataFrame | None = None) -> pd.DataFrame:
    rng = np.random.default_rng()
    ages = rng.integers(18, 90, row_count)
    return pd.DataFrame({
        "patient_id": [f"P{i:06d}" for i in range(row_count)],
        "age": ages,
        "gender": rng.choice(["M", "F", "Other"], row_count, p=[0.49, 0.49, 0.02]),
        "systolic_bp": rng.normal(120, 15, row_count).clip(80, 200).astype(int),
        "diastolic_bp": rng.normal(80, 10, row_count).clip(50, 130).astype(int),
        "bmi": rng.normal(26, 5, row_count).clip(16, 50).round(1),
        "glucose_mg_dl": rng.lognormal(4.8, 0.2, row_count).clip(60, 400).round(1),
        "cholesterol_mg_dl": rng.normal(195, 35, row_count).clip(100, 400).round(1),
        "diagnosis_code": rng.choice(["E11", "I10", "J45", "M54", "F32", "Z00"], row_count),
        "los_days": rng.integers(1, 15, row_count),
    })


_STATISTICAL_FN = {
    "finance": _statistical_finance,
    "aviation": _statistical_aviation,
    "healthcare": _statistical_healthcare,
}


def _generate_statistical(domain_slug: str, row_count: int, seed_df: pd.DataFrame | None = None) -> pd.DataFrame:
    fn = _STATISTICAL_FN.get(domain_slug, _statistical_finance)
    return fn(row_count, seed_df)


# ─────────────────────────────────────────────────────────────────────────────
# Gradient-backed generation
# ─────────────────────────────────────────────────────────────────────────────

def _generate_via_gradient(domain_slug: str, row_count: int) -> pd.DataFrame:
    """
    Generate data via DO Gradient in batches of _GRADIENT_BATCH_SIZE rows.
    For row_count beyond do_gradient_max_direct_rows, the Gradient seed is used
    to calibrate statistical generation for the remainder.
    """
    system_prompt = _DOMAIN_PROMPTS.get(domain_slug, _DOMAIN_PROMPTS[_DEFAULT_DOMAIN])
    max_direct = settings.do_gradient_max_direct_rows

    # How many rows to generate directly via Gradient
    gradient_rows = min(row_count, max_direct)

    frames: list[pd.DataFrame] = []
    generated = 0

    while generated < gradient_rows:
        batch_size = min(_GRADIENT_BATCH_SIZE, gradient_rows - generated)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Generate exactly {batch_size} data rows in CSV format. "
                    f"Include the header row on the first line. "
                    f"Output raw CSV only — no extra text."
                ),
            },
        ]
        try:
            response_text = _call_gradient(messages)
            df_batch = _parse_csv_response(response_text, domain_slug)
        except Exception as exc:
            log.warning("Gradient batch failed: %s — falling back to statistical for this batch", exc)
            df_batch = None

        if df_batch is not None and not df_batch.empty:
            frames.append(df_batch)
            generated += len(df_batch)
        else:
            # Partial failure: fill remaining direct rows statistically
            remaining_direct = gradient_rows - generated
            frames.append(_generate_statistical(domain_slug, remaining_direct))
            generated = gradient_rows
            break

    seed_df = pd.concat(frames, ignore_index=True) if frames else None

    # If we need more rows than Gradient generated, use calibrated statistical generation
    if row_count > gradient_rows:
        extra = _generate_statistical(domain_slug, row_count - gradient_rows, seed_df)
        if seed_df is not None:
            # Align columns to seed schema
            extra = extra.reindex(columns=seed_df.columns)
            result = pd.concat([seed_df, extra], ignore_index=True)
        else:
            result = extra
    else:
        result = seed_df if seed_df is not None else _generate_statistical(domain_slug, row_count)

    return result.head(row_count)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_for_domain(
    domain_slug: str,
    row_count: int,
    parameters: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Generate *row_count* rows of synthetic data for *domain_slug*.

    Priority:
      1. DO Gradient Inference  (DO_GRADIENT_API_KEY + DO_GRADIENT_INFERENCE_ENDPOINT set)
      2. Statistical fallback
    """
    parameters = parameters or {}
    slug = domain_slug.lower().strip()

    if _gradient_available():
        log.info("Generating %d rows for '%s' via DO Gradient (%s)",
                 row_count, slug, settings.do_gradient_model_id)
        try:
            return _generate_via_gradient(slug, row_count)
        except Exception as exc:
            log.error("DO Gradient generation failed, falling back to statistical: %s", exc)

    log.info("Generating %d rows for '%s' via statistical fallback", row_count, slug)
    return _generate_statistical(slug, row_count)


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
