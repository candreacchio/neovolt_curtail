"""Number platform for Bytewatt Export Limiter integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
    """Set up Bytewatt Export Limiter number entities from a config entry."""
    coordinator: BytewattCoordinator = hass.data[DOMAIN][entry.entry_id]

    numbers = [
        BytewattManualLimitNumber(coordinator, entry),
    ]

    async_add_entities(numbers)


class BytewattManualLimitNumber(CoordinatorEntity, NumberEntity):
    """Number entity for manual export limit override."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 15000
    _attr_native_step = 100
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:speedometer"

    def __init__(
        self,
        coordinator: BytewattCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_manual_limit"
        self._attr_name = "Manual Export Limit"

    @property
    def available(self) -> bool:
        """Return True if entity is available (High fix #4)."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> float | None:
        """Return the current manual limit value."""
        if self.coordinator.data is None:
            # Medium fix #9: Standardize logging to DEBUG
            _LOGGER.debug("Coordinator data is None, cannot get manual limit")
            return None
        return self.coordinator.data.get("our_limit")

    async def async_set_native_value(self, value: float) -> None:
        """Set the manual export limit."""
        _LOGGER.debug("Setting manual export limit to %s W", value)
        try:
            success = await self.coordinator.set_export_limit(int(value))
            if not success:
                raise HomeAssistantError(f"Failed to set export limit to {int(value)}W")
        except HomeAssistantError:
            raise
        except Exception as err:
            _LOGGER.exception("Error setting export limit: %s", err)
            raise HomeAssistantError(f"Error setting export limit: {err}") from err

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self.coordinator.device_info
