import sys,os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(ROOT)

import csv

import numpy as np

from src.ml.feature_extractor import FEATURE_NAMES
from src.ml.model_manager import TrafficAnomalyModel


DATA_PATH = os.path.abspath(os.path.join(ROOT, "data", "training_packets.csv"))


def load_training_data(path: str = DATA_PATH) -> np.ndarray:
    """
    Expect a CSV with columns matching FEATURE_NAMES.
    This can be created by a capture-mode of NetSleuth that just logs 'normal' traffic.
    """
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                vec = [float(row[name]) for name in FEATURE_NAMES]
                rows.append(vec)
            except Exception as e:
                # Skip problem rows if appear and notify
                print(f"[WARN] Skipping invalid row: {e}")
                continue
    return np.array(rows)


def main():
    print("[TRAIN] Loading training data from:",DATA_PATH)
    X = load_training_data()
    print(f"[TRAIN] {len(X)} samples loaded.")

    if len(X) < 20:
        print("[ERROR] Not enough samples to train. Capture more traffic.")
        return

    model = TrafficAnomalyModel()
    model.fit(X)
    model.save()
    print("[TRAIN] Training complete. Saved to models/isoforest.pkl")


if __name__ == "__main__":
    main()
