"""
DataUpdateCoordinator for Bytewatt Export Limiter integration.

This coordinator manages:
- Polling Modbus registers for export limits
- Tracking grid operator limits vs our overrides
- Price-based automation for curtailment
- Debounced price entity monitoring
- Re-applying our limits when grid overrides
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypedDict

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
    REG_EXPORT_LIMIT,
    SOFTWARE_VERSION,
)
from .modbus_client import AsyncModbusClient

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


class BytewattCoordinatorData(TypedDict):
    """Type definition for coordinator data structure."""

    export_limit: int | None
    our_limit: int | None
    their_limit: int | None
    current_price: float | None
    is_curtailed: bool
    automation_enabled: bool


_LOGGER = logging.getLogger(__name__)


class BytewattCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Bytewatt export limiter data and automation."""

    def __init__(
        self,
        hass: HomeAssistant,
        modbus_client: AsyncModbusClient,
        entry: ConfigEntry,
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
        # Note (Low fix #17): their_limit is initialized from first device read and
        # only updated when a grid override is detected. It does not periodically
        # re-sync with the device. If the device is offline for extended periods
        # and returns with a different value, this may be detected as an override.
        self.their_limit: int | None = None  # Grid operator's limit
        self.our_limit: int | None = None  # Our manual override
        self.current_reading: int | None = None  # Current register value
        self.automation_enabled: bool = False  # Price automation toggle
        self.current_price: float | None = None  # Current electricity price
        # Track last write with timestamp for TTL (Medium fix #9)
        # Tuple of (value, timestamp) - expires after 3 poll cycles
        self._last_write: tuple[int, float] | None = None
        self._write_in_progress: bool = False  # High fix #2 - prevent false override detection

        # Debouncing
        self._price_debounce_task: asyncio.Task[None] | None = None
        self._price_change_cancel: Any = None

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
                _LOGGER.warning("Price entity became unavailable, clearing current_price")
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
        self._price_debounce_task = self.hass.async_create_task(self._debounced_price_update())

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

    async def _fetch_data(self, max_retries: int = 2) -> dict[str, Any]:
        """
        Fetch data from Modbus registers with retry logic (Medium fix #8).

        Args:
            max_retries: Number of retry attempts on failure

        Returns:
            Dictionary with current register values
        """
        last_error = None

        for attempt in range(max_retries + 1):
            # Read export limit register (0x08A2) - 16-bit value
            export_limit = await self.modbus_client.read_register_single(REG_EXPORT_LIMIT)
            if export_limit is None:
                last_error = "Failed to read export limit register"
                if attempt < max_retries:
                    _LOGGER.debug("Retry %d/%d: %s", attempt + 1, max_retries, last_error)
                    await asyncio.sleep(0.5)  # Brief delay before retry
                    continue
                raise UpdateFailed(last_error)

            _LOGGER.debug("Polled register: export_limit=%s", export_limit)

            return {
                "export_limit": export_limit,
            }

        # Should not reach here, but just in case
        raise UpdateFailed(last_error or "Unknown error fetching data")

    async def _async_update_data(self) -> BytewattCoordinatorData:
        """
        Poll Modbus and update coordinator state.

        This is called by DataUpdateCoordinator at the configured interval.
        It handles:
        1. Reading current register values
        2. Detecting grid overrides
        3. Re-applying our limits when needed
        4. Applying price-based automation

        Returns:
            BytewattCoordinatorData with all coordinator data for entities
        """
        # Fetch raw Modbus data
        raw_data = await self._fetch_data()
        export_limit = raw_data["export_limit"]

        # Update current reading
        self.current_reading = export_limit

        # Initialize their_limit on first read (Critical fix #1)
        if self.their_limit is None:
            self.their_limit = export_limit
            _LOGGER.info("Initialized their_limit from first read: %s", self.their_limit)

        # Get poll interval for TTL calculation
        poll_interval = (
            self.update_interval.total_seconds() if self.update_interval else DEFAULT_POLL_INTERVAL
        )

        # Check for grid override (High fix #2, Medium fix #9)
        # Skip if write is in progress to avoid false detection
        # Check TTL on last write - expire after 3 poll cycles (default 180s)
        last_write_value = None
        if self._last_write is not None:
            write_value, write_time = self._last_write
            ttl_seconds = poll_interval * 3
            if time.time() - write_time < ttl_seconds:
                last_write_value = write_value
            else:
                self._last_write = None  # Expired

        # If we had set a limit AND the current reading doesn't match our limit,
        # AND this isn't our own write echoing back, AND no write in progress
        if (
            self.our_limit is not None
            and self.current_reading != self.our_limit
            and self.current_reading != last_write_value
            and not self._write_in_progress
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

        # High fix #4: Re-check current_price right before comparison
        # to handle race where price becomes None between earlier check and here
        if self.current_price is None:
            _LOGGER.debug("Price became None during logic, skipping")
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

        # Set write-in-progress flag to prevent false override detection (High fix #2)
        self._write_in_progress = True
        try:
            success = await self.modbus_client.write_register(REG_EXPORT_LIMIT, value)

            if success:
                # Track last write with timestamp for TTL (Medium fix #9)
                self._last_write = (value, time.time())
                _LOGGER.debug("Successfully wrote limit %s", value)
            else:
                _LOGGER.error(
                    "Failed to write limit %s to register 0x%04X", value, REG_EXPORT_LIMIT
                )

            return success
        finally:
            self._write_in_progress = False

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
            # Trigger coordinator update to refresh entities (Medium fix #10)
            await self._safe_request_refresh()

        return success

    async def _safe_request_refresh(self, timeout: float = 30.0) -> None:
        """
        Request coordinator refresh with timeout (Medium fix #10).

        Args:
            timeout: Maximum time to wait for refresh in seconds
        """
        try:
            await asyncio.wait_for(self.async_request_refresh(), timeout=timeout)
        except TimeoutError:
            _LOGGER.warning("Coordinator refresh timed out after %ss", timeout)
        except Exception as err:
            _LOGGER.error("Error during coordinator refresh: %s", err)

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
            # High fix #5: Cancel any pending price debounce task
            # to prevent queued automation from triggering after disable
            if self._price_debounce_task and not self._price_debounce_task.done():
                self._price_debounce_task.cancel()
                _LOGGER.debug("Cancelled pending price debounce task")
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

        # Trigger coordinator update to refresh entities (Medium fix #10)
        await self._safe_request_refresh()
