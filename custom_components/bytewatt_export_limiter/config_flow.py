"""Config flow for Bytewatt Export Limiter integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
# Removed unused imports CONF_HOST, CONF_PORT (Medium fix #13)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_MODBUS_SLAVE,
    CONF_PRICE_ENTITY,
    CONF_PRICE_THRESHOLD,
    CONF_CURTAILED_LIMIT,
    CONF_POLL_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_CURTAILED_LIMIT,
    DEFAULT_POLL_INTERVAL,
    REG_EXPORT_LIMIT,
)

_LOGGER = logging.getLogger(__name__)


async def validate_modbus_connection(
    hass: HomeAssistant, host: str, port: int, slave: int
) -> dict[str, Any]:
    """Validate the Modbus connection by reading a test register.

    Args:
        hass: Home Assistant instance
        host: Modbus TCP host
        port: Modbus TCP port
        slave: Modbus slave address

    Returns:
        Dict with title for the integration

    Raises:
        CannotConnect: If connection fails
        InvalidAuth: If slave address is invalid
    """
    from pymodbus.client import AsyncModbusTcpClient

    client = AsyncModbusTcpClient(host, port=port)

    try:
        # Attempt to connect with timeout
        try:
            connected = await asyncio.wait_for(client.connect(), timeout=10.0)
        except asyncio.TimeoutError:
            raise CannotConnect("Connection timed out")

        if not connected:
            raise CannotConnect("Failed to connect to Modbus device")

        # Try to read the export limit register as a validation test with timeout
        try:
            result = await asyncio.wait_for(
                client.read_holding_registers(
                    address=REG_EXPORT_LIMIT,
                    count=2,  # 32-bit register
                    slave=slave,
                ),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            raise CannotConnect("Register read timed out")

        if result.isError():
            _LOGGER.error("Failed to read register 0x%04X: %s", REG_EXPORT_LIMIT, result)
            raise InvalidAuth(f"Slave address {slave} not responding or invalid")

        _LOGGER.info(
            "Successfully validated Modbus connection to %s:%s (slave %s)",
            host,
            port,
            slave,
        )

        # Return title info
        return {"title": f"Bytewatt ({host})"}

    # High fix #5: Proper exception handling order - specific handlers first
    except CannotConnect:
        raise
    except InvalidAuth:
        raise
    except Exception as err:
        _LOGGER.exception("Unexpected exception validating Modbus connection")
        raise CannotConnect(f"Connection error: {err}") from err

    finally:
        client.close()


class BytewattConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bytewatt Export Limiter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._modbus_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - Modbus connection settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Medium fix #11: Check unique_id BEFORE validation to avoid
            # unnecessary network calls for already-configured devices
            await self.async_set_unique_id(
                f"{user_input[CONF_MODBUS_HOST]}_{user_input[CONF_MODBUS_SLAVE]}"
            )
            self._abort_if_unique_id_configured()

            try:
                # Validate Modbus connection
                info = await validate_modbus_connection(
                    self.hass,
                    user_input[CONF_MODBUS_HOST],
                    user_input[CONF_MODBUS_PORT],
                    user_input[CONF_MODBUS_SLAVE],
                )

                # Store Modbus config for next step
                self._modbus_config = user_input

                # Move to automation settings step
                return await self.async_step_automation()

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_slave"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show form for Modbus settings
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MODBUS_HOST, default=DEFAULT_HOST
                ): cv.string,
                vol.Required(
                    CONF_MODBUS_PORT, default=DEFAULT_PORT
                ): cv.port,
                vol.Required(
                    CONF_MODBUS_SLAVE, default=DEFAULT_SLAVE
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=247)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "default_host": DEFAULT_HOST,
                "default_port": str(DEFAULT_PORT),
                "default_slave": str(DEFAULT_SLAVE),
            },
        )

    async def async_step_automation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the automation settings step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # High fix #3: Validate price entity exists and is numeric
            price_entity = user_input.get(CONF_PRICE_ENTITY)
            if price_entity:
                state = self.hass.states.get(price_entity)
                if not state:
                    errors["base"] = "invalid_price_entity"
                else:
                    # Check if state is numeric
                    try:
                        float(state.state)
                    except (ValueError, TypeError):
                        if state.state not in ("unavailable", "unknown"):
                            errors["base"] = "invalid_price_entity"

            if not errors:
                # Combine Modbus config with automation config
                full_config = {**self._modbus_config, **user_input}

                # Create the config entry
                return self.async_create_entry(
                    title=f"Bytewatt ({self._modbus_config[CONF_MODBUS_HOST]})",
                    data=full_config,
                )

        # Show form for automation settings
        data_schema = vol.Schema(
            {
                vol.Required(CONF_PRICE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_PRICE_THRESHOLD, default=DEFAULT_PRICE_THRESHOLD
                ): vol.All(vol.Coerce(float), vol.Range(min=-100.0, max=100.0)),
                vol.Required(
                    CONF_CURTAILED_LIMIT, default=DEFAULT_CURTAILED_LIMIT
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
                vol.Optional(
                    CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            }
        )

        return self.async_show_form(
            step_id="automation",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "default_threshold": str(DEFAULT_PRICE_THRESHOLD),
                "default_limit": str(DEFAULT_CURTAILED_LIMIT),
                "default_poll": str(DEFAULT_POLL_INTERVAL),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BytewattOptionsFlow:
        """Get the options flow for this handler."""
        return BytewattOptionsFlow(config_entry)


class BytewattOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Bytewatt Export Limiter."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        # Get current config values (prefer options, fallback to data)
        current_price_entity = self.config_entry.options.get(
            CONF_PRICE_ENTITY, self.config_entry.data.get(CONF_PRICE_ENTITY)
        )

        # Medium fix #7: Early validation - check if current price entity still exists
        if user_input is None and current_price_entity:
            if not self.hass.states.get(current_price_entity):
                _LOGGER.warning(
                    "Configured price entity %s no longer exists",
                    current_price_entity,
                )
                # Show warning but don't block - let user select new entity

        if user_input is not None:
            # Validate that price entity still exists
            price_entity = user_input.get(CONF_PRICE_ENTITY)
            if price_entity and not self.hass.states.get(price_entity):
                errors["base"] = "invalid_price_entity"
            else:
                return self.async_create_entry(title="", data=user_input)

        current_price_threshold = self.config_entry.options.get(
            CONF_PRICE_THRESHOLD,
            self.config_entry.data.get(CONF_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD),
        )
        current_curtailed_limit = self.config_entry.options.get(
            CONF_CURTAILED_LIMIT,
            self.config_entry.data.get(CONF_CURTAILED_LIMIT, DEFAULT_CURTAILED_LIMIT),
        )
        current_poll_interval = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )

        # Build options schema
        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_PRICE_ENTITY, default=current_price_entity
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_PRICE_THRESHOLD, default=current_price_threshold
                ): vol.All(vol.Coerce(float), vol.Range(min=-100.0, max=100.0)),
                vol.Required(
                    CONF_CURTAILED_LIMIT, default=current_curtailed_limit
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=50000)),
                vol.Optional(
                    CONF_POLL_INTERVAL, default=current_poll_interval
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid slave address."""
