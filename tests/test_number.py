"""Tests for number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.bytewatt_export_limiter.const import DOMAIN
from custom_components.bytewatt_export_limiter.number import BytewattManualLimitNumber


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "export_limit": 5000,
        "our_limit": 5000,
    }
    coordinator.our_limit = 5000
    coordinator.last_update_success = True
    coordinator.set_export_limit = AsyncMock(return_value=True)
    coordinator.device_info = {
        "identifiers": {(DOMAIN, "test_entry")},
        "name": "Bytewatt Export Limiter",
        "manufacturer": "Bytewatt",
        "model": "Export Limiter",
    }
    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return entry


class TestManualLimitNumber:
    """Test manual limit number entity."""

    def test_native_value(self, mock_coordinator, mock_config_entry):
        """Test native value returns our_limit."""
        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.native_value == 5000

    def test_native_value_none_when_data_missing(self, mock_coordinator, mock_config_entry):
        """Test native value is None when data is missing."""
        mock_coordinator.data = None

        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.native_value is None

    def test_native_value_none_when_our_limit_not_set(self, mock_coordinator, mock_config_entry):
        """Test native value is None when our_limit is not set."""
        mock_coordinator.data["our_limit"] = None

        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.native_value is None

    @pytest.mark.asyncio
    async def test_set_native_value_success(self, mock_coordinator, mock_config_entry):
        """Test setting value successfully."""
        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        await number.async_set_native_value(7500)

        mock_coordinator.set_export_limit.assert_called_once_with(7500)

    @pytest.mark.asyncio
    async def test_set_native_value_failure_raises(self, mock_coordinator, mock_config_entry):
        """Test setting value failure raises HomeAssistantError."""
        from homeassistant.exceptions import HomeAssistantError

        mock_coordinator.set_export_limit = AsyncMock(return_value=False)

        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        with pytest.raises(HomeAssistantError):
            await number.async_set_native_value(7500)

    def test_unique_id(self, mock_coordinator, mock_config_entry):
        """Test unique ID is correctly formatted."""
        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.unique_id == "test_entry_manual_limit"

    def test_device_info(self, mock_coordinator, mock_config_entry):
        """Test device info is from coordinator."""
        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.device_info == mock_coordinator.device_info

    def test_native_min_value(self, mock_coordinator, mock_config_entry):
        """Test minimum value is 0."""
        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.native_min_value == 0

    def test_native_max_value(self, mock_coordinator, mock_config_entry):
        """Test maximum value is 15000."""
        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.native_max_value == 15000

    def test_native_step(self, mock_coordinator, mock_config_entry):
        """Test step is 100."""
        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.native_step == 100

    def test_native_unit_of_measurement(self, mock_coordinator, mock_config_entry):
        """Test unit is watts."""
        number = BytewattManualLimitNumber(mock_coordinator, mock_config_entry)

        assert number.native_unit_of_measurement == "W"
