"""Raw PID access - GET/SET any PID by number, for PIDs with no dedicated API module.

Every other module in this package wraps one or more StandardPID values behind a
typed, named method (device_label.get(), lamp.set_hours(), ...). This module is the
escape hatch for everything else: manufacturer-specific PIDs, or standard PIDs this
library hasn't wired a typed accessor for yet. Payloads are exchanged as a string in
a user-chosen format (hex/ascii/fixed-width number) since a generic raw accessor has
no per-PID type information of its own to encode/decode with - use describe() first
to check a PID's real data type before picking a format.
"""

import struct
from typing import TYPE_CHECKING, Literal

from ...domain.parameters import command_class_name, parameter_data_type_info

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice

DataFormat = Literal["hex", "ascii", "uint8", "int8", "uint16", "int16", "uint32", "int32"]

# ANSI E1.20 multi-byte fields are big-endian.
_STRUCT_FORMATS: dict[str, str] = {
    "uint8": ">B",
    "int8": ">b",
    "uint16": ">H",
    "int16": ">h",
    "uint32": ">I",
    "int32": ">i",
}


def _decode(data: bytes, data_format: DataFormat) -> str:
    """Render a raw RDM response payload as a string, per the chosen display format."""
    if data_format == "hex":
        return data.hex().upper()
    if data_format == "ascii":
        return data.split(b"\x00")[0].decode("ascii", errors="replace")
    struct_fmt = _STRUCT_FORMATS[data_format]
    width = struct.calcsize(struct_fmt)
    # Payload too short for the requested numeric width - fall back to hex instead of
    # raising, so a mismatched format choice doesn't hide an otherwise-successful response.
    if len(data) < width:
        return data.hex().upper()
    return str(struct.unpack(struct_fmt, data[:width])[0])


def _encode(value: str, data_format: DataFormat) -> bytes:
    """Encode a user-entered value into an RDM payload, per the chosen input format."""
    if data_format == "hex":
        return bytes.fromhex(value)
    if data_format == "ascii":
        return value.encode("ascii")
    struct_fmt = _STRUCT_FORMATS[data_format]
    return struct.pack(struct_fmt, int(value, 0))  # base 0: accepts "0x..", "0b..", or decimal


class RawPidAPI:
    """Generic GET/SET for arbitrary PIDs, bypassing the typed per-PID API modules."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def describe(self, pid: int) -> dict | None:
        """
        Look up what a PID supports (data type, GET/SET, range) before poking at it.

        Wraps ``system.get_parameter_description`` and adds human-readable labels for
        its numeric ``data_type``/``command_class`` fields (e.g. "ASCII string",
        "Unsigned word (0-65535)", "GET and SET") so the raw hex payload can be
        formatted correctly. Only devices that implement PARAMETER_DESCRIPTION for
        this PID return data here - see ``get_parameter_description``'s docstring.

        Args:
            pid: Parameter ID (0-65535) to describe.

        Returns:
            The parameter description dict, plus ``data_type_name``, ``byte_width``
            (fixed payload size in bytes, or None for variable-length/ASCII), and
            ``command_class_name``. None if the device didn't describe this PID.
        """
        info = await self._device.system.get_parameter_description(pid)
        if info is None:
            return None
        data_type_name, byte_width = parameter_data_type_info(info["data_type"])
        return {
            **info,
            "data_type_name": data_type_name,
            "byte_width": byte_width,
            "command_class_name": command_class_name(info["command_class"]),
        }

    async def get(self, pid: int, data_format: DataFormat = "hex") -> str | None:
        """
        GET an arbitrary PID and render the response payload in the chosen format.

        Args:
            pid: Parameter ID (0-65535), including manufacturer-specific PIDs.
            data_format: How to render the response - "hex", "ascii", or a fixed-width
                big-endian number ("uint8"/"int8"/"uint16"/"int16"/"uint32"/"int32").
                Use ``describe()`` first to check the PID's real data type/width.

        Returns:
            The response payload rendered per ``data_format``, or None if the device
            NAK'd or didn't respond.
        """
        response = await self._device.execute_get(pid)
        if response is None:
            return None
        return _decode(bytes(response), data_format)

    async def set(self, pid: int, value: str, data_format: DataFormat = "hex") -> bool:
        """
        SET an arbitrary PID, encoding ``value`` per the chosen format.

        Args:
            pid: Parameter ID (0-65535), including manufacturer-specific PIDs.
            value: The value to send, per ``data_format`` - a hex string ("0000000A"),
                ASCII text, or a number (decimal, or "0x.."/"0b..").
            data_format: How to encode ``value`` - "hex", "ascii", or a fixed-width
                big-endian number ("uint8"/"int8"/"uint16"/"int16"/"uint32"/"int32").

        Returns:
            True if the device ACKed.
        """
        data = _encode(value, data_format)
        return await self._device.execute_set(pid, data)
