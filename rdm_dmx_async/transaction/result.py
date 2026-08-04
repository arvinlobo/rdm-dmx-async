"""
Transaction result and attempt tracking for RDM operations.

Tracks the outcome of transaction attempts including successes, failures, and retries.
"""

from dataclasses import dataclass, field
from datetime import datetime

from ..packets.rdm import NAKReason, RDMResponse
from ..packets.types import ResponseType


@dataclass
class Attempt:
    """
    Record of a single transaction attempt.

    Tracks the attempt's outcome, timing, and response details.
    """

    attempt_number: int
    transaction_number: int
    timestamp: datetime
    success: bool
    response: RDMResponse | None = None
    error: str | None = None
    timeout: bool = False
    nak_reason: NAKReason | None = None
    is_late_response: bool = False

    @property
    def is_ack(self) -> bool:
        """Check if attempt received ACK response"""
        return (
            self.success
            and self.response is not None
            and self.response.response_type == ResponseType.ACK
        )

    @property
    def is_nak(self) -> bool:
        """Check if attempt received NAK response"""
        return self.response is not None and self.response.response_type in [
            ResponseType.NAK,
            ResponseType.ACK_TIMER,
        ]

    def __str__(self) -> str:
        """String representation of attempt"""
        status = "SUCCESS" if self.success else "FAILED"
        detail = ""

        if self.timeout:
            detail = " (timeout)"
        elif self.nak_reason is not None:
            detail = f" (NAK: {self.nak_reason.name})"
        elif self.error:
            detail = f" (error: {self.error})"
        elif self.is_late_response:
            detail = " (late response)"

        return f"Attempt {self.attempt_number} [TXN={self.transaction_number}]: {status}{detail}"


@dataclass
class TransactionResult:
    """
    Final result of an RDM transaction including all attempts.

    Provides comprehensive information about transaction outcome:
    - Success/failure status
    - All attempts made
    - Final response (if successful)
    - Error details (if failed)
    """

    success: bool
    attempts: list[Attempt] = field(default_factory=list)
    final_response: RDMResponse | None = None
    error_message: str | None = None
    permanent_failure: bool = False

    @property
    def attempt_count(self) -> int:
        """Get total number of attempts made"""
        return len(self.attempts)

    @property
    def successful_attempt(self) -> Attempt | None:
        """Get the successful attempt (if any)"""
        for attempt in self.attempts:
            if attempt.success:
                return attempt
        return None

    @property
    def had_timeout(self) -> bool:
        """Check if any attempt timed out"""
        return any(attempt.timeout for attempt in self.attempts)

    @property
    def had_nak(self) -> bool:
        """Check if any attempt received NAK"""
        return any(attempt.is_nak for attempt in self.attempts)

    @property
    def nak_reasons(self) -> list[NAKReason]:
        """Get list of all NAK reasons received"""
        reasons = []
        for attempt in self.attempts:
            if attempt.nak_reason is not None:
                reasons.append(attempt.nak_reason)
        return reasons

    def __str__(self) -> str:
        """String representation of transaction result"""
        status = "SUCCESS" if self.success else "FAILED"
        detail = f" after {self.attempt_count} attempt(s)"

        if self.permanent_failure:
            detail += " (permanent failure)"
        elif self.error_message:
            detail += f": {self.error_message}"

        return f"Transaction {status}{detail}"
