"""Sensor PIDs - get sensor values and record sensors."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class SensorsAPI:
    """API for sensor PIDs - SENSOR_VALUE and RECORD_SENSORS."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_value(self, sensor_number: int) -> dict | None:
        """
        Get sensor value for a specific sensor.

        Args:
            sensor_number: Sensor index (0-based)

        Returns:
            Dictionary with sensor data or None
        """
        data = struct.pack("B", sensor_number)
        response_data = await self._device.execute_get(
            pid=StandardPID.SENSOR_VALUE.value,
            data=data,
        )

        if response_data and len(response_data) >= 9:
            return {
                "sensor_number": response_data[0],
                "present_value": struct.unpack(">h", bytes(response_data[1:3]))[0],
                "lowest": struct.unpack(">h", bytes(response_data[3:5]))[0],
                "highest": struct.unpack(">h", bytes(response_data[5:7]))[0],
                "recorded": struct.unpack(">h", bytes(response_data[7:9]))[0],
            }
        return None

    async def record(self, sensor_number: int = 0xFF) -> bool:
        """
        Record sensor values (0xFF = all sensors).

        Args:
            sensor_number: Sensor to record (0xFF for all)

        Returns:
            True if successful
        """
        data = struct.pack("B", sensor_number)
        return await self._device.execute_set(
            pid=StandardPID.RECORD_SENSORS.value,
            data=data,
        )
