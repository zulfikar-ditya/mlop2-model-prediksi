"""Verify the exported .joblib by running inference on sample applications.

Input : all 29 model features, from a JSON file (one object or a list) or sampled from data/Base.csv month 3.
Output: fraud_score + is_fraud per row; --threshold and --fields adjust what is returned.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.fraud_model import ROOT, FraudModel  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="JSON file with one record or a list of records")
    parser.add_argument("--rows", type=int, default=5, help="rows to sample from Base.csv when --input is omitted")
    parser.add_argument("--threshold", type=float, help="decision threshold (default: threshold_fpr5 from the model)")
    parser.add_argument("--fields", default="model_name,model_version,fraud_score,is_fraud,threshold", help="comma-separated output fields")
    args = parser.parse_args()

    model = FraudModel()

    labels: list[int] | None = None
    if args.input:
        data = json.loads(args.input.read_text())
        records = data if isinstance(data, list) else [data]
    else:
        df = pd.read_csv(ROOT / "data" / "Base.csv")
        valid = df[df["month"] == 3]
        sample = pd.concat([valid[valid["fraud_bool"] == 1].head(args.rows // 2 + 1), valid[valid["fraud_bool"] == 0].head(args.rows)])
        sample = sample.head(args.rows)
        labels = sample["fraud_bool"].tolist()
        records = sample[model.features].to_dict("records")

    fields = [f.strip() for f in args.fields.split(",")]
    results = model.predict(records, args.threshold)
    for i, res in enumerate(results):
        out = {k: res[k] for k in fields if k in res}
        if labels is not None:
            out["actual"] = labels[i]
        print(json.dumps(out))


if __name__ == "__main__":
    main()
