"""
Adapter for DMXKing ultraDMX interfaces.
"""

from ..interface_adapter import InterfaceAdapter, InterfaceType, SerialConfig


class DMXKingAdapter(InterfaceAdapter):
    """
    Adapter for DMXKing ultraDMX interfaces.

    This is a placeholder showing how to add support for other interfaces.
    DMXKing uses a different protocol than Enttec.
    """

    def __init__(self, port: str):
        self._port = port

    @property
    def interface_type(self) -> InterfaceType:
        """Return the DMXKing ultraDMX interface identifier."""
        return InterfaceType.DMXKING_ULTRA_DMX

    @property
    def serial_config(self) -> SerialConfig:
        """Return serial settings for the adapter.

        Raises:
            NotImplementedError: DMXKing support is not implemented.
        """
        raise NotImplementedError("DMXKing adapter not yet implemented")

    def frame_rdm_request(self, rdm_data: bytes, port: int = 1) -> bytes:
        """Frame an RDM request.

        Raises:
            NotImplementedError: DMXKing support is not implemented.
        """
        # TODO: Implement DMXKing framing protocol
        raise NotImplementedError("DMXKing adapter not yet implemented")

    def frame_rdm_discovery_request(self, rdm_data: bytes, port: int = 1) -> bytes:
        """Frame an RDM discovery request.

        Raises:
            NotImplementedError: DMXKing support is not implemented.
        """
        # TODO: Implement DMXKing discovery framing
        raise NotImplementedError("DMXKing adapter not yet implemented")

    def parse_rdm_response(self, raw_data: bytes) -> bytes | None:
        """Extract RDM data from an ultraDMX response.

        Raises:
            NotImplementedError: DMXKing support is not implemented.
        """
        # TODO: Implement DMXKing parsing
        raise NotImplementedError("DMXKing adapter not yet implemented")

    def find_frame_length(self, buffer: bytes) -> int:
        """Determine the length of an ultraDMX frame.

        Raises:
            NotImplementedError: DMXKing support is not implemented.
        """
        # TODO: Implement DMXKing frame length detection
        raise NotImplementedError("DMXKing adapter not yet implemented")

    def frame_dmx_output(self, dmx_data: bytes, port: int = 1) -> bytes:
        """Frame a DMX output universe.

        Raises:
            NotImplementedError: DMXKing support is not implemented.
        """
        # TODO: Implement DMXKing DMX output framing
        raise NotImplementedError("DMXKing adapter not yet implemented")
