"""Pydantic request/response models for the RDM/DMX REST API."""

from typing import Annotated

from pydantic import BaseModel, Field


class PortListResponse(BaseModel):
    ports: list[str]


class InterfaceTypeListResponse(BaseModel):
    interface_types: list[str]


class ConnectRequest(BaseModel):
    port: str | None = Field(
        default=None, description="Serial port, e.g. COM5 (auto-detect if omitted)"
    )
    interface_type: str = Field(default="ENTTEC_USB_PRO", description="InterfaceType name")
    controller_uid: str | None = Field(
        default=None,
        description=(
            "Hex UID (e.g. 454E00000000) this controller identifies itself as. Required for "
            "interfaces with no onboard widget to query a UID from (e.g. BARE_USB_RS485); ignored "
            "for interfaces that can report their own (e.g. Enttec)."
        ),
    )


class StatusResponse(BaseModel):
    connected: bool
    port: str | None = None
    device_count: int = 0


class DiscoverRequest(BaseModel):
    timeout: float = Field(default=5.0, gt=0)


class DeviceSummary(BaseModel):
    uid: str
    manufacturer: str = ""
    device_label: str = ""
    model: str = ""
    dmx_start_address: int = 1
    dmx_personality: int = 0
    dmx_footprint: int = 0

    @classmethod
    def from_device_state(cls, uid_hex: str, state) -> "DeviceSummary":  # noqa: ANN001
        return cls(
            uid=uid_hex,
            manufacturer=state.manufacturer,
            device_label=state.device_label,
            model=state.model,
            dmx_start_address=state.dmx_start_address,
            dmx_personality=state.dmx_personality,
            dmx_footprint=state.dmx_footprint,
        )


class DiscoverResponse(BaseModel):
    devices: list[DeviceSummary]


class DeviceLabelUpdate(BaseModel):
    label: str = Field(max_length=32)


class StartAddressUpdate(BaseModel):
    address: int = Field(ge=1, le=512)


class IdentifyRequest(BaseModel):
    enable: bool = True


class OkResponse(BaseModel):
    success: bool = True


class DmxSendRequest(BaseModel):
    channels: list[Annotated[int, Field(ge=0, le=255)]] = Field(min_length=1, max_length=512)
    port: int = Field(default=1, ge=1)
    repeat: bool = Field(
        default=False,
        description=(
            "If True, keep re-transmitting this frame in the background (~40 Hz) "
            "until overwritten or stopped. Default False (single send)."
        ),
    )


class ModuleSupport(BaseModel):
    """Per-module PID coverage, as reported by `RdmDevice.get_api_support_details()`."""

    supported: bool
    pids: list[int]
    supported_pids: list[int]
    missing_pids: list[int]
    coverage: float


class CapabilityReport(BaseModel):
    modules: dict[str, ModuleSupport]


class ModuleParamSpec(BaseModel):
    """A single parameter of a module method, for dynamic form generation."""

    name: str
    kind: str = Field(description="'int' | 'str' | 'bool' | 'enum' | 'unknown'")
    required: bool
    default: bool | int | str | None = None
    min: int | None = Field(default=None, description="Inclusive lower bound, for int params")
    max: int | None = Field(default=None, description="Inclusive upper bound, for int params")


class ModuleMethodSpec(BaseModel):
    """A callable method on a device API module (getter or action)."""

    name: str
    is_getter: bool = Field(
        description="True for zero-arg get_*/get methods, auto-fetched into state"
    )
    params: list[ModuleParamSpec]
    supported: bool = Field(
        default=True, description="False when this method's PID is confirmed unsupported"
    )


class ModuleSchema(BaseModel):
    module: str
    methods: list[ModuleMethodSpec]


class MethodCallRequest(BaseModel):
    args: list[bool | int | float | str] = Field(default_factory=list)


class MethodCallResponse(BaseModel):
    result: bool | int | float | str | list | dict | None = None


class PersonalityOption(BaseModel):
    personality: int
    footprint: int
    description: str


class PersonalityListResponse(BaseModel):
    current: int | None = None
    options: list[PersonalityOption]


class SupportedPidOption(BaseModel):
    pid: int
    name: str


class SupportedPidListResponse(BaseModel):
    options: list[SupportedPidOption]


class SensorReading(BaseModel):
    """A sensor's live value merged with its static definition, for display.

    Numeric fields are already scaled by the sensor's SI unit prefix (ANSI
    E1.20), so consumers can display them directly without further scaling.
    """

    sensor_number: int
    description: str
    unit: int
    prefix: int
    present_value: float | None = None
    lowest: float | None = None
    highest: float | None = None
    recorded: float | None = None
    range_min: float
    range_max: float
    normal_min: float
    normal_max: float
    supports_recording: bool


class SensorReadingsResponse(BaseModel):
    sensors: list[SensorReading]
