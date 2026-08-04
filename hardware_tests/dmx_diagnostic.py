"""
DMX Output Diagnostic Tool

This script helps diagnose DMX output issues by testing EVERY step:
1. Port detection and connection
2. Serial communication
3. Packet framing verification
4. Single packet transmission
5. Continuous transmission
6. Common configuration issues

Usage:
    python dmx_diagnostic.py [--port COM3] [--address 1] [--verbose]
"""

import argparse
import asyncio
import logging
import sys

import serial.tools.list_ports

from rdm_dmx_async import NetworkConfig, NetworkManager
from rdm_dmx_async.transport.adapters import EnttecAdapter

# Configure logging - will be adjusted based on --verbose
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DMXDiagnostic:
    """DMX output diagnostic tool with comprehensive checks."""

    def __init__(self, port: str | None = None, dmx_address: int = 1, verbose: bool = False):
        self.port = port
        self.dmx_address = dmx_address
        self.verbose = verbose
        self.config = NetworkConfig(port=port)
        self.manager: NetworkManager | None = None

        # Adjust logging based on verbose flag
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logging.getLogger("rdm_dmx_async").setLevel(logging.DEBUG)
        else:
            logging.getLogger("rdm_dmx_async").setLevel(logging.WARNING)

    def check_available_ports(self) -> bool:
        """Check for available serial ports."""
        logger.info("=" * 70)
        logger.info("STEP 1: Checking Available Serial Ports")
        logger.info("=" * 70)
        logger.info("")

        ports = list(serial.tools.list_ports.comports())

        if not ports:
            logger.error("✗ NO serial ports found!")
            logger.error("")
            logger.error("SOLUTION:")
            logger.error("  1. Check that your Enttec USB device is plugged in")
            logger.error("  2. Install drivers if needed (check Device Manager on Windows)")
            logger.error("  3. Try a different USB port")
            logger.error("")
            return False

        logger.info("Found %d serial port(s):", len(ports))
        logger.info("")

        enttec_found = False
        for port in ports:
            is_enttec = "enttec" in port.description.lower() or "ftdi" in port.description.lower()
            marker = "  ← Enttec device" if is_enttec else ""
            logger.info("  %s: %s%s", port.device, port.description, marker)
            if is_enttec:
                enttec_found = True

        logger.info("")

        if not enttec_found:
            logger.warning("⚠ No Enttec devices detected by name")
            logger.warning("   This may be okay - testing will continue")
            logger.warning("")
        else:
            logger.info("✓ Enttec device detected")
            logger.info("")

        return True

    def check_packet_framing(self) -> bool:
        """Verify packet framing is correct."""
        logger.info("=" * 70)
        logger.info("STEP 2: Verifying Packet Framing")
        logger.info("=" * 70)
        logger.info("")

        try:
            adapter = EnttecAdapter("COM1", use_mk2_protocol=True)

            # Test DMX framing
            dmx_data = bytes([255, 128, 64])
            framed = adapter.frame_dmx_output(dmx_data)

            logger.info("Testing DMX packet framing:")
            logger.info("  Input: %d channels", len(dmx_data))
            logger.info("  Framed packet: %d bytes", len(framed))
            logger.info("  First 10 bytes: %s", " ".join(f"{b:02X}" for b in framed[:10]))
            logger.info("")

            # Verify structure
            if framed[0] != 0x7E:
                logger.error("✗ Invalid START byte (expected 0x7E, got 0x%02X)", framed[0])
                return False

            if framed[-1] != 0xE7:
                logger.error("✗ Invalid END byte (expected 0xE7, got 0x%02X)", framed[-1])
                return False

            if framed[1] != 0x06:
                logger.error(
                    "✗ Invalid message type (expected 0x06 for DMX, got 0x%02X)", framed[1]
                )
                return False

            logger.info("✓ Packet framing is CORRECT")
            logger.info("  - START byte: 0x7E ✓")
            logger.info("  - Message type: 0x06 (DMX) ✓")
            logger.info("  - END byte: 0xE7 ✓")
            logger.info("")

            return True

        except Exception as e:
            logger.error("✗ Framing test failed: %s", e)
            logger.error("")
            return False

    async def setup(self) -> bool:
        """Initialize network manager with detailed diagnostics."""
        logger.info("=" * 70)
        logger.info("STEP 3: Connecting to Enttec Device")
        logger.info("=" * 70)
        logger.info("")

        if self.port:
            logger.info("Using specified port: %s", self.port)
        else:
            logger.info("Auto-detecting Enttec port...")

        logger.info("")

        try:
            self.manager = NetworkManager(self.config)

            # Enable verbose logging for connection
            if self.verbose:
                logger.info("Starting network manager (verbose mode)...")

            await self.manager.start()

            actual_port = self.config.port
            logger.info("✓ Successfully connected!")
            logger.info("  Port: %s", actual_port)
            logger.info("  Baudrate: 250000 (DMX512-A standard)")
            logger.info("  Stop bits: 2")
            logger.info("")

            return True

        except Exception as e:
            logger.error("✗ Connection FAILED: %s", e)
            logger.error("")
            logger.error("COMMON CAUSES:")
            logger.error("  1. Wrong port specified (use --port COM3 or similar)")
            logger.error("  2. Enttec device not plugged in")
            logger.error("  3. Another program is using the port")
            logger.error("  4. Driver not installed")
            logger.error("  5. Insufficient permissions (try running as admin)")
            logger.error("")
            logger.error("TRY:")
            logger.error("  - Check Device Manager (Windows) for COM ports")
            logger.error("  - Close any other DMX software")
            logger.error("  - Replug the Enttec device")
            logger.error("  - Run: python dmx_diagnostic.py --port COM3 (adjust COM number)")
            logger.error("")

            return False

    async def teardown(self):
        """Cleanup."""
        if self.manager:
            await self.manager.stop()

    async def test_single_packet(self):
        """
        Test 1: Single send_dmx() Call

        EXPECTED BEHAVIOR:
        - Fixture should turn ON and STAY ON.
        - NetworkManager.send_dmx() lazily starts a background scheduler that
          keeps re-transmitting the last buffer automatically (~40 Hz), so a
          single call is enough to hold a static DMX level.
        """
        logger.info("=" * 70)
        logger.info("TEST 1: Single send_dmx() Call")
        logger.info("=" * 70)
        logger.info("")
        logger.info(
            "Sending ONE send_dmx() call with channels %d-%d at full brightness...",
            self.dmx_address,
            self.dmx_address + 2,
        )
        logger.info("")
        logger.info("EXPECTED: Fixture turns ON and STAYS ON (auto-refreshed in background)")
        logger.info("")

        assert self.manager is not None

        # Create DMX universe with first 3 channels at full
        dmx_data = bytearray([0] * 512)
        for i in range(3):
            dmx_data[self.dmx_address - 1 + i] = 255

        try:
            await self.manager.send_dmx(bytes(dmx_data))
            logger.info("✓ Packet sent successfully")
            logger.info("")
            logger.info("If the fixture turned ON and stayed on, DMX output is WORKING!")
            logger.info("")
            return True
        except Exception as e:
            logger.error("✗ FAILED to send DMX packet: %s", e)
            logger.error("")
            logger.error("POSSIBLE CAUSES:")
            logger.error("  1. Enttec device not responding")
            logger.error("  2. Wrong port selected")
            logger.error("  3. Hardware/driver issue")
            return False

    async def test_continuous_transmission(self, duration: float = 5.0):
        """
        Test 2: Sustained Output Over Time

        EXPECTED BEHAVIOR:
        - Fixture stays ON for the full duration.
        - This confirms the background scheduler (started by Test 1's single
          send_dmx() call) keeps refreshing the output on its own.
        """
        logger.info("=" * 70)
        logger.info("TEST 2: Sustained Output Over Time")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Holding DMX output for %.1f seconds (single send_dmx() call)...", duration)
        logger.info("Channels %d-%d at full brightness", self.dmx_address, self.dmx_address + 2)
        logger.info("")
        logger.info("EXPECTED: Fixture stays ON for full %d seconds", int(duration))
        logger.info("")

        assert self.manager is not None

        # Create DMX universe
        dmx_data = bytearray([0] * 512)
        for i in range(3):
            dmx_data[self.dmx_address - 1 + i] = 255

        try:
            # A single send_dmx() call lazily starts the background scheduler,
            # which keeps re-transmitting this buffer automatically (~40 Hz).
            await self.manager.send_dmx(bytes(dmx_data))
            await asyncio.sleep(duration)

            logger.info("✓ Held output for %.1f seconds", duration)
            logger.info("")
            logger.info("If fixture stayed ON, your DMX output is WORKING CORRECTLY!")
            logger.info("")

            # Send blackout
            logger.info("Sending blackout (all channels to 0)...")
            blackout = bytes([0] * 512)
            for _ in range(10):
                await self.manager.send_dmx(blackout)
                await asyncio.sleep(0.02)

            logger.info("✓ Test completed successfully")
            return True

        except Exception as e:
            logger.error("✗ FAILED during sustained output test: %s", e)
            logger.error("")
            return False

    async def show_solution(self):
        """Show the current, correct pattern for DMX output."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("HOW DMX OUTPUT WORKS IN THIS LIBRARY")
        logger.info("=" * 70)
        logger.info("")
        logger.info("DMX512 requires continuous transmission at ~40 Hz to hold a level,")
        logger.info("but NetworkManager handles this automatically for you.")
        logger.info("")
        logger.info("CORRECT Pattern (recommended):")
        logger.info("")
        logger.info("  async def control_lights():")
        logger.info("      manager = NetworkManager(NetworkConfig())")
        logger.info("      await manager.start()")
        logger.info("      ")
        logger.info("      # Create DMX data")
        logger.info("      dmx_data = bytes([255, 255, 255] + [0] * 509)  # First 3 channels on")
        logger.info("      ")
        logger.info("      # A single call is enough - a background scheduler keeps")
        logger.info("      # re-transmitting this buffer automatically (~40 Hz).")
        logger.info("      await manager.send_dmx(dmx_data)")
        logger.info("      await asyncio.sleep(10)  # Fixture stays on for 10s")
        logger.info("")
        logger.info("Only loop manually if the DMX VALUES need to change over time")
        logger.info("(e.g. a fade or chase) - call send_dmx() again whenever you have")
        logger.info("a new frame ready; the scheduler always transmits the latest one.")
        logger.info("")
        logger.info("=" * 70)
        logger.info("")
        logger.info("See examples:")
        logger.info("  - hardware_tests/dmx_continuous_output.py")
        logger.info("  - hardware_tests/dmx_output_test.py")
        logger.info("")

    async def run_diagnostic(self):
        """Run all diagnostic tests with comprehensive checks."""
        logger.info("")
        logger.info("╔" + "═" * 68 + "╗")
        logger.info("║" + " " * 20 + "DMX OUTPUT DIAGNOSTIC TOOL" + " " * 22 + "║")
        logger.info("╚" + "═" * 68 + "╝")
        logger.info("")
        logger.info("This tool will check EVERY step of DMX output:")
        logger.info("  Step 1: Available serial ports")
        logger.info("  Step 2: Packet framing verification")
        logger.info("  Step 3: Connection to Enttec device")
        logger.info("  Step 4: Single send_dmx() call test")
        logger.info("  Step 5: Sustained output test")
        logger.info("")
        logger.info("Press ENTER to begin...")
        input()
        logger.info("")

        # Step 1: Check ports
        if not self.check_available_ports():
            logger.error("Cannot continue without serial ports. Fix the issues above.")
            return 1

        logger.info("Press ENTER to continue to Step 2...")
        input()
        logger.info("")

        # Step 2: Verify framing
        if not self.check_packet_framing():
            logger.error("Packet framing is broken. This is a code issue, not hardware.")
            return 1

        logger.info("Press ENTER to continue to Step 3...")
        input()
        logger.info("")

        # Step 3: Connect
        if not await self.setup():
            logger.error("Connection failed. Fix the issues above before continuing.")
            return 1

        try:
            logger.info("Press ENTER to continue to Step 4 (single send_dmx() call test)...")
            input()
            logger.info("")

            # Step 4: Single send_dmx() call
            success = await self.test_single_packet()
            if not success:
                logger.error("Single send_dmx() call test failed. Check the error above.")
                return 1

            logger.info("")
            print("Did the fixture turn ON and stay on? (y/n): ", end="")
            response = input().strip().lower()

            if response != "y":
                logger.warning("")
                logger.warning("No output seen. Additional troubleshooting:")
                logger.warning("")
                logger.warning("FIXTURE SETUP:")
                logger.warning("  1. Fixture must be POWERED ON")
                logger.warning("  2. Fixture DMX address must be set to %d", self.dmx_address)
                logger.warning("     (Use --address X to test different addresses)")
                logger.warning("  3. Fixture must be in DMX mode (not standalone/sound mode)")
                logger.warning("")
                logger.warning("CABLING:")
                logger.warning("  1. Use proper DMX cable (NOT microphone cable!)")
                logger.warning("  2. DMX uses XLR 5-pin (or sometimes 3-pin)")
                logger.warning("  3. Check: Enttec OUT → Fixture IN (correct direction)")
                logger.warning("  4. Long cable runs may need 120Ω terminator at end")
                logger.warning("")
                logger.warning("ENTTEC DEVICE:")
                logger.warning("  1. Check DMX OUT port (not IN)")
                logger.warning("  2. Some Enttec devices have multiple ports")
                logger.warning("  3. Try unplugging and replugging")
                logger.warning("")
                print("Want to continue to sustained output test anyway? (y/n): ", end="")
                if input().strip().lower() != "y":
                    return 1

            logger.info("")
            logger.info("Press ENTER to start Step 5 (sustained output test)...")
            input()
            logger.info("")

            # Step 5: Sustained output over time
            success = await self.test_continuous_transmission(duration=5.0)
            if not success:
                return 1

            # Show solution
            await self.show_solution()

            return 0

        finally:
            await self.teardown()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DMX Output Diagnostic Tool - Comprehensive troubleshooting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dmx_diagnostic.py                    # Auto-detect port
  python dmx_diagnostic.py --port COM3        # Use specific port
  python dmx_diagnostic.py --address 10       # Test DMX address 10
  python dmx_diagnostic.py --verbose          # Show all debug logs
  python dmx_diagnostic.py --port COM3 --address 1 --verbose
        """,
    )
    parser.add_argument(
        "--port", type=str, help="Serial port (e.g., COM3) or auto-detect if not specified"
    )
    parser.add_argument(
        "--address", type=int, default=1, help="DMX start address to test (1-512, default: 1)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    diagnostic = DMXDiagnostic(port=args.port, dmx_address=args.address, verbose=args.verbose)
    result = await diagnostic.run_diagnostic()

    sys.exit(result)


if __name__ == "__main__":
    asyncio.run(main())
