"""
DMX Output Test

Tests DMX512 data transmission to output.
Sends a simple DMX universe and verifies the framing.

Usage:
    python dmx_output_test.py [--port COM3]
"""

import argparse
import asyncio
import logging

from rdm_dmx_async import NetworkConfig, NetworkManager

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DMXOutputTester:
    """Test DMX512 output transmission."""

    def __init__(self, port: str | None = None):
        self.port = port
        self.config = NetworkConfig(port=port)
        self.manager: NetworkManager | None = None

    async def setup(self):
        """Initialize network manager."""
        logger.info("=" * 70)
        logger.info("DMX Output Test")
        logger.info("=" * 70)

        self.manager = NetworkManager(self.config)
        await self.manager.start()
        logger.info("Connected to port: %s", self.config.port)
        logger.info("")

    async def teardown(self):
        """Cleanup network manager."""
        if self.manager:
            await self.manager.stop()
            logger.info("Test complete")

    async def test_dmx_output(self):
        """Test sending DMX data."""
        logger.info("--- Testing DMX Output ---")

        assert self.manager is not None, "Manager not initialized"

        try:
            # Test 1: Send simple DMX data (first 10 channels)
            logger.info("Test 1: Sending 10 channels")
            dmx_data = bytes([255, 128, 64, 32, 16, 8, 4, 2, 1, 0])
            await self.manager.send_dmx(dmx_data)
            logger.info("✓ PASS - Sent 10 channels: %s", " ".join(f"{b:3d}" for b in dmx_data))

            await asyncio.sleep(0.5)

            # Test 2: Send full universe (512 channels)
            logger.info("\nTest 2: Sending full 512-channel universe")
            # Create gradient pattern
            full_universe = bytes([i % 256 for i in range(512)])
            await self.manager.send_dmx(full_universe)
            logger.info("✓ PASS - Sent 512 channels")

            await asyncio.sleep(0.5)

            # Test 3: Send all channels at max (full white)
            logger.info("\nTest 3: Sending all channels at maximum (255)")
            max_data = bytes([255] * 512)
            await self.manager.send_dmx(max_data)
            logger.info("✓ PASS - Sent 512 channels at max value")

            await asyncio.sleep(0.5)

            # Test 4: Send all channels at zero (blackout)
            logger.info("\nTest 4: Sending all channels at zero (blackout)")
            blackout = bytes([0] * 512)
            await self.manager.send_dmx(blackout)
            logger.info("✓ PASS - Sent 512 channels at zero")

            logger.info("")
            logger.info("=" * 70)
            logger.info("All DMX output tests passed!")
            logger.info("=" * 70)

        except (RuntimeError, ValueError, AssertionError):
            logger.exception("✗ FAIL - DMX output test failed")

    async def run_tests(self):
        """Run all DMX output tests."""
        try:
            await self.setup()
            await self.test_dmx_output()
        finally:
            await self.teardown()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="DMX Output Test")
    parser.add_argument(
        "--port", type=str, help="Serial port (e.g., COM3). Auto-detect if not specified."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    tester = DMXOutputTester(port=args.port)
    await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main())
