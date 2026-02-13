"""Constants for the Midea M-Control integration."""

VERSION = "2.2.1"
DOMAIN = "midea_mcontrol"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_HOST = "host"

BASE_URL = "https://www.aircontrolbase.com"
LOGIN_PATH = "/web/user/login"
DETAILS_PATH = "/web/userGroup/getDetails"
CONTROL_PATH = "/web/device/control"

SESSION_EXPIRED_CODE = 40018

DEFAULT_CLOUD_SCAN_INTERVAL = 60  # seconds (cloud fallback)
DEFAULT_LOCAL_SCAN_INTERVAL = 5   # seconds (local fast polling)

LOCAL_STATUS_ENDPOINT = "/get_mbdata_all.jsn"

MIN_TEMP = 14
MAX_TEMP = 30

# Cloud API mode values
MODE_COOL = "cool"
MODE_HEAT = "heat"
MODE_AUTO = "auto"
MODE_FAN = "fan"
MODE_DRY = "dry"

# Cloud API wind values
WIND_AUTO = "auto"
WIND_LOW = "low"
WIND_MID = "mid"
WIND_HIGH = "high"

# Cloud API power values
POWER_ON = "y"
POWER_OFF = "n"

# Local API mode integer values (from CCM15/CCM21-i hex protocol)
LOCAL_MODE_COOL = 0
LOCAL_MODE_HEAT = 1
LOCAL_MODE_DRY = 2
LOCAL_MODE_FAN = 3
LOCAL_MODE_OFF = 4
LOCAL_MODE_AUTO = 5

# Local API fan integer values
LOCAL_FAN_AUTO = 0
LOCAL_FAN_LOW = 2
LOCAL_FAN_MEDIUM = 3
LOCAL_FAN_HIGH = 4
LOCAL_FAN_OFF = 5
