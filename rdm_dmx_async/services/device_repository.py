"""Repository for managing RDM device collections."""

import logging
from datetime import datetime, timedelta

from ..packets.types import UID
from ..protocols.base import RdmProtocol
from .rdm_device import RdmDevice


class DeviceRepository:
    """Repository for managing RDM devices."""

    def __init__(self, protocol: RdmProtocol, stale_timeout: float = 300.0):
        self._protocol = protocol
        self._devices: dict[UID, RdmDevice] = {}
        self._stale_timeout = stale_timeout
        self._logger = logging.getLogger(self.__class__.__name__)

    def add_device(self, uid: UID) -> RdmDevice:
        """Add ``uid`` if necessary and return its device facade."""
        if uid not in self._devices:
            device = RdmDevice(uid, self._protocol)
            self._devices[uid] = device
            self._logger.info(f"Added device {uid:012X}")
        return self._devices[uid]

    def get_device(self, uid: UID) -> RdmDevice | None:
        """Return the device for ``uid``, or ``None`` if it is unknown."""
        return self._devices.get(uid)

    def get_all_devices(self) -> list[RdmDevice]:
        """Return a snapshot list of every known device."""
        return list(self._devices.values())

    def remove_device(self, uid: UID) -> bool:
        """Remove ``uid`` and return whether it was present."""
        if uid in self._devices:
            del self._devices[uid]
            self._logger.info(f"Removed device {uid:012X}")
            return True
        return False

    def cleanup_stale_devices(self) -> int:
        """Remove devices not seen within the configured stale timeout.

        Returns:
            The number of devices removed.
        """
        now = datetime.now()
        stale_uids = [
            uid
            for uid, device in self._devices.items()
            if device.state.last_seen
            and (now - device.state.last_seen) > timedelta(seconds=self._stale_timeout)
        ]

        for uid in stale_uids:
            self.remove_device(uid)

        return len(stale_uids)

    def get_responsive_devices(self) -> list[RdmDevice]:
        """Return all devices currently marked as responsive."""
        return [d for d in self._devices.values() if d.state.is_responsive]
