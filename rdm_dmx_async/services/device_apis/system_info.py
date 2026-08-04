"""System information PIDs - language, supported parameters, queued messages, status, comms."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class SystemInfoAPI:
    """API for system info PIDs - language, parameters, queued messages, status, comms."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_supported_parameters(self, use_cache: bool = True) -> list[int] | None:
        """
        Get list of supported PIDs.

        Args:
            use_cache: Whether to use cached value

        Returns:
            List of supported PID values or None
        """
        pid_value = StandardPID.SUPPORTED_PARAMETERS.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data:
            # Each PID is 2 bytes (big-endian)
            pids = []
            for i in range(0, len(response_data), 2):
                if i + 1 < len(response_data):
                    pid = struct.unpack(">H", bytes(response_data[i : i + 2]))[0]
                    pids.append(pid)
            if use_cache:
                self._device.cache_set(pid_value, pids)
            return pids
        return None

    async def get_parameter_description(self, pid: int) -> dict | None:
        """
        Get parameter description for a specific PID (ANSI E1.20 sec. 10.7.2 GET_RESPONSE).

        Only PIDs the device itself defines (typically its own manufacturer-specific
        PIDs, 0x8000-0xFFDF) return meaningful data here - standard/native PIDs already
        have their type/range fixed by the E1.20 spec itself, so devices commonly NAK
        UNKNOWN_PID rather than echo back a description for them.

        Args:
            pid: PID to query description for

        Returns:
            Dictionary with parameter metadata (data_type, command_class, unit, prefix,
            min_value, max_value, default_value, description) or None
        """
        data = struct.pack(">H", pid)
        response_data = await self._device.execute_get(
            pid=StandardPID.PARAMETER_DESCRIPTION.value,
            data=data,
        )

        # Fixed-size fields below run 18 bytes (pdl_size..default_value), plus the
        # queried PID itself (2 bytes) = 20 - the variable-length ASCII description
        # (up to 32 bytes) follows and may be absent, so a device with no description
        # text may still return exactly 20.
        if response_data and len(response_data) >= 20:
            queried_pid = struct.unpack(">H", bytes(response_data[:2]))[0]
            pdl_size = response_data[2]
            data_type = response_data[3]
            command_class = response_data[4]
            # response_data[5] is reserved ("type"), always 0x00 per spec
            unit = response_data[6]
            prefix = response_data[7]
            min_value = struct.unpack(">I", bytes(response_data[8:12]))[0]
            max_value = struct.unpack(">I", bytes(response_data[12:16]))[0]
            default_value = struct.unpack(">I", bytes(response_data[16:20]))[0]
            description = (
                bytes(response_data[20:]).split(b"\x00")[0].decode("ascii", errors="replace")
            )
            return {
                "pid": queried_pid,
                "pdl_size": pdl_size,
                "data_type": data_type,
                "command_class": command_class,
                "unit": unit,
                "prefix": prefix,
                "min_value": min_value,
                "max_value": max_value,
                "default_value": default_value,
                "description": description,
            }
        return None

    async def get_queued_message(self, status_type: int = 0x00) -> dict | None:
        """
        Get queued message from device.

        Args:
            status_type: Status type filter (0x00 for all)

        Returns:
            Dictionary with message data or None
        """
        data = struct.pack("B", status_type)
        response_data = await self._device.execute_get(
            pid=StandardPID.QUEUED_MESSAGE.value,
            data=data,
        )

        if response_data:
            return {"status_type": status_type, "data": list(response_data)}
        return None

    async def get_status_messages(self, status_type: int = 0x00) -> dict | None:
        """
        Get status messages from device.

        Args:
            status_type: Status type filter (0x00 for all)

        Returns:
            Dictionary with status message data or None
        """
        data = struct.pack("B", status_type)
        response_data = await self._device.execute_get(
            pid=StandardPID.STATUS_MESSAGES.value,
            data=data,
        )

        if response_data and len(response_data) >= 2:
            return {
                "status_type": status_type,
                "message_count": struct.unpack(">H", bytes(response_data[:2]))[0]
                if len(response_data) >= 2
                else 0,
                "data": list(response_data),
            }
        return None

    async def get_status_id_description(self, status_id: int) -> str | None:
        """
        Get description for a status ID.

        Args:
            status_id: Status ID to query

        Returns:
            Description string or None
        """
        data = struct.pack(">H", status_id)
        response_data = await self._device.execute_get(
            pid=StandardPID.STATUS_ID_DESCRIPTION.value,
            data=data,
        )

        if response_data:
            # Response: status_id (2 bytes) + description (string)
            if len(response_data) > 2:
                description = response_data[2:].decode("utf-8", errors="ignore").strip("\x00")
                return description
        return None

    async def clear_status_id(self, status_id: int) -> bool:
        """
        Clear a specific status ID.

        Args:
            status_id: Status ID to clear

        Returns:
            True if successful
        """
        data = struct.pack(">H", status_id)
        return await self._device.execute_set(
            pid=StandardPID.CLEAR_STATUS_ID.value,
            data=data,
        )

    async def get_comms_status(self) -> dict | None:
        """
        Get communication error counters (short message, length mismatch, checksum fail).

        Returns:
            Dictionary with error counters or None
        """
        response_data = await self._device.execute_get(pid=StandardPID.COMMS_STATUS.value)

        if response_data and len(response_data) >= 6:
            short_message, length_mismatch, checksum_fail = struct.unpack(
                ">HHH", bytes(response_data[:6])
            )
            return {
                "short_message": short_message,
                "length_mismatch": length_mismatch,
                "checksum_fail": checksum_fail,
            }
        return None

    async def clear_comms_status(self) -> bool:
        """
        Clear the device's communication error counters.

        Returns:
            True if successful
        """
        return await self._device.execute_set(pid=StandardPID.COMMS_STATUS.value, data=b"")

    async def get_sub_device_status_report_threshold(self, use_cache: bool = True) -> int | None:
        """
        Get the minimum status message severity this device will report.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Status type threshold (0x00-0x03) or None
        """
        pid_value = StandardPID.SUB_DEVICE_STATUS_REPORT_THRESHOLD.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 1:
            status_type = response_data[0]
            if use_cache:
                self._device.cache_set(pid_value, status_type)
            return status_type
        return None

    async def set_sub_device_status_report_threshold(self, status_type: int) -> bool:
        """
        Set the minimum status message severity this device should report.

        Args:
            status_type: Status type threshold (0x00-0x03)

        Returns:
            True if successful
        """
        data = struct.pack("B", status_type)
        success = await self._device.execute_set(
            pid=StandardPID.SUB_DEVICE_STATUS_REPORT_THRESHOLD.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.SUB_DEVICE_STATUS_REPORT_THRESHOLD.value)
        return success

    async def get_language_capabilities(self, use_cache: bool = True) -> list[str] | None:
        """
        Get supported language codes.

        Args:
            use_cache: Whether to use cached value

        Returns:
            List of language codes or None
        """
        pid_value = StandardPID.LANGUAGE_CAPABILITIES.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data:
            # Each language code is 2 bytes (ASCII)
            languages = []
            for i in range(0, len(response_data), 2):
                if i + 1 < len(response_data):
                    lang = bytes(response_data[i : i + 2]).decode("ascii", errors="ignore")
                    languages.append(lang)
            if use_cache:
                self._device.cache_set(pid_value, languages)
            return languages
        return None

    async def get_language(self, use_cache: bool = True) -> str | None:
        """
        Get current language setting.

        Args:
            use_cache: Whether to use cached value

        Returns:
            Language code or None
        """
        pid_value = StandardPID.LANGUAGE.value

        if use_cache:
            cached = self._device.cache_get(pid_value)
            if cached is not None:
                return cached

        response_data = await self._device.execute_get(pid=pid_value)

        if response_data and len(response_data) >= 2:
            language = bytes(response_data[:2]).decode("ascii", errors="ignore")
            if use_cache:
                self._device.cache_set(pid_value, language)
            return language
        return None

    async def set_language(self, language: str) -> bool:
        """
        Set device language.

        Args:
            language: 2-character language code (e.g., 'en')

        Returns:
            True if successful
        """
        if len(language) != 2:
            self._device.logger.error("Invalid language code: %s (must be 2 characters)", language)
            return False

        data = language.encode("ascii")
        success = await self._device.execute_set(
            pid=StandardPID.LANGUAGE.value,
            data=data,
        )
        if success:
            self._device.clear_cache(StandardPID.LANGUAGE.value)
        return success
