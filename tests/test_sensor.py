"""Tests for sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.bytewatt_export_limiter.const import DOMAIN
from custom_components.bytewatt_export_limiter.sensor import (
    BytewattCurrentPriceSensor,
    BytewattExportLimitSensor,
    BytewattGridMaxSensor,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "export_limit": 5000,
        "grid_max_limit": 10000,
        "current_price": 0.10,
        "is_curtailed": False,
        "automation_enabled": False,
    }
    coordinator.last_update_success = True
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


class TestExportLimitSensor:
    """Test export limit sensor."""

    def test_native_value(self, mock_coordinator, mock_config_entry):
        """Test native value returns export limit."""
        sensor = BytewattExportLimitSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_value == 5000

    def test_native_value_none_when_data_missing(self, mock_coordinator, mock_config_entry):
        """Test native value is None when data is missing."""
        mock_coordinator.data = None

        sensor = BytewattExportLimitSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_value is None

    def test_unique_id(self, mock_coordinator, mock_config_entry):
        """Test unique ID is correctly formatted."""
        sensor = BytewattExportLimitSensor(mock_coordinator, mock_config_entry)

        assert sensor.unique_id == "test_entry_export_limit"

    def test_device_info(self, mock_coordinator, mock_config_entry):
        """Test device info is from coordinator."""
        sensor = BytewattExportLimitSensor(mock_coordinator, mock_config_entry)

        assert sensor.device_info == mock_coordinator.device_info

    def test_native_unit_of_measurement(self, mock_coordinator, mock_config_entry):
        """Test unit of measurement is watts."""
        sensor = BytewattExportLimitSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_unit_of_measurement == "W"


class TestGridMaxSensor:
    """Test grid max limit sensor."""

    def test_native_value(self, mock_coordinator, mock_config_entry):
        """Test native value returns grid max limit."""
        sensor = BytewattGridMaxSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_value == 10000

    def test_native_value_none_when_data_missing(self, mock_coordinator, mock_config_entry):
        """Test native value is None when data is missing."""
        mock_coordinator.data = None

        sensor = BytewattGridMaxSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_value is None

    def test_unique_id(self, mock_coordinator, mock_config_entry):
        """Test unique ID is correctly formatted."""
        sensor = BytewattGridMaxSensor(mock_coordinator, mock_config_entry)

        assert sensor.unique_id == "test_entry_grid_max"


class TestCurrentPriceSensor:
    """Test current price sensor."""

    def test_native_value(self, mock_coordinator, mock_config_entry):
        """Test native value returns current price."""
        sensor = BytewattCurrentPriceSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_value == 0.10

    def test_native_value_none_when_data_missing(self, mock_coordinator, mock_config_entry):
        """Test native value is None when data is missing."""
        mock_coordinator.data = None

        sensor = BytewattCurrentPriceSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_value is None

    def test_unique_id(self, mock_coordinator, mock_config_entry):
        """Test unique ID is correctly formatted."""
        sensor = BytewattCurrentPriceSensor(mock_coordinator, mock_config_entry)

        assert sensor.unique_id == "test_entry_current_price"

    def test_native_unit_of_measurement(self, mock_coordinator, mock_config_entry):
        """Test unit of measurement is $/kWh."""
        sensor = BytewattCurrentPriceSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_unit_of_measurement == "$/kWh"
