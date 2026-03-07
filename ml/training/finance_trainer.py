"""Finance CTGAN trainer.

Usage (local or GPU Droplet):
    python finance_trainer.py --data seed_data/finance_seed.csv --epochs 300 --output models/finance/model.pkl

Uploads trained model.pkl to HuggingFace Hub when HF_TOKEN env var is set.
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

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows from {data_path}")

    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(df)

    synthesizer = CTGANSynthesizer(metadata, epochs=epochs, verbose=True)
    synthesizer.fit(df)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    synthesizer.save(output_path)
    print(f"Model saved to {output_path}")

    # Validate quickly
    sample = synthesizer.sample(num_rows=500)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    from app.services.validation import compute_fidelity
    report = compute_fidelity(df.select_dtypes("number"), sample.select_dtypes("number"))
    print(f"Fidelity score: {report.overall_score:.4f}")

    _maybe_upload_to_hf(output_path, repo_id=os.environ.get("HF_MODEL_REPO_FINANCE", "synthrare/finance-ctgan"))


def _maybe_upload_to_hf(model_path: str, repo_id: str) -> None:
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("HF_TOKEN not set — skipping HuggingFace upload")
        return
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_file(
        path_or_fileobj=model_path,
        path_in_repo="model.pkl",
        repo_id=repo_id,
        token=hf_token,
    )
    print(f"Uploaded model to HuggingFace: {repo_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--output", default="models/finance/model.pkl")
    args = parser.parse_args()
    train(args.data, args.epochs, args.output)
