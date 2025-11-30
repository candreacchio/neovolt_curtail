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

from .const import DOMAIN
from .coordinator import BytewattCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bytewatt Export Limiter sensors from a config entry."""
    coordinator: BytewattCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        BytewattExportLimitSensor(coordinator, entry),
        BytewattGridMaxSensor(coordinator, entry),
        BytewattCurrentPriceSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class BytewattExportLimitSensor(CoordinatorEntity, SensorEntity):
    """Sensor for current export limit in watts."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
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
    def native_value(self) -> int | None:
        """Return the current export limit in watts."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("export_limit")

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Bytewatt Export Limiter",
            "manufacturer": "Bytewatt",
            "model": "Export Limiter",
            "sw_version": "1.0",
        }


class BytewattGridMaxSensor(CoordinatorEntity, SensorEntity):
    """Sensor for grid's maximum export limit in watts."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_icon = "mdi:transmission-tower"

    def __init__(
        self,
        coordinator: BytewattCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_grid_max"
        self._attr_name = "Grid Maximum Limit"

    @property
    def native_value(self) -> int | None:
        """Return the grid's maximum limit in watts."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("grid_max_limit")

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Bytewatt Export Limiter",
            "manufacturer": "Bytewatt",
            "model": "Export Limiter",
            "sw_version": "1.0",
        }


class BytewattCurrentPriceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for mirrored electricity price from monitored entity."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "c/kWh"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:currency-usd"

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
    def native_value(self) -> float | None:
        """Return the current electricity price in c/kWh."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("current_price")

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Bytewatt Export Limiter",
            "manufacturer": "Bytewatt",
            "model": "Export Limiter",
            "sw_version": "1.0",
        }
