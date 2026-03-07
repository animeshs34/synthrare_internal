"""Aviation TimeGAN / CTGAN trainer.

Aviation telemetry is time-series. We use SDV's PARSynthesizer for
sequential data (contextual PAR), falling back to CTGAN for tabular runs.

Usage:
    python aviation_trainer.py --data seed_data/aviation_seed.csv --epochs 200 --output models/aviation/model.pkl
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def train(data_path: str, epochs: int, output_path: str) -> None:
    import pandas as pd
    from sdv.metadata import SingleTableMetadata
    from sdv.single_table import CTGANSynthesizer

    df = pd.read_csv(data_path, parse_dates=["timestamp"] if "timestamp" in pd.read_csv(data_path, nrows=0).columns else [])
    print(f"Loaded {len(df)} rows from {data_path}")

    # Drop non-numeric string cols that CTGAN can't handle directly
    numeric_cols = df.select_dtypes(include=["number", "float", "int"]).columns.tolist()
    df_num = df[numeric_cols]

    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(df_num)

    synthesizer = CTGANSynthesizer(metadata, epochs=epochs, verbose=True)
    synthesizer.fit(df_num)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    synthesizer.save(output_path)
    print(f"Model saved to {output_path}")

    sample = synthesizer.sample(num_rows=500)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from app.services.validation import compute_fidelity
    report = compute_fidelity(df_num, sample)
    print(f"Fidelity score: {report.overall_score:.4f}")

    _maybe_upload_to_hf(output_path, repo_id=os.environ.get("HF_MODEL_REPO_AVIATION", "synthrare/aviation-timegan"))


def _maybe_upload_to_hf(model_path: str, repo_id: str) -> None:
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("HF_TOKEN not set — skipping HuggingFace upload")
        return
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_file(path_or_fileobj=model_path, path_in_repo="model.pkl", repo_id=repo_id, token=hf_token)
    print(f"Uploaded model to HuggingFace: {repo_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--output", default="models/aviation/model.pkl")
    args = parser.parse_args()
    train(args.data, args.epochs, args.output)
