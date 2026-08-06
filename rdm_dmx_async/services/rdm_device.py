"""High-level RDM device interface with modular PID API support."""

import logging
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..domain.parameters import StandardPID
from ..packets.types import UID
from ..protocols.base import RdmProtocol
from ..transaction import AsyncTransactionManager
from .device_apis import (
    DeviceControlAPI,
    DeviceInfoAPI,
    DeviceLabelAPI,
    DeviceMaintenanceAPI,
    DisplaySettingsAPI,
    DmxConfigAPI,
    DmxModesAPI,
    DmxSlotsAPI,
    LampControlAPI,
    PositionConfigAPI,
    PowerControlAPI,
    PresetControlAPI,
    ProxyAPI,
    RawPidAPI,
    SelfTestAPI,
    SensorDefinitionsAPI,
    SensorsAPI,
    SystemInfoAPI,
)

# Mapping of API module names to the PIDs they require
API_PID_MAPPING: dict[str, list[StandardPID]] = {
    "device_label": [StandardPID.DEVICE_LABEL],
    "dmx_config": [
        StandardPID.DMX_START_ADDRESS,
        StandardPID.DMX_PERSONALITY,
        StandardPID.DMX_PERSONALITY_DESCRIPTION,
    ],
    "control": [
        StandardPID.IDENTIFY_DEVICE,
        StandardPID.RESET_DEVICE,
        StandardPID.FACTORY_DEFAULTS,
    ],
    "sensors": [
        StandardPID.SENSOR_VALUE,
        StandardPID.RECORD_SENSORS,
    ],
    "sensor_definitions": [StandardPID.SENSOR_DEFINITION],
    "maintenance": [
        StandardPID.DEVICE_HOURS,
        StandardPID.DEVICE_POWER_CYCLES,
    ],
    "info": [
        StandardPID.DEVICE_MODEL_DESCRIPTION,
        StandardPID.BOOT_SOFTWARE_VERSION_LABEL,
        StandardPID.BOOT_SOFTWARE_VERSION_ID,
        StandardPID.PRODUCT_DETAIL_ID_LIST,
    ],
    "slots": [
        StandardPID.SLOT_INFO,
        StandardPID.SLOT_DESCRIPTION,
        StandardPID.DEFAULT_SLOT_VALUE,
    ],
    "modes": [
        StandardPID.DMX_STARTUP_MODE,
        StandardPID.OUTPUT_RESPONSE_TIME,
        StandardPID.CAPTURE_PRESET,
        StandardPID.DMX_BLOCK_ADDRESS,
        StandardPID.DMX_FAIL_MODE,
    ],
    "lamp": [
        StandardPID.LAMP_HOURS,
        StandardPID.LAMP_STRIKES,
        StandardPID.LAMP_STATE,
        StandardPID.LAMP_ON_MODE,
    ],
    "display": [
        StandardPID.DISPLAY_INVERT,
        StandardPID.DISPLAY_LEVEL,
    ],
    "position": [
        StandardPID.PAN_INVERT,
        StandardPID.TILT_INVERT,
        StandardPID.PAN_TILT_SWAP,
        StandardPID.REAL_TIME_CLOCK,
    ],
    "power": [StandardPID.POWER_STATE],
    "self_test": [
        StandardPID.PERFORM_SELFTEST,
        StandardPID.SELF_TEST_DESCRIPTION,
    ],
    "presets": [
        StandardPID.PRESET_PLAYBACK,
        StandardPID.PRESET_STATUS,
        StandardPID.PRESET_MERGEMODE,
    ],
    "system": [
        StandardPID.SUPPORTED_PARAMETERS,
        StandardPID.PARAMETER_DESCRIPTION,
        StandardPID.QUEUED_MESSAGE,
        StandardPID.STATUS_MESSAGES,
        StandardPID.STATUS_ID_DESCRIPTION,
        StandardPID.CLEAR_STATUS_ID,
        StandardPID.SUB_DEVICE_STATUS_REPORT_THRESHOLD,
        StandardPID.COMMS_STATUS,
        StandardPID.LANGUAGE_CAPABILITIES,
        StandardPID.LANGUAGE,
    ],
    "proxy": [
        StandardPID.PROXIED_DEVICES,
        StandardPID.PROXIED_DEVICE_COUNT,
    ],
    # No fixed PID list: this is the raw escape hatch for PIDs with no dedicated API
    # module (manufacturer-specific or otherwise), so it's always shown regardless of
    # which PIDs a given device happens to support - see supports_api()'s special case.
    "raw": [],
}

# Per ANSI E1.20 sec. 10.5, a responder's GET_SUPPORTED_PARAMETERS reply MAY
# omit these mandatory PIDs since every RDM device is required to implement
# them - so their absence from the discovered PID list does NOT mean "not
# supported". Always treat them as supported.
# NOTE: PARAMETER_DESCRIPTION is deliberately NOT here - per E1.20 it's only
# required for responders that expose manufacturer-specific PIDs, so a device
# omitting it from GET_SUPPORTED_PARAMETERS genuinely may not implement it
# (confirmed live: a real device NAK'd UNKNOWN_PID for GET PID=0x51).
_MANDATORY_PIDS: frozenset[int] = frozenset(
    {
        StandardPID.DISC_UNIQUE_BRANCH,
        StandardPID.DISC_MUTE,
        StandardPID.DISC_UN_MUTE,
        StandardPID.SUPPORTED_PARAMETERS,
        StandardPID.DEVICE_INFO,
        StandardPID.SOFTWARE_VERSION_LABEL,
        StandardPID.DMX_START_ADDRESS,
        StandardPID.IDENTIFY_DEVICE,
    }
)


@dataclass
class DeviceState:
    """Cached snapshot of an RDM device's known parameter values.

    Populated as parameters are read via `RdmDevice`'s device API properties
    (e.g. `RdmDevice.device_label`, `RdmDevice.dmx_config`) and kept in sync
    as those APIs perform SETs.
    """

    uid: UID
    """48-bit RDM UID of the device this state describes."""

    # String labels
    manufacturer: str = ""
    device_label: str = ""
    model: str = ""
    software_version: str = ""
    # DEVICE_INFO fields
    rdm_protocol_version: str = ""
    device_model_id: int = 0
    product_category: int = 0
    software_version_id: int = 0
    dmx_footprint: int = 0
    dmx_personality: int = 0
    dmx_personality_count: int = 0
    dmx_start_address: int = 1
    sub_device_count: int = 0
    sensor_count: int = 0
    # State tracking
    last_seen: datetime | None = None
    is_responsive: bool = False


@dataclass
class CachedParameter:
    """Cached parameter value with expiration timestamp."""

    value: Any
    timestamp: datetime = field(default_factory=datetime.now)

    def is_expired(self, max_age: timedelta) -> bool:
        """Return whether the cached value is older than ``max_age``."""
        return (datetime.now() - self.timestamp) > max_age


class RdmDevice:
    """
    High-level RDM device interface with state management, caching, and throttling.

    Features:
    - AsyncTransaction with retry logic and permanent failure detection
    - Parameter caching with configurable expiration
    - Comprehensive device state management
    - Modular PID APIs organized by functionality (composition pattern)
    - Device capability detection and API-to-PID mapping

    Capability Detection:
    - check_capabilities(): Query device for supported PIDs
    - supports_pid(pid): Check if device supports a specific PID
    - supports_api(api_name): Check if device supports an API module
    - get_available_apis(): Get list of supported API modules
    - get_api_support_details(): Get detailed support information
    - print_capability_report(): Print formatted capability report

    PID API Modules (accessed as properties):
    - device_label: get() / set() - DEVICE_LABEL PID
    - dmx_config: set_start_address() / get/set_personality() - DMX configuration
    - control: identify() / reset() / factory_defaults() - Device control
    - sensors: get_value() / record() - Sensor operations
    - sensor_definitions: get_sensor_definition() / get_all_sensor_definitions() - Sensor metadata
    - maintenance: get/set_hours() / get/set_power_cycles() - Device maintenance
    - info: get_model_description() / get_boot_software_version() - Device information
    - slots: get_slot_info() / get_slot_description() / get_all_slot_descriptions() - DMX slots
    - modes: get/set_dmx_startup_mode() / get/set_output_response_time() / capture_preset() / get/set_dmx_block_address() / get/set_dmx_fail_mode() - DMX modes
    - lamp: get/set_hours() / get/set_strikes() / get/set_state() / get/set_on_mode() - Lamp control
    - display: get/set_invert() / get/set_level() - Display settings
    - position: get/set_pan_invert() / get/set_tilt_invert() / get/set_pan_tilt_swap() / get/set_real_time_clock() - Position config
    - power: get/set_state() - Power control
    - self_test: perform() / get_description() - Self-test operations
    - presets: get/set_playback() / get_status() / get/set_merge_mode() - Preset control
    - system: get_supported_parameters() / get_parameter_description() / get_queued_message() / get_status_messages() / get/set_language() / get/clear_comms_status() / get/set_sub_device_status_report_threshold() - System info
    - proxy: get_proxied_devices() / get_proxied_device_count() - RDM proxy management (only meaningful for proxy devices)
    - raw: describe(pid) / get(pid, data_format) / set(pid, value, data_format) - Generic GET/SET
      for any PID (hex/ascii/fixed-width-number encoding), including manufacturer-specific or
      otherwise-unwrapped PIDs with no dedicated API module

    Example usage:
        # Basic API usage
        await device.device_label.set("My Device")
        await device.dmx_config.set_start_address(1)
        await device.sensors.get_value(0)
        definitions = await device.sensor_definitions.get_all_sensor_definitions()
        await device.modes.capture_preset(1)
        await device.lamp.set_hours(1000)
        await device.display.set_level(255)
        await device.position.set_pan_invert(1)
        await device.power.set_state(1)
        await device.self_test.perform(0xFF)
        await device.presets.set_playback(1, 255)

        # Capability detection (optional - APIs work optimistically without checking)
        await device.check_capabilities()
        available = device.get_available_apis()
        device.print_capability_report()
    """

    def __init__(
        self,
        uid: UID,
        protocol: RdmProtocol,
        cache_max_age: timedelta = timedelta(seconds=30),
    ):
        self._uid = uid
        self._protocol = protocol
        self._txn = AsyncTransactionManager(protocol)  # Transaction manager
        self._state = DeviceState(uid=uid)
        self._logger = logging.getLogger(f"{self.__class__.__name__}[{uid:012X}]")

        # Caching
        self._cache_max_age = cache_max_age
        self._parameter_cache: dict[int, CachedParameter] = {}

        # Capability tracking
        self._supported_pids: set[int] | None = None
        self._capabilities_checked = False

        # Compose PID API modules
        self.device_label = DeviceLabelAPI(self)
        self.dmx_config = DmxConfigAPI(self)
        self.control = DeviceControlAPI(self)
        self.sensors = SensorsAPI(self)
        self.sensor_definitions = SensorDefinitionsAPI(self)
        self.maintenance = DeviceMaintenanceAPI(self)
        self.info = DeviceInfoAPI(self)
        self.slots = DmxSlotsAPI(self)
        self.modes = DmxModesAPI(self)
        self.lamp = LampControlAPI(self)
        self.display = DisplaySettingsAPI(self)
        self.position = PositionConfigAPI(self)
        self.power = PowerControlAPI(self)
        self.self_test = SelfTestAPI(self)
        self.presets = PresetControlAPI(self)
        self.system = SystemInfoAPI(self)
        self.proxy = ProxyAPI(self)
        self.raw = RawPidAPI(self)

    @property
    def uid(self) -> UID:
        """Return this device's 48-bit RDM UID."""
        return self._uid

    @property
    def state(self) -> DeviceState:
        """Return the mutable cached state for this device."""
        return self._state

    @property
    def logger(self):
        """Logger for API modules to use."""
        return self._logger

    def cache_get(self, pid: int) -> Any | None:
        """Get cached parameter value if not expired (public for API modules)."""
        if pid in self._parameter_cache:
            cached = self._parameter_cache[pid]
            if not cached.is_expired(self._cache_max_age):
                self._logger.debug("Cache hit for PID 0x%04X", pid)
                return cached.value
            else:
                self._logger.debug("Cache expired for PID 0x%04X", pid)
                del self._parameter_cache[pid]
        return None

    def cache_set(self, pid: int, value: Any) -> None:
        """Cache parameter value with current timestamp (public for API modules)."""
        self._parameter_cache[pid] = CachedParameter(value=value)
        self._logger.debug("Cached PID 0x%04X", pid)

    def clear_cache(self, pid: int | None = None) -> None:
        """
        Clear parameter cache.

        Args:
            pid: Specific PID to clear, or None to clear all
        """
        if pid is None:
            self._parameter_cache.clear()
            self._logger.debug("Cleared all cache")
        elif pid in self._parameter_cache:
            del self._parameter_cache[pid]
            self._logger.debug("Cleared cache for PID 0x%04X", pid)

    async def execute_get(self, pid: int, data: bytes | None = None) -> bytes | None:
        """
        Execute GET command - public API for composed modules.

        Handles all low-level details: transaction allocation, UID, timeout.

        Args:
            pid: Parameter ID to get
            data: Optional data for GET request

        Returns:
            Response data or None if failed
        """
        result = await self._txn.get(
            uid=self._uid,
            pid=StandardPID.to_pid(pid) if isinstance(pid, int) else pid,
            data=data if data is not None else b"",
            timeout=2.0,
        )

        if result.success and result.final_response:
            return result.final_response.data
        return None

    async def execute_set(self, pid: int, data: bytes) -> bool:
        """
        Execute SET command - public API for composed modules.

        Handles all low-level details: transaction allocation, UID, timeout.

        Args:
            pid: Parameter ID to set
            data: Data to send

        Returns:
            True if successful
        """
        result = await self._txn.set(
            uid=self._uid,
            pid=StandardPID.to_pid(pid) if isinstance(pid, int) else pid,
            data=data,
            timeout=2.0,
        )

        return result.success

    async def initialize(self, check_capabilities: bool = True) -> bool:
        """
        Initialize device by querying comprehensive information.

        Args:
            check_capabilities: Whether to query and cache supported parameters

        Returns:
            True if initialization succeeded
        """
        try:
            # Query DEVICE_INFO (contains most device parameters)
            await self.get_device_info(use_cache=False)

            # Query string labels
            self._state.manufacturer = await self.get_manufacturer_label(use_cache=False)
            self._state.device_label = await self.device_label.get(use_cache=False)
            self._state.software_version = await self.get_software_version_label(use_cache=False)

            # Check device capabilities
            if check_capabilities:
                await self.check_capabilities()
                available_apis = self.get_available_apis()
                self._logger.info(
                    "Device supports %d/%d API modules: %s",
                    len(available_apis),
                    len(API_PID_MAPPING),
                    ", ".join(sorted(available_apis)),
                )

            self._state.is_responsive = True
            self._state.last_seen = datetime.now()
            return True
        except Exception as e:
            self._logger.error("Initialization failed: %s", e)
            return False

    async def get_manufacturer_label(self, use_cache: bool = True) -> str:
        """Get manufacturer label string with optional caching."""
        return await self.get_string_parameter(StandardPID.MANUFACTURER_LABEL, use_cache=use_cache)

    async def get_software_version_label(self, use_cache: bool = True) -> str:
        """Get software version label string with optional caching."""
        return await self.get_string_parameter(
            StandardPID.SOFTWARE_VERSION_LABEL, use_cache=use_cache
        )

    async def get_device_info(self, use_cache: bool = True) -> bool:
        """
        Query DEVICE_INFO (PID 0x0060) and populate device state.

        DEVICE_INFO contains:
        - RDM Protocol Version (2 bytes)
        - Device Model ID (2 bytes)
        - Product Category (2 bytes)
        - Software Version ID (4 bytes)
        - DMX Footprint (2 bytes)
        - DMX Personality (1 byte)
        - DMX Personality Count (1 byte)
        - DMX Start Address (2 bytes)
        - Sub-Device Count (2 bytes)
        - Sensor Count (1 byte)

        Args:
            use_cache: Whether to use cached value

        Returns:
            True if successful, False otherwise
        """
        pid_value = StandardPID.DEVICE_INFO.value

        # Check cache
        if use_cache:
            cached = self.cache_get(pid_value)
            if cached is not None:
                return True  # Already populated from cache

        result = await self._txn.get(
            uid=self._uid,
            pid=StandardPID.to_pid(StandardPID.DEVICE_INFO),
            timeout=2.0,
        )

        if result.success and result.final_response and len(result.final_response.data) >= 19:
            data = result.final_response.data

            # Parse DEVICE_INFO structure (19 bytes)
            # All values are big-endian (network byte order)
            (
                protocol_version,  # 2 bytes
                device_model_id,  # 2 bytes
                product_category,  # 2 bytes
                software_version_id,  # 4 bytes
                dmx_footprint,  # 2 bytes
                dmx_personality,  # 1 byte
                dmx_personality_count,  # 1 byte
                dmx_start_address,  # 2 bytes
                sub_device_count,  # 2 bytes
                sensor_count,  # 1 byte
            ) = struct.unpack(">HHHIHBBHHB", data[:19])

            # Update device state
            self._state.rdm_protocol_version = f"{protocol_version >> 8}.{protocol_version & 0xFF}"
            self._state.device_model_id = device_model_id
            self._state.product_category = product_category
            self._state.software_version_id = software_version_id
            self._state.dmx_footprint = dmx_footprint
            self._state.dmx_personality = dmx_personality
            self._state.dmx_personality_count = dmx_personality_count
            self._state.dmx_start_address = dmx_start_address
            self._state.sub_device_count = sub_device_count
            self._state.sensor_count = sensor_count

            # Cache the result
            if use_cache:
                self.cache_set(pid_value, data)

            return True
        return False

    async def get_string_parameter(self, pid: StandardPID, use_cache: bool = True) -> str:
        """Get string parameter with optional caching and throttling."""
        pid_value = pid.value

        # Check cache
        if use_cache:
            cached = self.cache_get(pid_value)
            if cached is not None:
                return cached

        result = await self._txn.get(
            uid=self._uid,
            pid=StandardPID.to_pid(pid),
            timeout=2.0,
        )

        if result.success and result.final_response:
            value = result.final_response.data.decode("utf-8", errors="ignore").strip("\x00")
            # Cache the result
            if use_cache:
                self.cache_set(pid_value, value)
            return value
        return ""

    # ========== Capability Detection Methods ==========

    async def check_capabilities(self, force_refresh: bool = False) -> bool:
        """
        Query device for supported parameters and cache the result.

        Args:
            force_refresh: Force re-query even if already cached

        Returns:
            True if capabilities were successfully queried
        """
        if self._capabilities_checked and not force_refresh:
            self._logger.debug("Capabilities already checked (use force_refresh=True to re-query)")
            return True

        pids = await self.system.get_supported_parameters(use_cache=not force_refresh)
        if pids:
            self._supported_pids = set(pids)
            self._capabilities_checked = True
            self._logger.info("Device supports %d PIDs", len(pids))
            return True

        self._logger.warning("Failed to query supported parameters")
        return False

    def supports_pid(self, pid: int) -> bool:
        """
        Check if device supports a specific PID.

        Args:
            pid: Parameter ID value (int)

        Returns:
            True if supported, or True if capabilities haven't been checked
            (optimistic), or True if the PID is mandatory per E1.20 (always
            supported even if the device omits it from GET_SUPPORTED_PARAMETERS).
        """
        if pid in _MANDATORY_PIDS:
            return True

        if not self._capabilities_checked:
            self._logger.debug("Capabilities not checked for PID 0x%04X (assuming supported)", pid)
            return True  # Optimistic: assume supported until proven otherwise

        return pid in (self._supported_pids or set())

    def supports_api(self, api_name: str) -> bool:
        """
        Check if device supports an API module (at least one of its PIDs).

        Args:
            api_name: API module name (e.g., 'lamp', 'display', 'sensors')

        Returns:
            True if device supports at least one PID from this API
        """
        if api_name not in API_PID_MAPPING:
            self._logger.warning("Unknown API module: %s", api_name)
            return False

        if api_name == "raw":
            return True  # Escape hatch for PIDs with no dedicated API - always available

        if not self._capabilities_checked:
            self._logger.debug(
                "Capabilities not checked for API '%s' (assuming supported)", api_name
            )
            return True  # Optimistic

        required_pids = [p.value for p in API_PID_MAPPING[api_name]]
        supported_count = sum(1 for pid in required_pids if self.supports_pid(pid))

        return supported_count > 0

    def get_available_apis(self) -> list[str]:
        """
        Get list of API modules supported by this device.

        Returns:
            List of API module names that are supported
        """
        return [api for api in API_PID_MAPPING if self.supports_api(api)]

    def get_api_support_details(self) -> dict[str, dict[str, Any]]:
        """
        Get detailed support information for all API modules.

        Returns:
            Dictionary mapping API names to their support details:
            {
                'lamp': {
                    'supported': True,
                    'pids': [0x0401, 0x0402],
                    'supported_pids': [0x0401],
                    'missing_pids': [0x0402],
                    'coverage': 0.5
                },
                ...
            }
        """
        details = {}

        for api_name, required_pids in API_PID_MAPPING.items():
            if api_name == "raw":
                # Escape hatch, not tied to any fixed PID list - always available.
                details[api_name] = {
                    "supported": True,
                    "pids": [],
                    "supported_pids": [],
                    "missing_pids": [],
                    "coverage": 1.0,
                }
                continue

            pid_values = [p.value for p in required_pids]

            if self._capabilities_checked and self._supported_pids:
                known_supported = self._supported_pids | _MANDATORY_PIDS
                supported_pids = [p for p in pid_values if p in known_supported]
                missing_pids = [p for p in pid_values if p not in known_supported]
                coverage = len(supported_pids) / len(pid_values) if pid_values else 0.0
                supported = len(supported_pids) > 0
            else:
                supported_pids = pid_values  # Assume all supported
                missing_pids = []
                coverage = 1.0
                supported = True

            details[api_name] = {
                "supported": supported,
                "pids": pid_values,
                "supported_pids": supported_pids,
                "missing_pids": missing_pids,
                "coverage": coverage,
            }

        return details

    def print_capability_report(self) -> None:
        """Print a formatted capability report to logger."""
        if not self._capabilities_checked:
            self._logger.warning("Capabilities have not been checked yet")
            return

        details = self.get_api_support_details()
        supported = [api for api, info in details.items() if info["supported"]]
        unsupported = [api for api, info in details.items() if not info["supported"]]
        partial = [
            api for api, info in details.items() if info["supported"] and 0 < info["coverage"] < 1.0
        ]

        self._logger.info("=" * 60)
        self._logger.info("Device Capability Report: %012X", self._uid)
        self._logger.info("=" * 60)
        self._logger.info("Total PIDs supported: %d", len(self._supported_pids or []))
        self._logger.info("Fully supported APIs: %d/%d", len(supported), len(API_PID_MAPPING))

        if supported:
            self._logger.info("  Supported: %s", ", ".join(sorted(supported)))

        if partial:
            self._logger.info("  Partial support:")
            for api in sorted(partial):
                info = details[api]
                self._logger.info(
                    "    - %s: %.0f%% (%d/%d PIDs)",
                    api,
                    info["coverage"] * 100,
                    len(info["supported_pids"]),
                    len(info["pids"]),
                )

        if unsupported:
            self._logger.info("  Not supported: %s", ", ".join(sorted(unsupported)))

        self._logger.info("=" * 60)
