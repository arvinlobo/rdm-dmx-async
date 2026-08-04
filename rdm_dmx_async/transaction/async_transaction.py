"""
Async transaction implementation with retry logic for RDM operations.

Provides reliable RDM communication with automatic retries, late response handling,
and permanent failure detection.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from ..packets.rdm import NAKReason, RDMResponse
from ..packets.types import UID, ResponseType
from ..protocols.rdm_e120 import ProtocolTimeoutError
from .allocator import TransactionNumberAllocator
from .correlator import LateResponseClassifier, ResponseClassification
from .policy import RetryPolicy
from .result import Attempt, TransactionResult
from .state import TransactionState

logger = logging.getLogger(__name__)


class AsyncTransaction:
    """
    Manages the lifecycle of a single RDM transaction with retry logic.

    An AsyncTransaction encapsulates a complete RDM operation including:
    - Initial attempt execution
    - Retry attempts (if needed)
    - Response correlation (detecting late responses)
    - Permanent failure detection (certain NAKs)
    - Comprehensive result tracking

    The transaction owns multiple transaction numbers (one per attempt) and
    correlates responses to handle cases where devices respond to earlier
    attempts after a retry has been initiated.

    Example:
        allocator = TransactionNumberAllocator()
        policy = RetryPolicy(max_attempts=3, timeout=3.0)

        async def rdm_operation(txn: int) -> RDMResponse:
            return await protocol.send_get_command(
                destination_uid=device_uid,
                pid=PID(0x0082),
                transaction_number=txn
            )

        transaction = AsyncTransaction(
            operation=rdm_operation,
            policy=policy,
            allocator=allocator,
            device_uid=device_uid
        )

        result = await transaction.execute()
        if result.success:
            print(f"Got response: {result.final_response}")
        else:
            print(f"Failed: {result.error_message}")
    """

    def __init__(
        self,
        operation: Callable[[int], Awaitable[RDMResponse]],
        policy: RetryPolicy,
        allocator: TransactionNumberAllocator | None = None,
        device_uid: UID | None = None,
        command_label: str | None = None,
        queued_message_operation: Callable[[int], Awaitable[RDMResponse]] | None = None,
    ):
        """
        Initialize a new async transaction.

        Args:
            operation: Async callable that executes RDM command with transaction number.
                      Should return RDMResponse or raise exception.
            policy: RetryPolicy defining retry behavior
            allocator: TransactionNumberAllocator for generating transaction numbers (optional)
            device_uid: Target device UID (optional, for logging)
            command_label: Human-readable command description (e.g. "GET PID=0x60"),
                          included in log messages so failures identify the command
            queued_message_operation: Async callable (same shape as `operation`) that
                          issues a GET QUEUED_MESSAGE request. When provided, an
                          ACK_TIMER response is followed up per ANSI E1.20 instead of
                          being treated as a plain retry-worthy failure. If omitted,
                          ACK_TIMER responses fall back to a generic retry.
        """
        self.operation = operation
        self.policy = policy
        self.allocator = allocator or TransactionNumberAllocator()
        self.device_uid = device_uid or UID(0)
        self.command_label = command_label
        self.queued_message_operation = queued_message_operation

        # Transaction state
        self.state = TransactionState.CREATED
        self.attempts: list[Attempt] = []
        self.allocated_txn_numbers: list[int] = []
        self.correlator = LateResponseClassifier()

    @property
    def _device_desc(self) -> str:
        """Device UID plus command label (if set), for log messages."""
        suffix = f" ({self.command_label})" if self.command_label else ""
        return f"device {self.device_uid:012X}{suffix}"

    async def execute(self) -> TransactionResult:
        """
        Execute the transaction with retries until success, permanent failure, or exhaustion.

        Returns:
            TransactionResult with comprehensive outcome information
        """
        logger.debug(
            f"Starting transaction for device {self.device_uid:012X} "
            f"with policy: max_attempts={self.policy.max_attempts}, "
            f"timeout={self.policy.timeout}s"
        )

        try:
            for attempt_index in range(self.policy.max_attempts):
                # Update state
                self._update_state(attempt_index)

                # Execute one attempt
                response, is_late = await self._execute_attempt(attempt_index)

                # Skip late responses from previous attempts
                if is_late:
                    logger.debug(f"Skipping late response for device {self.device_uid:012X}")
                    # Don't count as an attempt, retry immediately
                    continue

                # Check if successful
                if response and response.response_type == ResponseType.ACK:
                    logger.debug(
                        f"Transaction succeeded for device {self.device_uid:012X} "
                        f"on attempt {attempt_index + 1}"
                    )
                    return self._create_success_result(response)

                # Check for permanent failure (based on policy configuration)
                if response and response.response_type == ResponseType.NAK:
                    nak_reason = NAKReason(response.data[0]) if response.data else None
                    # NOTE: must check `is not None`, not truthiness - NAKReason.UNKNOWN_PID == 0,
                    # which is falsy, so a plain `if nak_reason` would silently skip the permanent-
                    # failure short-circuit for the single most common NAK reason.
                    if nak_reason is not None and self.policy.is_permanent_failure(nak_reason):
                        logger.warning(
                            f"Permanent failure for {self._device_desc}: NAK {nak_reason.name}"
                        )
                        return self._create_permanent_failure_result(nak_reason)

                # Retry needed - add delay if configured
                if attempt_index < self.policy.max_attempts - 1:
                    if self.policy.delay_between_attempts > 0:
                        logger.debug(f"Waiting {self.policy.delay_between_attempts}s before retry")
                        await asyncio.sleep(self.policy.delay_between_attempts)

            # All attempts exhausted
            logger.warning(
                f"Transaction failed for {self._device_desc}: "
                f"all {self.policy.max_attempts} attempts exhausted"
            )
            return self._create_failure_result("All retry attempts exhausted")

        finally:
            # Release all allocated transaction numbers
            if self.allocated_txn_numbers:
                self.allocator.release_all(self.allocated_txn_numbers)
                logger.debug(f"Released {len(self.allocated_txn_numbers)} transaction numbers")

    async def _execute_attempt(self, attempt_index: int) -> tuple[RDMResponse | None, bool]:
        """
        Execute a single attempt of the operation.

        Args:
            attempt_index: Zero-based attempt number

        Returns:
            Tuple of (response, is_late_response)
        """
        # Allocate transaction number for this attempt
        txn_number = self.allocator.allocate()
        self.allocated_txn_numbers.append(txn_number)
        self.correlator.register_transaction_numbers(self.allocated_txn_numbers)

        logger.debug(
            f"Attempt {attempt_index + 1}/{self.policy.max_attempts} "
            f"for device {self.device_uid:012X} with TXN={txn_number}"
        )

        timestamp = datetime.now()
        response = None
        error = None
        timeout = False
        is_late = False

        try:
            # Execute operation with timeout
            response = await asyncio.wait_for(
                self.operation(txn_number), timeout=self.policy.timeout
            )

            # Correlate response to detect late responses
            if response and hasattr(response, "transaction_number"):
                classification = self.correlator.classify_response(
                    response.transaction_number, txn_number
                )

                if classification == ResponseClassification.LATE:
                    is_late = True
                    logger.debug(
                        f"Received late response with TXN={response.transaction_number} "
                        f"(expected {txn_number})"
                    )
                elif classification == ResponseClassification.ANOMALOUS:
                    logger.warning(
                        f"Received anomalous response with TXN={response.transaction_number} "
                        f"(not in active set)"
                    )

            if (
                response is not None
                and not is_late
                and response.response_type == ResponseType.ACK_TIMER
                and self.queued_message_operation is not None
            ):
                response = await self._poll_queued_message(response)

            success = (
                response is not None and response.response_type == ResponseType.ACK and not is_late
            )

        except (TimeoutError, ProtocolTimeoutError):
            timeout = True
            error = f"Timeout after {self.policy.timeout}s"
            success = False
            logger.debug(f"Attempt {attempt_index + 1} timed out for {self._device_desc}")

        except Exception as e:
            error = str(e)
            success = False
            logger.error(f"Attempt {attempt_index + 1} failed for {self._device_desc}: {e}")

        # Record attempt
        nak_reason = None
        if response and response.response_type == ResponseType.NAK:
            nak_reason = NAKReason(response.data[0]) if response.data else None

        attempt = Attempt(
            attempt_number=attempt_index + 1,
            transaction_number=txn_number,
            timestamp=timestamp,
            success=success,
            response=response,
            error=error,
            timeout=timeout,
            nak_reason=nak_reason,
            is_late_response=is_late,
        )

        self.attempts.append(attempt)
        logger.debug(str(attempt))

        return response, is_late

    async def _poll_queued_message(self, response: RDMResponse) -> RDMResponse:
        """
        Follow up an ACK_TIMER response per ANSI E1.20: wait the device-indicated
        delay, then GET QUEUED_MESSAGE, repeating while it keeps returning
        ACK_TIMER (up to `policy.max_ack_timer_polls` times).

        Returns:
            The final response (ACK/NAK from QUEUED_MESSAGE, or the last
            ACK_TIMER seen if the poll budget or a poll timeout cuts it short).
        """
        assert self.queued_message_operation is not None

        for _ in range(self.policy.max_ack_timer_polls):
            if response.response_type != ResponseType.ACK_TIMER:
                break

            delay_ms = response.ack_timer_value or 0
            logger.debug(
                f"ACK_TIMER for {self._device_desc}: waiting {delay_ms}ms then "
                f"polling QUEUED_MESSAGE"
            )
            await asyncio.sleep(delay_ms / 1000)

            txn_number = self.allocator.allocate()
            self.allocated_txn_numbers.append(txn_number)
            self.correlator.register_transaction_numbers(self.allocated_txn_numbers)

            try:
                response = await asyncio.wait_for(
                    self.queued_message_operation(txn_number), timeout=self.policy.timeout
                )
            except (TimeoutError, ProtocolTimeoutError):
                logger.debug(f"QUEUED_MESSAGE poll timed out for {self._device_desc}")
                break

        return response

    def _update_state(self, attempt_index: int) -> None:
        """Update transaction state based on attempt number"""
        if attempt_index == 0:
            self.state = TransactionState.IN_PROGRESS
        else:
            self.state = TransactionState.RETRYING

    def _create_success_result(self, response: RDMResponse) -> TransactionResult:
        """Create successful transaction result"""
        self.state = TransactionState.SUCCEEDED
        return TransactionResult(
            success=True, attempts=self.attempts, final_response=response, permanent_failure=False
        )

    def _create_failure_result(self, error_message: str) -> TransactionResult:
        """Create failed transaction result"""
        self.state = TransactionState.FAILED
        return TransactionResult(
            success=False,
            attempts=self.attempts,
            error_message=error_message,
            permanent_failure=False,
        )

    def _create_permanent_failure_result(self, nak_reason: NAKReason) -> TransactionResult:
        """Create permanent failure result"""
        self.state = TransactionState.FAILED
        return TransactionResult(
            success=False,
            attempts=self.attempts,
            error_message=f"Permanent failure: NAK {nak_reason.name}",
            permanent_failure=True,
        )
