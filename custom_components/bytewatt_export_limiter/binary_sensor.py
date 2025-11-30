"""Binary sensor platform for Bytewatt Export Limiter integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up Bytewatt Export Limiter binary sensors from a config entry."""
    coordinator: BytewattCoordinator = hass.data[DOMAIN][entry.entry_id]

    binary_sensors = [
        BytewattCurtailedBinarySensor(coordinator, entry),
    ]

    async_add_entities(binary_sensors)


class BytewattCurtailedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating whether export is currently curtailed."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_icon = "mdi:solar-power-variant"

    def __init__(
        self,
        coordinator: BytewattCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_curtailed"
        self._attr_name = "Export Curtailed"

    @property
    def available(self) -> bool:
        """Return True if entity is available (High fix #4)."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Return True if export is curtailed (limit < their_limit)."""
        if self.coordinator.data is None:
            _LOGGER.debug("Coordinator data is None for curtailed sensor")
            return None
        # High fix #7: Don't use False as default - return None if key missing
        return self.coordinator.data.get("is_curtailed")

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self.coordinator.device_info
