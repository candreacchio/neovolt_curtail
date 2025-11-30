"""Constants for the Bytewatt Export Limiter integration."""

DOMAIN = "bytewatt_export_limiter"

# Device info
DEVICE_MANUFACTURER = "Bytewatt"
DEVICE_MODEL = "Export Limiter"
SOFTWARE_VERSION = "1.0"

# Modbus defaults
DEFAULT_HOST = "192.168.20.29"
DEFAULT_PORT = 502
DEFAULT_SLAVE = 85  # 0x55

# Register addresses
REG_EXPORT_LIMIT = 0x08A2      # Active export limit (W) - R/W
REG_DEFAULT_LIMIT = 0x08A5     # Default/grid max limit (W) - R/W
REG_DER_CONTROL = 0x08A0       # DER dispatch control

# Config keys
CONF_MODBUS_HOST = "modbus_host"
CONF_MODBUS_PORT = "modbus_port"
CONF_MODBUS_SLAVE = "modbus_slave"
CONF_PRICE_ENTITY = "price_entity"
CONF_PRICE_THRESHOLD = "price_threshold"
CONF_CURTAILED_LIMIT = "curtailed_limit"
CONF_POLL_INTERVAL = "poll_interval"

# Defaults
DEFAULT_PRICE_THRESHOLD = 0.0    # cents
DEFAULT_CURTAILED_LIMIT = 0      # watts
DEFAULT_POLL_INTERVAL = 60       # seconds

# Debounce
PRICE_DEBOUNCE_SECONDS = 5

# Platforms (Low fix #20: Added type hint)
PLATFORMS: list[str] = ["sensor", "binary_sensor", "number", "switch"]
