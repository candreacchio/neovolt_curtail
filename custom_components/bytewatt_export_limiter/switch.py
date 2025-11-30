"""Switch platform for Bytewatt Export Limiter integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Bytewatt Export Limiter switches from a config entry."""
    coordinator: BytewattCoordinator = hass.data[DOMAIN][entry.entry_id]

    switches = [
        BytewattAutomationSwitch(coordinator, entry),
    ]

    async_add_entities(switches)


class BytewattAutomationSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable price-based automation."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:robot"

    def __init__(
        self,
        coordinator: BytewattCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_automation_enabled"
        self._attr_name = "Automation Enabled"

    @property
    def is_on(self) -> bool | None:
        """Return True if automation is enabled."""
        if self.coordinator.data is None:
            _LOGGER.warning("Coordinator data is None, cannot get automation state")
            return None
        return self.coordinator.data.get("automation_enabled", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on automation."""
        _LOGGER.debug("Enabling price-based automation")
        try:
            await self.coordinator.set_automation_enabled(True)
        except Exception as err:
            _LOGGER.exception("Error enabling automation: %s", err)
            raise HomeAssistantError(f"Error enabling automation: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off automation."""
        _LOGGER.debug("Disabling price-based automation")
        try:
            await self.coordinator.set_automation_enabled(False)
        except Exception as err:
            _LOGGER.exception("Error disabling automation: %s", err)
            raise HomeAssistantError(f"Error disabling automation: {err}") from err

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
