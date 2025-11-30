"""
Bytewatt Export Limiter Integration for Home Assistant.

This integration automatically adjusts solar export limits on a Bytewatt battery system
based on electricity price thresholds using Modbus TCP communication.
"""

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_MODBUS_SLAVE,
)
from .coordinator import BytewattCoordinator
from .modbus_client import AsyncModbusClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bytewatt Export Limiter from a config entry."""
    _LOGGER.debug("Setting up Bytewatt Export Limiter integration")

    # Extract Modbus connection settings from config entry
    host = entry.data[CONF_MODBUS_HOST]
    port = entry.data[CONF_MODBUS_PORT]
    slave_address = entry.data[CONF_MODBUS_SLAVE]

    _LOGGER.info(
        "Initializing Modbus connection to %s:%s (slave: %s)",
        host,
        port,
        slave_address,
    )

    # Create Modbus client
    modbus_client = AsyncModbusClient(
        host=host,
        port=port,
        slave_address=slave_address,
    )

    # Test connection to ensure device is accessible
    try:
        if not await modbus_client.connect():
            _LOGGER.error(
                "Failed to connect to Modbus device at %s:%s",
                host,
                port,
            )
            raise ConfigEntryNotReady(
                f"Could not connect to Modbus device at {host}:{port}"
            )
    except Exception as err:
        _LOGGER.error(
            "Error connecting to Modbus device at %s:%s: %s",
            host,
            port,
            err,
        )
        raise ConfigEntryNotReady(
            f"Could not connect to Modbus device at {host}:{port}: {err}"
        ) from err

    # Create coordinator
    coordinator = BytewattCoordinator(
        hass=hass,
        modbus_client=modbus_client,
        entry=entry,
    )

    # Perform initial data refresh
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to perform initial data refresh: %s", err)
        await modbus_client.disconnect()
        raise ConfigEntryNotReady(
            f"Failed to fetch initial data from device: {err}"
        ) from err

    # Set up price monitoring and automation
    try:
        await coordinator.async_setup()
    except Exception as err:
        _LOGGER.error("Failed to set up coordinator automation: %s", err)
        await modbus_client.disconnect()
        raise ConfigEntryNotReady(
            f"Failed to set up price monitoring: {err}"
        ) from err

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to all platforms (Medium fix #11 - cleanup on failure)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as err:
        _LOGGER.error("Failed to set up platforms: %s", err)
        # Clean up on failure
        await coordinator.async_shutdown()
        await modbus_client.disconnect()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN, None)
        raise ConfigEntryNotReady(f"Failed to set up platforms: {err}") from err

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # TODO (Low fix #19): Consider registering HA services for:
    # - bytewatt_export_limiter.set_export_limit(limit)
    # - bytewatt_export_limiter.enable_automation(enable)
    # This would allow scripting/automation beyond entity control.

    _LOGGER.info("Bytewatt Export Limiter integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Bytewatt Export Limiter integration")

    # Unload all platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Get coordinator with guard check (High fix #7)
        if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
            _LOGGER.warning("Coordinator not found in hass.data during unload")
            return unload_ok

        coordinator: BytewattCoordinator = hass.data[DOMAIN][entry.entry_id]

        # Clean up coordinator (stop price monitoring, etc.) with timeout
        try:
            await asyncio.wait_for(coordinator.async_shutdown(), timeout=5.0)
        except asyncio.TimeoutError:
            _LOGGER.warning("Coordinator shutdown timed out after 5s")
        except Exception as err:
            _LOGGER.error("Error shutting down coordinator: %s", err)

        # Disconnect Modbus client with timeout
        try:
            await asyncio.wait_for(coordinator.modbus_client.disconnect(), timeout=5.0)
        except asyncio.TimeoutError:
            _LOGGER.warning("Modbus disconnect timed out after 5s")
        except Exception as err:
            _LOGGER.error("Error disconnecting Modbus client: %s", err)

        # Remove coordinator from hass.data
        hass.data[DOMAIN].pop(entry.entry_id)

        # Clean up domain data if empty
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

        _LOGGER.info("Bytewatt Export Limiter integration unloaded successfully")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    _LOGGER.debug("Reloading Bytewatt Export Limiter integration")

    # Unload the entry (Medium fix #12 - check return value)
    unload_ok = await async_unload_entry(hass, entry)

    if not unload_ok:
        _LOGGER.error("Failed to unload entry during reload, skipping setup")
        return

    # Reload the entry
    await async_setup_entry(hass, entry)

    _LOGGER.info("Bytewatt Export Limiter integration reloaded successfully")
