"""
Batch operation service for multi-device operations.

Executes operations across multiple RDM devices concurrently.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from ..packets.types import UID

if TYPE_CHECKING:
    from ..services import RdmDevice
    from .device_collection_manager import DeviceCollectionManager


class BatchOperationService:
    """
    Handles batch operations across multiple devices.

    Single Responsibility: Multi-device concurrent operations
    """

    def __init__(self, device_manager: "DeviceCollectionManager"):
        """
        Initialize batch operation service.

        Args:
            device_manager: Device collection manager instance
        """
        self._device_manager = device_manager
        self._logger = logging.getLogger(self.__class__.__name__)

    async def query_all_device_info(self) -> dict[UID, dict]:
        """
        Query device information from all devices concurrently.

        Returns:
            Dictionary mapping UIDs to device info dictionaries
        """
        results = {}
        tasks = []
        devices_list = []

        for uid, device in self._device_manager:
            devices_list.append((uid, device))
            tasks.append(self._query_device_info(device))

        if tasks:
            self._logger.debug("Querying device info for %d devices", len(tasks))
            query_results = await asyncio.gather(*tasks, return_exceptions=True)

            for (uid, _), result in zip(devices_list, query_results, strict=True):
                if isinstance(result, Exception):
                    self._logger.error("Error querying %012X: %s", uid, result)
                else:
                    results[uid] = result

        return results

    async def _query_device_info(self, device: "RdmDevice") -> dict:
        """Query single device info."""
        await device.get_device_info()

        return {
            "uid": device.uid,
            "manufacturer": device.state.manufacturer,
            "device_label": device.state.device_label,
            "software_version": device.state.software_version,
            "rdm_protocol_version": device.state.rdm_protocol_version,
            "device_model_id": device.state.device_model_id,
            "dmx_start_address": device.state.dmx_start_address,
        }

    async def query_all_device_labels(self) -> dict[UID, str]:
        """
        Query device labels from all devices concurrently.

        Returns:
            Dictionary mapping UIDs to device labels
        """
        results = {}
        tasks = []
        uids = []

        for uid, device in self._device_manager:
            uids.append(uid)
            tasks.append(device.device_label.get())

        if tasks:
            self._logger.debug("Querying labels for %d devices", len(tasks))
            labels = await asyncio.gather(*tasks, return_exceptions=True)

            for uid, label in zip(uids, labels, strict=True):
                if isinstance(label, Exception):
                    self._logger.error("Error querying label %012X: %s", uid, label)
                else:
                    results[uid] = label

        return results

    async def set_all_dmx_addresses(self, start_address: int, spacing: int = 1) -> dict[UID, bool]:
        """
        Set DMX addresses for all devices with sequential spacing.

        Args:
            start_address: Starting DMX address
            spacing: Address spacing between devices

        Returns:
            Dictionary mapping UIDs to success status
        """
        results = {}
        address = start_address

        self._logger.info(
            "Setting DMX addresses for %d devices (start=%d, spacing=%d)",
            self._device_manager.get_device_count(),
            start_address,
            spacing,
        )

        for uid, device in self._device_manager:
            try:
                success = await device.dmx_config.set_start_address(address)
                results[uid] = success

                if success:
                    self._logger.debug("Set %012X to address %d", uid, address)
                else:
                    self._logger.warning("Failed to set %012X to address %d", uid, address)

                address += spacing

            except Exception as e:
                self._logger.error("Error setting address for %012X: %s", uid, e)
                results[uid] = False

        return results

    async def identify_all(self, enable: bool = True) -> dict[UID, bool]:
        """
        Enable/disable identify mode on all devices concurrently.

        Args:
            enable: True to enable identify, False to disable

        Returns:
            Dictionary mapping UIDs to success status
        """
        results = {}
        tasks = []
        uids = []

        for uid, device in self._device_manager:
            uids.append(uid)
            tasks.append(device.control.identify(enable))

        if tasks:
            action = "Enabling" if enable else "Disabling"
            self._logger.info("%s identify on %d devices", action, len(tasks))

            statuses = await asyncio.gather(*tasks, return_exceptions=True)

            for uid, status in zip(uids, statuses, strict=True):
                if isinstance(status, Exception):
                    self._logger.error("Error setting identify %012X: %s", uid, status)
                    results[uid] = False
                else:
                    results[uid] = status

        return results

    async def reset_all(self, warm_reset: bool = True) -> dict[UID, bool]:
        """
        Reset all devices concurrently.

        Args:
            warm_reset: True for warm reset, False for cold reset

        Returns:
            Dictionary mapping UIDs to success status
        """
        results = {}
        tasks = []
        uids = []

        for uid, device in self._device_manager:
            uids.append(uid)
            tasks.append(device.control.reset(warm_reset))

        if tasks:
            reset_type = "warm" if warm_reset else "cold"
            self._logger.info("Performing %s reset on %d devices", reset_type, len(tasks))

            statuses = await asyncio.gather(*tasks, return_exceptions=True)

            for uid, status in zip(uids, statuses, strict=True):
                if isinstance(status, Exception):
                    self._logger.error("Error resetting %012X: %s", uid, status)
                    results[uid] = False
                else:
                    results[uid] = status

        return results

    async def get_all_personalities(self) -> dict[UID, tuple]:
        """
        Get DMX personality from all devices concurrently.

        Returns:
            Dictionary mapping UIDs to (current, count) tuples
        """
        results = {}
        tasks = []
        uids = []

        for uid, device in self._device_manager:
            uids.append(uid)
            tasks.append(device.dmx_config.get_personality())

        if tasks:
            self._logger.debug("Querying personalities for %d devices", len(tasks))
            personalities = await asyncio.gather(*tasks, return_exceptions=True)

            for uid, personality in zip(uids, personalities, strict=True):
                if isinstance(personality, Exception):
                    self._logger.error("Error querying personality %012X: %s", uid, personality)
                else:
                    results[uid] = personality

        return results
