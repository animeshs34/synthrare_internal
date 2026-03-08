"""Domain-aware synthetic data generator (ML scripts layer).

Generation priority:
  1. DO Gradient Inference  — if DO_GRADIENT_API_KEY + DO_GRADIENT_INFERENCE_ENDPOINT are set
  2. Local trained model    — if models/<domain>/model.pkl exists (from GPU Droplet training)
  3. Statistical fallback   — always available, no external dependencies

The RQ worker uses backend/app/services/gradient.py directly.
This module is intended for training/evaluation scripts in ml/ that run outside the backend container.
"""
from __future__ import annotations

import io
import os
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd


class DomainSlug(str, Enum):
    FINANCE = "finance"
    AVIATION = "aviation"
    HEALTHCARE = "healthcare"


_MODEL_CACHE: dict[str, Any] = {}


def _load_ctgan(model_path: str) -> Any:
    from sdv.single_table import CTGANSynthesizer
    if model_path not in _MODEL_CACHE:
        _MODEL_CACHE[model_path] = CTGANSynthesizer.load(model_path)
    return _MODEL_CACHE[model_path]


def generate(
    domain_slug: str,
    row_count: int,
    parameters: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Generate *row_count* rows of synthetic data for the given domain.

    Priority:
      1. DO Gradient Inference (DO_GRADIENT_API_KEY + DO_GRADIENT_INFERENCE_ENDPOINT)
      2. Local trained model  (models/<domain>/model.pkl)
      3. Statistical fallback
    """
    parameters = parameters or {}

    try:
        slug = DomainSlug(domain_slug)
    except ValueError:
        slug = DomainSlug.FINANCE

    # ── Priority 1: DO Gradient Inference ────────────────────────────────────
    if _gradient_available():
        try:
            return _generate_via_gradient(slug, row_count)
        except Exception as exc:
            import warnings
            warnings.warn(f"DO Gradient inference failed ({exc}), trying local model", stacklevel=2)

    # ── Priority 2: Local trained model ──────────────────────────────────────
    model_path = _resolve_model_path(slug)
    if model_path and Path(model_path).exists():
        try:
            if slug == DomainSlug.AVIATION:
                return _generate_timegan(model_path, row_count, parameters)
            else:
                return _generate_ctgan(model_path, row_count, parameters)
        except Exception as exc:
            import warnings
            warnings.warn(f"Local model inference failed ({exc}), using statistical fallback", stacklevel=2)

    # ── Priority 3: Statistical fallback ─────────────────────────────────────
    return _generate_statistical(slug, row_count)


# ─────────────────────────────────────────────────────────────────────────────
# Priority 1: DO Gradient
# ─────────────────────────────────────────────────────────────────────────────

def _gradient_available() -> bool:
    return bool(
        os.environ.get("DO_GRADIENT_API_KEY")
        and os.environ.get("DO_GRADIENT_INFERENCE_ENDPOINT")
    )


def _generate_via_gradient(slug: DomainSlug, row_count: int) -> pd.DataFrame:
    """Delegate to the standalone gradient_client module."""
    from ml.inference.gradient_client import generate_via_gradient
    return generate_via_gradient(slug.value, row_count)


# ─────────────────────────────────────────────────────────────────────────────
# Priority 2: local trained models
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_model_path(slug: DomainSlug) -> str | None:
    base = Path(os.environ.get("MODEL_DIR", "models"))
    candidate = base / slug.value / "model.pkl"
    return str(candidate) if candidate.exists() else None


def _generate_ctgan(model_path: str, row_count: int, params: dict) -> pd.DataFrame:
    synthesizer = _load_ctgan(model_path)
    return synthesizer.sample(num_rows=row_count)


def _generate_timegan(model_path: str, row_count: int, params: dict) -> pd.DataFrame:
    import pickle
    if model_path not in _MODEL_CACHE:
        with open(model_path, "rb") as f:
            _MODEL_CACHE[model_path] = pickle.load(f)
    return _MODEL_CACHE[model_path].sample(num_rows=row_count)


# ─────────────────────────────────────────────────────────────────────────────
# Priority 3: statistical fallback
# ─────────────────────────────────────────────────────────────────────────────

def _generate_statistical(slug: DomainSlug, row_count: int) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng()

    if slug == DomainSlug.FINANCE:
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

    if slug == DomainSlug.AVIATION:
        t = pd.date_range("2023-01-01", periods=row_count, freq="s")
        altitude = 30_000 + rng.normal(0, 500, row_count).cumsum() * 0.01
        return pd.DataFrame({
            "timestamp": t,
            "altitude_ft": altitude.clip(0, 45_000).round(1),
            "speed_kts": rng.normal(480, 30, row_count).clip(200, 600).round(1),
            "heading_deg": rng.uniform(0, 360, row_count).round(2),
            "vertical_speed_fpm": rng.normal(0, 200, row_count).round(1),
            "latitude": rng.uniform(30, 60, row_count).round(4),
            "longitude": rng.uniform(-120, -70, row_count).round(4),
            "flight_id": [f"SYN{i:04d}" for i in range(row_count)],
        })

    # Healthcare
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
        "diagnosis_code": rng.choice(
            ["E11", "I10", "J45", "M54", "F32", "Z00"], row_count
        ),
        "los_days": rng.integers(1, 15, row_count),
    })


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
