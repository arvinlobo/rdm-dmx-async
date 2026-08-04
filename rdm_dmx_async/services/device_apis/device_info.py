"""Device information PIDs - model description, boot version, product details, etc."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class DeviceInfoAPI:
    """API for device information PIDs - read-only device metadata."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_model_description(self, use_cache: bool = True) -> str:
        """
        Get device model description.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Model description string
        """
        return await self._device.get_string_parameter(
            StandardPID.DEVICE_MODEL_DESCRIPTION, use_cache=use_cache
        )

    async def get_boot_software_version(self, use_cache: bool = True) -> str:
        """
        Get boot software version label.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Boot software version string
        """
        return await self._device.get_string_parameter(
            StandardPID.BOOT_SOFTWARE_VERSION_LABEL, use_cache=use_cache
        )

    async def get_boot_software_version_id(self, use_cache: bool = True) -> int | None:
        """
        Get numeric boot software version ID.

        Args:
            use_cache: Whether to use cached value

        Returns:
            32-bit version ID or None
        """
        pid_value = StandardPID.BOOT_SOFTWARE_VERSION_ID.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 4:
            version_id = struct.unpack(">I", bytes(response_data[:4]))[0]
            if use_cache:
                self._device.cache_set(pid_value, version_id)
            return version_id
        return None

    async def get_product_detail_id_list(self, use_cache: bool = True) -> list[int] | None:
        """
        Get list of product detail IDs describing this device's category.

        Args:
            use_cache: Whether to use cached value

        Returns:
            List of product detail ID values or None
        """
        pid_value = StandardPID.PRODUCT_DETAIL_ID_LIST.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data:
            details = []
            for i in range(0, len(response_data), 2):
                if i + 1 < len(response_data):
                    detail_id = struct.unpack(">H", bytes(response_data[i : i + 2]))[0]
                    details.append(detail_id)
            if use_cache:
                self._device.cache_set(pid_value, details)
            return details
        return None
