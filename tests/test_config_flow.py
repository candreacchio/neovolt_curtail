"""Tests for config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.bytewatt_export_limiter.config_flow import (
    BytewattConfigFlow,
    BytewattOptionsFlow,
    CannotConnect,
    InvalidAuth,
)
from custom_components.bytewatt_export_limiter.const import (
    CONF_CURTAILED_LIMIT,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_MODBUS_SLAVE,
    CONF_POLL_INTERVAL,
    CONF_PRICE_ENTITY,
    CONF_PRICE_THRESHOLD,
    DEFAULT_PORT,
    DEFAULT_SLAVE,
)


class TestConfigFlowUserStep:
    """Test the user config flow step (Modbus connection)."""

    @pytest.mark.asyncio
    async def test_form_shows_on_init(self):
        """Test that the form is shown when flow is initialized."""
        flow = BytewattConfigFlow()
        flow.hass = MagicMock()

        result = await flow.async_step_user()

        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_connection_success_proceeds_to_automation(self):
        """Test successful connection proceeds to automation step."""
        flow = BytewattConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}

        # Mock the unique_id methods to avoid already_configured abort
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        with patch(
            "custom_components.bytewatt_export_limiter.config_flow.validate_modbus_connection"
        ) as mock_validate:
            mock_validate.return_value = {"title": "Bytewatt (192.168.1.100)"}

            result = await flow.async_step_user(
                {
                    CONF_MODBUS_HOST: "192.168.1.100",
                    CONF_MODBUS_PORT: DEFAULT_PORT,
                    CONF_MODBUS_SLAVE: DEFAULT_SLAVE,
                }
            )

        assert result["type"] == "form"
        assert result["step_id"] == "automation"

    @pytest.mark.asyncio
    async def test_connection_failure_shows_error(self):
        """Test connection failure shows error."""
        flow = BytewattConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}

        # Mock the unique_id methods
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        with patch(
            "custom_components.bytewatt_export_limiter.config_flow.validate_modbus_connection"
        ) as mock_validate:
            mock_validate.side_effect = CannotConnect("Connection failed")

            result = await flow.async_step_user(
                {
                    CONF_MODBUS_HOST: "192.168.1.100",
                    CONF_MODBUS_PORT: DEFAULT_PORT,
                    CONF_MODBUS_SLAVE: DEFAULT_SLAVE,
                }
            )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "errors" in result
        assert "base" in result["errors"]
        assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_connection_invalid_slave_shows_error(self):
        """Test invalid slave address shows error."""
        flow = BytewattConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}

        # Mock the unique_id methods
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        with patch(
            "custom_components.bytewatt_export_limiter.config_flow.validate_modbus_connection"
        ) as mock_validate:
            mock_validate.side_effect = InvalidAuth("Invalid slave")

            result = await flow.async_step_user(
                {
                    CONF_MODBUS_HOST: "192.168.1.100",
                    CONF_MODBUS_PORT: DEFAULT_PORT,
                    CONF_MODBUS_SLAVE: DEFAULT_SLAVE,
                }
            )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "errors" in result
        assert result["errors"]["base"] == "invalid_slave"

    @pytest.mark.asyncio
    async def test_connection_timeout_shows_error(self):
        """Test connection timeout shows error."""
        flow = BytewattConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}

        # Mock the unique_id methods
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        with patch(
            "custom_components.bytewatt_export_limiter.config_flow.validate_modbus_connection"
        ) as mock_validate:
            mock_validate.side_effect = CannotConnect("Connection timed out")

            result = await flow.async_step_user(
                {
                    CONF_MODBUS_HOST: "192.168.1.100",
                    CONF_MODBUS_PORT: DEFAULT_PORT,
                    CONF_MODBUS_SLAVE: DEFAULT_SLAVE,
                }
            )

        assert result["type"] == "form"
        assert "errors" in result
        assert result["errors"]["base"] == "cannot_connect"


class TestConfigFlowAutomationStep:
    """Test the automation config flow step."""

    @pytest.mark.asyncio
    async def test_automation_step_creates_entry(self):
        """Test automation step creates config entry."""
        flow = BytewattConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}

        # Mock the unique_id methods
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        # Mock state for price entity
        price_state = MagicMock()
        price_state.state = "0.10"
        flow.hass.states.get = MagicMock(return_value=price_state)

        # First complete user step with mocked validation
        with patch(
            "custom_components.bytewatt_export_limiter.config_flow.validate_modbus_connection"
        ) as mock_validate:
            mock_validate.return_value = {"title": "Bytewatt (192.168.1.100)"}
            await flow.async_step_user(
                {
                    CONF_MODBUS_HOST: "192.168.1.100",
                    CONF_MODBUS_PORT: DEFAULT_PORT,
                    CONF_MODBUS_SLAVE: DEFAULT_SLAVE,
                }
            )

        # Then complete automation step
        result = await flow.async_step_automation(
            {
                CONF_PRICE_ENTITY: "sensor.electricity_price",
                CONF_PRICE_THRESHOLD: 0.05,
                CONF_CURTAILED_LIMIT: 0,
                CONF_POLL_INTERVAL: 60,
            }
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "Bytewatt (192.168.1.100)"
        assert CONF_MODBUS_HOST in result["data"]
        assert CONF_PRICE_ENTITY in result["data"]

    @pytest.mark.asyncio
    async def test_automation_step_invalid_price_entity(self):
        """Test automation step with invalid price entity."""
        flow = BytewattConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}

        # Mock the unique_id methods
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        # Mock state for price entity - doesn't exist
        flow.hass.states.get = MagicMock(return_value=None)

        # First complete user step with mocked validation
        with patch(
            "custom_components.bytewatt_export_limiter.config_flow.validate_modbus_connection"
        ) as mock_validate:
            mock_validate.return_value = {"title": "Bytewatt (192.168.1.100)"}
            await flow.async_step_user(
                {
                    CONF_MODBUS_HOST: "192.168.1.100",
                    CONF_MODBUS_PORT: DEFAULT_PORT,
                    CONF_MODBUS_SLAVE: DEFAULT_SLAVE,
                }
            )

        # Then complete automation step with invalid entity
        result = await flow.async_step_automation(
            {
                CONF_PRICE_ENTITY: "sensor.nonexistent",
                CONF_PRICE_THRESHOLD: 0.05,
                CONF_CURTAILED_LIMIT: 0,
                CONF_POLL_INTERVAL: 60,
            }
        )

        assert result["type"] == "form"
        assert result["step_id"] == "automation"
        assert "errors" in result
        assert result["errors"]["base"] == "invalid_price_entity"


class TestConfigFlowDuplicateCheck:
    """Test duplicate entry checking."""

    @pytest.mark.asyncio
    async def test_duplicate_entry_aborts(self):
        """Test that duplicate entries are aborted."""
        from homeassistant.data_entry_flow import AbortFlow

        flow = BytewattConfigFlow()
        flow.hass = MagicMock()
        flow.context = {}

        # Configure the flow to abort when checking unique_id
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock(side_effect=AbortFlow("already_configured"))

        # Try to create an entry - this should raise AbortFlow
        # When called outside the HA framework, AbortFlow propagates as an exception
        with pytest.raises(AbortFlow) as exc_info:
            await flow.async_step_user(
                {
                    CONF_MODBUS_HOST: "192.168.1.100",
                    CONF_MODBUS_PORT: DEFAULT_PORT,
                    CONF_MODBUS_SLAVE: DEFAULT_SLAVE,
                }
            )

        assert exc_info.value.reason == "already_configured"


class TestValidateModbusConnection:
    """Test the validate_modbus_connection function."""

    @pytest.mark.asyncio
    async def test_validate_success(self):
        """Test successful connection validation."""
        from custom_components.bytewatt_export_limiter.config_flow import (
            validate_modbus_connection,
        )

        mock_hass = MagicMock()

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_class:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.close = MagicMock()

            # Mock successful register read
            mock_response = MagicMock()
            mock_response.isError.return_value = False
            mock_response.registers = [0, 5000]
            mock_client.read_holding_registers = AsyncMock(return_value=mock_response)

            mock_class.return_value = mock_client

            result = await validate_modbus_connection(mock_hass, "192.168.1.100", 502, 85)

        assert "title" in result
        assert "Bytewatt" in result["title"]

    @pytest.mark.asyncio
    async def test_validate_connection_fails(self):
        """Test connection failure."""
        from custom_components.bytewatt_export_limiter.config_flow import (
            CannotConnect,
            validate_modbus_connection,
        )

        mock_hass = MagicMock()

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_class:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=False)
            mock_client.close = MagicMock()

            mock_class.return_value = mock_client

            with pytest.raises(CannotConnect):
                await validate_modbus_connection(mock_hass, "192.168.1.100", 502, 85)

    @pytest.mark.asyncio
    async def test_validate_register_read_fails(self):
        """Test register read failure."""
        from custom_components.bytewatt_export_limiter.config_flow import (
            InvalidAuth,
            validate_modbus_connection,
        )

        mock_hass = MagicMock()

        with patch("pymodbus.client.AsyncModbusTcpClient") as mock_class:
            mock_client = AsyncMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.close = MagicMock()

            # Mock error register read
            mock_response = MagicMock()
            mock_response.isError.return_value = True
            mock_client.read_holding_registers = AsyncMock(return_value=mock_response)

            mock_class.return_value = mock_client

            with pytest.raises(InvalidAuth):
                await validate_modbus_connection(mock_hass, "192.168.1.100", 502, 85)


class TestOptionsFlow:
    """Test options flow."""

    @pytest.mark.asyncio
    async def test_options_flow_init(self):
        """Test options flow initialization."""
        # Create mock entry
        entry = MagicMock()
        entry.data = {
            CONF_PRICE_ENTITY: "sensor.electricity_price",
            CONF_PRICE_THRESHOLD: 0.05,
            CONF_CURTAILED_LIMIT: 0,
            CONF_POLL_INTERVAL: 60,
        }
        entry.options = {}

        flow = BytewattOptionsFlow(entry)
        flow.hass = MagicMock()

        # Mock state for price entity
        price_state = MagicMock()
        price_state.state = "0.10"
        flow.hass.states.get = MagicMock(return_value=price_state)

        result = await flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_flow_update(self):
        """Test options flow update."""
        # Create mock entry
        entry = MagicMock()
        entry.data = {
            CONF_PRICE_ENTITY: "sensor.electricity_price",
            CONF_PRICE_THRESHOLD: 0.05,
            CONF_CURTAILED_LIMIT: 0,
            CONF_POLL_INTERVAL: 60,
        }
        entry.options = {}

        flow = BytewattOptionsFlow(entry)
        flow.hass = MagicMock()

        # Mock state for price entity
        price_state = MagicMock()
        price_state.state = "0.10"
        flow.hass.states.get = MagicMock(return_value=price_state)

        result = await flow.async_step_init(
            {
                CONF_PRICE_ENTITY: "sensor.new_price",
                CONF_PRICE_THRESHOLD: 0.10,
                CONF_CURTAILED_LIMIT: 1000,
                CONF_POLL_INTERVAL: 30,
            }
        )

        assert result["type"] == "create_entry"
        assert result["data"][CONF_PRICE_THRESHOLD] == 0.10
        assert result["data"][CONF_CURTAILED_LIMIT] == 1000

    @pytest.mark.asyncio
    async def test_options_flow_invalid_price_entity(self):
        """Test options flow rejects invalid price entity."""
        # Create mock entry
        entry = MagicMock()
        entry.data = {
            CONF_PRICE_ENTITY: "sensor.electricity_price",
            CONF_PRICE_THRESHOLD: 0.05,
            CONF_CURTAILED_LIMIT: 0,
            CONF_POLL_INTERVAL: 60,
        }
        entry.options = {}

        flow = BytewattOptionsFlow(entry)
        flow.hass = MagicMock()

        # Mock - entity doesn't exist
        flow.hass.states.get = MagicMock(return_value=None)

        result = await flow.async_step_init(
            {
                CONF_PRICE_ENTITY: "sensor.nonexistent",
                CONF_PRICE_THRESHOLD: 0.10,
                CONF_CURTAILED_LIMIT: 1000,
                CONF_POLL_INTERVAL: 30,
            }
        )

        assert result["type"] == "form"
        assert "errors" in result
        assert result["errors"]["base"] == "invalid_price_entity"
