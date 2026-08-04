"""
Transaction layer for RDM operations.

Provides reliable RDM communication with automatic retries, late response handling,
and permanent failure detection.

Key features:
- Automatic retry logic with configurable policies
- Response correlation to detect late responses
- Transaction number management and allocation
- Permanent failure detection (NAK codes that shouldn't be retried)
- Comprehensive result tracking for all attempts

Example:
    from rdm_dmx_async.transaction import (
        AsyncTransaction,
        RetryPolicy,
        TransactionNumberAllocator,
        STANDARD_POLICY
    )

    # Create shared allocator
    allocator = TransactionNumberAllocator()

    # Execute transaction with retries
    transaction = AsyncTransaction(
        operation=lambda txn: protocol.send_get_command(uid, pid, txn),
        policy=STANDARD_POLICY,
        allocator=allocator,
        device_uid=uid
    )

    result = await transaction.execute()
    if result.success:
        print(f"Response: {result.final_response}")
    else:
        print(f"Failed: {result.error_message}")
"""

from .allocator import TransactionNumberAllocator
from .async_transaction import AsyncTransaction
from .correlator import LateResponseClassifier, ResponseClassification
from .policy import (
    AGGRESSIVE_RETRY_POLICY,
    DISCOVERY_POLICY,
    NO_RETRY_POLICY,
    STANDARD_POLICY,
    RetryPolicy,
)
from .result import Attempt, TransactionResult
from .state import TransactionState
from .transaction_manager import AsyncTransactionManager

__all__ = [
    # Main transaction class
    "AsyncTransaction",
    "AsyncTransactionManager",
    # Allocation
    "TransactionNumberAllocator",
    # Correlation
    "LateResponseClassifier",
    "ResponseClassification",
    # Policy
    "RetryPolicy",
    "STANDARD_POLICY",
    "NO_RETRY_POLICY",
    "AGGRESSIVE_RETRY_POLICY",
    "DISCOVERY_POLICY",
    # Results
    "TransactionResult",
    "Attempt",
    # State
    "TransactionState",
]
