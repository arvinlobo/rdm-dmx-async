"""Correlates RDM responses with their originating requests."""

import asyncio
import logging
from datetime import datetime, timedelta

from ..packets.rdm import RDMResponse
from ..packets.types import TransactionNumber


class CorrelationError(Exception):
    """Raised when response correlation fails."""


class ResponseCorrelator:
    """Correlates RDM responses with their originating requests."""

    def __init__(self, stale_timeout: float = 30.0):
        self._handlers: dict[int, asyncio.Future[RDMResponse]] = {}
        self._handler_timestamps: dict[int, datetime] = {}
        self._stale_timeout = stale_timeout
        self._logger = logging.getLogger(self.__class__.__name__)
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background cleanup task."""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._logger.debug("Response correlator started")

    async def stop(self) -> None:
        """Stop cleanup and cancel all unresolved response futures."""
        if not self._running:
            return

        self._running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending handlers
        for future in self._handlers.values():
            if not future.done():
                future.cancel()

        self._handlers.clear()
        self._handler_timestamps.clear()
        self._logger.debug("Response correlator stopped")

    def register_handler(
        self, transaction_number: TransactionNumber
    ) -> asyncio.Future[RDMResponse]:
        """Register and return a future for ``transaction_number``.

        Raises:
            CorrelationError: If that transaction already has a handler.
        """
        txn_num = int(transaction_number)

        if txn_num in self._handlers:
            raise CorrelationError(f"Handler already registered for transaction {txn_num}")

        future = asyncio.get_running_loop().create_future()
        self._handlers[txn_num] = future
        self._handler_timestamps[txn_num] = datetime.now()

        self._logger.debug(
            f"[TXN_REG] Registered handler for TXN {txn_num} (active handlers: {len(self._handlers)})"
        )
        return future

    def correlate_response(self, response: RDMResponse) -> bool:
        """Returns True if response was correlated with a handler."""
        txn_num = int(response.transaction_number)

        self._logger.debug(
            f"[TXN_CORRELATE] Looking for handler for TXN {txn_num}, active: {list(self._handlers.keys())}"
        )

        future = self._handlers.get(txn_num)

        if future is None:
            self._logger.warning(
                f"[TXN_CORRELATE] No handler for TXN {txn_num} (unsolicited or timed out)"
            )
            return False

        if future.done():
            self._logger.warning(f"[TXN_CORRELATE] Handler for TXN {txn_num} already resolved")
            return False

        # Set the result
        future.set_result(response)

        # Cleanup
        self._handlers.pop(txn_num, None)
        self._handler_timestamps.pop(txn_num, None)

        self._logger.debug(f"[TXN_CORRELATE] Correlated response for TXN {txn_num}")
        return True

    def unregister_handler(self, transaction_number: TransactionNumber) -> None:
        """Discard the handler for a transaction, if present."""
        txn_num = int(transaction_number)
        self._handlers.pop(txn_num, None)
        self._handler_timestamps.pop(txn_num, None)
        self._logger.debug(f"Unregistered handler for TXN {txn_num}")

    def get_pending_count(self) -> int:
        """Return the number of responses currently being awaited."""
        return len(self._handlers)

    def get_handler_info(self) -> dict[int, float]:
        """Returns dict mapping transaction number to age in seconds."""
        now = datetime.now()
        return {
            txn: (now - timestamp).total_seconds()
            for txn, timestamp in self._handler_timestamps.items()
        }

    async def _cleanup_loop(self) -> None:
        self._logger.debug("Cleanup loop started")

        try:
            while self._running:
                await asyncio.sleep(10.0)  # Check every 10 seconds
                self._cleanup_stale_handlers()

        except asyncio.CancelledError:
            self._logger.debug("Cleanup loop cancelled")

    def _cleanup_stale_handlers(self) -> None:
        now = datetime.now()
        stale_threshold = timedelta(seconds=self._stale_timeout)

        stale_txns = [
            txn
            for txn, timestamp in self._handler_timestamps.items()
            if now - timestamp > stale_threshold
        ]

        for txn in stale_txns:
            future = self._handlers.get(txn)
            if future and not future.done():
                future.cancel()

            self._handlers.pop(txn, None)
            self._handler_timestamps.pop(txn, None)
            self._logger.warning(f"Cleaned up stale handler for TXN {txn}")

        if stale_txns:
            self._logger.info(f"Cleaned up {len(stale_txns)} stale handler(s)")
