"""Tests for AsyncModbusClient."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.bytewatt_export_limiter.modbus_client import AsyncModbusClient

from .conftest import create_32bit_registers, create_modbus_response


class TestAsyncModbusClientConnection:
    """Test connection handling."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100", port=502, slave_address=85)
            result = await client.connect()

            assert result is True
            assert client.is_connected is True
            mock_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=False)
            mock_client.connected = False
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            result = await client.connect()

            assert result is False
            assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        """Test connection timeout."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()

            async def slow_connect():
                await asyncio.sleep(20)  # Longer than timeout

            mock_client.connect = slow_connect
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100", timeout=1)
            result = await client.connect()

            assert result is False
            assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_exception(self):
        """Test connection exception handling."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(side_effect=Exception("Connection refused"))
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            result = await client.connect()

            assert result is False
            assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.close = MagicMock()
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            await client.disconnect()

            assert client.is_connected is False
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_connected_property(self):
        """Test is_connected property."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")

            # Before connection
            assert client.is_connected is False

            # After connection
            await client.connect()
            assert client.is_connected is True


class TestAsyncModbusClientRead:
    """Test read operations."""

    @pytest.mark.asyncio
    async def test_read_register_success(self):
        """Test successful register read."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response([1234])
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_register(0x0102)

            assert result == [1234]

    @pytest.mark.asyncio
    async def test_read_register_error_response(self):
        """Test register read with error response."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.close = MagicMock()
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response(is_error=True)
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_register(0x0102)

            assert result is None

    @pytest.mark.asyncio
    async def test_read_register_timeout(self):
        """Test register read timeout."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.close = MagicMock()

            async def slow_read(*args, **kwargs):
                await asyncio.sleep(20)

            mock_client.read_holding_registers = slow_read
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100", timeout=1)
            await client.connect()
            result = await client.read_register(0x0102)

            assert result is None

    @pytest.mark.asyncio
    async def test_read_register_32bit_success(self):
        """Test successful 32-bit register read."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            # 32-bit value: 65536 = (1 << 16) | 0
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response([1, 0])
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_register_32bit(0x08A2)

            assert result == 65536

    @pytest.mark.asyncio
    async def test_read_register_32bit_large_value(self):
        """Test 32-bit register read with large value."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            # 10000W = 0x00002710 = [0, 10000]
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response(create_32bit_registers(10000))
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_register_32bit(0x08A2)

            assert result == 10000

    @pytest.mark.asyncio
    async def test_read_register_single(self):
        """Test single register read convenience method."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response([850])  # SOC 85.0%
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_register_single(0x0102)

            assert result == 850


class TestAsyncModbusClientWrite:
    """Test write operations."""

    @pytest.mark.asyncio
    async def test_write_register_success(self):
        """Test successful register write."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.write_register = AsyncMock(return_value=create_modbus_response())
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.write_register(0x0800, 50)

            assert result is True
            mock_client.write_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_register_error_response(self):
        """Test register write with error response."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.close = MagicMock()
            mock_client.write_register = AsyncMock(
                return_value=create_modbus_response(is_error=True)
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.write_register(0x0800, 50)

            assert result is False

    @pytest.mark.asyncio
    async def test_write_register_32bit_success(self):
        """Test successful 32-bit register write."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.write_register = AsyncMock(return_value=create_modbus_response())
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.write_register_32bit(0x08A2, 5000)

            assert result is True
            # Should write both high and low words
            assert mock_client.write_register.call_count == 2

    @pytest.mark.asyncio
    async def test_write_register_32bit_invalid_value(self):
        """Test 32-bit write with invalid value."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()

            # Negative value
            result = await client.write_register_32bit(0x08A2, -1)
            assert result is False

            # Value too large
            result = await client.write_register_32bit(0x08A2, 0x100000000)
            assert result is False

    @pytest.mark.asyncio
    async def test_write_register_32bit_partial_failure_retry(self):
        """Test 32-bit write retry on partial failure."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.close = MagicMock()

            # First attempt fails completely, second succeeds
            call_results = [
                create_modbus_response(),  # First high word succeeds
                create_modbus_response(is_error=True),  # First low word fails
                create_modbus_response(),  # Second high word succeeds
                create_modbus_response(),  # Second low word succeeds
            ]
            mock_client.write_register = AsyncMock(side_effect=call_results)
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.write_register_32bit(0x08A2, 5000, max_retries=2)

            assert result is True
            assert mock_client.write_register.call_count == 4


class TestAsyncModbusClientConvenienceMethods:
    """Test convenience methods for specific registers."""

    @pytest.mark.asyncio
    async def test_read_soc(self):
        """Test SOC reading with scale factor."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response([850])  # 85.0%
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_soc()

            assert result == 85.0

    @pytest.mark.asyncio
    async def test_read_voltage(self):
        """Test voltage reading with scale factor."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response([520])  # 52.0V
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_voltage()

            assert result == 52.0

    @pytest.mark.asyncio
    async def test_read_current_positive(self):
        """Test positive current reading (discharge)."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response([100])  # 10.0A discharge
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_current()

            assert result == 10.0

    @pytest.mark.asyncio
    async def test_read_current_negative(self):
        """Test negative current reading (charge)."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            # -10.0A as unsigned 16-bit: 65536 - 100 = 65436
            mock_client.read_holding_registers = AsyncMock(
                return_value=create_modbus_response([65436])
            )
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.read_current()

            assert result == -10.0

    @pytest.mark.asyncio
    async def test_write_max_feed_grid_pct_valid(self):
        """Test writing valid percentage."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_client.write_register = AsyncMock(return_value=create_modbus_response())
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()
            result = await client.write_max_feed_grid_pct(50)

            assert result is True

    @pytest.mark.asyncio
    async def test_write_max_feed_grid_pct_invalid(self):
        """Test writing invalid percentage."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()

            # Negative
            result = await client.write_max_feed_grid_pct(-1)
            assert result is False

            # Over 100
            result = await client.write_max_feed_grid_pct(101)
            assert result is False


class TestAsyncModbusClientThreadSafety:
    """Test thread safety with lock."""

    @pytest.mark.asyncio
    async def test_concurrent_reads(self):
        """Test concurrent read operations are serialized."""
        with patch(
            "custom_components.bytewatt_export_limiter.modbus_client.AsyncModbusTcpClient"
        ) as mock_pymodbus:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.connected = True

            call_order = []

            async def mock_read(*args, **kwargs):
                call_order.append("start")
                await asyncio.sleep(0.1)
                call_order.append("end")
                return create_modbus_response([1234])

            mock_client.read_holding_registers = mock_read
            mock_pymodbus.return_value = mock_client

            client = AsyncModbusClient("192.168.1.100")
            await client.connect()

            # Run two reads concurrently
            await asyncio.gather(
                client.read_register(0x0100),
                client.read_register(0x0101),
            )

            # Due to lock, operations should be serialized
            assert call_order == ["start", "end", "start", "end"]
