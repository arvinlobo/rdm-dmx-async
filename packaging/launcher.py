"""
Standalone entry point used to package rdm-dmx-async as a single executable
(see packaging/rdm_dmx.spec). Not used by normal `uv run` / dev workflows -
use `uvicorn api.app:app` for that (see README.md).

Imports the FastAPI app directly (rather than the "api.app:app" import
string) so it resolves correctly inside a frozen PyInstaller build. Serves
the bundled `frontend/dist` (if present) and opens the default browser once
the server is listening.
"""

import threading
import time
import webbrowser

import uvicorn

from api.app import app

HOST = "127.0.0.1"
PORT = 8000


def _open_browser() -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT}/")


def main() -> None:
    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
