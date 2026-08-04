"""
Simple DMX Output Example

Demonstrates the correct way to control DMX fixtures.
Key point: DMX requires continuous transmission at ~44 Hz!

Usage:
    python simple_dmx_example.py [--port COM3]
"""

import argparse
import asyncio
import logging

from rdm_dmx_async import NetworkConfig, NetworkManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def simple_dmx_example(port: str | None = None):
    """
    Simple example: Turn on lights for 10 seconds.

    This shows the CORRECT pattern for DMX output.
    """
    # 1. Initialize network manager
    config = NetworkConfig(port=port)
    manager = NetworkManager(config)
    await manager.start()

    logger.info("Connected! Starting DMX output...")
    logger.info("")
    logger.info("Channels 1-3 will be at full brightness")
    logger.info("(Make sure your fixture is set to DMX address 1)")
    logger.info("")

    try:
        # 2. Create DMX universe (512 channels)
        # Set first 3 channels to full (255), rest to 0
        dmx_universe = bytes([255, 255, 255] + [0] * 509)

        # 3. Send continuously for 10 seconds
        # THIS IS THE KEY: You MUST send repeatedly!
        duration = 10.0
        refresh_rate = 44.0  # Hz (standard for DMX)
        refresh_interval = 1.0 / refresh_rate

        start_time = asyncio.get_event_loop().time()

        logger.info("Lights ON - sending continuously for %.0f seconds...", duration)

        while True:
            # Send DMX packet
            await manager.send_dmx(dmx_universe)

            # Check if done
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= duration:
                break

            # Wait for next refresh interval
            await asyncio.sleep(refresh_interval)

        logger.info("")
        logger.info("Turning lights OFF...")

        # 4. Send blackout (all zeros) multiple times to ensure lights turn off
        blackout = bytes([0] * 512)
        for _ in range(10):
            await manager.send_dmx(blackout)
            await asyncio.sleep(0.02)

        logger.info("Done!")

    finally:
        await manager.stop()


async def fade_example(port: str | None = None):
    """
    Example: Smooth fade up and down.

    Demonstrates how to create smooth lighting effects with DMX.
    """
    config = NetworkConfig(port=port)
    manager = NetworkManager(config)
    await manager.start()

    logger.info("Connected! Starting fade example...")
    logger.info("Channels 1-3 will fade up and down")
    logger.info("")

    try:
        refresh_rate = 44.0
        refresh_interval = 1.0 / refresh_rate

        # Fade up from 0 to 255
        logger.info("Fading up...")
        for intensity in range(0, 256, 5):
            dmx_data = bytes([intensity, intensity, intensity] + [0] * 509)
            await manager.send_dmx(dmx_data)
            await asyncio.sleep(refresh_interval)

        await asyncio.sleep(1.0)

        # Fade down from 255 to 0
        logger.info("Fading down...")
        for intensity in range(255, -1, -5):
            dmx_data = bytes([intensity, intensity, intensity] + [0] * 509)
            await manager.send_dmx(dmx_data)
            await asyncio.sleep(refresh_interval)

        logger.info("Done!")

    finally:
        await manager.stop()


async def rgb_color_example(port: str | None = None):
    """
    Example: Cycle through RGB colors.

    Assumes fixture channels are: 1=Red, 2=Green, 3=Blue
    """
    config = NetworkConfig(port=port)
    manager = NetworkManager(config)
    await manager.start()

    logger.info("Connected! Cycling through RGB colors...")
    logger.info("")

    try:
        refresh_rate = 44.0
        refresh_interval = 1.0 / refresh_rate

        colors = [
            (255, 0, 0, "Red"),
            (0, 255, 0, "Green"),
            (0, 0, 255, "Blue"),
            (255, 255, 0, "Yellow"),
            (255, 0, 255, "Magenta"),
            (0, 255, 255, "Cyan"),
            (255, 255, 255, "White"),
        ]

        for r, g, b, name in colors:
            logger.info("Color: %s", name)
            dmx_data = bytes([r, g, b] + [0] * 509)

            # Send this color for 2 seconds
            start = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start < 2.0:
                await manager.send_dmx(dmx_data)
                await asyncio.sleep(refresh_interval)

        # Blackout
        logger.info("Blackout")
        blackout = bytes([0] * 512)
        for _ in range(10):
            await manager.send_dmx(blackout)
            await asyncio.sleep(refresh_interval)

        logger.info("Done!")

    finally:
        await manager.stop()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simple DMX Examples")
    parser.add_argument("--port", type=str, help="Serial port (e.g., COM3)")
    parser.add_argument(
        "--example",
        type=str,
        default="simple",
        choices=["simple", "fade", "rgb"],
        help="Which example to run",
    )

    args = parser.parse_args()

    if args.example == "simple":
        await simple_dmx_example(args.port)
    elif args.example == "fade":
        await fade_example(args.port)
    elif args.example == "rgb":
        await rgb_color_example(args.port)


if __name__ == "__main__":
    asyncio.run(main())
