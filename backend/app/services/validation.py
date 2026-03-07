"""Fidelity scoring service.

Computes statistical similarity between a real reference DataFrame and a
synthetic DataFrame.  All metrics are normalised to [0, 1] where 1 = perfect.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class FidelityReport:
    overall_score: float
    ks_statistic: float       # raw average KS (lower = better)
    correlation_delta: float  # raw average |Δcorr| (lower = better)
    coverage_score: float     # fraction of real space covered (higher = better)
    column_scores: list[dict[str, object]] = field(default_factory=list)
    # column_scores format: [{"column": str, "score": float, "ks": float}]


def compute_fidelity(real: pd.DataFrame, synthetic: pd.DataFrame) -> FidelityReport:
    """Compare real vs synthetic DataFrames and return a FidelityReport."""
    num_cols = [c for c in real.columns if pd.api.types.is_numeric_dtype(real[c])]

    if not num_cols:
        return FidelityReport(
            overall_score=0.0,
            ks_statistic=1.0,
            correlation_delta=1.0,
            coverage_score=0.0,
        )

    # --- KS statistic per column ---
    col_ks: list[float] = []
    col_scores: list[dict[str, object]] = []
    for col in num_cols:
        r = real[col].dropna().values
        s = synthetic[col].dropna().values
        if len(r) == 0 or len(s) == 0:
            col_ks.append(1.0)
            col_scores.append({"column": col, "score": 0.0, "ks": 1.0})
            continue
        ks_stat, _ = stats.ks_2samp(r, s)
        col_score = float(1.0 - ks_stat)
        col_ks.append(ks_stat)
        col_scores.append({"column": col, "score": round(col_score, 4), "ks": round(float(ks_stat), 4)})

    avg_ks = float(np.mean(col_ks)) if col_ks else 1.0

    # --- Correlation delta ---
    if len(num_cols) >= 2:
        real_corr = real[num_cols].corr().values
        synth_corr = synthetic[num_cols].corr().values
        mask = ~(np.isnan(real_corr) | np.isnan(synth_corr))
        if mask.any():
            corr_delta = float(np.abs(real_corr[mask] - synth_corr[mask]).mean())
        else:
            corr_delta = 1.0
    else:
        corr_delta = 0.0

    # --- Coverage score (percentile-based range coverage) ---
    coverage_vals: list[float] = []
    for col in num_cols:
        r = real[col].dropna()
        s = synthetic[col].dropna()
        if len(r) == 0 or len(s) == 0:
            coverage_vals.append(0.0)
            continue
        real_min, real_max = r.quantile(0.05), r.quantile(0.95)
        if real_max == real_min:
            coverage_vals.append(1.0)
            continue
        in_range = ((s >= real_min) & (s <= real_max)).mean()
        coverage_vals.append(float(in_range))

    avg_coverage = float(np.mean(coverage_vals)) if coverage_vals else 0.0

    # --- Overall composite score ---
    ks_score = 1.0 - avg_ks
    corr_score = max(0.0, 1.0 - corr_delta)
    overall = float(np.mean([ks_score, corr_score, avg_coverage]))

    return FidelityReport(
        overall_score=round(overall, 4),
        ks_statistic=round(avg_ks, 4),
        correlation_delta=round(corr_delta, 4),
        coverage_score=round(avg_coverage, 4),
        column_scores=col_scores,
    )


def fidelity_report_to_json(report: FidelityReport) -> str:
    return json.dumps(report.column_scores)
