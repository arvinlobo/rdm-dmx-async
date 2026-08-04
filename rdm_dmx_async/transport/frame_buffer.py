"""Frame buffering and parsing for serial transport."""

import logging

from .interface_adapter import InterfaceAdapter


class FrameBuffer:
    """Manages buffering and frame extraction from serial data stream."""

    def __init__(self, adapter: InterfaceAdapter, max_size: int = 1024):
        """
        Initialize frame buffer.

        Args:
            adapter: Interface adapter for frame parsing
            max_size: Maximum buffer size before overflow handling
        """
        self._adapter = adapter
        self._max_size = max_size
        self._buffer = bytearray()
        self._logger = logging.getLogger(self.__class__.__name__)
        # Length recorded the last time no frame could be found, used to
        # detect a stalled buffer (no new bytes arrived) vs. a frame that is
        # still in the process of arriving across multiple reads.
        self._stalled_length: int | None = None

    def append(self, data: bytes) -> None:
        """Add data to buffer."""
        self._buffer.extend(data)

    def _handle_overflow(self) -> None:
        """Discard oldest byte if buffer exceeds max size."""
        if len(self._buffer) > self._max_size:
            self._logger.warning("Buffer overflow, discarding oldest byte")
            self._buffer.pop(0)

    def extract_frame(self) -> bytes | None:
        """
        Try to extract one complete frame from buffer.

        Returns:
            Extracted frame bytes, or None if no complete frame available
        """
        if len(self._buffer) < 5:  # Minimum frame size
            # Too small for a frame, but still track staleness so leftover
            # garbage below the frame-size floor doesn't get stuck forever
            # waiting on logic further down that never runs for it.
            self._advance_stall_tracking()
            return None

        # Check if there's a complete frame (valid or not)
        frame_len = self._adapter.find_frame_length(bytes(self._buffer))

        if frame_len > 0:
            # Valid frame structure exists - try to parse it
            frame = self._adapter.parse_rdm_response(bytes(self._buffer))

            # Always consume the frame, even if parse returned None
            # (e.g., for unhandled message types like 0x0C)
            self._buffer = self._buffer[frame_len:]
            self._stalled_length = None

            return frame  # May be None for unhandled frames

        # No frame at the front of the buffer. Before falling back to the
        # stall check (which only fires once the buffer stops growing),
        # look ahead for a complete frame starting at a later offset - if
        # one is already fully present, byte 0 is provably garbage and can
        # be discarded immediately. This matters when unrelated valid
        # traffic keeps arriving right behind a leading garbage byte: the
        # buffer never "stalls" (it keeps growing), so without this check
        # recovery would depend entirely on the max_size overflow cap.
        resync_offset = self._find_resync_offset()
        if resync_offset is not None:
            self._logger.warning(
                "Discarding %d leading garbage byte(s) before resynced frame", resync_offset
            )
            del self._buffer[:resync_offset]
            self._stalled_length = None
            return None

        # No resync candidate either. If the buffer hasn't grown since the
        # last time we checked, no more bytes are coming to complete a frame
        # here, so byte 0 must be garbage - discard it. Otherwise, a frame
        # may still be arriving across multiple reads, so wait for more data
        # rather than discarding a byte that belongs to a valid frame.
        self._advance_stall_tracking()
        return None

    def _advance_stall_tracking(self) -> None:
        """Discard one leading byte if the buffer hasn't grown since the
        last check (a genuine stall), otherwise just record its length."""
        if self._buffer and len(self._buffer) == self._stalled_length:
            self._buffer.pop(0)
        self._stalled_length = len(self._buffer)
        self._handle_overflow()

    def _find_resync_offset(self) -> int | None:
        """
        Look for a complete, recognizable frame starting at some offset
        beyond the front of the buffer.

        Returns:
            The offset of the first recognized frame beyond position 0, or
            None if no such frame is present yet.
        """
        buffer_view = bytes(self._buffer)
        for offset in range(1, len(buffer_view) - 4):  # need >= 5 bytes remaining
            if self._adapter.find_frame_length(buffer_view[offset:]) > 0:
                return offset
        return None

    def extract_all_frames(self, max_iterations: int = 10) -> list[bytes]:
        """
        Extract all available complete frames from buffer.

        Args:
            max_iterations: Safety limit to prevent infinite loops

        Returns:
            List of extracted frames (may be empty)
        """
        frames = []
        iteration = 0

        while len(self._buffer) >= 5 and iteration < max_iterations:
            iteration += 1
            frame = self.extract_frame()

            if frame is None:
                break

            frames.append(frame)

        return frames

    def clear(self) -> None:
        """Clear all buffered data."""
        self._buffer.clear()
        self._stalled_length = None

    def __len__(self) -> int:
        """Return current buffer size."""
        return len(self._buffer)
