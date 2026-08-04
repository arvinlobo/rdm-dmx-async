"""
Async transaction manager for RDM operations.

Provides a high-level interface for RDM GET/SET operations with automatic
transaction number management, retries, and error handling.
"""

import logging
from typing import TYPE_CHECKING

from ..packets.types import PID, UID
from .async_transaction import AsyncTransaction
from .policy import STANDARD_POLICY, RetryPolicy
from .result import TransactionResult

if TYPE_CHECKING:
    from ..protocols.base import RdmProtocol

_QUEUED_MESSAGE_PID = PID(0x0020)  # StandardPID.QUEUED_MESSAGE, per ANSI E1.20 ACK_TIMER follow-up


class AsyncTransactionManager:
    """
    High-level transaction manager for RDM operations.

    Handles all low-level transaction details including:
    - Transaction number allocation/deallocation
    - Retry logic with AsyncTransaction
    - Error handling and result formatting

    Device layer never sees transaction numbers - they're completely encapsulated here.
    """

    def __init__(self, protocol: "RdmProtocol", policy: RetryPolicy | None = None):
        """
        Initialize transaction manager.

        Args:
            protocol: RDM protocol instance
            policy: Retry policy (defaults to STANDARD_POLICY)
        """
        self._protocol = protocol
        self._policy = policy or STANDARD_POLICY
        # Reuse the protocol's single allocator so concurrent transactions
        # (e.g. batch operations across devices) never collide on the same
        # transaction number in the shared ResponseCorrelator.
        self._allocator = protocol.allocator
        self._logger = logging.getLogger(self.__class__.__name__)

    async def get(
        self,
        uid: UID,
        pid: PID,
        data: bytes = b"",
        timeout: float = 2.0,
    ) -> TransactionResult:
        """
        Execute GET command with automatic transaction management.

        Args:
            uid: Target device UID
            pid: Parameter ID
            data: Optional parameter data
            timeout: Command timeout in seconds

        Returns:
            TransactionResult with success status and response data
        """
        self._logger.debug(f"GET command: UID={uid:012X}, PID={pid:#x}")
        transaction = AsyncTransaction(
            operation=lambda txn: self._protocol.send_get_command(
                destination_uid=uid,
                pid=pid,
                transaction_number=txn,
                data=data,
                timeout=timeout,
            ),
            policy=self._policy,
            allocator=self._allocator,
            device_uid=uid,
            command_label=f"GET PID={pid:#x}",
            queued_message_operation=lambda txn: self._protocol.send_get_command(
                destination_uid=uid,
                pid=_QUEUED_MESSAGE_PID,
                transaction_number=txn,
                data=b"",
                timeout=timeout,
            ),
        )

        result = await transaction.execute()
        self._logger.debug(f"GET result: success={result.success}, UID={uid:012X}, PID={pid:#x}")
        return result

    async def set(
        self,
        uid: UID,
        pid: PID,
        data: bytes,
        timeout: float = 2.0,
    ) -> TransactionResult:
        """
        Execute SET command with automatic transaction management.

        Args:
            uid: Target device UID
            pid: Parameter ID
            data: Parameter data to set
            timeout: Command timeout in seconds

        Returns:
            TransactionResult with success status
        """
        self._logger.debug(f"SET command: UID={uid:012X}, PID={pid:#x}")
        transaction = AsyncTransaction(
            operation=lambda txn: self._protocol.send_set_command(
                destination_uid=uid,
                pid=pid,
                transaction_number=txn,
                data=data,
                timeout=timeout,
            ),
            policy=self._policy,
            allocator=self._allocator,
            device_uid=uid,
            command_label=f"SET PID={pid:#x}",
            queued_message_operation=lambda txn: self._protocol.send_get_command(
                destination_uid=uid,
                pid=_QUEUED_MESSAGE_PID,
                transaction_number=txn,
                data=b"",
                timeout=timeout,
            ),
        )

        result = await transaction.execute()
        self._logger.debug(f"SET result: success={result.success}, UID={uid:012X}, PID={pid:#x}")
        return result
