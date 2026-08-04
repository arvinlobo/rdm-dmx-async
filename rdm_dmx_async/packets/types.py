"""
Type definitions for RDM/DMX protocols.

Provides semantic types for type safety and clarity.
"""

from enum import IntEnum
from typing import NewType

# Semantic types for type safety
UID = NewType("UID", int)  # 48-bit unique identifier
PID = NewType("PID", int)  # 16-bit parameter ID
TransactionNumber = NewType("TransactionNumber", int)  # 8-bit transaction ID


class CommandClass(IntEnum):
    """RDM Command Classes"""

    DISCOVERY_COMMAND = 0x10
    DISCOVERY_COMMAND_RESPONSE = 0x11
    GET_COMMAND = 0x20
    GET_COMMAND_RESPONSE = 0x21
    SET_COMMAND = 0x30
    SET_COMMAND_RESPONSE = 0x31


class ResponseType(IntEnum):
    """RDM Response Types"""

    ACK = 0x00
    ACK_TIMER = 0x01
    NAK = 0x02
    ACK_OVERFLOW = 0x03


class NAKReason(IntEnum):
    """RDM NAK Reason Codes"""

    UNKNOWN_PID = 0x0000
    FORMAT_ERROR = 0x0001
    HARDWARE_FAULT = 0x0002
    PROXY_REJECT = 0x0003
    WRITE_PROTECT = 0x0004
    UNSUPPORTED_COMMAND_CLASS = 0x0005
    DATA_OUT_OF_RANGE = 0x0006
    BUFFER_FULL = 0x0007
    PACKET_SIZE_UNSUPPORTED = 0x0008
    SUB_DEVICE_OUT_OF_RANGE = 0x0009
    PROXY_BUFFER_FULL = 0x000A


class StartCode(IntEnum):
    """DMX/RDM Start Codes"""

    DMX = 0x00
    RDM = 0xCC
    RDM_DISCOVERY = 0xFE


def uid_from_bytes(data: bytes) -> UID:
    """Convert 6 bytes to UID"""
    if len(data) != 6:
        raise ValueError("UID must be 6 bytes")
    return UID(int.from_bytes(data, byteorder="big"))


def uid_to_bytes(uid: UID) -> bytes:
    """Convert UID to 6 bytes"""
    return int(uid).to_bytes(6, byteorder="big")


def uid_from_string(uid_str: str) -> UID:
    """
    Parse UID from string format.

    Accepts formats:
    - "454e:00000001" (with colon)
    - "454e00000001" (without colon)
    - "45:4e:00:00:00:01" (with colons between each byte)
    """
    uid_str = uid_str.replace(":", "")
    if len(uid_str) != 12:
        raise ValueError(f"Invalid UID string: {uid_str}")
    return UID(int(uid_str, 16))


def uid_to_string(uid: UID) -> str:
    """Convert UID to string format (MMMM:DDDDDDDD)"""
    uid_bytes = uid_to_bytes(uid)
    manufacturer = uid_bytes[0:2].hex()
    device = uid_bytes[2:6].hex()
    return f"{manufacturer}:{device}"
