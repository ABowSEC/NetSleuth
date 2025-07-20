# NetSleuth Configuration
# Set these to True to enable debugging and verbose output

# Enable verbose packet logging (shows every packet)
VERBOSE = False

# Enable debug mode (shows additional diagnostic information)
DEBUG_MODE = False

# Web interface settings
WEB_HOST = '0.0.0.0'
WEB_PORT = 5000

# Summary interval (seconds)
SUMMARY_INTERVAL = 30

# Web interface update interval (seconds)
WEB_UPDATE_INTERVAL = 5

# Performance settings
MAX_DEVICES = 1000
MAX_CONNECTIONS_PER_DEVICE = 100
MAX_DNS_QUERIES_PER_DEVICE = 50

# Logging settings
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE = False
LOG_FILE = 'netsleuth.log' 