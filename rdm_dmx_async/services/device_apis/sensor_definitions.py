"""Sensor definition PIDs - SENSOR_DEFINITION."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID, sensor_prefix_decimals, sensor_prefix_factor

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class SensorDefinitionsAPI:
    """API for sensor definitions - SENSOR_DEFINITION PID."""

    def __init__(self, device: "RdmDevice"):
        self._device = device
        self._cached_definitions: list[dict] | None = None

    async def get_sensor_definition(self, sensor_number: int) -> dict | None:
        """
        Get sensor definition for a specific sensor.

        Args:
            sensor_number: Sensor index (0-based)

        Returns:
            Dictionary with sensor definition or None
        """

        data = struct.pack("B", sensor_number)
        response_data = await self._device.execute_get(
            pid=StandardPID.SENSOR_DEFINITION.value,
            data=data,
        )

        if response_data and len(response_data) >= 13:
            prefix = response_data[3]
            # Range/normal values are in the sensor's own units, scaled by its own
            # PREFIX field (ANSI E1.20) - not a fixed divisor.
            factor = sensor_prefix_factor(prefix)
            decimals = sensor_prefix_decimals(prefix)
            range_min = struct.unpack(">h", bytes(response_data[4:6]))[0]
            range_max = struct.unpack(">h", bytes(response_data[6:8]))[0]
            normal_min = struct.unpack(">h", bytes(response_data[8:10]))[0]
            normal_max = struct.unpack(">h", bytes(response_data[10:12]))[0]
            sensor_def = {
                "sensor_number": response_data[0],
                "type": response_data[1],
                "unit": response_data[2],
                "prefix": prefix,
                "range_min": round(range_min * factor, decimals),
                "range_max": round(range_max * factor, decimals),
                "normal_min": round(normal_min * factor, decimals),
                "normal_max": round(normal_max * factor, decimals),
                "supports_recording": response_data[12] & 0x01,
                "description": response_data[13:].decode("utf-8", errors="ignore").strip("\x00")
                if len(response_data) > 13
                else "",
            }
            return sensor_def
        return None

    async def get_all_sensor_definitions(self, use_cache: bool = True) -> list[dict]:
        """
        Get sensor definitions for all sensors.

        Args:
            use_cache: Whether to use cached definitions

        Returns:
            List of sensor definition dictionaries
        """
        if use_cache and self._cached_definitions is not None:
            return self._cached_definitions

        sensor_count = self._device.state.sensor_count
        if sensor_count <= 0:
            return []

        definitions = []
        for sensor_num in range(sensor_count):
            definition = await self.get_sensor_definition(sensor_num)
            if definition:
                definitions.append(definition)

        self._cached_definitions = definitions
        return definitions

    def get_cached_definition(self, sensor_number: int) -> dict | None:
        """Look up a sensor's definition from the cache without an RDM round-trip.

        Returns None if `get_all_sensor_definitions()` hasn't been called yet
        (or the cache was invalidated), rather than triggering a live fetch.
        """
        if not self._cached_definitions:
            return None
        for definition in self._cached_definitions:
            if definition["sensor_number"] == sensor_number:
                return definition
        return None

    def invalidate_cache(self) -> None:
        """Discard the cached collection of sensor definitions."""
        self._cached_definitions = None
