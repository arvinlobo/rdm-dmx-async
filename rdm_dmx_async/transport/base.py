"""Base transport interface and exceptions."""

from typing import Protocol


class TransportError(Exception):
    """Base exception for transport-related errors."""


class NotConnectedError(TransportError):
    """Raised when attempting operations on disconnected transport."""


class ConnectionFailedError(TransportError):
    """Raised when connection attempt fails."""


class AsyncTransport(Protocol):
    """Abstract interface for async transport implementations."""

    @property
    def is_connected(self) -> bool:
        """Return whether the transport is connected and ready for I/O."""
        ...

    async def connect(self) -> None:
        """Open the underlying transport connection."""
        ...

    async def disconnect(self) -> None:
        """Close the underlying transport connection."""
        ...

    async def send(self, data: bytes, destination: str) -> None:
        """Send one encoded packet to ``destination``."""
        ...

    async def send_dmx_frame(self, dmx_data: bytes, port: int = 1) -> None:
        """Frame and transmit one DMX512 output frame on ``port``."""
        ...

    async def receive(self, timeout: float | None = None) -> tuple[bytes, str]:
        """Receive one packet and return its bytes and source address."""
        ...

    async def __aenter__(self) -> "AsyncTransport":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
