"""
Transaction number allocation for RDM operations.

Manages allocation of unique transaction numbers within the valid RDM range (1-255).
"""

import logging


class TransactionNumberAllocator:
    """
    Allocates unique transaction numbers for RDM operations.

    RDM transaction numbers are 8-bit values in the range 1-255 (0 is reserved).
    This allocator cycles through the range and tracks which numbers are in use.

    Thread-safe for single-threaded async code (not thread-safe for multi-threading).
    """

    # RDM transaction number valid range (E1.20 spec)
    RDM_TXN_MIN = 1
    RDM_TXN_MAX = 255

    def __init__(self, starting_number: int = 1):
        """
        Initialize allocator.

        Args:
            starting_number: Starting transaction number (default 1)

        Raises:
            ValueError: If starting number is out of valid range
        """
        if not (self.RDM_TXN_MIN <= starting_number <= self.RDM_TXN_MAX):
            raise ValueError(
                f"Starting number must be in range [{self.RDM_TXN_MIN}, {self.RDM_TXN_MAX}]"
            )

        self._next_number = starting_number
        self._in_use: set[int] = set()
        self._logger = logging.getLogger(self.__class__.__name__)

    def allocate(self) -> int:
        """
        Allocate the next available transaction number.

        Returns:
            Unique transaction number (1-255)

        Raises:
            RuntimeError: If all 255 numbers are in use (should never happen in practice)
        """
        # Try up to 255 times to find an available number
        for _ in range(self.RDM_TXN_MAX):
            candidate = self._next_number
            self._next_number += 1

            # Wrap around to 1 (skip 0)
            if self._next_number > self.RDM_TXN_MAX:
                self._next_number = self.RDM_TXN_MIN

            # Check if candidate is available
            if candidate not in self._in_use:
                self._in_use.add(candidate)
                self._logger.debug(
                    f"Allocated transaction number {candidate} (in use: {len(self._in_use)})"
                )
                return candidate

        # All 255 numbers in use (very unlikely)
        self._logger.error("All transaction numbers in use. Too many concurrent transactions.")
        raise RuntimeError("All transaction numbers in use. Too many concurrent transactions.")

    def release(self, txn_number: int) -> None:
        """
        Release a transaction number back to the pool.

        Args:
            txn_number: Transaction number to release

        Raises:
            ValueError: If number is invalid or not in use
        """
        if not (self.RDM_TXN_MIN <= txn_number <= self.RDM_TXN_MAX):
            raise ValueError(f"Invalid transaction number {txn_number}")

        if txn_number not in self._in_use:
            raise ValueError(f"Transaction number {txn_number} is not in use")

        self._in_use.discard(txn_number)
        self._logger.debug(
            f"Released transaction number {txn_number} (in use: {len(self._in_use)})"
        )

    def release_all(self, txn_numbers: list[int]) -> None:
        """
        Release multiple transaction numbers.

        Args:
            txn_numbers: List of transaction numbers to release
        """
        for txn in txn_numbers:
            if txn in self._in_use:
                self._in_use.discard(txn)

    @property
    def in_use_count(self) -> int:
        """Get count of transaction numbers currently in use"""
        return len(self._in_use)

    @property
    def available_count(self) -> int:
        """Get count of available transaction numbers"""
        return self.RDM_TXN_MAX - len(self._in_use)
