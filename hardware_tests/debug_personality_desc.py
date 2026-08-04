"""Ad-hoc debug script: query DMX_PERSONALITY_DESCRIPTION for every personality index.

Used to check whether the connected fixture only answers this GET for its
currently active personality (vs. all personalities per the RDM spec).
"""

import argparse
import asyncio
import logging

from rdm_dmx_async import NetworkConfig, NetworkManager

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=str, default=None)
    args = parser.parse_args()

    manager = NetworkManager(NetworkConfig(port=args.port))
    await manager.start()
    try:
        devices = await manager.discover_devices()
        if not devices:
            print("No devices found")
            return
        device = devices[0]
        await device.initialize()

        current, count = await device.dmx_config.get_personality(use_cache=False)
        print(f"\nCurrent personality: {current} / count={count}\n")

        for p in range(1, count + 1):
            print(f"--- Querying personality {p} description ---")
            info = await device.dmx_config.get_personality_description(p)
            print(f"personality {p} -> {info}")
    finally:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
