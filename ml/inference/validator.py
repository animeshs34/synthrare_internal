"""ML-layer validator — wraps the backend fidelity service for use in training pipelines."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Allow importing from backend when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.validation import FidelityReport, compute_fidelity  # noqa: E402


def validate_synthetic(
    real: pd.DataFrame,
    synthetic: pd.DataFrame,
    threshold: float = 0.70,
) -> tuple[FidelityReport, bool]:
    """Return (FidelityReport, passed) where passed = overall_score >= threshold."""
    report = compute_fidelity(real, synthetic)
    passed = report.overall_score >= threshold
    return report, passed


def print_report(report: FidelityReport) -> None:
    print(f"Overall score    : {report.overall_score:.4f}")
    print(f"KS statistic     : {report.ks_statistic:.4f}  (lower = better)")
    print(f"Correlation delta: {report.correlation_delta:.4f}  (lower = better)")
    print(f"Coverage score   : {report.coverage_score:.4f}")
    print("\nPer-column scores:")
    for cs in report.column_scores:
        print(f"  {cs['column']:30s}  score={cs['score']:.4f}  ks={cs['ks']:.4f}")
