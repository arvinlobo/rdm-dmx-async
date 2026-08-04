"""
End-to-end DMX/RDM latency benchmark: direct library calls vs the FastAPI HTTP layer.

Measures the same two operations (an RDM GET and a DMX send) both ways so the
difference isolates the HTTP/FastAPI request-handling overhead from the actual
hardware round-trip time. The React frontend itself adds no extra hardware
latency - it just issues the same HTTP calls the "http" mode does here.

Usage:
    # Direct: opens the serial port itself, bypassing FastAPI/HTTP entirely.
    uv run hardware_tests/benchmark_latency.py direct --port COM5

    # HTTP: hits an already-running, already-connected backend
    # (start it first: uv run uvicorn api.app:app, then POST /network/connect
    # and POST /devices/discover, or just launch the frontend and connect there).
    uv run hardware_tests/benchmark_latency.py http --base-url http://localhost:8000 --uid 056C4729D469
"""

import argparse
import asyncio
import logging
import statistics
import time

from rdm_dmx_async import NetworkConfig, NetworkManager
from rdm_dmx_async.packets.types import UID

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

N_ITERATIONS = 30


def summarize(label: str, samples_ms: list[float]) -> None:
    ordered = sorted(samples_ms)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    print(
        f"{label:<28} n={len(ordered):<3} avg={statistics.mean(ordered):6.1f}ms "
        f"min={ordered[0]:6.1f}ms max={ordered[-1]:6.1f}ms p95={p95:6.1f}ms"
    )


async def run_direct(port: str | None, uid_hex: str | None) -> None:
    """Call the async library directly - no FastAPI, no HTTP, no browser."""
    config = NetworkConfig(port=port)
    manager = NetworkManager(config)
    await manager.start()
    print(f"Connected directly on {manager.config.port} (no HTTP layer involved)\n")
    try:
        if uid_hex is not None:
            devices = await manager.discover_devices(known_uids=[UID(int(uid_hex, 16))])
        else:
            devices = await manager.discover_devices()
        if not devices:
            raise SystemExit("No RDM devices found")
        device = devices[0]
        print(f"Target device: {device.uid:012X}\n")

        rdm_samples: list[float] = []
        for _ in range(N_ITERATIONS):
            start = time.perf_counter()
            await device.dmx_config.get_personality(use_cache=False)
            rdm_samples.append((time.perf_counter() - start) * 1000)

        dmx_samples: list[float] = []
        for i in range(N_ITERATIONS):
            channels = bytes([i % 256] + [0] * 511)
            start = time.perf_counter()
            await manager.send_dmx(channels)
            dmx_samples.append((time.perf_counter() - start) * 1000)

        summarize("DIRECT RDM get_personality", rdm_samples)
        summarize("DIRECT DMX send_dmx", dmx_samples)
    finally:
        await manager.stop()


async def run_http(base_url: str, uid_hex: str) -> None:
    """Hit the running FastAPI server's HTTP endpoints - the same calls the React UI makes."""
    import httpx

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        status = await client.get("/network/status")
        status.raise_for_status()
        if not status.json().get("connected"):
            raise SystemExit(
                "Backend is not connected. POST /network/connect (and discover a device) first."
            )
        print(f"Using already-connected backend at {base_url}\n")

        rdm_samples: list[float] = []
        for _ in range(N_ITERATIONS):
            start = time.perf_counter()
            # use_cache=False to match the direct-mode call and force a real wire round-trip.
            resp = await client.post(
                f"/devices/{uid_hex}/modules/dmx_config/get_personality", json={"args": [False]}
            )
            resp.raise_for_status()
            rdm_samples.append((time.perf_counter() - start) * 1000)

        dmx_samples: list[float] = []
        for i in range(N_ITERATIONS):
            channels = [i % 256] + [0] * 511
            start = time.perf_counter()
            resp = await client.post("/dmx/send", json={"channels": channels})
            resp.raise_for_status()
            dmx_samples.append((time.perf_counter() - start) * 1000)

        summarize("HTTP RDM get_personality", rdm_samples)
        summarize("HTTP DMX send_dmx", dmx_samples)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    direct_p = sub.add_parser(
        "direct", help="Bypass FastAPI/HTTP - call the async library directly"
    )
    direct_p.add_argument("--port", default=None, help="Serial port (default: auto-detect)")
    direct_p.add_argument("--uid", default=None, help="Known device UID hex (skips full discovery)")

    http_p = sub.add_parser("http", help="Go through the running FastAPI server over HTTP")
    http_p.add_argument("--base-url", default="http://localhost:8000")
    http_p.add_argument("--uid", required=True, help="Device UID hex to target")

    args = parser.parse_args()
    if args.mode == "direct":
        asyncio.run(run_direct(args.port, args.uid))
    else:
        asyncio.run(run_http(args.base_url, args.uid))


if __name__ == "__main__":
    main()
