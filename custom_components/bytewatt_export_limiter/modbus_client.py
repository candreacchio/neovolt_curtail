"""
Async Modbus TCP client wrapper for Bytewatt battery system.

This module provides a thread-safe async wrapper around pymodbus AsyncModbusTcpClient
with automatic reconnection and error handling for Home Assistant integration.
"""

import asyncio
import logging
from typing import Optional, List

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)

# Default connection settings
DEFAULT_PORT = 502
DEFAULT_SLAVE = 85  # 0x55
DEFAULT_TIMEOUT = 10  # seconds

# Register addresses (commonly used)
REG_BATTERY_VOLTAGE = 0x0100
REG_BATTERY_CURRENT = 0x0101
REG_BATTERY_SOC = 0x0102
REG_BATTERY_STATUS = 0x0103
REG_BATTERY_POWER = 0x0126
REG_MAX_FEED_GRID_PCT = 0x0800
REG_PV_CAPACITY_STORAGE = 0x0801  # 32-bit value
REG_SYSTEM_MODE = 0x0805


class AsyncModbusClient:
    """Thread-safe async Modbus TCP client for Bytewatt battery system."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        slave_address: int = DEFAULT_SLAVE,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize the async Modbus client.

        Args:
            host: IP address or hostname of the Modbus device
            port: Modbus TCP port (default: 502)
            slave_address: Modbus slave/device ID (default: 85/0x55)
            timeout: Connection timeout in seconds (default: 10)
        """
        self.host = host
        self.port = port
        self.slave_address = slave_address
        self.timeout = timeout

        self._client: Optional[AsyncModbusTcpClient] = None
        self._lock = asyncio.Lock()  # Thread safety for pymodbus
        self._connected = False

    async def connect(self) -> bool:
        """
        Establish connection to the Modbus device.

        Returns:
            True if connection successful, False otherwise
        """
        async with self._lock:
            try:
                if self._client is None:
                    self._client = AsyncModbusTcpClient(
                        host=self.host,
                        port=self.port,
                        timeout=self.timeout,
                    )

                if not self._connected:
                    # Add timeout to connect (Critical fix #3)
                    try:
                        await asyncio.wait_for(
                            self._client.connect(),
                            timeout=float(self.timeout)
                        )
                    except asyncio.TimeoutError:
                        _LOGGER.error(
                            "Connection to %s:%s timed out after %ss",
                            self.host,
                            self.port,
                            self.timeout,
                        )
                        self._connected = False
                        return False
                    self._connected = self._client.connected

                    if self._connected:
                        _LOGGER.info(
                            "Connected to Modbus device at %s:%s (slave %s)",
                            self.host,
                            self.port,
                            self.slave_address,
                        )
                    else:
                        _LOGGER.error(
                            "Failed to connect to Modbus device at %s:%s",
                            self.host,
                            self.port,
                        )

                return self._connected

            except Exception as err:
                _LOGGER.error(
                    "Error connecting to Modbus device at %s:%s: %s",
                    self.host,
                    self.port,
                    err,
                )
                self._connected = False
                return False

    async def disconnect(self) -> None:
        """Close the Modbus connection."""
        async with self._lock:
            if self._client is not None:
                try:
                    self._client.close()
                    _LOGGER.info(
                        "Disconnected from Modbus device at %s:%s",
                        self.host,
                        self.port,
                    )
                except Exception as err:
                    _LOGGER.error("Error disconnecting from Modbus device: %s", err)
                finally:
                    self._connected = False
                    self._client = None

    @property
    def is_connected(self) -> bool:
        """Check if the client is currently connected."""
        return self._connected and self._client is not None

    async def _ensure_connected(self) -> bool:
        """
        Ensure the client is connected, attempting reconnection if needed.

        Returns:
            True if connected, False otherwise
        """
        if not self.is_connected:
            _LOGGER.debug("Not connected, attempting to reconnect...")
            return await self.connect()
        return True

    async def read_register(
        self,
        address: int,
        count: int = 1,
    ) -> Optional[List[int]]:
        """
        Read holding register(s) from the Modbus device.

        Args:
            address: Register address (e.g., 0x0102 for SOC)
            count: Number of consecutive registers to read (default: 1)

        Returns:
            List of register values (unsigned 16-bit integers), or None on error
        """
        async with self._lock:
            try:
                # Ensure we're connected
                if not await self._ensure_connected():
                    return None

                # Read holding registers with timeout (Critical fix #3)
                try:
                    result = await asyncio.wait_for(
                        self._client.read_holding_registers(
                            address=address,
                            count=count,
                            device_id=self.slave_address,
                        ),
                        timeout=float(self.timeout)
                    )
                except asyncio.TimeoutError:
                    _LOGGER.error(
                        "Modbus read at address 0x%04X timed out after %ss",
                        address,
                        self.timeout,
                    )
                    self._connected = False
                    return None

                # Check for errors
                if result.isError():
                    _LOGGER.error(
                        "Modbus read error at address 0x%04X: %s",
                        address,
                        result,
                    )
                    # Mark as disconnected to trigger reconnect on next operation
                    self._connected = False
                    return None

                return result.registers

            except ModbusException as err:
                _LOGGER.error(
                    "Modbus exception reading address 0x%04X: %s",
                    address,
                    err,
                )
                self._connected = False
                return None
            except Exception as err:
                _LOGGER.error(
                    "Unexpected error reading address 0x%04X: %s",
                    address,
                    err,
                )
                self._connected = False
                return None

    async def write_register(
        self,
        address: int,
        value: int,
    ) -> bool:
        """
        Write a single holding register to the Modbus device.

        Args:
            address: Register address
            value: Value to write (0-65535, unsigned 16-bit)

        Returns:
            True on success, False on error
        """
        async with self._lock:
            try:
                # Ensure we're connected
                if not await self._ensure_connected():
                    return False

                # Write single register with timeout (Critical fix #3)
                try:
                    result = await asyncio.wait_for(
                        self._client.write_register(
                            address=address,
                            value=value,
                            device_id=self.slave_address,
                        ),
                        timeout=float(self.timeout)
                    )
                except asyncio.TimeoutError:
                    _LOGGER.error(
                        "Modbus write at address 0x%04X timed out after %ss",
                        address,
                        self.timeout,
                    )
                    self._connected = False
                    return False

                # Check for errors
                if result.isError():
                    _LOGGER.error(
                        "Modbus write error at address 0x%04X (value=%s): %s",
                        address,
                        value,
                        result,
                    )
                    # Mark as disconnected to trigger reconnect on next operation
                    self._connected = False
                    return False

                _LOGGER.debug(
                    "Successfully wrote value %s to address 0x%04X",
                    value,
                    address,
                )
                return True

            except ModbusException as err:
                _LOGGER.error(
                    "Modbus exception writing address 0x%04X (value=%s): %s",
                    address,
                    value,
                    err,
                )
                self._connected = False
                return False
            except Exception as err:
                _LOGGER.error(
                    "Unexpected error writing address 0x%04X (value=%s): %s",
                    address,
                    value,
                    err,
                )
                self._connected = False
                return False

    async def read_register_single(self, address: int) -> Optional[int]:
        """
        Read a single holding register and return its raw value.

        Args:
            address: Register address

        Returns:
            Raw register value (unsigned 16-bit integer), or None on error
        """
        registers = await self.read_register(address, count=1)
        if registers:
            return registers[0]
        return None

    async def read_register_32bit(self, address: int) -> Optional[int]:
        """
        Read a 32-bit value from two consecutive registers.

        The value is constructed as: (register[0] << 16) | register[1]

        Args:
            address: Starting register address

        Returns:
            32-bit unsigned integer value, or None on error
        """
        registers = await self.read_register(address, count=2)
        if registers and len(registers) == 2:
            # Combine two 16-bit registers into 32-bit value
            return (registers[0] << 16) | registers[1]
        return None

    async def write_register_32bit(
        self, address: int, value: int, max_retries: int = 2
    ) -> bool:
        """
        Write a 32-bit value to two consecutive registers.

        The value is split as: register[0] = (value >> 16), register[1] = (value & 0xFFFF)

        Args:
            address: Starting register address
            value: 32-bit unsigned integer value to write
            max_retries: Number of retries on partial failure

        Returns:
            True on success, False on error
        """
        # Medium fix #10: Bounds check for 32-bit value
        if not (0 <= value <= 0xFFFFFFFF):
            _LOGGER.error(
                "Invalid 32-bit value: %s (must be 0-4294967295)", value
            )
            return False

        # Split 32-bit value into two 16-bit registers
        high_word = (value >> 16) & 0xFFFF
        low_word = value & 0xFFFF

        for attempt in range(max_retries + 1):
            # Write high word first
            success_high = await self.write_register(address, high_word)
            if not success_high:
                _LOGGER.error(
                    "Failed to write high word of 32-bit value at 0x%04X (attempt %d/%d)",
                    address,
                    attempt + 1,
                    max_retries + 1,
                )
                continue  # Retry the whole operation

            # Write low word
            success_low = await self.write_register(address + 1, low_word)
            if not success_low:
                _LOGGER.error(
                    "Failed to write low word of 32-bit value at 0x%04X (attempt %d/%d)",
                    address + 1,
                    attempt + 1,
                    max_retries + 1,
                )
                # Critical fix #3: Attempt recovery by re-writing high word
                # This ensures the device gets a consistent value on retry
                if attempt < max_retries:
                    _LOGGER.warning(
                        "Partial 32-bit write detected, will retry entire operation"
                    )
                    continue
                else:
                    _LOGGER.error(
                        "Partial 32-bit write failure at 0x%04X after %d attempts - "
                        "device may be in inconsistent state",
                        address,
                        max_retries + 1,
                    )
                    return False

            # Both writes succeeded
            return True

        return False

    async def read_soc(self) -> Optional[float]:
        """
        Read battery State of Charge.

        Returns:
            SOC as percentage (0.0-100.0), or None on error
        """
        value = await self.read_register_single(REG_BATTERY_SOC)
        if value is not None:
            return value / 10.0  # Scale factor 0.1
        return None

    async def read_voltage(self) -> Optional[float]:
        """
        Read battery voltage.

        Returns:
            Voltage in volts, or None on error
        """
        value = await self.read_register_single(REG_BATTERY_VOLTAGE)
        if value is not None:
            return value / 10.0  # Scale factor 0.1
        return None

    async def read_current(self) -> Optional[float]:
        """
        Read battery current.

        Returns:
            Current in amps (positive=discharge, negative=charge), or None on error
        """
        value = await self.read_register_single(REG_BATTERY_CURRENT)
        if value is not None:
            # Convert to signed 16-bit
            if value > 32767:
                value -= 65536
            return value / 10.0  # Scale factor 0.1
        return None

    async def read_power(self) -> Optional[int]:
        """
        Read battery power.

        Returns:
            Power in watts (positive=discharge, negative=charge), or None on error
        """
        value = await self.read_register_single(REG_BATTERY_POWER)
        if value is not None:
            # Convert to signed 16-bit
            if value > 32767:
                value -= 65536
            return value
        return None

    async def read_max_feed_grid_pct(self) -> Optional[int]:
        """
        Read maximum feed into grid percentage setting.

        Returns:
            Percentage (0-100), or None on error
        """
        return await self.read_register_single(REG_MAX_FEED_GRID_PCT)

    async def write_max_feed_grid_pct(self, percentage: int) -> bool:
        """
        Write maximum feed into grid percentage setting.

        Args:
            percentage: Percentage value (0-100)

        Returns:
            True on success, False on error
        """
        if not 0 <= percentage <= 100:
            _LOGGER.error("Invalid percentage value: %s (must be 0-100)", percentage)
            return False

        return await self.write_register(REG_MAX_FEED_GRID_PCT, percentage)
