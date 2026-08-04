"""Logging setup for the REST API / packaged desktop app.

Console output alone is invisible once this project runs as a packaged
Windows executable (no attached terminal, see `packaging/launcher.py`), so
this attaches a rotating file handler in addition to the console so users
can locate and send us logs for troubleshooting.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3
_MANAGED_ATTR = "_rdm_dmx_managed"


def default_log_dir() -> Path:
    """Log directory relative to the current working directory."""
    return Path.cwd() / "logs"


def configure_logging(level: int = logging.INFO, log_dir: Path | None = None) -> Path:
    """Attach console + rotating file handlers to the root logger.

    Safe to call more than once (e.g. under `--reload`): previously added
    handlers are removed first so they aren't duplicated.

    Returns the path of the log file being written to.
    """
    log_dir = log_dir or default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "rdm-dmx.log"

    root = logging.getLogger()
    root.setLevel(level)
    for handler in [h for h in root.handlers if getattr(h, _MANAGED_ATTR, False)]:
        root.removeHandler(handler)

    formatter = logging.Formatter(_LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    setattr(console_handler, _MANAGED_ATTR, True)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    setattr(file_handler, _MANAGED_ATTR, True)
    root.addHandler(file_handler)

    return log_file
