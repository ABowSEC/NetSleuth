"""Tuning values for the ML anomaly module. Core modules keep their own constants."""

ML_ANOMALY_THRESHOLD = -0.2       # IsolationForest score below this = anomaly
ML_LAST_SEEN_MAX = 2000           # max IPs tracked for inter-arrival timing
