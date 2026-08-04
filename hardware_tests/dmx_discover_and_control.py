"""
DMX Discovery and Control

Discovers RDM devices, reads their DMX address, and sends DMX output to that address.

Note: NetworkManager.send_dmx(repeat=True) starts a background scheduler that
keeps re-transmitting the last buffer automatically (~40 Hz) - a single call is
enough to hold the output for the whole duration.

Usage:
    python dmx_discover_and_control.py [--port COM3] [--duration 10]
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


async def discover_and_control(port: str | None = None, duration: float = 10.0):
    """Discover device, get its DMX address, and send DMX output."""

    config = NetworkConfig(port=port)
    manager = NetworkManager(config)

    try:
        # Start network
        await manager.start()
        logger.info("=" * 70)
        logger.info("DMX Discovery and Control")
        logger.info("=" * 70)
        logger.info("Connected to port: %s", config.port)
        logger.info("")

        # Discover devices
        logger.info("Discovering RDM devices...")
        devices = await manager.discover_devices()

        if not devices:
            logger.error("No RDM devices found!")
            logger.info("")
            logger.info("Troubleshooting tips:")
            logger.info("  1. Check DMX cable is connected")
            logger.info("  2. Check fixture is powered ON")
            logger.info("  3. Check fixture has RDM enabled")
            return

        device = devices[0]
        logger.info("Found device:")
        logger.info("  UID: %012X", device.uid)
        logger.info("  Manufacturer: %s", device.state.manufacturer)
        logger.info("  Model: %s", device.state.model)
        logger.info("  Device Label: %s", device.state.device_label)
        logger.info("")

        # Get DMX configuration
        logger.info("Reading DMX configuration...")
        dmx_address = device.state.dmx_start_address
        personality = await device.dmx_config.get_personality(use_cache=False)

        if personality:
            current_personality, total_personalities = personality
            logger.info("  DMX Start Address: %d", dmx_address)
            logger.info("  Personality: %d of %d", current_personality, total_personalities)

            # Get slot info if available
            try:
                slot_info = await device.slots.get_slot_info()
                if slot_info:
                    logger.info("  DMX Footprint: %d channels", len(slot_info))
                    logger.info("")
                    logger.info("  Channel Layout:")
                    for i, slot in enumerate(slot_info[:8], 1):  # Show first 8
                        logger.info(
                            "    Ch %d (DMX %d): Type 0x%04X",
                            i,
                            dmx_address + i - 1,
                            slot["slot_type"],
                        )
                    if len(slot_info) > 8:
                        logger.info("    ... and %d more channels", len(slot_info) - 8)
            except Exception:
                pass
        else:
            logger.info("  DMX Start Address: %d", dmx_address)

        logger.info("")
        logger.info("=" * 70)
        logger.info("SENDING DMX OUTPUT")
        logger.info("=" * 70)
        logger.info("Address: %d", dmx_address)
        logger.info("Duration: %.1f seconds", duration)
        logger.info("")

        # Create DMX universe with first 16 channels at device address set to full
        dmx_universe = bytearray([0] * 512)
        for i in range(16):
            channel = dmx_address - 1 + i  # DMX addresses are 1-based
            if channel < 512:
                dmx_universe[channel] = 255

        logger.info("Turning lights ON...")
        logger.info(
            "Setting channels %d-%d to 255 (full brightness)",
            dmx_address,
            min(dmx_address + 15, 512),
        )
        logger.info("")
        logger.info("Press Ctrl+C to stop early")
        logger.info("")

        # send_dmx(repeat=True) starts a background scheduler that keeps
        # re-transmitting this buffer automatically - one call holds the
        # level for the full duration.
        try:
            await manager.send_dmx(bytes(dmx_universe), repeat=True)
            await asyncio.sleep(duration)
        except KeyboardInterrupt:
            logger.info("")
            logger.info("Interrupted by user")

        # Blackout
        logger.info("")
        logger.info("Turning lights OFF (blackout)...")
        blackout = bytes([0] * 512)
        for _ in range(10):
            await manager.send_dmx(blackout)
            await asyncio.sleep(0.02)

        logger.info("Done!")

    finally:
        await manager.stop()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="DMX Discovery and Control")
    parser.add_argument(
        "--port", type=str, help="Serial port (e.g., COM3). Auto-detect if not specified."
    )
    parser.add_argument(
        "--duration", type=float, default=10.0, help="Duration in seconds (default: 10)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    await discover_and_control(port=args.port, duration=args.duration)


if __name__ == "__main__":
    asyncio.run(main())
