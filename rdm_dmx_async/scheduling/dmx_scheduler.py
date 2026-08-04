"""DMX frame scheduler with proper timing control."""

import asyncio
import logging
from collections.abc import Awaitable, Callable


class DmxFrameScheduler:
    """
    Schedules DMX frame transmission.

    Hardware timing (Break/MAB/slot timing) is handled by the adapter.
    This scheduler only manages frame refresh rate.
    """

    def __init__(
        self,
        frame_callback: Callable[[], bytes] | None = None,
        frame_interval_ms: float = 25.0,
        send_callback: Callable[[bytes], Awaitable[None]] | None = None,
    ):
        """
        Initialize DMX frame scheduler.

        Args:
            frame_callback: Optional callback to get frame data
            frame_interval_ms: Frame refresh interval in milliseconds (~40 Hz typical)
            send_callback: Async callback that transmits a frame (e.g. to the
                transport). If not provided, frames are built each interval
                but never sent anywhere.
        """
        self._frame_callback = frame_callback
        self._send_callback = send_callback
        self._frame_interval_ms = frame_interval_ms
        self._running = False
        self._task: asyncio.Task | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

        # State
        self._current_frame = bytearray(512)  # DMX universe
        self._frame_count = 0
        self._rdm_pause_event = asyncio.Event()
        self._rdm_pause_event.set()  # Not paused initially

    def set_dmx_data(self, start_address: int, data: bytes) -> None:
        """Update consecutive slots in the current DMX universe.

        Data extending beyond slot 512 is truncated.

        Raises:
            ValueError: If ``start_address`` is outside the 1–512 range.
        """
        if not (1 <= start_address <= 512):
            raise ValueError(f"Invalid DMX address: {start_address}")

        end = min(start_address + len(data), 513)
        self._current_frame[start_address - 1 : end - 1] = data[: end - start_address]

    def get_dmx_data(self, start_address: int, length: int) -> bytes:
        """Return up to ``length`` slots from the current DMX universe.

        Raises:
            ValueError: If ``start_address`` is outside the 1–512 range.
        """
        if not (1 <= start_address <= 512):
            raise ValueError(f"Invalid DMX address: {start_address}")

        end = min(start_address + length, 513)
        return bytes(self._current_frame[start_address - 1 : end - 1])

    async def pause_for_rdm(self, duration_ms: float) -> None:
        """Suspend frame scheduling for an RDM window measured in milliseconds."""
        self._rdm_pause_event.clear()
        self._logger.debug(f"DMX paused for RDM ({duration_ms}ms)")

        try:
            await asyncio.sleep(duration_ms / 1000.0)
        finally:
            # Always resume, even if this task is cancelled mid-sleep (e.g. an
            # RDM operation finishing early), otherwise DMX output stalls forever.
            self._rdm_pause_event.set()
            self._logger.debug("DMX resumed")

    async def start(self) -> None:
        """Start the background frame scheduling loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._schedule_loop())
        self._logger.info(f"DMX scheduler started (interval={self._frame_interval_ms}ms)")

    async def stop(self) -> None:
        """Stop the background frame scheduling loop."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._logger.info("DMX scheduler stopped")

    async def _schedule_loop(self) -> None:
        """Background scheduling loop"""
        try:
            while self._running:
                # Wait if RDM is active
                await self._rdm_pause_event.wait()

                # Get frame data
                if self._frame_callback:
                    frame_data = self._frame_callback()
                else:
                    frame_data = bytes(self._current_frame)

                if self._send_callback:
                    try:
                        await self._send_callback(frame_data)
                    except Exception as e:
                        self._logger.error(f"Error sending scheduled DMX frame: {e}")

                self._frame_count += 1

                # Wait for next frame interval
                await asyncio.sleep(self._frame_interval_ms / 1000.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error in schedule loop: {e}", exc_info=True)

    @property
    def frame_count(self) -> int:
        """Get total frames sent"""
        return self._frame_count
