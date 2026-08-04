"""Device API modules - organized by PID functionality."""

from .device_control import DeviceControlAPI
from .device_info import DeviceInfoAPI
from .device_label import DeviceLabelAPI
from .device_maintenance import DeviceMaintenanceAPI
from .display_settings import DisplaySettingsAPI
from .dmx_config import DmxConfigAPI
from .dmx_modes import DmxModesAPI
from .dmx_slots import DmxSlotsAPI
from .lamp_control import LampControlAPI
from .position_config import PositionConfigAPI
from .power_control import PowerControlAPI
from .preset_control import PresetControlAPI
from .proxy import ProxyAPI
from .self_test import SelfTestAPI
from .sensor_definitions import SensorDefinitionsAPI
from .sensors import SensorsAPI
from .system_info import SystemInfoAPI

__all__ = [
    "DeviceLabelAPI",
    "DmxConfigAPI",
    "DeviceControlAPI",
    "SensorsAPI",
    "SensorDefinitionsAPI",
    "DeviceMaintenanceAPI",
    "DeviceInfoAPI",
    "DmxSlotsAPI",
    "DmxModesAPI",
    "LampControlAPI",
    "DisplaySettingsAPI",
    "PositionConfigAPI",
    "PowerControlAPI",
    "SelfTestAPI",
    "PresetControlAPI",
    "SystemInfoAPI",
    "ProxyAPI",
]
