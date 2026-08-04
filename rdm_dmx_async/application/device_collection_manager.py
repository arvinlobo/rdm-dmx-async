"""
Device collection management service.

Manages the collection of discovered RDM devices.
"""

import logging

from ..packets.types import UID
from ..services import RdmDevice


class DeviceCollectionManager:
    """
    Manages collection of discovered RDM devices.

    Single Responsibility: Device collection tracking and access
    """

    def __init__(self):
        self._devices: dict[UID, RdmDevice] = {}
        self._logger = logging.getLogger(self.__class__.__name__)

    def add_device(self, device: RdmDevice) -> None:
        """
        Add device to collection.

        Args:
            device: RdmDevice instance to add
        """
        uid = device.uid
        if uid in self._devices:
            self._logger.debug("Device %012X already exists, updating reference", uid)
        else:
            self._logger.debug("Adding device %012X to collection", uid)

        self._devices[uid] = device

    def remove_device(self, uid: UID) -> bool:
        """
        Remove device from collection.

        Args:
            uid: Device UID to remove

        Returns:
            True if device was removed, False if not found
        """
        if uid in self._devices:
            del self._devices[uid]
            self._logger.debug("Removed device %012X from collection", uid)
            return True
        else:
            self._logger.debug("Device %012X not found in collection", uid)
            return False

    def get_device(self, uid: UID) -> RdmDevice | None:
        """
        Get device by UID.

        Args:
            uid: Device UID

        Returns:
            RdmDevice instance or None if not found
        """
        return self._devices.get(uid)

    def has_device(self, uid: UID) -> bool:
        """
        Check if device exists in collection.

        Args:
            uid: Device UID

        Returns:
            True if device exists
        """
        return uid in self._devices

    def get_all_devices(self) -> list[RdmDevice]:
        """
        Get all devices in collection.

        Returns:
            List of all RdmDevice instances
        """
        return list(self._devices.values())

    def get_all_uids(self) -> list[UID]:
        """
        Get all device UIDs in collection.

        Returns:
            List of UIDs
        """
        return list(self._devices.keys())

    def get_device_count(self) -> int:
        """
        Get count of devices in collection.

        Returns:
            Number of devices
        """
        return len(self._devices)

    def clear(self) -> None:
        """Clear all devices from collection."""
        count = len(self._devices)
        self._devices.clear()
        self._logger.debug("Cleared %d devices from collection", count)

    def clear_all_caches(self) -> None:
        """Clear parameter cache for all devices in collection."""
        for device in self._devices.values():
            device.clear_cache()
        self._logger.debug("Cleared caches for %d devices", len(self._devices))

    def get_devices_dict(self) -> dict[UID, RdmDevice]:
        """
        Get internal devices dictionary (for iteration).

        Returns:
            Dictionary mapping UIDs to RdmDevice instances
        """
        return self._devices

    def __len__(self) -> int:
        """Get device count via len()."""
        return len(self._devices)

    def __contains__(self, uid: UID) -> bool:
        """Check device existence via 'in' operator."""
        return uid in self._devices

    def __iter__(self):
        """Iterate over (uid, device) pairs."""
        return iter(self._devices.items())
