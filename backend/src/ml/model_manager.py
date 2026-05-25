# src/ml/model_manager.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, List

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest


try:
    from config import ML_ANOMALY_THRESHOLD
except ImportError:
    ML_ANOMALY_THRESHOLD = -0.2

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
    def load(cls, path: str = MODEL_PATH, threshold: float = ML_ANOMALY_THRESHOLD) -> "TrafficAnomalyModel":
        if not os.path.exists(path):
            print(f"[ML] No model found at {path}, running without ML.")
            return cls(model=None, threshold=threshold)
        payload = joblib.load(path)
        # Support both old format (bare model) and new format (dict with threshold)
        if isinstance(payload, dict):
            model = payload["model"]
            threshold = payload.get("threshold", threshold)
        else:
            model = payload
        print(f"[ML] Loaded anomaly model from {path} (threshold={threshold:.4f})")
        return cls(model=model, threshold=threshold)

    def save(self, path: str = MODEL_PATH) -> None:
        if self.model is None:
            raise RuntimeError("No model to save")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({"model": self.model, "threshold": self.threshold}, path)
        print(f"[ML] Saved model to {path} (threshold={self.threshold:.4f})")

    def fit(self, X: np.ndarray, contamination: float = 0.05) -> None:
        """
        Train an unsupervised IsolationForest on 'normal' traffic.
        X: shape (n_samples, n_features)
        contamination: assumed fraction of anomalies in training data (used to calibrate threshold)
        """
        self.model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
        )
        self.model.fit(X)
        # Calibrate threshold from training scores so exactly `contamination` fraction
        # of training samples fall below it — avoids hardcoded magic constants
        scores = self.model.score_samples(X)
        self.threshold = float(np.percentile(scores, contamination * 100))
        print(f"[ML] Threshold calibrated to {self.threshold:.4f} ({contamination*100:.0f}th percentile of training scores)")

    def predict_one(self, x: List[float]) -> Optional[AnomalyResult]:
        if self.model is None:
            return None
        X = np.array(x, dtype=float).reshape(1, -1)
        scores = self.model.score_samples(X)  # shape (1,)
        score = float(scores[0])
        is_anom = score < self.threshold
        return AnomalyResult(score=score, is_anomaly=is_anom)
