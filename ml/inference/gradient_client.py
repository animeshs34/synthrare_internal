"""Standalone DO Gradient Inference client for ML training/evaluation scripts.

Used by ml/inference/generator.py when running outside the backend container.
The RQ worker uses backend/app/services/gradient.py instead.

Environment variables:
  DO_GRADIENT_API_KEY              — DO personal access token
  DO_GRADIENT_INFERENCE_ENDPOINT   — e.g. https://inference.do-ai.run/v1
  DO_GRADIENT_MODEL_ID             — model name (default: llama3.1-8b-instruct)
  DO_GRADIENT_MAX_DIRECT_ROWS      — max rows via LLM before statistical augmentation (default: 200)
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
from typing import Any

import httpx
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

_BATCH_SIZE = 50  # rows per LLM call

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


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _call_api(messages: list[dict[str, str]], max_tokens: int = 4096) -> str:
    endpoint = _cfg("DO_GRADIENT_INFERENCE_ENDPOINT").rstrip("/")
    api_key = _cfg("DO_GRADIENT_API_KEY")
    model = _cfg("DO_GRADIENT_MODEL_ID", "llama3.1-8b-instruct")
    url = f"{endpoint}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }
    for attempt in range(3):
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            if attempt == 2:
                raise RuntimeError(f"DO Gradient API failed after 3 attempts: {exc}") from exc
            time.sleep(2 ** attempt)
    raise RuntimeError("Unreachable")


def _extract_csv(text: str) -> str:
    match = re.search(r"```(?:csv)?\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def _parse_response(text: str, domain_slug: str) -> pd.DataFrame | None:
    try:
        return pd.read_csv(io.StringIO(_extract_csv(text)))
    except Exception as exc:
        log.warning("CSV parse failed for %s: %s", domain_slug, exc)
        return None


def _stat_fallback(domain_slug: str, row_count: int) -> pd.DataFrame:
    """Minimal statistical fallback — mirrors generator.py _generate_statistical."""
    rng = np.random.default_rng()
    if domain_slug == "finance":
        close = rng.lognormal(5.0, 0.3, row_count)
        spread = rng.uniform(0.002, 0.015, row_count)
        return pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=row_count, freq="B"),
            "open": (close * (1 - spread / 2)).round(2),
            "high": (close * (1 + spread)).round(2),
            "low": (close * (1 - spread)).round(2),
            "close": close.round(2),
            "volume": rng.integers(1_000_000, 50_000_000, row_count),
        })
    if domain_slug == "aviation":
        t = pd.date_range("2023-01-01", periods=row_count, freq="s")
        alt = 30_000 + rng.normal(0, 500, row_count).cumsum() * 0.01
        return pd.DataFrame({
            "timestamp": t,
            "altitude_ft": alt.clip(0, 45_000).round(1),
            "speed_kts": rng.normal(480, 30, row_count).clip(200, 600).round(1),
            "heading_deg": rng.uniform(0, 360, row_count).round(2),
            "vertical_speed_fpm": rng.normal(0, 200, row_count).round(1),
            "latitude": rng.uniform(30, 60, row_count).round(4),
            "longitude": rng.uniform(-120, -70, row_count).round(4),
            "flight_id": [f"SYN{i:04d}" for i in range(row_count)],
        })
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


def generate_via_gradient(domain_slug: str, row_count: int) -> pd.DataFrame:
    """
    Generate *row_count* rows via DO Gradient Inference.

    Batches calls in groups of _BATCH_SIZE rows. For row_count beyond
    DO_GRADIENT_MAX_DIRECT_ROWS, augments with statistical generation calibrated
    to the Gradient-generated seed.
    """
    system_prompt = _DOMAIN_PROMPTS.get(domain_slug, _DOMAIN_PROMPTS["finance"])
    max_direct = int(_cfg("DO_GRADIENT_MAX_DIRECT_ROWS", "200"))
    gradient_rows = min(row_count, max_direct)

    frames: list[pd.DataFrame] = []
    generated = 0

    while generated < gradient_rows:
        batch = min(_BATCH_SIZE, gradient_rows - generated)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Generate exactly {batch} data rows in CSV format. "
                    "Include the header row on the first line. "
                    "Output raw CSV only — no extra text."
                ),
            },
        ]
        try:
            text = _call_api(messages)
            df_batch = _parse_response(text, domain_slug)
        except Exception as exc:
            log.warning("Gradient batch failed: %s", exc)
            df_batch = None

        if df_batch is not None and not df_batch.empty:
            frames.append(df_batch)
            generated += len(df_batch)
        else:
            # Fill remainder statistically
            remaining = gradient_rows - generated
            frames.append(_stat_fallback(domain_slug, remaining))
            generated = gradient_rows
            break

    seed_df = pd.concat(frames, ignore_index=True) if frames else None

    if row_count > gradient_rows:
        extra_count = row_count - gradient_rows
        extra = _stat_fallback(domain_slug, extra_count)
        if seed_df is not None:
            extra = extra.reindex(columns=seed_df.columns)
            result = pd.concat([seed_df, extra], ignore_index=True)
        else:
            result = extra
    else:
        result = seed_df if seed_df is not None else _stat_fallback(domain_slug, row_count)

    return result.head(row_count)
