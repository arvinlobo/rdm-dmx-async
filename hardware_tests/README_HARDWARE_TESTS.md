# Hardware Device API Tests

Test scripts for validating RDM device APIs with real hardware.

## Quick Start with uv

```bash
# Full test suite (all APIs)
uv run hardware_tests/hardware_device_api_test.py

# Quick test (specific API)
uv run hardware_tests/quick_device_test.py --test sensors

# With specific port
uv run hardware_tests/quick_device_test.py --port COM3

# Enable debug logging
uv run hardware_tests/quick_device_test.py --test all --debug
```

## Test Scripts

### 1. Comprehensive Hardware Test (`hardware_device_api_test.py`)

Full test suite that validates all device API modules systematically.

**Features:**
- Tests all 16 API modules
- Detailed logging with pass/fail status
- Test summary report
- Safe testing (restores original values)

**Usage:**
```bash
# Using uv (recommended)
uv run hardware_tests/hardware_device_api_test.py

# Auto-detect Enttec port
uv run hardware_tests/hardware_device_api_test.py

# Specify port
uv run hardware_tests/hardware_device_api_test.py --port COM3

# Enable debug logging
uv run hardware_tests/hardware_device_api_test.py --debug

# Or using python directly
python hardware_tests/hardware_device_api_test.py
```

**Tested APIs:**
- Device Label (GET/SET)
- DMX Config (address, personality)
- Device Control (identify, reset)
- Sensors (get values, definitions)
- Device Maintenance (hours, power cycles)
- Device Info (model, manufacturer, versions)
- DMX Slots (slot info, descriptions)
- DMX Modes (startup mode, response time)
- Lamp Control (hours, strikes, state, on mode)
- Display Settings (invert, level)
- Position Config (pan/tilt invert, swap, RTC)
- Power Control (power state)
- Self Test (perform, descriptions)
- Preset Control (playback, status, merge mode)
- System Info (supported PIDs, language)

**Example Output:**
```
======================================================================
RDM Device API Hardware Test Suite
======================================================================
Connected to port: COM3
Testing device: UID=454E00000001

--- Device Label API ---
✓ PASS - device_label.get(): "Living Room Light"
✓ PASS - device_label.set(): "TEST_143022"
✓ PASS - device_label.set() verify: "TEST_143022"

--- DMX Config API ---
✓ PASS - dmx_config.get_start_address(): Address: 1
✓ PASS - dmx_config.set_start_address(): Set to: 100
✓ PASS - dmx_config.get_personality(): Current: 1/4

...

======================================================================
Test Summary
======================================================================
Passed: 45/48
Failed: 3/48
======================================================================
```

---

### 2. Quick Test (`quick_device_test.py`)

Lightweight script for rapid testing of specific APIs.

**Features:**
- Fast execution
- Targeted testing
- Interactive output
- Easy to read results

**Usage:**
```bash
# Using uv (recommended)
# Run all tests
uv run hardware_tests/quick_device_test.py

# Test specific API
uv run hardware_tests/quick_device_test.py --test sensors
uv run hardware_tests/quick_device_test.py --test dmx
uv run hardware_tests/quick_device_test.py --test label
uv run hardware_tests/quick_device_test.py --test identify

# Specify port
uv run hardware_tests/quick_device_test.py --port COM3 --test sensors

# Enable debug logging
uv run hardware_tests/quick_device_test.py --test all --debug

# Or using python directly
python hardware_tests/quick_device_test.py
```

**Available Tests:**
- `info` - Basic device information
- `sensors` - Sensor values and definitions
- `dmx` - DMX configuration (address, personality)
- `label` - Device label GET/SET
- `identify` - Identify mode (blinking)
- `slots` - DMX slot info and descriptions
- `maintenance` - Device hours and power cycles
- `system` - System info and supported PIDs
- `all` - Run all tests (default)

**Example Output:**
```
Connected to port: COM3
Testing device: UID=454E00000001

=== Basic Device Information ===
UID: 454E00000001
Manufacturer: abc
Model: RDM Test Device
Device Label: Living Room Light
Software Version: FW001.1
RDM Protocol: 1.0
DMX Address: 1
DMX Footprint: 4
Personality: 1/4
Sensors: 3
Sub-devices: 0

=== Sensor Testing ===
Sensor count: 3

Sensor Definitions:
  Sensor 0:
    Type: Voltage
    Unit: Volts DC
    Range: 0 - 60
  Sensor 1:
    Type: Current
    Unit: Amperes
    Range: 0 - 10
  Sensor 2:
    Type: Temperature
    Unit: Degrees Celsius
    Range: -40 - 125

Sensor Values:
  Sensor 0:
    Present: 24000
    Low: 23500
    High: 24500
    Recorded: 24000

==================================================
Test completed successfully!
==================================================
```

---

## Hardware Requirements

1. **Enttec USB DMX Interface**
   - Enttec USB Pro
   - Or compatible RDM-capable DMX interface

2. **RDM Device**
   - Any RDM E1.20 compliant device
   - Connected to DMX output of Enttec interface

3. **USB Connection**
   - Enttec interface connected via USB
   - Driver installed (automatic on Windows 10+)

---

## Troubleshooting
uv run python -c "from rdm_dmx_async.application import PortDetectionService; print(PortDetectionService().list_all_ports())"

# Then specify port manually
uv rut available ports first
python -c "from rdm_dmx_async.application import PortDetectionService; print(PortDetectionService().list_all_ports())"

# Then specify port manually
python hardware_tests/quick_device_test.py --port COM3
```

### No Devices Found
1. Check DMX cable connection
2. Verify device is powered on
3. Check device supports RDM (not all DMX devices do)
4. Try re-discovering:
   ```bash
   uv run hardware_tests/quick_device_test.py --debug
   ```

### Timeout Errors
- Increase timeout in test if needed
- Check DMX cable quality
- Ensure only one RDM device on network
- Verify Enttec interface firmware is up to date

### API Not Supported
- Some devices don't support all PIDs
- Test marks as "Not supported" - this is normal
- Check device documentation for supported PIDs

---

## Development Workflow

### 1. Quick Iteration
Use `quick_device_test.py` during development:
```bash
# Test specific API you're working on
uv run hardware_tests/quick_device_test.py --test sensors

# Add debug logging to see protocol details
uv run hardware_tests/quick_device_test.py --test dmx --debug
```

### 2. Validation
Run full test suite before commits:
```bash
uv run hardware_tests/hardware_device_api_test.py
```

### 3. Continuous Testing
Set up hardware test station with device connected for automated testing.

---

## Writing Custom Tests

### Example: Test Custom PID

```python
import asyncio
from rdm_dmx_async import NetworkManager, NetworkConfig

async def test_custom_pid():
    config = NetworkConfig()  # Auto-detect

    async with NetworkManager(config) as manager:
        devices = await manager.discover_devices()
        device = devices[0]

        # Test your custom API
        result = await device.your_api.your_method()
        print(f"Result: {result}")

asyncio.run(test_custom_pid())
```

### Example: Batch Testing Multiple Devices

```python
async def test_multiple_devices():
    config = NetworkConfig()

    async with NetworkManager(config) as manager:
        devices = await manager.discover_devices()

        for device in devices:
            print(f"\nTesting UID={device.uid:012X}")
            label = await device.device_label.get()
            print(f"  Label: {label}")

asyncio.run(test_multiple_devices())
```

---

## Test Coverage

| API Module | GET | SET | Notes |
|------------|-----|-----|-------|
| device_label | ✓ | ✓ | Full coverage |
| dmx_config | ✓ | ✓ | Address & personality |
| control | ✓ | ✓ | Identify, reset, factory defaults |
| sensors | ✓ | ✓ | Values, definitions, record |
| maintenance | ✓ | ✓ | Hours, power cycles |
| info | ✓ | - | Read-only |
| slots | ✓ | - | Read-only |
| modes | ✓ | ✓ | Startup, response time, fail mode |
| lamp | ✓ | ✓ | Hours, strikes, state, mode |
| display | ✓ | ✓ | Invert, level |
| position | ✓ | ✓ | Pan/tilt, swap, RTC |
| power | ✓ | ✓ | Power state |
| self_test | ✓ | ✓ | Perform, descriptions |
| presets | ✓ | ✓ | Playback, status, merge |
| system | ✓ | ✓ | PIDs, language, status |

---

## Safety Notes

⚠️ **Important:**
- Tests restore original values after SET operations
- Identify mode turns off automatically after 3 seconds
- Factory defaults and reset operations are NOT tested automatically (too destructive)
- Power state changes are READ-ONLY in tests (avoid unexpected shutdowns)

---

## Performance

- **Quick Test**: ~5-10 seconds for single API
- **Full Test Suite**: ~30-60 seconds depending on device
- **Discovery**: ~2-5 seconds for single device

---

## Contributing

When adding new APIs, update both test files:

1. Add test method to `hardware_device_api_test.py`
2. Add quick test to `quick_device_test.py`
3. Update this README with coverage info
4. Test with real hardware before committing

---

## Support

For issues:
1. Check device documentation for supported PIDs
2. Enable `--debug` logging
3. Verify hardware connections
4. Check that device firmware is up to date
