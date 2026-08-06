"""
Standard RDM Parameter IDs (PIDs) from E1.20 specification.
"""

from enum import IntEnum

from ..packets.types import PID, UID

# Standard RDM Constants (ANSI E1.20)
BROADCAST_UID = UID(0xFFFFFFFFFFFF)  # Broadcast to all devices


class StandardPID(IntEnum):
    """Standard RDM PIDs from ANSI E1.20"""

    # Network Management
    DISC_UNIQUE_BRANCH = 0x0001
    DISC_MUTE = 0x0002
    DISC_UN_MUTE = 0x0003
    PROXIED_DEVICES = 0x0010
    PROXIED_DEVICE_COUNT = 0x0011
    COMMS_STATUS = 0x0015

    # Status Collection
    QUEUED_MESSAGE = 0x0020
    STATUS_MESSAGES = 0x0030
    STATUS_ID_DESCRIPTION = 0x0031
    CLEAR_STATUS_ID = 0x0032
    SUB_DEVICE_STATUS_REPORT_THRESHOLD = 0x0033

    # RDM Information
    SUPPORTED_PARAMETERS = 0x0050
    PARAMETER_DESCRIPTION = 0x0051

    # Product Information
    DEVICE_INFO = 0x0060
    PRODUCT_DETAIL_ID_LIST = 0x0070
    DEVICE_MODEL_DESCRIPTION = 0x0080
    MANUFACTURER_LABEL = 0x0081
    DEVICE_LABEL = 0x0082
    FACTORY_DEFAULTS = 0x0090
    LANGUAGE_CAPABILITIES = 0x00A0
    LANGUAGE = 0x00B0
    SOFTWARE_VERSION_LABEL = 0x00C0
    BOOT_SOFTWARE_VERSION_ID = 0x00C1
    BOOT_SOFTWARE_VERSION_LABEL = 0x00C2

    # DMX512 Setup
    DMX_PERSONALITY = 0x00E0
    DMX_PERSONALITY_DESCRIPTION = 0x00E1
    DMX_START_ADDRESS = 0x00F0
    SLOT_INFO = 0x0120
    SLOT_DESCRIPTION = 0x0121
    DEFAULT_SLOT_VALUE = 0x0122

    # Sensors
    SENSOR_DEFINITION = 0x0200
    SENSOR_VALUE = 0x0201
    RECORD_SENSORS = 0x0202

    # Power/Lamp Settings
    DEVICE_HOURS = 0x0400
    LAMP_HOURS = 0x0401
    LAMP_STRIKES = 0x0402
    LAMP_STATE = 0x0403
    LAMP_ON_MODE = 0x0404
    DEVICE_POWER_CYCLES = 0x0405

    # Display Settings
    DISPLAY_INVERT = 0x0500
    DISPLAY_LEVEL = 0x0501

    # Configuration
    PAN_INVERT = 0x0600
    TILT_INVERT = 0x0601
    PAN_TILT_SWAP = 0x0602
    REAL_TIME_CLOCK = 0x0603

    # E1.37-1 PIDs
    DMX_STARTUP_MODE = 0x0142
    DMX_BLOCK_ADDRESS = 0x0140
    DMX_FAIL_MODE = 0x0141
    OUTPUT_RESPONSE_TIME = 0x0345

    # Control
    IDENTIFY_DEVICE = 0x1000
    RESET_DEVICE = 0x1001
    POWER_STATE = 0x1010
    PERFORM_SELFTEST = 0x1020
    SELF_TEST_DESCRIPTION = 0x1021
    CAPTURE_PRESET = 0x1030
    PRESET_PLAYBACK = 0x1031
    PRESET_STATUS = 0x1032
    PRESET_MERGEMODE = 0x1033

    @classmethod
    def to_pid(cls, value: int) -> PID:
        """Convert enum value to PID type"""
        return PID(value)


class ParameterDataType(IntEnum):
    """ANSI E1.20 Table A-9: PARAMETER_DESCRIPTION's DATA_TYPE field."""

    NOT_DEFINED = 0x00
    BIT_FIELD = 0x01
    ASCII = 0x02
    UNSIGNED_BYTE = 0x03
    SIGNED_BYTE = 0x04
    UNSIGNED_WORD = 0x05
    SIGNED_WORD = 0x06
    UNSIGNED_DWORD = 0x07
    SIGNED_DWORD = 0x08


class ParameterCommandClass(IntEnum):
    """ANSI E1.20 Table A-8: PARAMETER_DESCRIPTION's COMMAND_CLASS field."""

    GET = 0x00
    SET = 0x01
    GET_SET = 0x02


# Friendly (name, byte width) per DATA_TYPE - byte width is None for ASCII (variable
# length, up to PDL_SIZE) and for codes this library doesn't have a fixed width for
# (BIT_FIELD is 1-N bytes per spec, manufacturer-specific/reserved codes are unknown).
_PARAMETER_DATA_TYPE_INFO: dict[int, tuple[str, int | None]] = {
    ParameterDataType.NOT_DEFINED: ("Not defined", None),
    ParameterDataType.BIT_FIELD: ("Bit field", None),
    ParameterDataType.ASCII: ("ASCII string", None),
    ParameterDataType.UNSIGNED_BYTE: ("Unsigned byte (0-255)", 1),
    ParameterDataType.SIGNED_BYTE: ("Signed byte (-128 to 127)", 1),
    ParameterDataType.UNSIGNED_WORD: ("Unsigned word (0-65535)", 2),
    ParameterDataType.SIGNED_WORD: ("Signed word (-32768 to 32767)", 2),
    ParameterDataType.UNSIGNED_DWORD: ("Unsigned dword (0-4294967295)", 4),
    ParameterDataType.SIGNED_DWORD: ("Signed dword", 4),
}

_COMMAND_CLASS_NAMES: dict[int, str] = {
    ParameterCommandClass.GET: "GET only",
    ParameterCommandClass.SET: "SET only",
    ParameterCommandClass.GET_SET: "GET and SET",
}


def parameter_data_type_info(data_type: int) -> tuple[str, int | None]:
    """Friendly (label, fixed byte width) for a PARAMETER_DESCRIPTION DATA_TYPE code.

    Falls back to a generic manufacturer-specific/reserved label for codes outside
    the fixed E1.20 range (0x80-0xDF manufacturer-specific, 0x09-0x7F/0xE0-0xFF
    reserved) since this library can't know their real shape.
    """
    if data_type in _PARAMETER_DATA_TYPE_INFO:
        return _PARAMETER_DATA_TYPE_INFO[data_type]
    if 0x80 <= data_type <= 0xDF:
        return (f"Manufacturer-specific (0x{data_type:02X})", None)
    return (f"Reserved (0x{data_type:02X})", None)


def command_class_name(command_class: int) -> str:
    """Friendly label for a PARAMETER_DESCRIPTION COMMAND_CLASS code."""
    return _COMMAND_CLASS_NAMES.get(command_class, f"Unknown (0x{command_class:02X})")


# ANSI E1.20 Table A-14: SENSOR_DEFINITION's PREFIX field -> power-of-ten exponent.
# The wire value is not the exponent itself (it jumps from YOCTO=0x0A to DECA=0x11,
# skipping 0x0B-0x10), so this map is the authoritative conversion - not `10**prefix`.
_SENSOR_PREFIX_EXPONENT: dict[int, int] = {
    0x00: 0,  # NONE
    0x01: -1,  # DECI
    0x02: -2,  # CENTI
    0x03: -3,  # MILLI
    0x04: -6,  # MICRO
    0x05: -9,  # NANO
    0x06: -12,  # PICO
    0x07: -15,  # FEMTO
    0x08: -18,  # ATTO
    0x09: -21,  # ZEPTO
    0x0A: -24,  # YOCTO
    0x11: 1,  # DECA
    0x12: 2,  # HECTO
    0x13: 3,  # KILO
    0x14: 6,  # MEGA
    0x15: 9,  # GIGA
    0x16: 12,  # TERA
    0x17: 15,  # PETA
    0x18: 18,  # EXA
    0x19: 21,  # ZETTA
    0x1A: 24,  # YOTTA
}


def sensor_prefix_exponent(prefix: int) -> int:
    """Power-of-ten exponent for a SENSOR_DEFINITION PREFIX value (unknown -> 0)."""
    return _SENSOR_PREFIX_EXPONENT.get(prefix, 0)


def sensor_prefix_factor(prefix: int) -> float:
    """Multiplier that converts a raw sensor value into its real engineering value."""
    return 10.0 ** sensor_prefix_exponent(prefix)


def sensor_prefix_decimals(prefix: int) -> int:
    """Decimal places implied by a SENSOR_DEFINITION PREFIX, for display rounding."""
    return max(0, -sensor_prefix_exponent(prefix))
