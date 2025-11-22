# scripts/train_model.py

import csv
import os

import numpy as np

from src.ml.feature_extractor import FEATURE_NAMES
from src.ml.model_manager import TrafficAnomalyModel


DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "training_packets.csv")


def load_training_data(path: str = DATA_PATH) -> np.ndarray:
    """
    Expect a CSV with columns matching FEATURE_NAMES.
    This can be created by a capture-mode of NetSleuth that just logs 'normal' traffic.
    """
    X = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vec = [float(row[name]) for name in FEATURE_NAMES]
            X.append(vec)
    return np.array(X)


def main():
    X = load_training_data()
    print(f"[TRAIN] Loaded {X.shape[0]} samples with {X.shape[1]} features")

    model = TrafficAnomalyModel()
    model.fit(X)
    model.save()
    print("[TRAIN] Training complete.")


if __name__ == "__main__":
    main()
