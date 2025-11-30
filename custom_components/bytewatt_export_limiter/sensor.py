"""Sensor platform for Bytewatt Export Limiter integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN  # Still needed for hass.data lookup
from .coordinator import BytewattCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bytewatt Export Limiter sensors from a config entry."""
    # Medium fix #13: Guard against missing coordinator during platform setup
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.error("Coordinator not found for entry %s", entry.entry_id)
        return

    coordinator: BytewattCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        BytewattExportLimitSensor(coordinator, entry),
        BytewattCurrentPriceSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class BytewattExportLimitSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current export limit in watts."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_suggested_display_precision = 0  # Low fix #15: Watts are integers
    _attr_icon = "mdi:transmission-tower-export"

    def __init__(
        self,
        coordinator: BytewattCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_export_limit"
        self._attr_name = "Export Limit"

    @property
    def available(self) -> bool:
        """Return True if entity is available (High fix #4)."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> int | None:
        """Return the current export limit in watts."""
        if self.coordinator.data is None:
            _LOGGER.debug("Coordinator data is None for export_limit sensor")
            return None
        return self.coordinator.data.get("export_limit")

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self.coordinator.device_info


class BytewattCurrentPriceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for mirrored electricity price from monitored entity."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "$/kWh"
    _attr_suggested_display_precision = 2
    # Low fix #14: Use generic currency icon instead of USD-specific
    _attr_icon = "mdi:currency-sign"

    def __init__(
        self,
        coordinator: BytewattCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_current_price"
        self._attr_name = "Current Price"

    @property
    def available(self) -> bool:
        """Return True if entity is available (High fix #4)."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> float | None:
        """Return the current electricity price in $/kWh."""
        if self.coordinator.data is None:
            _LOGGER.debug("Coordinator data is None for current_price sensor")
            return None
        return self.coordinator.data.get("current_price")

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self.coordinator.device_info
