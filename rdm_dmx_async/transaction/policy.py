"""
Retry policy configuration for RDM transactions.

Defines retry behavior including max attempts, timeouts, and permanent failure detection.
"""

from dataclasses import dataclass, field

from ..packets.rdm import NAKReason


@dataclass
class RetryPolicy:
    """
    Configuration for RDM transaction retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including initial attempt).
                     Default 3 means: 1 initial attempt + 2 retries.

        delay_between_attempts: Delay in seconds between retry attempts.
                               Default 0.0 since protocol layer already waits for timeout.

        timeout: RDM response wait duration in seconds per attempt.
                Protocol layer waits this long for device response before
                marking attempt as failed.
                Default 3.0s for serial/Enttec protocols.

        permanent_failures: Set of NAK reason codes that stop retries immediately.
                           These indicate errors that won't be fixed by retrying
                           (e.g., unknown PID, format error, hardware fault).
                           User can customize this set based on device behavior.

    Example:
        # Standard policy with 3 attempts
        policy = RetryPolicy()

        # Aggressive retry for flaky devices
        policy = RetryPolicy(max_attempts=5, timeout=5.0)

        # No retries for discovery
        policy = RetryPolicy(max_attempts=1)
    """

    max_attempts: int = 3
    delay_between_attempts: float = 0.0
    timeout: float = 3.0

    permanent_failures: set[NAKReason] = field(
        default_factory=lambda: {
            NAKReason.UNKNOWN_PID,
            NAKReason.FORMAT_ERROR,
            NAKReason.HARDWARE_FAULT,
            NAKReason.PROXY_REJECT,
            NAKReason.WRITE_PROTECT,
            NAKReason.UNSUPPORTED_COMMAND_CLASS,
            NAKReason.DATA_OUT_OF_RANGE,
            NAKReason.BUFFER_FULL,
            NAKReason.PACKET_SIZE_UNSUPPORTED,
            NAKReason.SUB_DEVICE_OUT_OF_RANGE,
        }
    )

    def __post_init__(self):
        """Validate policy parameters"""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self.delay_between_attempts < 0:
            raise ValueError("delay_between_attempts cannot be negative")

    def is_permanent_failure(self, nak_reason: NAKReason) -> bool:
        """
        Check if a NAK reason indicates permanent failure.

        Args:
            nak_reason: NAK reason code from device

        Returns:
            True if this NAK should not be retried
        """
        return nak_reason in self.permanent_failures


# Predefined policies for common scenarios
STANDARD_POLICY = RetryPolicy()
NO_RETRY_POLICY = RetryPolicy(max_attempts=1)
AGGRESSIVE_RETRY_POLICY = RetryPolicy(max_attempts=5, timeout=5.0)
DISCOVERY_POLICY = RetryPolicy(max_attempts=1, timeout=2.0)
