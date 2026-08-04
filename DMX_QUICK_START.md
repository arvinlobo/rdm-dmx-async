# DMX Not Working? Start Here!

## Your fixture isn't lighting up? Follow these steps:

### Step 1: Run the Diagnostic Tool
```bash
cd tests
python dmx_diagnostic.py --port COM3 --address 1
```

Replace `COM3` with your actual port (check Device Manager on Windows).

**What it does:**
- Checks all serial ports
- Verifies packet framing
- Tests connection to Enttec
- Sends test packets
- Provides specific fixes for each problem found

### Step 2: Common Issues and Quick Fixes

#### Issue: "No serial ports found"
- **Fix**: Plug in your Enttec USB device
- **Fix**: Install FTDI drivers if needed

#### Issue: "Connection failed"
- **Fix**: Check COM port number in Device Manager
- **Fix**: Close any other DMX software (QLC+, etc.)
- **Fix**: Try different USB port

#### Issue: "Packet sent but no flash"
Check these in order:
1. **Fixture powered on?** (sounds obvious, but check!)
2. **DMX address correct?** Fixture must be set to address 1 (or use `--address X`)
3. **DMX cable?** Must be proper DMX cable, not microphone cable
4. **Cable direction?** Enttec OUT → Fixture IN (not reversed)
5. **Fixture in DMX mode?** Not standalone/sound mode

### Step 3: If Fixture Flashes Briefly Then Turns Off

**This is actually GOOD NEWS!** It means your hardware works!

DMX requires continuous transmission. You need to send packets ~44 times per second.

Try this working example:
```bash
cd examples
python simple_dmx_example.py --port COM3
```

Your fixture should stay on for 10 seconds.

### Step 4: Understanding Your Fixture

**Know your fixture's DMX setup:**
- What DMX address is it set to? (Usually adjustable via menu/DIP switches)
- How many channels does it use? (RGB = 3 channels, RGBW = 4, moving head = 10-20+)
- What channel does what? (Check fixture manual)

**Example:** RGB fixture at address 1
- Channel 1 (DMX address 1): Red
- Channel 2 (DMX address 2): Green
- Channel 3 (DMX address 3): Blue

To send full white: `[255, 255, 255, 0, 0, 0, ...]` (512 bytes total)

### Step 5: Test Different DMX Addresses

If your fixture is at address 10 instead of 1:
```bash
python dmx_diagnostic.py --port COM3 --address 10
```

### Step 6: Enable Verbose Logging

See exactly what's happening:
```bash
python dmx_diagnostic.py --port COM3 --address 1 --verbose
```

## Need More Help?

1. Read `DMX_TROUBLESHOOTING.md` for comprehensive guide
2. Check hardware: cables, power, termination
3. Verify fixture is in DMX mode (not standalone)
4. Try another fixture to rule out fixture problems
5. Check Enttec device has correct port (some have multiple ports)

## Working Examples

Once your hardware is working, use these examples:

**Simple on/off:**
```bash
python examples/simple_dmx_example.py --port COM3
```

**Smooth fade:**
```bash
python examples/simple_dmx_example.py --port COM3 --example fade
```

**RGB colors:**
```bash
python examples/simple_dmx_example.py --port COM3 --example rgb
```

**Continuous control:**
```bash
python hardware_tests/dmx_continuous_output.py --port COM3 --address 1 --duration 30
```

## Quick Check: Is My Port Working?

Windows - Check Device Manager:
1. Open Device Manager
2. Look under "Ports (COM & LPT)"
3. Find "USB Serial Port (COM3)" or similar
4. Note the COM number
5. Use that number: `--port COM3`

## The #1 Mistake

**Sending DMX once instead of continuously!**

❌ **Wrong:**
```python
await manager.send_dmx(dmx_data)  # Sends once, fixture flashes
```

✅ **Correct:**
```python
while True:  # Send continuously!
    await manager.send_dmx(dmx_data)
    await asyncio.sleep(1/44)  # 44 Hz
```

See `examples/simple_dmx_example.py` for complete working code.
