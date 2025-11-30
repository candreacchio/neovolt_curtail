"""Tests for binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.bytewatt_export_limiter.binary_sensor import (
    BytewattCurtailedBinarySensor,
)
from custom_components.bytewatt_export_limiter.const import DOMAIN


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "is_curtailed": False,
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


class TestExportCurtailedSensor:
    """Test export curtailed binary sensor."""

    def test_is_on_false_when_not_curtailed(self, mock_coordinator, mock_config_entry):
        """Test is_on returns False when not curtailed."""
        mock_coordinator.data["is_curtailed"] = False

        sensor = BytewattCurtailedBinarySensor(mock_coordinator, mock_config_entry)

        assert sensor.is_on is False

    def test_is_on_true_when_curtailed(self, mock_coordinator, mock_config_entry):
        """Test is_on returns True when curtailed."""
        mock_coordinator.data["is_curtailed"] = True

        sensor = BytewattCurtailedBinarySensor(mock_coordinator, mock_config_entry)

        assert sensor.is_on is True

    def test_is_on_none_when_data_missing(self, mock_coordinator, mock_config_entry):
        """Test is_on returns None when data is missing."""
        mock_coordinator.data = None

        sensor = BytewattCurtailedBinarySensor(mock_coordinator, mock_config_entry)

        assert sensor.is_on is None

    def test_unique_id(self, mock_coordinator, mock_config_entry):
        """Test unique ID is correctly formatted."""
        sensor = BytewattCurtailedBinarySensor(mock_coordinator, mock_config_entry)

        assert sensor.unique_id == "test_entry_curtailed"

    def test_device_info(self, mock_coordinator, mock_config_entry):
        """Test device info is from coordinator."""
        sensor = BytewattCurtailedBinarySensor(mock_coordinator, mock_config_entry)

        assert sensor.device_info == mock_coordinator.device_info

    def test_icon(self, mock_coordinator, mock_config_entry):
        """Test icon is consistent."""
        sensor = BytewattCurtailedBinarySensor(mock_coordinator, mock_config_entry)

        # The icon is fixed for this sensor
        assert sensor.icon == "mdi:solar-power-variant"
