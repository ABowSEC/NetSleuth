# NetSleuth Configuration

# Debugging
VERBOSE = False
DEBUG_MODE = False

# Web interface
WEB_HOST = '0.0.0.0'
WEB_PORT = 5000
WEB_UPDATE_INTERVAL = 5       # seconds between dashboard data refresh
ALERTS_PANEL_LIMIT = 50       # alerts returned to dashboard

# Console summary
SUMMARY_INTERVAL = 30         # seconds between printed summaries

# Per-device memory limits
MAX_DEVICES = 1000
MAX_CONNECTIONS_PER_DEVICE = 100
MAX_DNS_QUERIES_PER_DEVICE = 50

# Device staleness — purge devices not seen for this many hours
DEVICE_STALE_HOURS = 24

# Alert thresholds
ALERT_HIGH_CONNECTION_THRESHOLD = 50
ALERT_PORT_SCAN_THRESHOLD = 20

# ML model settings
ML_ANOMALY_THRESHOLD = -0.2       # IsolationForest score below this = anomaly
ML_ANOMALY_STORE_MAXLEN = 500     # rolling deque size for anomaly events
ML_LAST_SEEN_MAX = 2000           # max IPs tracked for inter-arrival timing

# Suspicious device score boundaries (IsolationForest: more negative = worse)
SUSPICIOUS_SCORE_LOW = -0.15
SUSPICIOUS_SCORE_MEDIUM = -0.35
SUSPICIOUS_SCORE_HIGH = -0.60

# Logging
LOG_LEVEL = 'INFO'
LOG_TO_FILE = False
LOG_FILE = 'netsleuth.log'