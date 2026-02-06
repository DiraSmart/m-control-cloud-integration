"""Constants for the Midea M-Control integration."""

DOMAIN = "midea_mcontrol"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

BASE_URL = "https://www.aircontrolbase.com"
LOGIN_PATH = "/web/user/login"
DETAILS_PATH = "/web/userGroup/getDetails"
CONTROL_PATH = "/web/device/control"

SESSION_EXPIRED_CODE = 40018

DEFAULT_SCAN_INTERVAL = 30  # seconds

MIN_TEMP = 16
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
