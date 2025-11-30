"""Tests for BytewattCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.bytewatt_export_limiter.const import (
    CONF_CURTAILED_LIMIT,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_MODBUS_SLAVE,
    CONF_POLL_INTERVAL,
    CONF_PRICE_ENTITY,
    CONF_PRICE_THRESHOLD,
    DOMAIN,
    REG_EXPORT_LIMIT,
)
from custom_components.bytewatt_export_limiter.coordinator import BytewattCoordinator


@pytest.fixture
def mock_modbus_client():
    """Create a mock Modbus client."""
    client = AsyncMock()
    client.read_register_single = AsyncMock(return_value=5000)
    client.write_register = AsyncMock(return_value=True)
    client.is_connected = True
    return client


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}

    # Mock state for price entity
    price_state = MagicMock()
    price_state.state = "0.10"
    hass.states.get = MagicMock(return_value=price_state)

    def create_task(coro):
        return asyncio.ensure_future(coro)

    hass.async_create_task = create_task
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {
        CONF_MODBUS_HOST: "192.168.1.100",
        CONF_MODBUS_PORT: 502,
        CONF_MODBUS_SLAVE: 85,
        CONF_PRICE_ENTITY: "sensor.electricity_price",
        CONF_PRICE_THRESHOLD: 0.05,
        CONF_CURTAILED_LIMIT: 0,
        CONF_POLL_INTERVAL: 60,
    }
    entry.options = {}
    return entry


class TestCoordinatorInit:
    """Test coordinator initialization."""

    def test_init_with_defaults(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test coordinator initializes with config values."""
        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)

            assert coordinator.modbus_client == mock_modbus_client
            assert coordinator.price_entity_id == "sensor.electricity_price"
            assert coordinator.price_threshold == 0.05
            assert coordinator.curtailed_limit == 0
            assert coordinator.their_limit is None
            assert coordinator.our_limit is None
            assert coordinator.automation_enabled is False

    def test_init_with_options_override(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test coordinator uses options over data."""
        mock_config_entry.options = {
            CONF_PRICE_THRESHOLD: 0.10,
            CONF_CURTAILED_LIMIT: 1000,
        }

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)

            assert coordinator.price_threshold == 0.10
            assert coordinator.curtailed_limit == 1000


class TestCoordinatorDataFetch:
    """Test data fetching."""

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test successful data fetch."""
        mock_modbus_client.read_register_single = AsyncMock(return_value=5000)

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)

            data = await coordinator._fetch_data()

            assert data["export_limit"] == 5000

    @pytest.mark.asyncio
    async def test_fetch_data_retry_on_failure(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test data fetch retry logic."""
        # First call fails, second succeeds
        mock_modbus_client.read_register_single = AsyncMock(side_effect=[None, 5000])

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)

            data = await coordinator._fetch_data()

            assert data["export_limit"] == 5000
            assert mock_modbus_client.read_register_single.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_data_failure_after_retries(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test data fetch fails after all retries."""
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_modbus_client.read_register_single = AsyncMock(return_value=None)

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)

            with pytest.raises(UpdateFailed):
                await coordinator._fetch_data()


class TestCoordinatorStateTracking:
    """Test state tracking logic."""

    @pytest.mark.asyncio
    async def test_their_limit_initialized_on_first_read(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test their_limit is set on first successful read."""
        mock_modbus_client.read_register_single = AsyncMock(return_value=8000)

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.update_interval = timedelta(seconds=60)

            assert coordinator.their_limit is None

            await coordinator._async_update_data()

            assert coordinator.their_limit == 8000
            assert coordinator.current_reading == 8000

    @pytest.mark.asyncio
    async def test_grid_override_detection(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test detection of grid override."""
        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.update_interval = timedelta(seconds=60)

            # Initial state
            coordinator.their_limit = 10000
            coordinator.our_limit = 5000
            coordinator.current_reading = 5000
            coordinator._last_write = None
            coordinator._write_in_progress = False

            # Simulate grid override - current reading changed to something else
            mock_modbus_client.read_register_single = AsyncMock(return_value=8000)

            await coordinator._async_update_data()

            # their_limit should be updated to the new grid-imposed value
            assert coordinator.their_limit == 8000


class TestCoordinatorPriceAutomation:
    """Test price-based automation."""

    @pytest.mark.asyncio
    async def test_automation_disabled_no_action(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test no action when automation is disabled."""
        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.automation_enabled = False
            coordinator.current_price = 0.01  # Below threshold
            coordinator.their_limit = 10000

            await coordinator._apply_price_logic()

            # No write should occur
            mock_modbus_client.write_register.assert_not_called()

    @pytest.mark.asyncio
    async def test_automation_curtails_on_low_price(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test curtailment when price is below threshold."""
        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.automation_enabled = True
            coordinator.current_price = 0.01  # Below threshold of 0.05
            coordinator.their_limit = 10000
            coordinator.current_reading = 10000  # Currently at full limit
            coordinator.curtailed_limit = 0

            await coordinator._apply_price_logic()

            # Should write curtailed limit
            mock_modbus_client.write_register.assert_called()
            call_args = mock_modbus_client.write_register.call_args
            assert call_args[0][1] == 0  # curtailed_limit

    @pytest.mark.asyncio
    async def test_automation_restores_on_high_price(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test restoration when price goes above threshold."""
        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.automation_enabled = True
            coordinator.current_price = 0.10  # Above threshold of 0.05
            coordinator.their_limit = 10000
            coordinator.current_reading = 0  # Currently curtailed
            coordinator.curtailed_limit = 0

            await coordinator._apply_price_logic()

            # Should write their_limit (restore full export)
            mock_modbus_client.write_register.assert_called()
            call_args = mock_modbus_client.write_register.call_args
            assert call_args[0][1] == 10000  # their_limit

    @pytest.mark.asyncio
    async def test_no_write_when_target_matches_current(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test no write when target matches current reading."""
        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.automation_enabled = True
            coordinator.current_price = 0.01
            coordinator.their_limit = 10000
            coordinator.current_reading = 0  # Already at curtailed limit
            coordinator.curtailed_limit = 0

            await coordinator._apply_price_logic()

            # No write needed - already at target
            mock_modbus_client.write_register.assert_not_called()


class TestCoordinatorManualControl:
    """Test manual control methods."""

    @pytest.mark.asyncio
    async def test_set_export_limit_success(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test manual export limit setting."""
        mock_modbus_client.write_register = AsyncMock(return_value=True)

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.async_request_refresh = AsyncMock()

            result = await coordinator.set_export_limit(5000)

            assert result is True
            assert coordinator.our_limit == 5000
            mock_modbus_client.write_register.assert_called_once_with(REG_EXPORT_LIMIT, 5000)

    @pytest.mark.asyncio
    async def test_set_export_limit_failure(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test manual export limit setting failure."""
        mock_modbus_client.write_register = AsyncMock(return_value=False)

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.our_limit = None

            result = await coordinator.set_export_limit(5000)

            assert result is False
            assert coordinator.our_limit is None  # Not updated on failure

    @pytest.mark.asyncio
    async def test_set_export_limit_invalid_value(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test manual export limit with invalid value."""
        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)

            result = await coordinator.set_export_limit(-1)

            assert result is False
            mock_modbus_client.write_register.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_automation_enabled(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test enabling automation."""
        mock_modbus_client.write_register = AsyncMock(return_value=True)

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.async_request_refresh = AsyncMock()
            coordinator.their_limit = 10000
            coordinator.current_price = 0.01
            coordinator.current_reading = 10000
            coordinator.curtailed_limit = 0

            await coordinator.set_automation_enabled(True)

            assert coordinator.automation_enabled is True
            # Should apply price logic immediately
            mock_modbus_client.write_register.assert_called()

    @pytest.mark.asyncio
    async def test_set_automation_disabled_reverts(
        self, mock_hass, mock_modbus_client, mock_config_entry
    ):
        """Test disabling automation reverts to their_limit."""
        mock_modbus_client.write_register = AsyncMock(return_value=True)

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            coordinator.async_request_refresh = AsyncMock()
            coordinator.automation_enabled = True
            coordinator.their_limit = 10000
            coordinator.current_reading = 0  # Currently curtailed

            await coordinator.set_automation_enabled(False)

            assert coordinator.automation_enabled is False
            # Should revert to their_limit
            mock_modbus_client.write_register.assert_called()


class TestCoordinatorDeviceInfo:
    """Test device info property."""

    def test_device_info(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test device info is correctly formatted."""
        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event"
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)

            device_info = coordinator.device_info

            assert "identifiers" in device_info
            assert (DOMAIN, mock_config_entry.entry_id) in device_info["identifiers"]
            assert device_info["manufacturer"] == "Bytewatt"
            assert device_info["model"] == "Export Limiter"


class TestCoordinatorCleanup:
    """Test cleanup and shutdown."""

    @pytest.mark.asyncio
    async def test_async_shutdown(self, mock_hass, mock_modbus_client, mock_config_entry):
        """Test shutdown cleans up resources."""
        cancel_mock = MagicMock()

        with patch(
            "custom_components.bytewatt_export_limiter.coordinator.async_track_state_change_event",
            return_value=cancel_mock,
        ):
            coordinator = BytewattCoordinator(mock_hass, mock_modbus_client, mock_config_entry)
            await coordinator.async_setup()

            await coordinator.async_shutdown()

            cancel_mock.assert_called_once()
            assert coordinator._price_change_cancel is None
