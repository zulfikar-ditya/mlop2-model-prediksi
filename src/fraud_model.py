from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = ROOT / "models" / "kasus_a_fraud_lgbm.joblib"
MODEL_NAME = "fraud-lgbm"


class FraudModel:
    def __init__(self, path: Path = DEFAULT_MODEL_PATH) -> None:
        self.name = MODEL_NAME
        self.version = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        bundle = joblib.load(path)
        self.model = bundle["model"]
        self.features: list[str] = bundle["features"]
        self.categories: dict[str, list[str]] = bundle["categories"]
        self.default_threshold: float = bundle["threshold_fpr5"]

    def prepare(self, records: list[dict[str, Any]]) -> pd.DataFrame:
        X = pd.DataFrame(records)[self.features]
        for col, cats in self.categories.items():
            X[col] = pd.Categorical(X[col], categories=cats)
        return X

    def predict(self, records: list[dict[str, Any]], threshold: float | None = None) -> list[dict[str, Any]]:
        thr = self.default_threshold if threshold is None else threshold
        scores = self.model.predict_proba(self.prepare(records))[:, 1]
        return [
            {
                "model_name": self.name,
                "model_version": self.version,
                "fraud_score": float(s),
                "is_fraud": bool(s >= thr),
                "threshold": thr,
            }
            for s in scores
        ]
