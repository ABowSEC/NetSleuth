import sys, os #ref for training models

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(ROOT)

import csv
import time
from datetime import datetime
from scapy.all import sniff, IP, TCP, UDP
from src.ml.feature_extractor import extract_features, FEATURE_NAMES



OUTPUT_PATH = "data/training_packets.csv"
CAPTURE_DURATION = 300  # seconds of normal traffic

def packet_handler(pkt, writer):
    feat = extract_features(pkt)
    if feat is None:
        return
    writer.writerow(feat)

def capture_training():
    print(f"[TRAIN] Capturing {CAPTURE_DURATION} seconds of normal traffic...")
    print(f"[TRAIN] Writing feature data to {OUTPUT_PATH}")

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FEATURE_NAMES)
        writer.writeheader()

        start = time.time()
        sniff(prn=lambda pkt: packet_handler(pkt, writer),
              store=False,
              stop_filter=lambda _: time.time() - start > CAPTURE_DURATION)

    print("[TRAIN] Capture complete!")

if __name__ == "__main__":
    capture_training()
