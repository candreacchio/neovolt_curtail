# Bytewatt Export Limiter

A Home Assistant integration to automatically control solar export limits on Bytewatt/NeoVolt battery systems based on electricity feed-in prices.

## Features

- **Price-based automation**: Automatically curtail exports when feed-in prices are low (e.g., ≤0 c/kWh)
- **Respects grid limits**: Uses the grid operator's limit as maximum, never exceeds it
- **Auto re-apply**: If the grid resets your limit, automatically re-applies your curtailment
- **Manual override**: Set export limits manually via Home Assistant
- **5-second debounce**: Prevents rapid toggling on price fluctuations

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → Custom repositories
3. Add this repository URL and select "Integration"
4. Search for "Bytewatt Export Limiter" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/bytewatt_export_limiter` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Bytewatt Export Limiter"
4. Enter your Modbus connection settings:
   - **IP Address**: Your inverter's IP (e.g., 192.168.20.29)
   - **Port**: 502 (default)
   - **Slave Address**: 85 (default for Bytewatt)
5. Configure price automation:
   - **Price Entity**: Select your Amber Electric price sensor
   - **Price Threshold**: Curtail when price is at or below this (e.g., 0 c/kWh)
   - **Curtailed Limit**: Export limit when curtailing (e.g., 0W)
   - **Poll Interval**: How often to check Modbus (default: 60s)

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.bytewatt_export_limit` | Sensor | Current export limit (W) |
| `sensor.bytewatt_grid_max` | Sensor | Grid's maximum allowed limit (W) |
| `sensor.bytewatt_current_price` | Sensor | Current electricity price (c/kWh) |
| `binary_sensor.bytewatt_curtailed` | Binary Sensor | ON when curtailed |
| `number.bytewatt_manual_limit` | Number | Manual limit override (W) |
| `switch.bytewatt_automation` | Switch | Enable/disable price automation |

## How It Works

### Price-Based Logic

```
IF automation enabled AND price ≤ threshold:
    Set export limit to curtailed_limit (e.g., 0W)
ELSE:
    Set export limit to grid's maximum
```

### Grid Override Handling

The grid operator can change your export limit at any time. This integration:
1. Detects when the grid changes the limit
2. Updates the known grid maximum
3. Re-applies your curtailment if it's lower than the grid's new limit

## Modbus Registers

| Address | Name | Description |
|---------|------|-------------|
| 0x08A2 | Export Limit | Active export limit in watts (R/W) |
| 0x08A5 | Default Limit | Grid's maximum limit in watts (R/W) |

## Requirements

- Home Assistant 2024.1.0 or newer
- Bytewatt/NeoVolt battery system with Modbus TCP access
- Network access to inverter (port 502)

## Troubleshooting

### Cannot connect to inverter
- Verify the IP address is correct
- Check that port 502 is accessible
- Ensure no firewall is blocking Modbus TCP

### Limit not being applied
- Check that the automation switch is enabled
- Verify the price entity is providing valid data
- Check Home Assistant logs for errors

## License

MIT
