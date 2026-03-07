"""Domain-aware synthetic data generator.

Dispatches to the appropriate model (CTGAN for finance/healthcare, TimeGAN for aviation).
In production, models are loaded from HuggingFace Hub or DO Gradient Serverless Inference.
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

    Falls back to lightweight statistical simulation when model files are
    not present (CI / local dev without training artifacts).
    """
    parameters = parameters or {}

    model_env_map = {
        DomainSlug.FINANCE: "HF_MODEL_REPO_FINANCE",
        DomainSlug.AVIATION: "HF_MODEL_REPO_AVIATION",
        DomainSlug.HEALTHCARE: "HF_MODEL_REPO_HEALTHCARE",
    }

    try:
        slug = DomainSlug(domain_slug)
    except ValueError:
        slug = DomainSlug.FINANCE

    model_path = _resolve_model_path(slug)
    if model_path and Path(model_path).exists():
        if slug == DomainSlug.AVIATION:
            return _generate_timegan(model_path, row_count, parameters)
        else:
            return _generate_ctgan(model_path, row_count, parameters)

    # Fallback: statistical simulation
    return _generate_statistical(slug, row_count)


def _resolve_model_path(slug: DomainSlug) -> str | None:
    """Return local model.pkl path if it exists."""
    base = Path(os.environ.get("MODEL_DIR", "models"))
    candidate = base / slug.value / "model.pkl"
    if candidate.exists():
        return str(candidate)
    return None


def _generate_ctgan(model_path: str, row_count: int, params: dict) -> pd.DataFrame:
    synthesizer = _load_ctgan(model_path)
    return synthesizer.sample(num_rows=row_count)


def _generate_timegan(model_path: str, row_count: int, params: dict) -> pd.DataFrame:
    # TimeGAN models are stored as pkl via SDV TabularPreset or custom wrapper
    import pickle
    if model_path not in _MODEL_CACHE:
        with open(model_path, "rb") as f:
            _MODEL_CACHE[model_path] = pickle.load(f)
    model = _MODEL_CACHE[model_path]
    return model.sample(num_rows=row_count)


def _generate_statistical(slug: DomainSlug, row_count: int) -> pd.DataFrame:
    """Lightweight statistical fallback — no trained model required."""
    import numpy as np
    rng = np.random.default_rng()

    if slug == DomainSlug.FINANCE:
        return pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=row_count, freq="B"),
            "open": rng.lognormal(5.0, 0.3, row_count),
            "high": rng.lognormal(5.05, 0.3, row_count),
            "low": rng.lognormal(4.95, 0.3, row_count),
            "close": rng.lognormal(5.0, 0.3, row_count),
            "volume": rng.integers(1_000_000, 50_000_000, row_count),
        })

    if slug == DomainSlug.AVIATION:
        t = pd.date_range("2023-01-01", periods=row_count, freq="s")
        altitude = 30_000 + rng.normal(0, 500, row_count).cumsum() * 0.01
        return pd.DataFrame({
            "timestamp": t,
            "altitude_ft": altitude.clip(0, 45_000),
            "speed_kts": rng.normal(480, 30, row_count).clip(200, 600),
            "heading_deg": rng.uniform(0, 360, row_count),
            "vertical_speed_fpm": rng.normal(0, 200, row_count),
            "latitude": rng.uniform(30, 60, row_count),
            "longitude": rng.uniform(-120, -70, row_count),
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
        "bmi": rng.normal(26, 5, row_count).clip(16, 50),
        "glucose_mg_dl": rng.lognormal(4.8, 0.2, row_count).clip(60, 400),
        "cholesterol_mg_dl": rng.normal(195, 35, row_count).clip(100, 400),
        "diagnosis_code": rng.choice(
            ["E11", "I10", "J45", "M54", "F32", "Z00"], row_count
        ),
        "los_days": rng.integers(1, 15, row_count),
    })


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
