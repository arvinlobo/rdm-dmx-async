"""Manages RDM request windows within DMX stream."""

import asyncio
import logging

from .dmx_scheduler import DmxFrameScheduler


class RdmRequestWindow:
    """Manages RDM request windows within DMX stream per ANSI E1.20."""

    # RDM timing constants (from ANSI E1.20)
    DEFAULT_WINDOW_MS = 10.0  # Time allocated for RDM transaction
    MIN_RESPONSE_TIMEOUT_MS = 2.0  # Minimum time to wait for response
    MAX_RESPONSE_TIMEOUT_MS = 3.0  # Maximum response timeout

    def __init__(self, scheduler: DmxFrameScheduler | None = None):
        self._scheduler = scheduler
        self._logger = logging.getLogger(self.__class__.__name__)
        self._window_lock = asyncio.Lock()

    async def execute_in_window(
        self, rdm_operation: callable, timeout_ms: float = MAX_RESPONSE_TIMEOUT_MS
    ) -> any:
        """Run an async operation during an exclusive RDM timing window.

        Args:
            rdm_operation: Zero-argument callable returning an awaitable.
            timeout_ms: Maximum operation duration in milliseconds.

        Returns:
            The value returned by the operation.

        Raises:
            asyncio.TimeoutError: If the operation exceeds ``timeout_ms``.
        """
        async with self._window_lock:
            # Pause DMX for the full possible operation duration - not a fixed
            # small window - otherwise DMX resumes mid-operation whenever the
            # operation takes longer than DEFAULT_WINDOW_MS. The early-resume
            # cancellation below still lets DMX resume immediately once the
            # operation actually finishes.
            if self._scheduler:
                pause_task = asyncio.create_task(self._scheduler.pause_for_rdm(timeout_ms))

            try:
                # Execute RDM operation with timeout
                result = await asyncio.wait_for(rdm_operation(), timeout=timeout_ms / 1000.0)

                self._logger.debug("RDM operation completed in window")
                return result

            except TimeoutError:
                self._logger.warning(f"RDM operation timed out ({timeout_ms}ms)")
                raise
            finally:
                # Ensure DMX resumes
                if self._scheduler and not pause_task.done():
                    pause_task.cancel()

    async def request_window(self, duration_ms: float) -> None:
        """Pause DMX output, or wait, for ``duration_ms`` milliseconds."""
        if self._scheduler:
            await self._scheduler.pause_for_rdm(duration_ms)
        else:
            # No scheduler, just wait
            await asyncio.sleep(duration_ms / 1000.0)

    def attach_scheduler(self, scheduler: DmxFrameScheduler) -> None:
        """Attach the DMX scheduler that will be paused for RDM operations."""
        self._scheduler = scheduler
        self._logger.info("Attached DMX scheduler to RDM window")

    @property
    def has_scheduler(self) -> bool:
        """Return whether a DMX scheduler is attached."""
        return self._scheduler is not None
