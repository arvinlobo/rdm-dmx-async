# rdm-dmx-async

`rdm-dmx-async` is an async-first Python library for controlling DMX512
universes and managing RDM devices. It provides packet encoding and decoding,
serial transport, RDM discovery, request/response correlation, retry policies,
device parameter APIs, and high-level network lifecycle management.

The project currently targets the ENTTEC DMX USB Pro interface. DMXKing
adapter types are present as extension points, but their framing
implementation is not yet complete.

> **Project status:** Alpha. The public API may change before the first stable
> release.

## Requirements

- Python 3.11 or newer
- A supported USB DMX/RDM interface
- Appropriate serial drivers for the interface
- A DMX cable and, where required, bus termination
- Node.js 18 or newer, only if you plan to run the [Web UI](#web-ui-rest-api--react-frontend)

## Installation

Install the package from the repository:

```console
python -m pip install .
```

For development with [uv](https://docs.astral.sh/uv/):

```console
uv sync --extra dev --extra docs
```

The core runtime dependency is `pyserial`.

## Command-line interface

Installation provides the `rdm-dmx` command.

List available serial ports:

```console
rdm-dmx list-ports
```

Discover RDM devices using an automatically detected ENTTEC interface:

```console
rdm-dmx discover
```

Specify the serial port and discovery timeout when needed:

```console
rdm-dmx --verbose discover --port COM3 --timeout 10
```

On Linux, a port will typically look like `/dev/ttyUSB0` instead of `COM3`.

## RDM discovery

`NetworkManager` owns the transport, protocol, discovery service, and device
collection. Using it as an async context manager ensures that all background
tasks and the serial connection are cleaned up.

```python
import asyncio

from rdm_dmx_async import NetworkConfig, NetworkManager


async def main() -> None:
    config = NetworkConfig(port="COM3")

    async with NetworkManager(config) as manager:
        devices = await manager.discover_devices()

        for device in devices:
            print(f"{device.uid:012X}: {device.state.device_label}")


asyncio.run(main())
```

Omit `port` to auto-detect the first compatible ENTTEC interface:

```python
config = NetworkConfig()
```

Discovered devices expose focused API groups for common RDM parameters:

```python
async with NetworkManager(NetworkConfig(port="COM3")) as manager:
    devices = await manager.discover_devices()
    if not devices:
        return

    device = devices[0]

    await device.device_label.set("Front Wash")
    await device.dmx_config.set_start_address(1)
    await device.control.identify(True)

    label = await device.device_label.get()
    sensor_definitions = (
        await device.sensor_definitions.get_all_sensor_definitions()
    )

    print(label, sensor_definitions)
```

Other API groups include sensors, maintenance, device information, DMX slots
and modes, lamp control, display settings, position configuration, power,
self-test, presets, and system information.

## DMX output

DMX fixtures require a continuously refreshed stream. Sending a universe once
may produce only a brief flash.

```python
import asyncio

from rdm_dmx_async import NetworkConfig, NetworkManager


async def main() -> None:
    # Channels 1–3 at full intensity; all remaining channels are zero.
    universe = bytes([255, 255, 255] + [0] * 509)
    refresh_interval = 1 / 44

    async with NetworkManager(NetworkConfig(port="COM3")) as manager:
        try:
            while True:
                await manager.send_dmx(universe)
                await asyncio.sleep(refresh_interval)
        finally:
            # Send several blackout frames before disconnecting.
            blackout = bytes(512)
            for _ in range(10):
                await manager.send_dmx(blackout)
                await asyncio.sleep(refresh_interval)


asyncio.run(main())
```

Runnable demonstrations are available in [`examples/`](examples/):

```console
python examples/simple_dmx_example.py --port COM3
python examples/simple_dmx_example.py --port COM3 --example fade
python examples/simple_dmx_example.py --port COM3 --example rgb
python examples/srp_network_manager_example.py
```

## Public API

Frequently used objects are re-exported from `rdm_dmx_async`:

- Application: `NetworkManager`, `NetworkConfig`
- Services: `RdmDevice`, `DeviceRepository`, `DiscoveryService`
- Protocol: `RDME120Protocol`, `ResponseCorrelator`, `RdmValidator`
- Transport: `AsyncSerialTransport`, `EnttecAdapter`, `InterfaceAdapter`
- Packets: `RDMRequest`, `RDMResponse`, `PacketEncoder`, `PacketDecoder`
- Transactions: `AsyncTransaction`, `RetryPolicy`, `TransactionResult`
- Scheduling: `DmxFrameScheduler`
- Types and helpers: `UID`, `PID`, `CommandClass`, UID conversion helpers

Importing from the top-level package is recommended for these stable entry
points:

```python
from rdm_dmx_async import (
    CommandClass,
    NetworkConfig,
    NetworkManager,
    RDMRequest,
    UID,
    uid_from_string,
)
```

## API documentation with pdoc

Install the documentation dependencies and generate the full API reference:

```console
uv sync --extra docs
uv run pdoc rdm_dmx_async --output-directory docs/api
```

To serve the documentation locally with live reload:

```console
uv run pdoc rdm_dmx_async
```

## Web UI (REST API + React frontend)

A FastAPI backend (`api/`) exposes device discovery/control and DMX output
over HTTP, and a Vite + React frontend (`frontend/`) provides a browser UI on
top of it. Both are optional and separate from the core library.

Install the API extra and start the backend (defaults to port 8000):

```console
uv sync --extra api
uv run uvicorn api.app:app --reload --reload-dir api --reload-dir rdm_dmx_async
```

The `--reload-dir` flags scope the file watcher to the source directories;
without them, uvicorn watches the whole working directory (including
`.venv`), which triggers a reload loop on Windows.

The `NetworkManager` is not started automatically - use the UI's Connect
button, or `POST /network/connect`, to open the serial connection.

In a second terminal, start the frontend:

```console
cd frontend
npm install
npm run dev
```

Open the printed URL (default `http://localhost:5173`) - it expects the
backend at `http://localhost:8000` (CORS is preconfigured for this).

### Production build (single process)

For day-to-day use on an operator's machine, you don't need two dev
processes (Vite + uvicorn) or CORS. Build the frontend once, and the
FastAPI backend will serve it directly:

```console
cd frontend
npm install
npm run build
cd ..
uv sync --extra api
uv run uvicorn api.app:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/` - the API and UI are served from the
same origin/port, so no `--reload` and no separate Node/Vite process are
needed at runtime. `api/app.py` automatically mounts `frontend/dist` at `/`
when it exists; if it's missing (no build was run), the backend still
serves the API only. Rebuild the frontend (`npm run build`) after any
frontend code change to pick it up.

See `docs/ARCHITECTURE.md` and `frontend/README.md` for more detail.

### Standalone .exe (Windows)

For non-developer end users, the production build can be packaged as a
single Windows executable with PyInstaller - no Python, Node, or `uv`
needs to be installed on the target machine:

```console
cd frontend
npm install
npm run build
cd ..
uv sync --extra exe
uv run pyinstaller packaging/rdm_dmx.spec
```

This produces `dist/rdm-dmx.exe`, which bundles the Python runtime, all
dependencies, and the built frontend. Double-clicking it starts the
server on `http://127.0.0.1:8000` and opens it in the default browser;
closing the console window stops the server. Rebuild both the frontend
and the exe after any code change - nothing is watched/hot-reloaded in
this mode.

Every public module, class, function, method, and property has a pdoc-compatible
docstring.

## Development

Install the development environment:

```console
uv sync --extra dev --extra docs
uv run pre-commit install
```

Run the automated tests:

```console
uv run pytest
```

Run static checks:

```console
uv run ruff check rdm_dmx_async tests
uv run mypy rdm_dmx_async
```

Run every pre-commit hook manually:

```console
uv run pre-commit run --all-files
```

Tests that require connected DMX/RDM hardware are kept separately in
[`hardware_tests/`](hardware_tests/).

## Project layout

```text
rdm_dmx_async/
├── application/       High-level network orchestration
├── domain/            Standard parameter identifiers
├── packets/           RDM packet types, encoding, and decoding
├── protocols/         E1.20 operations, validation, and correlation
├── scheduling/        DMX refresh and RDM request windows
├── services/          Discovery, devices, repositories, and PID APIs
├── transaction/       Transactions, retries, allocation, and results
└── transport/         Async serial transport and hardware adapters
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a detailed description
of the layers and their responsibilities.

## Troubleshooting

If an interface or fixture is not responding:

1. Confirm the serial port with `rdm-dmx list-ports`.
2. Close other software that may have opened the same serial port.
3. Verify the fixture's DMX address, personality, and operating mode.
4. Use a proper DMX cable and check signal direction and termination.
5. Ensure DMX output is refreshed continuously rather than sent once.

Additional guides:

- [`DMX_QUICK_START.md`](DMX_QUICK_START.md)
- [`DMX_TROUBLESHOOTING.md`](DMX_TROUBLESHOOTING.md)
- [`NEW_ENTTEC_DMX_USB_PRO_API.pdf`](NEW_ENTTEC_DMX_USB_PRO_API.pdf)

## Standards and references

- ANSI E1.11, USITT DMX512-A
- ANSI E1.20, Remote Device Management
- ANSI E1.37-1, additional RDM parameter messages
- ENTTEC DMX USB Pro API
