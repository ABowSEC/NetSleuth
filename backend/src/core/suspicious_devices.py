from collections import defaultdict
from datetime import datetime, timedelta

class SuspiciousDeviceTracker:
    SEVERITY_RANK = {
        "NORMAL": 0,
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4
    }

    def __init__(self):
        self.devices = defaultdict(lambda: {
            "ip": None,
            "score": None,
            "level": "NORMAL",
            "total_anomalies": 0,
            "recent_anomalies": [],
            "last_seen": None
        })

    def _severity(self, score):
        if score is None:
            return "NORMAL"
        if score > -0.15:
            return "LOW"
        elif score > -0.35:
            return "MEDIUM"
        elif score > -0.60:
            return "HIGH"
        else:
            return "CRITICAL"

    def register_anomaly(self, ip, score):
        now = datetime.now()
        entry = self.devices[ip]

        entry["ip"] = ip
        entry["score"] = score
        entry["total_anomalies"] += 1
        entry["last_seen"] = now.strftime("%Y-%m-%d %H:%M:%S")
        entry["level"] = self._severity(score)
        entry["recent_anomalies"].append((now, score))

        # Remove anomalies older than 10 minutes
        cutoff = now - timedelta(minutes=10)
        entry["recent_anomalies"] = [
            (t, s) for (t, s) in entry["recent_anomalies"] if t > cutoff
        ]

    def get_top_suspicious(self, limit=5):
        # Filter out devices with no anomalies
        devices_with_activity = [
            d for d in self.devices.values() if d["total_anomalies"] > 0
        ]

        # Sort by numeric severity rank *then* by anomaly count
        ranked = sorted(
            devices_with_activity,
            key=lambda d: (self.SEVERITY_RANK[d["level"]], d["total_anomalies"]),
            reverse=True
        )

        return ranked[:limit]


suspicious_tracker = SuspiciousDeviceTracker()
