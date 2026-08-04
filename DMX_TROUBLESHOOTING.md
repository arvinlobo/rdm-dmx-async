# DMX Troubleshooting Guide

## Quick Diagnosis

### Problem: Fixture doesn't light up at all (not even a flash)

#### Check Hardware Connection:
1. **Power**: Is the fixture powered on?
2. **DMX Cable**:
   - Use proper DMX cable (5-pin or 3-pin XLR)
   - NOT a microphone cable (they look similar but won't work reliably)
3. **Cable Direction**:
   - Enttec DMX OUT → Fixture DMX IN
   - Chain: Enttec OUT → Fixture 1 IN → Fixture 1 OUT → Fixture 2 IN → etc.
4. **Terminator**: Long cable runs (>300ft) may need 120Ω terminator at the end

#### Check Fixture Configuration:
1. **DMX Address**: Fixture must be set to correct DMX address
   - If testing address 1, fixture should be set to address 1
   - Use `--address X` flag to test different addresses
2. **DMX Mode**: Fixture must be in DMX mode (not standalone, sound-active, or master/slave)
3. **Channel Configuration**: Know how many channels your fixture uses
   - Example: RGB fixture uses 3 channels (R, G, B)
   - Example: Moving head might use 16+ channels

#### Check Enttec Device:
1. **Port Selection**:
   - Use Device Manager (Windows) to find COM port number
   - Run with `--port COM3` (adjust number)
2. **Driver**: Enttec uses FTDI drivers - ensure they're installed
3. **Multiple Ports**: Some Enttec devices have Port A and Port B - try both
4. **USB Power**: Try different USB port or use powered USB hub

#### Check Software:
1. **Port Access**: Close any other DMX software (QLC+, Freestyler, etc.)
2. **Permissions**: On some systems, may need administrator rights
3. **Run Diagnostic**: `python hardware_tests/dmx_diagnostic.py --verbose`

---

## Problem: Fixture flashes briefly then turns off

### This is NORMAL!

DMX512 requires **continuous transmission** at ~44 Hz (packets every 23ms).

### Wrong Pattern (fixture flashes):
```python
manager = NetworkManager(NetworkConfig())
await manager.start()
dmx_data = bytes([255, 255, 255] + [0] * 509)
await manager.send_dmx(dmx_data)  # ← Sends only ONCE!
# Fixture flashes and turns off
```

### Correct Pattern (fixture stays on):
```python
manager = NetworkManager(NetworkConfig())
await manager.start()
dmx_data = bytes([255, 255, 255] + [0] * 509)

# Send continuously!
while True:
    await manager.send_dmx(dmx_data)
    await asyncio.sleep(1/44)  # 44 Hz refresh
```

### Quick Test:
```bash
# This will keep lights on for 10 seconds
python examples/simple_dmx_example.py --port COM3
```

---

## DMX Protocol Basics

### Key Facts:
- **Universe**: 512 channels (addresses 1-512)
- **Refresh Rate**: 44 Hz minimum (packets every ~23ms)
- **Continuous**: Must send packets repeatedly, not just once
- **Start Code**: DMX packets begin with 0x00 start code
- **Values**: Each channel is 0-255 (0=off, 255=full)

### Channel Mapping Example:
```
Fixture at DMX Address 1 (RGB fixture, 3 channels):
  Channel 1 (Address 1): Red intensity
  Channel 2 (Address 2): Green intensity
  Channel 3 (Address 3): Blue intensity

To send full white:
  dmx_universe = bytes([255, 255, 255] + [0] * 509)
```

### Multiple Fixtures Example:
```python
# Fixture 1: Address 1 (RGB)
# Fixture 2: Address 4 (RGB)
# Fixture 3: Address 7 (RGB)

dmx_universe = bytearray([0] * 512)

# Fixture 1: Red
dmx_universe[0:3] = [255, 0, 0]

# Fixture 2: Green
dmx_universe[3:6] = [0, 255, 0]

# Fixture 3: Blue
dmx_universe[6:9] = [0, 0, 255]

# Send continuously
while True:
    await manager.send_dmx(bytes(dmx_universe))
    await asyncio.sleep(1/44)
```

---

## Common Error Messages

### "Port not found" / "Could not open port"
- **Cause**: Enttec device not detected or wrong port
- **Fix**: Check Device Manager, verify COM port number, try different USB port

### "Permission denied"
- **Cause**: Another program using the port, or insufficient permissions
- **Fix**: Close other DMX software, run as administrator

### "Timeout waiting for response"
- **Cause**: This is for RDM operations, not DMX output
- **Fix**: DMX output doesn't need responses - this error shouldn't appear for send_dmx()

---

## Testing Commands

### Run Full Diagnostic:
```bash
python hardware_tests/dmx_diagnostic.py --port COM3 --address 1 --verbose
```

### Simple Test (lights on for 10 seconds):
```bash
python examples/simple_dmx_example.py --port COM3
```

### Continuous Output (with fade):
```bash
python examples/simple_dmx_example.py --port COM3 --example fade
```

### RGB Color Cycling:
```bash
python examples/simple_dmx_example.py --port COM3 --example rgb
```

---

## Hardware Checklist

Before reporting a software bug, verify:

- [ ] Fixture is powered ON
- [ ] DMX cable is proper DMX cable (not mic cable)
- [ ] Cable connected: Enttec OUT → Fixture IN
- [ ] Fixture DMX address matches test address
- [ ] Fixture is in DMX mode
- [ ] Enttec device appears in Device Manager
- [ ] Correct COM port number used
- [ ] No other DMX software running
- [ ] Tried different USB port
- [ ] Tested with diagnostic tool

---

## Getting Help

If the diagnostic tool passes all tests but you still have no output:

1. Run verbose diagnostic: `python hardware_tests/dmx_diagnostic.py --verbose --port COM3`
2. Note which step fails
3. Check fixture manual for:
   - DMX address setting procedure
   - Channel configuration
   - DMX mode selection
4. Try a different fixture (if available) to rule out fixture issues
5. Check Enttec device LED indicators (if present)

## Additional Resources

- Enttec USB Pro Manual: https://www.enttec.com/product/lighting-communication-protocols/dmx512/dmx-usb-pro/
- DMX512-A Standard: ANSI E1.11
- Python Examples: `examples/` directory
- Hardware Tests: `tests/dmx_*.py`
