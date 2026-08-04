"""Generic, reflection-based endpoints that drive any PID API module on a device.

Rather than hand-writing an endpoint per method across 16 device API modules
(device_label, dmx_config, control, sensors, lamp, display, ...), this router
introspects each module's public async methods at request time. This lets the
frontend discover a device's capabilities and available actions dynamically,
without the backend needing a route defined per method.

- GET  /devices/{uid}/capabilities              - which modules this device supports
- GET  /devices/{uid}/modules/{module}/schema    - callable methods + param metadata
- GET  /devices/{uid}/modules/{module}/state     - current values of all zero-arg getters
- POST /devices/{uid}/modules/{module}/{method}  - invoke any method (getter or setter)
"""

import inspect
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from rdm_dmx_async.domain.parameters import StandardPID
from rdm_dmx_async.services.rdm_device import API_PID_MAPPING, RdmDevice

from ..dependencies import get_device
from ..schemas import (
    CapabilityReport,
    MethodCallRequest,
    MethodCallResponse,
    ModuleMethodSpec,
    ModuleParamSpec,
    ModuleSchema,
    ModuleSupport,
    PersonalityListResponse,
    PersonalityOption,
    SensorReading,
    SensorReadingsResponse,
    SupportedPidListResponse,
    SupportedPidOption,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices/{uid}", tags=["capabilities"])

# Maps (module, method) -> the single PID that method reads/writes, so the schema
# endpoint can flag methods whose PID is confirmed unsupported (partial module
# coverage - e.g. a device may support DMX_START_ADDRESS but not DMX_PERSONALITY).
_METHOD_PID: dict[str, dict[str, int]] = {
    "device_label": {"get": StandardPID.DEVICE_LABEL, "set": StandardPID.DEVICE_LABEL},
    "dmx_config": {
        "set_start_address": StandardPID.DMX_START_ADDRESS,
        "get_personality": StandardPID.DMX_PERSONALITY,
        "set_personality": StandardPID.DMX_PERSONALITY,
        "get_personality_description": StandardPID.DMX_PERSONALITY_DESCRIPTION,
    },
    "control": {
        "identify": StandardPID.IDENTIFY_DEVICE,
        "reset": StandardPID.RESET_DEVICE,
        "factory_defaults": StandardPID.FACTORY_DEFAULTS,
    },
    "sensors": {
        "get_value": StandardPID.SENSOR_VALUE,
        "record": StandardPID.RECORD_SENSORS,
    },
    "sensor_definitions": {
        "get_sensor_definition": StandardPID.SENSOR_DEFINITION,
        "get_all_sensor_definitions": StandardPID.SENSOR_DEFINITION,
    },
    "maintenance": {
        "get_hours": StandardPID.DEVICE_HOURS,
        "set_hours": StandardPID.DEVICE_HOURS,
        "get_power_cycles": StandardPID.DEVICE_POWER_CYCLES,
    },
    "info": {
        "get_model_description": StandardPID.DEVICE_MODEL_DESCRIPTION,
        "get_boot_software_version": StandardPID.BOOT_SOFTWARE_VERSION_LABEL,
        "get_boot_software_version_id": StandardPID.BOOT_SOFTWARE_VERSION_ID,
        "get_product_detail_id_list": StandardPID.PRODUCT_DETAIL_ID_LIST,
    },
    "slots": {
        "get_slot_info": StandardPID.SLOT_INFO,
        "get_slot_description": StandardPID.SLOT_DESCRIPTION,
        "get_all_slot_descriptions": StandardPID.SLOT_DESCRIPTION,
        "get_default_slot_values": StandardPID.DEFAULT_SLOT_VALUE,
    },
    "modes": {
        "get_dmx_startup_mode": StandardPID.DMX_STARTUP_MODE,
        "set_dmx_startup_mode": StandardPID.DMX_STARTUP_MODE,
        "get_output_response_time": StandardPID.OUTPUT_RESPONSE_TIME,
        "set_output_response_time": StandardPID.OUTPUT_RESPONSE_TIME,
        "capture_preset": StandardPID.CAPTURE_PRESET,
        "get_dmx_block_address": StandardPID.DMX_BLOCK_ADDRESS,
        "set_dmx_block_address": StandardPID.DMX_BLOCK_ADDRESS,
        "get_dmx_fail_mode": StandardPID.DMX_FAIL_MODE,
        "set_dmx_fail_mode": StandardPID.DMX_FAIL_MODE,
    },
    "lamp": {
        "get_hours": StandardPID.LAMP_HOURS,
        "set_hours": StandardPID.LAMP_HOURS,
        "get_strikes": StandardPID.LAMP_STRIKES,
        "set_strikes": StandardPID.LAMP_STRIKES,
        "get_state": StandardPID.LAMP_STATE,
        "set_state": StandardPID.LAMP_STATE,
        "get_on_mode": StandardPID.LAMP_ON_MODE,
        "set_on_mode": StandardPID.LAMP_ON_MODE,
    },
    "display": {
        "get_invert": StandardPID.DISPLAY_INVERT,
        "set_invert": StandardPID.DISPLAY_INVERT,
        "get_level": StandardPID.DISPLAY_LEVEL,
        "set_level": StandardPID.DISPLAY_LEVEL,
    },
    "position": {
        "get_pan_invert": StandardPID.PAN_INVERT,
        "set_pan_invert": StandardPID.PAN_INVERT,
        "get_tilt_invert": StandardPID.TILT_INVERT,
        "set_tilt_invert": StandardPID.TILT_INVERT,
        "get_pan_tilt_swap": StandardPID.PAN_TILT_SWAP,
        "set_pan_tilt_swap": StandardPID.PAN_TILT_SWAP,
        "get_real_time_clock": StandardPID.REAL_TIME_CLOCK,
        "set_real_time_clock": StandardPID.REAL_TIME_CLOCK,
    },
    "power": {
        "get_state": StandardPID.POWER_STATE,
        "set_state": StandardPID.POWER_STATE,
    },
    "self_test": {
        "perform": StandardPID.PERFORM_SELFTEST,
        "get_description": StandardPID.SELF_TEST_DESCRIPTION,
    },
    "presets": {
        "get_playback": StandardPID.PRESET_PLAYBACK,
        "set_playback": StandardPID.PRESET_PLAYBACK,
        "get_status": StandardPID.PRESET_STATUS,
        "get_merge_mode": StandardPID.PRESET_MERGEMODE,
        "set_merge_mode": StandardPID.PRESET_MERGEMODE,
    },
    "system": {
        "get_supported_parameters": StandardPID.SUPPORTED_PARAMETERS,
        # get_parameter_description deliberately has no PID mapping here (so it's never
        # flagged "Not supported by this device"): unlike other getters, it's meant to be
        # tried per-target-PID, not device-wide - it's most useful for a manufacturer-
        # specific PID the device doesn't otherwise expose a named getter for, and simply
        # NAKing for a standard PID (which already has a spec-fixed type/range) is expected
        # per E1.20, not evidence the whole command is unsupported.
        "get_queued_message": StandardPID.QUEUED_MESSAGE,
        "get_status_messages": StandardPID.STATUS_MESSAGES,
        "get_status_id_description": StandardPID.STATUS_ID_DESCRIPTION,
        "clear_status_id": StandardPID.CLEAR_STATUS_ID,
        "get_comms_status": StandardPID.COMMS_STATUS,
        "clear_comms_status": StandardPID.COMMS_STATUS,
        "get_sub_device_status_report_threshold": StandardPID.SUB_DEVICE_STATUS_REPORT_THRESHOLD,
        "set_sub_device_status_report_threshold": StandardPID.SUB_DEVICE_STATUS_REPORT_THRESHOLD,
        "get_language_capabilities": StandardPID.LANGUAGE_CAPABILITIES,
        "get_language": StandardPID.LANGUAGE,
        "set_language": StandardPID.LANGUAGE,
    },
    "proxy": {
        "get_proxied_devices": StandardPID.PROXIED_DEVICES,
        "get_proxied_device_count": StandardPID.PROXIED_DEVICE_COUNT,
    },
}

# Overrides the default 0-255 int range for params whose real-world range differs
# (e.g. a DMX address spans 1-512, not one byte). Keyed by (module, method, param).
_PARAM_RANGE_HINTS: dict[tuple[str, str, str], tuple[int, int]] = {
    ("dmx_config", "set_start_address", "address"): (1, 512),
    ("modes", "set_dmx_block_address", "start_address"): (1, 512),
    ("dmx_config", "set_personality", "personality"): (1, 255),
    ("dmx_config", "get_personality_description", "personality"): (1, 255),
    ("modes", "set_dmx_startup_mode", "mode"): (0, 65535),
    ("modes", "capture_preset", "mode"): (0, 65535),
    ("modes", "set_dmx_fail_mode", "scene"): (0, 65535),
    ("modes", "set_dmx_fail_mode", "loss_of_signal_delay"): (0, 65535),
    ("modes", "set_dmx_fail_mode", "hold_time"): (0, 65535),
    ("presets", "set_playback", "mode"): (0, 65535),
    ("system", "get_parameter_description", "pid"): (0, 65535),
    ("system", "clear_status_id", "status_id"): (0, 65535),
    ("system", "get_status_id_description", "status_id"): (0, 65535),
    ("maintenance", "set_hours", "hours"): (0, 999_999),
    ("lamp", "set_hours", "hours"): (0, 999_999),
    ("lamp", "set_strikes", "strikes"): (0, 999_999),
    ("slots", "get_slot_description", "slot_offset"): (0, 511),
    ("display", "set_invert", "invert"): (0, 1),
    ("position", "set_pan_invert", "invert"): (0, 1),
    ("position", "set_tilt_invert", "invert"): (0, 1),
    ("position", "set_pan_tilt_swap", "swap"): (0, 1),
    ("power", "set_state", "state"): (0, 3),
    ("lamp", "set_state", "state"): (0, 3),
    ("lamp", "set_on_mode", "mode"): (0, 3),
}

# (module, method, param) whose numeric value should be picked from a resolved set
# of options (e.g. personality index resolved via personality descriptions) rather
# than a bare slider.
_ENUM_PARAMS: set[tuple[str, str, str]] = {
    ("dmx_config", "set_personality", "personality"),
    ("dmx_config", "get_personality_description", "personality"),
}

# (module, method, param) whose value should be picked from the device's own
# GET_SUPPORTED_PARAMETERS list (e.g. PARAMETER_DESCRIPTION only makes sense for a PID
# the device actually reports supporting) rather than a bare 0-65535 numeric field.
_PID_PARAMS: set[tuple[str, str, str]] = {
    ("system", "get_parameter_description", "pid"),
}


def _resolve_module(device: RdmDevice, module_name: str) -> object:
    if module_name not in API_PID_MAPPING:
        raise HTTPException(status_code=404, detail=f"Unknown module: {module_name!r}")
    return getattr(device, module_name)


def _infer_kind(annotation: Any) -> str:
    if annotation is bool:
        return "bool"
    if annotation is int:
        return "int"
    if annotation is str:
        return "str"
    return "unknown"


def _public_async_methods(module: object):
    for name, method in inspect.getmembers(module, predicate=inspect.iscoroutinefunction):
        if not name.startswith("_"):
            yield name, method


def _serialize(value: Any) -> Any:
    """Make method return values JSON-safe (tuples -> lists)."""
    if isinstance(value, tuple | list):
        return [_serialize(v) for v in value]
    return value


@router.get("/capabilities", response_model=CapabilityReport)
async def get_capabilities(device: RdmDevice = Depends(get_device)) -> CapabilityReport:
    """Query the device for its supported PIDs and report per-module coverage."""
    await device.check_capabilities()
    details = device.get_api_support_details()
    return CapabilityReport(modules={name: ModuleSupport(**info) for name, info in details.items()})


@router.get("/modules/{module_name}/schema", response_model=ModuleSchema)
def get_module_schema(module_name: str, device: RdmDevice = Depends(get_device)) -> ModuleSchema:
    """Describe a module's methods and parameters, for dynamic UI generation."""
    module = _resolve_module(device, module_name)
    method_pids = _METHOD_PID.get(module_name, {})
    methods = []
    for name, method in _public_async_methods(module):
        sig = inspect.signature(method)
        params = []
        for p in sig.parameters.values():
            if p.name == "self":
                continue
            if (module_name, name, p.name) in _ENUM_PARAMS:
                kind = "enum"
            elif (module_name, name, p.name) in _PID_PARAMS:
                kind = "pid"
            else:
                kind = _infer_kind(p.annotation)
            param_min, param_max = _PARAM_RANGE_HINTS.get((module_name, name, p.name), (None, None))
            if kind == "int" and param_min is None:
                param_min, param_max = 0, 255
            params.append(
                ModuleParamSpec(
                    name=p.name,
                    kind=kind,
                    required=p.default is inspect.Parameter.empty,
                    default=None if p.default is inspect.Parameter.empty else p.default,
                    min=param_min,
                    max=param_max,
                )
            )
        is_getter = (name.startswith("get") or name == "get") and all(
            p.name in ("use_cache",) or not p.required for p in params
        )
        pid = method_pids.get(name)
        supported = device.supports_pid(pid) if pid is not None else True
        methods.append(
            ModuleMethodSpec(name=name, is_getter=is_getter, params=params, supported=supported)
        )
    return ModuleSchema(module=module_name, methods=methods)


@router.get("/modules/{module_name}/state")
async def get_module_state(
    module_name: str, device: RdmDevice = Depends(get_device)
) -> dict[str, Any]:
    """Call every zero-required-argument getter on a module and return the results."""
    module = _resolve_module(device, module_name)
    method_pids = _METHOD_PID.get(module_name, {})
    result: dict[str, Any] = {}
    for name, method in _public_async_methods(module):
        if not (name.startswith("get") or name == "get"):
            continue
        sig = inspect.signature(method)
        required = [
            p
            for p in sig.parameters.values()
            if p.name not in ("self", "use_cache") and p.default is inspect.Parameter.empty
        ]
        if required:
            continue
        # Skip PIDs already confirmed unsupported (from GET_SUPPORTED_PARAMETERS) instead
        # of issuing a GET that's known to come back NAK UNKNOWN_PID - this is the main
        # source of "Permanent failure ... NAK UNKNOWN_PID" warnings, since every state
        # refresh otherwise re-probes every optional getter on the module.
        pid = method_pids.get(name)
        if pid is not None and not device.supports_pid(pid):
            result[name] = None
            continue
        try:
            value = await method()
        except Exception:
            value = None
        result[name] = _serialize(value)
    return result


@router.post("/modules/{module_name}/{method_name}", response_model=MethodCallResponse)
async def call_module_method(
    module_name: str,
    method_name: str,
    body: MethodCallRequest,
    device: RdmDevice = Depends(get_device),
) -> MethodCallResponse:
    """Invoke any method on a module (getter with args, or a setter/action) with positional args."""
    module = _resolve_module(device, module_name)
    method = getattr(module, method_name, None) if not method_name.startswith("_") else None
    if method is None or not inspect.iscoroutinefunction(method):
        raise HTTPException(status_code=404, detail=f"Unknown method: {method_name!r}")

    try:
        result = await method(*body.args)
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    serialized = _serialize(result)
    # One line per user-initiated call (button click), regardless of module - the
    # per-packet RDM chatter underneath this is DEBUG-only, so this is the only
    # visible record that a set/action was performed unless something goes wrong.
    logger.info(
        "%012X %s.%s(%s) -> %r", device.uid, module_name, method_name, body.args, serialized
    )
    return MethodCallResponse(result=serialized)


@router.get("/modules/dmx_config/personalities", response_model=PersonalityListResponse)
async def get_personalities(device: RdmDevice = Depends(get_device)) -> PersonalityListResponse:
    """Resolve every personality index (1..count) to its footprint and description.

    Lets the frontend offer a "choose by description" selector for
    ``dmx_config.set_personality`` instead of a bare numeric slider.
    """
    current = await device.dmx_config.get_personality()
    if not current:
        return PersonalityListResponse(current=None, options=[])

    current_personality, count = current
    options = []
    for personality in range(1, count + 1):
        info = await device.dmx_config.get_personality_description(personality)
        if info:
            options.append(PersonalityOption(**info))
    return PersonalityListResponse(current=current_personality, options=options)


@router.get("/modules/system/supported-pids", response_model=SupportedPidListResponse)
async def get_supported_pids(device: RdmDevice = Depends(get_device)) -> SupportedPidListResponse:
    """List every PID this device reports supporting, for a "choose by name" selector.

    Used by ``system.get_parameter_description``, which otherwise NAKs (UNKNOWN_PID)
    for any PID the device wasn't actually asked about via GET_SUPPORTED_PARAMETERS.
    """
    pids = await device.system.get_supported_parameters()
    options = []
    for pid in pids or []:
        try:
            name = StandardPID(pid).name
        except ValueError:
            name = f"0x{pid:04X}"
        options.append(SupportedPidOption(pid=pid, name=name))
    return SupportedPidListResponse(options=options)


@router.get("/modules/sensors/readings", response_model=SensorReadingsResponse)
async def get_sensor_readings(device: RdmDevice = Depends(get_device)) -> SensorReadingsResponse:
    """Merge each sensor's static definition with its live value, for display.

    A bare ``sensors.get_value(n)`` result is meaningless without the matching
    definition's description/unit/scaling, so this composes both PIDs. Loading
    definitions first (below) warms `SensorDefinitionsAPI`'s cache, so
    `sensors.get_value()` can scale its readings by the sensor's own prefix.
    """
    definitions = await device.sensor_definitions.get_all_sensor_definitions()
    readings = []
    for definition in definitions:
        value = await device.sensors.get_value(definition["sensor_number"])
        readings.append(
            SensorReading(
                sensor_number=definition["sensor_number"],
                description=definition["description"],
                unit=definition["unit"],
                prefix=definition["prefix"],
                present_value=value["present_value"] if value else None,
                lowest=value["lowest"] if value else None,
                highest=value["highest"] if value else None,
                recorded=value["recorded"] if value else None,
                range_min=definition["range_min"],
                range_max=definition["range_max"],
                normal_min=definition["normal_min"],
                normal_max=definition["normal_max"],
                supports_recording=bool(definition["supports_recording"]),
            )
        )
    return SensorReadingsResponse(sensors=readings)
