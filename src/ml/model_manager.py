# src/ml/model_manager.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, List

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest


MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "models", "isoforest.pkl")


@dataclass
class AnomalyResult:
    score: float     # anomaly score (lower = more anomalous in IsolationForest)
    is_anomaly: bool # True if considered anomalous


class TrafficAnomalyModel:
    def __init__(self, model=None, threshold: float = -0.2):
        """
        threshold: decision threshold on score_samples.
        IsolationForest score_samples -> higher = more normal, lower = more anomalous.
        """
        self.model: Optional[IsolationForest] = model
        self.threshold = threshold

    @classmethod
    def load(cls, path: str = MODEL_PATH, threshold: float = -0.2) -> "TrafficAnomalyModel":
        if not os.path.exists(path):
            print(f"[ML] No model found at {path}, running without ML.")
            return cls(model=None, threshold=threshold)
        model = joblib.load(path)
        print(f"[ML] Loaded anomaly model from {path}")
        return cls(model=model, threshold=threshold)

    def save(self, path: str = MODEL_PATH) -> None:
        if self.model is None:
            raise RuntimeError("No model to save")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.model, path)
        print(f"[ML] Saved model to {path}")

    def fit(self, X: np.ndarray) -> None:
        """
        Train an unsupervised IsolationForest on 'normal' traffic.
        X: shape (n_samples, n_features)
        """
        self.model = IsolationForest(
            n_estimators=200,
            contamination="auto",
            random_state=42,
        )
        self.model.fit(X)

    def predict_one(self, x: List[float]) -> Optional[AnomalyResult]:
        if self.model is None:
            return None
        X = np.array(x, dtype=float).reshape(1, -1)
        scores = self.model.score_samples(X)  # shape (1,)
        score = float(scores[0])
        is_anom = score < self.threshold
        return AnomalyResult(score=score, is_anomaly=is_anom)
