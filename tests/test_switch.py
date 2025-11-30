"""Tests for switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.bytewatt_export_limiter.const import DOMAIN
from custom_components.bytewatt_export_limiter.switch import BytewattAutomationSwitch


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "automation_enabled": False,
    }
    coordinator.automation_enabled = False
    coordinator.last_update_success = True
    coordinator.set_automation_enabled = AsyncMock()
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


class TestAutomationSwitch:
    """Test automation switch."""

    def test_is_on_false(self, mock_coordinator, mock_config_entry):
        """Test is_on returns False when automation is disabled."""
        mock_coordinator.data["automation_enabled"] = False

        switch = BytewattAutomationSwitch(mock_coordinator, mock_config_entry)

        assert switch.is_on is False

    def test_is_on_true(self, mock_coordinator, mock_config_entry):
        """Test is_on returns True when automation is enabled."""
        mock_coordinator.data["automation_enabled"] = True

        switch = BytewattAutomationSwitch(mock_coordinator, mock_config_entry)

        assert switch.is_on is True

    def test_is_on_none_when_data_missing(self, mock_coordinator, mock_config_entry):
        """Test is_on returns None when data is missing."""
        mock_coordinator.data = None

        switch = BytewattAutomationSwitch(mock_coordinator, mock_config_entry)

        assert switch.is_on is None

    @pytest.mark.asyncio
    async def test_turn_on(self, mock_coordinator, mock_config_entry):
        """Test turning on automation."""
        switch = BytewattAutomationSwitch(mock_coordinator, mock_config_entry)

        await switch.async_turn_on()

        mock_coordinator.set_automation_enabled.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_turn_off(self, mock_coordinator, mock_config_entry):
        """Test turning off automation."""
        switch = BytewattAutomationSwitch(mock_coordinator, mock_config_entry)

        await switch.async_turn_off()

        mock_coordinator.set_automation_enabled.assert_called_once_with(False)

    def test_unique_id(self, mock_coordinator, mock_config_entry):
        """Test unique ID is correctly formatted."""
        switch = BytewattAutomationSwitch(mock_coordinator, mock_config_entry)

        assert switch.unique_id == "test_entry_automation_enabled"

    def test_device_info(self, mock_coordinator, mock_config_entry):
        """Test device info is from coordinator."""
        switch = BytewattAutomationSwitch(mock_coordinator, mock_config_entry)

        assert switch.device_info == mock_coordinator.device_info
