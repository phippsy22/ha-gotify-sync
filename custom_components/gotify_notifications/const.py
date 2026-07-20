"""Constants for the Gotify Notifications integration."""

DOMAIN = "gotify_notifications"

# Config keys
CONF_URL = "url"
CONF_TOKEN = "token"
CONF_VERIFY_SSL = "verify_ssl"

# Options keys
CONF_MAX_MESSAGES = "max_messages"
CONF_MAX_SENSOR_MESSAGES = "max_sensor_messages"
CONF_POLL_INTERVAL = "poll_interval"

# Defaults
DEFAULT_MAX_MESSAGES = 500
DEFAULT_MAX_SENSOR_MESSAGES = 50
DEFAULT_POLL_INTERVAL = 300  # seconds
DEFAULT_VERIFY_SSL = True

# Events
EVENT_NOTIFICATION_RECEIVED = f"{DOMAIN}_notification_received"

# WebSocket API
WS_TYPE_GET_MESSAGES = f"{DOMAIN}/get_messages"

# Priority color thresholds
PRIORITY_LOW = 3  # 0-3: green
PRIORITY_MEDIUM = 6  # 4-6: yellow
PRIORITY_HIGH = 8  # 7-8: orange
PRIORITY_CRITICAL = 10  # 9-10: red

# Platforms
PLATFORMS = ["sensor", "binary_sensor"]
