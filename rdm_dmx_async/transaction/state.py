"""
Transaction state management for RDM operations.

Defines the lifecycle states of an RDM transaction.
"""

from enum import Enum, auto


class TransactionState(Enum):
    """
    Lifecycle states for RDM transactions.

    State transitions:
    CREATED → IN_PROGRESS → SUCCEEDED
                          → RETRYING → SUCCEEDED
                                    → FAILED
    """

    CREATED = auto()  # Transaction created but not yet executed
    IN_PROGRESS = auto()  # First attempt in progress
    RETRYING = auto()  # Retry attempt in progress
    SUCCEEDED = auto()  # Transaction succeeded
    FAILED = auto()  # Transaction failed (all attempts exhausted or permanent failure)
