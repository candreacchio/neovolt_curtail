"""Pytest fixtures for Bytewatt Export Limiter tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any
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
    DEFAULT_CURTAILED_LIMIT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
    DOMAIN,
)


@pytest.fixture
def mock_modbus_client() -> Generator[AsyncMock, None, None]:
    """Create a mock AsyncModbusClient."""
    with patch(
        "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
    ) as mock_pymodbus:
        # Configure the mock pymodbus client
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.connected = True
        mock_client.close = MagicMock()
        mock_pymodbus.return_value = mock_client

        yield mock_client


@pytest.fixture
def mock_modbus_response() -> MagicMock:
    """Create a mock Modbus response."""
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [0, 5000]  # Default 32-bit value: 5000W
    return response


@pytest.fixture
def modbus_client_config() -> dict[str, Any]:
    """Return default Modbus client configuration."""
    return {
        "host": "192.168.1.100",
        "port": DEFAULT_PORT,
        "slave_address": DEFAULT_SLAVE,
        "timeout": 10,
    }


@pytest.fixture
def config_entry_data() -> dict[str, Any]:
    """Return default config entry data."""
    return {
        CONF_MODBUS_HOST: "192.168.1.100",
        CONF_MODBUS_PORT: DEFAULT_PORT,
        CONF_MODBUS_SLAVE: DEFAULT_SLAVE,
        CONF_PRICE_ENTITY: "sensor.electricity_price",
        CONF_PRICE_THRESHOLD: 0.05,
        CONF_CURTAILED_LIMIT: DEFAULT_CURTAILED_LIMIT,
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
    }


@pytest.fixture
def mock_config_entry(config_entry_data: dict[str, Any]) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = config_entry_data
    entry.options = {}
    entry.title = "Bytewatt Export Limiter"
    entry.domain = DOMAIN
    return entry


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.states = MagicMock()

    # Mock state for price entity
    price_state = MagicMock()
    price_state.state = "0.10"  # 10 cents/kWh
    hass.states.get.return_value = price_state

    # Mock async_create_task
    def create_task(coro):
        task = asyncio.ensure_future(coro)
        return task

    hass.async_create_task = create_task

    return hass


@pytest.fixture
def mock_coordinator(
    mock_hass: MagicMock,
    mock_modbus_client: AsyncMock,
    mock_config_entry: MagicMock,
) -> MagicMock:
    """Create a mock coordinator."""
    from custom_components.bytewatt_export_limiter.coordinator import BytewattCoordinator

    with patch.object(BytewattCoordinator, "__init__", return_value=None):
        coordinator = BytewattCoordinator.__new__(BytewattCoordinator)
        coordinator.hass = mock_hass
        coordinator.modbus_client = mock_modbus_client
        coordinator.entry = mock_config_entry
        coordinator.data = {
            "export_limit": 5000,
            "grid_max_limit": 10000,
            "our_limit": None,
            "their_limit": 10000,
            "current_price": 0.10,
            "is_curtailed": False,
            "automation_enabled": False,
        }
        coordinator.last_update_success = True
        coordinator.their_limit = 10000
        coordinator.our_limit = None
        coordinator.current_reading = 5000
        coordinator.automation_enabled = False
        coordinator.current_price = 0.10
        coordinator.price_threshold = 0.05
        coordinator.curtailed_limit = 0

        # Add device_info property
        coordinator.device_info = {
            "identifiers": {(DOMAIN, mock_config_entry.entry_id)},
            "name": "Bytewatt Export Limiter",
            "manufacturer": "Bytewatt",
            "model": "Export Limiter",
            "sw_version": "1.0",
        }

        return coordinator


# Helper functions for tests


def create_modbus_response(registers: list[int] | None = None, is_error: bool = False) -> MagicMock:
    """Create a mock Modbus response with specified values."""
    response = MagicMock()
    response.isError.return_value = is_error
    if registers is not None:
        response.registers = registers
    return response


def create_32bit_registers(value: int) -> list[int]:
    """Convert a 32-bit value to two 16-bit registers."""
    high_word = (value >> 16) & 0xFFFF
    low_word = value & 0xFFFF
    return [high_word, low_word]
