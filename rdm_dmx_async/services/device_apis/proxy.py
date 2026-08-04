"""RDM proxy management PIDs - PROXIED_DEVICES and PROXIED_DEVICE_COUNT."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID
from ...packets.types import UID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class ProxyAPI:
    """API for RDM proxy management - only meaningful when the target device is a proxy."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_proxied_device_count(self, use_cache: bool = True) -> tuple[int, bool] | None:
        """
        Get the number of devices this proxy is representing.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Tuple of (device_count, list_change_flag) or None
        """
        pid_value = StandardPID.PROXIED_DEVICE_COUNT.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 3:
            device_count = struct.unpack(">H", bytes(response_data[:2]))[0]
            list_change = bool(response_data[2])
            value = (device_count, list_change)
            if use_cache:
                self._device.cache_set(pid_value, value)
            return value
        return None

    async def get_proxied_devices(self) -> list[UID] | None:
        """
        Get the UIDs of all devices represented by this proxy.

        Returns:
            List of proxied device UIDs, or None on failure
        """
        response_data = await self._device.execute_get(pid=StandardPID.PROXIED_DEVICES.value)

        if response_data is None:
            return None

        uids = []
        for i in range(0, len(response_data), 6):
            if i + 6 <= len(response_data):
                uid_value = int.from_bytes(response_data[i : i + 6], byteorder="big")
                uids.append(UID(uid_value))
        return uids
