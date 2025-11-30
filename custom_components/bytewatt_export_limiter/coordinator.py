"""
DataUpdateCoordinator for Bytewatt Export Limiter integration.

This coordinator manages:
- Polling Modbus registers for export limits
- Tracking grid operator limits vs our overrides
- Price-based automation for curtailment
- Debounced price entity monitoring
- Re-applying our limits when grid overrides
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CURTAILED_LIMIT,
    CONF_POLL_INTERVAL,
    CONF_PRICE_ENTITY,
    CONF_PRICE_THRESHOLD,
    DEFAULT_POLL_INTERVAL,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
    PRICE_DEBOUNCE_SECONDS,
    REG_DEFAULT_LIMIT,
    REG_EXPORT_LIMIT,
    SOFTWARE_VERSION,
)
from .modbus_client import AsyncModbusClient

_LOGGER = logging.getLogger(__name__)


class BytewattCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Bytewatt export limiter data and automation."""

    def __init__(
        self,
        hass: HomeAssistant,
        modbus_client: AsyncModbusClient,
        entry: "ConfigEntry",
    ) -> None:
        """
        Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            modbus_client: Connected AsyncModbusClient instance
            entry: Config entry with all configuration
        """
        self.modbus_client = modbus_client
        self.entry = entry  # Store entry for entity device_info

        # Extract configuration from entry data and options
        config = {**entry.data, **entry.options}
        poll_interval = config.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        self.price_entity_id = config.get(CONF_PRICE_ENTITY)
        self.price_threshold = config.get(CONF_PRICE_THRESHOLD, 0.0)
        self.curtailed_limit = config.get(CONF_CURTAILED_LIMIT, 0)

        # State tracking
        self.their_limit: Optional[int] = None  # Grid operator's limit
        self.our_limit: Optional[int] = None  # Our manual override
        self.current_reading: Optional[int] = None  # Current register value
        self.automation_enabled: bool = False  # Price automation toggle
        self.current_price: Optional[float] = None  # Current electricity price
        self._last_write_value: Optional[int] = None  # Track our last write to avoid false override detection

        # Debouncing
        self._price_debounce_task: Optional[asyncio.Task] = None
        self._price_change_cancel = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )

    async def async_setup(self) -> None:
        """Set up the coordinator, including price entity subscription."""
        # Subscribe to price entity state changes if configured
        if self.price_entity_id:
            _LOGGER.info(
                "Subscribing to price entity: %s (threshold: %s, curtailed limit: %s)",
                self.price_entity_id,
                self.price_threshold,
                self.curtailed_limit,
            )
            self._price_change_cancel = async_track_state_change_event(
                self.hass,
                [self.price_entity_id],
                self._handle_price_change,
            )

            # Get initial price value
            price_state = self.hass.states.get(self.price_entity_id)
            if price_state and price_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                try:
                    self.current_price = float(price_state.state)
                    _LOGGER.debug("Initial price: %s", self.current_price)
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not parse initial price state: %s",
                        price_state.state,
                    )

    async def async_shutdown(self) -> None:
        """Clean up resources on shutdown."""
        # Cancel price entity subscription
        if self._price_change_cancel:
            self._price_change_cancel()
            self._price_change_cancel = None

        # Cancel any pending debounce tasks
        if self._price_debounce_task and not self._price_debounce_task.done():
            self._price_debounce_task.cancel()
            try:
                await self._price_debounce_task
            except asyncio.CancelledError:
                pass

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information for entities to use."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Bytewatt Export Limiter",
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
            "sw_version": SOFTWARE_VERSION,
        }

    @callback
    def _handle_price_change(self, event: Event) -> None:
        """
        Handle price entity state change with debouncing.

        This callback is triggered immediately when the price changes, but
        we debounce it to avoid excessive writes to Modbus.
        """
        new_state: State = event.data.get("new_state")
        if not new_state:
            return

        # Critical fix #2: Set current_price to None when entity unavailable
        # to avoid using stale price data
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if self.current_price is not None:
                _LOGGER.warning(
                    "Price entity became unavailable, clearing current_price"
                )
                self.current_price = None
            return

        try:
            new_price = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.warning("Could not parse price state: %s", new_state.state)
            return

        # Update current price immediately
        old_price = self.current_price
        self.current_price = new_price

        _LOGGER.debug("Price changed: %s -> %s", old_price, new_price)

        # Cancel existing debounce task if any
        if self._price_debounce_task and not self._price_debounce_task.done():
            self._price_debounce_task.cancel()

        # Create new debounced task
        self._price_debounce_task = self.hass.async_create_task(
            self._debounced_price_update()
        )

    async def _debounced_price_update(self) -> None:
        """Wait for debounce period, then apply price-based logic."""
        try:
            await asyncio.sleep(PRICE_DEBOUNCE_SECONDS)
            _LOGGER.debug(
                "Price debounce expired, applying logic (price: %s, threshold: %s)",
                self.current_price,
                self.price_threshold,
            )
            await self._apply_price_logic()
        except asyncio.CancelledError:
            _LOGGER.debug("Price debounce cancelled")
            raise
        except Exception as err:
            _LOGGER.exception("Error in debounced price update: %s", err)

    async def _fetch_data(self) -> dict[str, Any]:
        """
        Fetch data from Modbus registers.

        Returns:
            Dictionary with current register values and calculated state
        """
        # Read export limit register (0x08A2)
        export_limit = await self.modbus_client.read_register_32bit(REG_EXPORT_LIMIT)
        if export_limit is None:
            raise UpdateFailed("Failed to read export limit register")

        # Read grid max/default limit register (0x08A5)
        grid_max = await self.modbus_client.read_register_32bit(REG_DEFAULT_LIMIT)
        if grid_max is None:
            raise UpdateFailed("Failed to read grid max limit register")

        _LOGGER.debug(
            "Polled registers: export_limit=%s, grid_max=%s",
            export_limit,
            grid_max,
        )

        return {
            "export_limit": export_limit,
            "grid_max_limit": grid_max,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Poll Modbus and update coordinator state.

        This is called by DataUpdateCoordinator at the configured interval.
        It handles:
        1. Reading current register values
        2. Detecting grid overrides
        3. Re-applying our limits when needed
        4. Applying price-based automation

        Returns:
            Dictionary with all coordinator data for entities
        """
        # Fetch raw Modbus data
        raw_data = await self._fetch_data()
        export_limit = raw_data["export_limit"]
        grid_max = raw_data["grid_max_limit"]

        # Update current reading
        previous_reading = self.current_reading
        self.current_reading = export_limit

        # Initialize their_limit on first read (Critical fix #1)
        if self.their_limit is None:
            self.their_limit = export_limit
            _LOGGER.info("Initialized their_limit from first read: %s", self.their_limit)

        # Check for grid override
        # If we had set a limit AND the current reading doesn't match our limit,
        # AND this isn't our own write echoing back, then the grid operator changed it
        if (
            self.our_limit is not None
            and self.current_reading != self.our_limit
            and self.current_reading != self._last_write_value
        ):
            _LOGGER.info(
                "Grid override detected: our_limit=%s, current=%s",
                self.our_limit,
                self.current_reading,
            )
            # Update their_limit to the new grid-imposed value
            self.their_limit = self.current_reading

            # If our limit is lower than their new limit, re-apply ours
            if self.our_limit < self.their_limit:
                _LOGGER.info(
                    "Re-applying our limit %s (grid changed to %s)",
                    self.our_limit,
                    self.their_limit,
                )
                await self._write_limit(self.our_limit)

        # Apply price-based automation logic
        await self._apply_price_logic()

        # Determine if currently curtailed (High fix #8)
        # Curtailed = current export limit is lower than the grid's limit
        is_curtailed = False
        if self.current_reading is not None and self.their_limit is not None:
            is_curtailed = self.current_reading < self.their_limit

        # Build data dictionary for entities
        return {
            "export_limit": self.current_reading,
            "grid_max_limit": grid_max,
            "our_limit": self.our_limit,
            "their_limit": self.their_limit,
            "current_price": self.current_price,
            "is_curtailed": is_curtailed,
            "automation_enabled": self.automation_enabled,
        }

    async def _apply_price_logic(self) -> None:
        """
        Apply price-based automation logic.

        Logic:
        - If automation_enabled AND price <= threshold: target = curtailed_limit
        - Else: target = their_limit (use grid's limit)
        - If target != current: write to register
        """
        if not self.automation_enabled:
            _LOGGER.debug("Automation disabled, skipping price logic")
            return

        if self.current_price is None:
            _LOGGER.debug("No price data available, skipping price logic")
            return

        if self.their_limit is None:
            _LOGGER.debug("No their_limit set, skipping price logic")
            return

        # Guard against None curtailed_limit (Critical fix #4)
        if self.curtailed_limit is None:
            _LOGGER.warning("curtailed_limit is None, skipping price logic")
            return

        # Determine target limit based on price
        if self.current_price <= self.price_threshold:
            target_limit = self.curtailed_limit
            _LOGGER.debug(
                "Price %s <= threshold %s, target is curtailed_limit=%s",
                self.current_price,
                self.price_threshold,
                target_limit,
            )
        else:
            target_limit = self.their_limit
            _LOGGER.debug(
                "Price %s > threshold %s, target is their_limit=%s",
                self.current_price,
                self.price_threshold,
                target_limit,
            )

        # Only write if target differs from current reading
        if target_limit != self.current_reading:
            _LOGGER.info(
                "Applying price-based limit: %s (current: %s, price: %s)",
                target_limit,
                self.current_reading,
                self.current_price,
            )
            await self._write_limit(target_limit)
        else:
            _LOGGER.debug(
                "Target limit %s matches current reading, no write needed",
                target_limit,
            )

    async def _write_limit(self, value: int) -> bool:
        """
        Write export limit to Modbus register.

        Args:
            value: Export limit in watts

        Returns:
            True on success, False on error
        """
        _LOGGER.info("Writing export limit: %s W", value)

        success = await self.modbus_client.write_register_32bit(REG_EXPORT_LIMIT, value)

        if success:
            # Only track last write value - let the next poll update current_reading
            # to confirm device actually applied the change (Critical fix #1 - race condition)
            self._last_write_value = value
            _LOGGER.debug("Successfully wrote limit %s", value)
        else:
            _LOGGER.error("Failed to write limit %s to register 0x%04X", value, REG_EXPORT_LIMIT)

        return success

    async def set_export_limit(self, value: int) -> bool:
        """
        Manually set export limit (user override).

        This sets our_limit and writes it to the register immediately.
        It does NOT enable automation.

        Args:
            value: Export limit in watts (0-65535)

        Returns:
            True on success, False on error
        """
        if not 0 <= value <= 0xFFFFFFFF:  # 32-bit unsigned max
            _LOGGER.error("Invalid export limit value: %s (must be 0-4294967295)", value)
            return False

        _LOGGER.info("Manual export limit set: %s W", value)

        # Write to register first (Critical fix #2 - only update our_limit after success)
        success = await self._write_limit(value)

        if success:
            # Only update our_limit AFTER successful write
            self.our_limit = value
            # Trigger coordinator update to refresh entities
            await self.async_request_refresh()

        return success

    async def set_automation_enabled(self, enabled: bool) -> None:
        """
        Enable or disable price-based automation.

        When enabled, the system will automatically adjust export limits
        based on electricity price and threshold.

        When disabled, manual limits remain in effect.

        Args:
            enabled: True to enable automation, False to disable
        """
        old_state = self.automation_enabled
        self.automation_enabled = enabled

        _LOGGER.info("Automation %s -> %s", old_state, enabled)

        if enabled:
            # Immediately apply price logic when enabling
            await self._apply_price_logic()
        else:
            # When disabling, revert to their_limit if we had set a different limit
            if (
                self.their_limit is not None
                and self.current_reading is not None
                and self.current_reading != self.their_limit
            ):
                _LOGGER.info(
                    "Automation disabled, reverting to their_limit: %s",
                    self.their_limit,
                )
                await self._write_limit(self.their_limit)

        # Trigger coordinator update to refresh entities
        await self.async_request_refresh()
