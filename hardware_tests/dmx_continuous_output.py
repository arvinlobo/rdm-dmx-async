"""
DMX Output Example (static hold + fade)

Demonstrates DMX output using rdm_dmx_async.NetworkManager.

Note: NetworkManager.send_dmx(repeat=True) starts a background
DmxFrameScheduler that keeps re-transmitting the last buffer automatically
(~40 Hz). A single send_dmx(repeat=True) call is enough to hold a static
level - no manual send loop is needed. The 'fade' mode below still loops
manually because it needs to push genuinely new (changing) values at each
step.

Usage:
    python dmx_continuous_output.py [--port COM3] [--address 1] [--duration 10]
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


class ContinuousDMXController:
    """DMX output controller."""

    def __init__(self, port: str | None = None, fade_step_rate: float = 44.0):
        self.port = port
        self.config = NetworkConfig(port=port)
        self.manager: NetworkManager | None = None
        self.fade_step_rate = fade_step_rate  # Hz, only used by run_fade_test
        self.fade_step_interval = 1.0 / fade_step_rate  # seconds

    async def start(self):
        """Initialize network manager."""
        logger.info("=" * 70)
        logger.info("Continuous DMX Output Controller")
        logger.info("=" * 70)

        self.manager = NetworkManager(self.config)
        await self.manager.start()
        logger.info("Connected to port: %s", self.config.port)
        logger.info("")

    async def stop(self):
        """Cleanup network manager."""
        if self.manager:
            await self.manager.stop()
            logger.info("Controller stopped")

    async def run_simple_test(self, start_address: int = 1, duration: float = 10.0):
        """
        Run a simple lighting test.

        Sets channels at start_address to full brightness for specified duration.

        Args:
            start_address: DMX start address (1-512)
            duration: How long to keep lights on (seconds)
        """
        logger.info("--- Simple Lighting Test ---")
        logger.info("DMX Address: %d", start_address)
        logger.info("Duration: %.1f seconds", duration)
        logger.info("")

        assert self.manager is not None

        # Create DMX universe (512 channels, all zero)
        dmx_universe = bytearray([100] * 512)

        # Set first 8 channels at start_address to full (255)
        for i in range(8):
            channel = start_address - 1 + i  # DMX addresses are 1-based
            if channel < 512:
                dmx_universe[channel] = 255

        logger.info("Turning lights ON...")
        logger.info(
            "Channels %d-%d set to 255 (full brightness)",
            start_address,
            min(start_address + 7, 512),
        )

        # send_dmx(repeat=True) starts a background scheduler that keeps
        # re-transmitting this buffer automatically - one call is enough
        # to hold the level for the full duration.
        await self.manager.send_dmx(bytes(dmx_universe), repeat=True)
        await asyncio.sleep(duration)

        # Turn off
        logger.info("")
        logger.info("Turning lights OFF...")

        # Send blackout
        blackout = bytes([0] * 512)
        for _ in range(10):  # Send blackout multiple times
            await self.manager.send_dmx(blackout)
            await asyncio.sleep(0.02)

        logger.info("Test complete")

    async def run_fade_test(self, start_address: int = 1, duration: float = 10.0):
        """
        Run a fading test - smoothly fade lights up and down.

        Args:
            start_address: DMX start address (1-512)
            duration: Total duration for fade cycle (seconds)
        """
        logger.info("--- Fade Test ---")
        logger.info("DMX Address: %d", start_address)
        logger.info("Fade Duration: %.1f seconds", duration)
        logger.info("")

        assert self.manager is not None

        steps = int(duration / self.fade_step_interval)
        half_steps = steps // 2

        logger.info("Fading up...")

        for step in range(steps):
            # Create fade pattern (up then down)
            if step < half_steps:
                # Fade up
                intensity = int((step / half_steps) * 255)
            else:
                # Fade down
                intensity = int(((steps - step) / half_steps) * 255)

            # Create DMX universe
            dmx_universe = bytearray([0] * 512)

            # Set first 8 channels
            for i in range(8):
                channel = start_address - 1 + i
                if channel < 512:
                    dmx_universe[channel] = intensity

            await self.manager.send_dmx(bytes(dmx_universe))
            await asyncio.sleep(self.fade_step_interval)

            if step == half_steps - 1:
                logger.info("Fading down...")

        # Final blackout
        blackout = bytes([0] * 512)
        for _ in range(5):
            await self.manager.send_dmx(blackout)
            await asyncio.sleep(0.02)

        logger.info("Fade test complete")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Continuous DMX Output Controller")
    parser.add_argument(
        "--port", type=str, help="Serial port (e.g., COM3). Auto-detect if not specified."
    )
    parser.add_argument("--address", type=int, default=1, help="DMX start address (default: 1)")
    parser.add_argument(
        "--duration", type=float, default=10.0, help="Duration in seconds (default: 10)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["simple", "fade"],
        default="simple",
        help="Test mode: simple (on/off) or fade (smooth fade)",
    )
    parser.add_argument(
        "--fade-step-rate",
        type=float,
        default=44.0,
        help="Fade animation update rate in Hz (default: 44). Only used in 'fade' mode - "
        "the underlying DMX refresh is handled automatically.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    controller = ContinuousDMXController(port=args.port, fade_step_rate=args.fade_step_rate)

    try:
        await controller.start()

        if args.mode == "simple":
            await controller.run_simple_test(start_address=args.address, duration=args.duration)
        elif args.mode == "fade":
            await controller.run_fade_test(start_address=args.address, duration=args.duration)

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
