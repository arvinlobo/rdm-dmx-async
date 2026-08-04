"""
Command-line entry point for rdm_dmx_async.

Provides basic operational commands (list serial ports, discover RDM
devices on a network) for quick manual verification without writing code.

Installed as the `rdm-dmx` console script (see pyproject.toml [project.scripts]).
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from .application.network_manager import NetworkConfig, NetworkManager
from .transport.interface_adapter import InterfaceType
from .utils import list_available_ports

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rdm-dmx", description="RDM/DMX command-line utility")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-ports", help="List available serial ports")

    discover = subparsers.add_parser("discover", help="Discover RDM devices on the network")
    discover.add_argument("--port", help="Serial port, e.g. COM3 (auto-detected if omitted)")
    discover.add_argument(
        "--timeout", type=float, default=5.0, help="Discovery timeout in seconds (default: 5.0)"
    )

    return parser


def _cmd_list_ports() -> int:
    ports = list_available_ports()
    if not ports:
        print("No serial ports found.")
        return 1

    for port in ports:
        print(port)
    return 0


async def _cmd_discover(port: str | None, timeout: float) -> int:
    config = NetworkConfig(
        port=port,
        discovery_timeout=timeout,
        interface_type=InterfaceType.ENTTEC_USB_PRO,
    )

    async with NetworkManager(config) as manager:
        devices = await manager.discover_devices()
        print(f"Discovered {len(devices)} device(s) on {manager.config.port}")
        for uid in manager.devices.get_all_uids():
            print(f"  {uid:012X}")

    return 0


async def _async_main(argv: Sequence[str] | None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    if args.command == "list-ports":
        return _cmd_list_ports()
    if args.command == "discover":
        return await _cmd_discover(args.port, args.timeout)

    parser.error(f"Unknown command: {args.command}")
    return 2  # pragma: no cover - argparse.error() exits before this is reached


def main(argv: Sequence[str] | None = None) -> None:
    """Synchronous entry point registered as the `rdm-dmx` console script."""
    try:
        exit_code = asyncio.run(_async_main(argv))
    except KeyboardInterrupt:
        exit_code = 130
    except RuntimeError as e:
        logger.error("%s", e)
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
