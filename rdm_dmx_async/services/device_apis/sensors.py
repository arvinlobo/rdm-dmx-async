"""Sensor PIDs - get sensor values and record sensors."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID, sensor_prefix_decimals, sensor_prefix_factor

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class SensorsAPI:
    """API for sensor PIDs - SENSOR_VALUE and RECORD_SENSORS."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def get_value(self, sensor_number: int) -> dict | None:
        """
        Get sensor value for a specific sensor.

        Values are scaled by the sensor's PREFIX (ANSI E1.20) when its
        definition is already cached (see `SensorDefinitionsAPI`); otherwise
        the raw wire values are returned unscaled, since the prefix is
        unknown without an extra round-trip.

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
            present_value = struct.unpack(">h", bytes(response_data[1:3]))[0]
            lowest = struct.unpack(">h", bytes(response_data[3:5]))[0]
            highest = struct.unpack(">h", bytes(response_data[5:7]))[0]
            recorded = struct.unpack(">h", bytes(response_data[7:9]))[0]

            definition = self._device.sensor_definitions.get_cached_definition(sensor_number)
            if definition is not None:
                factor = sensor_prefix_factor(definition["prefix"])
                decimals = sensor_prefix_decimals(definition["prefix"])
                present_value = round(present_value * factor, decimals)
                lowest = round(lowest * factor, decimals)
                highest = round(highest * factor, decimals)
                recorded = round(recorded * factor, decimals)

            return {
                "sensor_number": response_data[0],
                "present_value": present_value,
                "lowest": lowest,
                "highest": highest,
                "recorded": recorded,
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
