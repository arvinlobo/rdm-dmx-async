"""
Manual-break interface discovery and control test.

Discovers RDM devices on a bare USB-RS485 interface with no onboard framing
microcontroller, prints their basic info, and (optionally) sends DMX output
to the first device's address.

Usage:
    python bare_usb_rs485_discover_and_control.py --port COM7 [--duration 10]
"""

import argparse
import asyncio
import logging

from rdm_dmx_async import UID, InterfaceType, NetworkConfig, NetworkManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Manual-break interfaces have no onboard widget to query for a UID, so this
# script picks one explicitly (Enttec's manufacturer prefix, all-zero device ID).
_CONTROLLER_UID = UID(0x454E00000000)


async def discover_and_control(port: str, duration: float) -> None:
    """Discover devices via the manual-break interface, print info, and send DMX to the first one."""
    config = NetworkConfig(
        port=port, interface_type=InterfaceType.BARE_USB_RS485, controller_uid=_CONTROLLER_UID
    )
    manager = NetworkManager(config)

    try:
        await manager.start()
        logger.info("=" * 70)
        logger.info("Manual-Break Interface Discovery and Control")
        logger.info("=" * 70)
        logger.info("Connected to port: %s", config.port)
        logger.info("")

        logger.info("Discovering RDM devices...")
        devices = await manager.discover_devices()

        if not devices:
            logger.error("No RDM devices found!")
            logger.info("")
            logger.info("Troubleshooting tips:")
            logger.info("  1. Check the RS485 cable is connected (data lines not swapped)")
            logger.info("  2. Check the fixture is powered ON")
            logger.info("  3. Check the fixture has RDM enabled")
            return

        for device in devices:
            await device.initialize()
            logger.info("Found device:")
            logger.info("  UID: %012X", device.uid)
            logger.info("  Manufacturer: %s", device.state.manufacturer)
            logger.info("  Model: %s", device.state.model)
            logger.info("  Device Label: %s", device.state.device_label)
            logger.info("  DMX Address: %d", device.state.dmx_start_address)
            logger.info("  DMX Footprint: %d", device.state.dmx_footprint)
            logger.info("")

        device = devices[0]
        dmx_address = device.state.dmx_start_address
        footprint = device.state.dmx_footprint or 1

        logger.info(
            "Sending DMX output to address %d (%d channels) for %.1fs...",
            dmx_address,
            footprint,
            duration,
        )
        dmx_data = bytearray(512)
        for i in range(footprint):
            dmx_data[dmx_address - 1 + i] = 255
        await manager.send_dmx(bytes(dmx_data), repeat=True)

        await asyncio.sleep(duration)
        logger.info("Done.")

    finally:
        await manager.stop()


def main() -> None:
    """Parse args and run the discovery/control test."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM7", help="Serial port (default: COM7)")
    parser.add_argument(
        "--duration", type=float, default=10.0, help="Seconds to hold DMX output (default: 10)"
    )
    args = parser.parse_args()

    asyncio.run(discover_and_control(args.port, args.duration))


if __name__ == "__main__":
    main()
