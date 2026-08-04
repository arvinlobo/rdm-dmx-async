"""
Response classification and correlation for RDM transactions.

Handles detection of late responses from previous transaction attempts.
"""

import logging
from enum import Enum, auto


class ResponseClassification(Enum):
    """Classification of received RDM responses"""

    ACTIVE = auto()  # Response matches current attempt's transaction number
    LATE = auto()  # Response matches a previous attempt's transaction number
    ANOMALOUS = auto()  # Response doesn't match any known transaction number


class LateResponseClassifier:
    """
    Correlates RDM responses with transaction numbers to detect late responses.

    Late responses occur when a device responds to a previous attempt after
    we've already started a retry with a new transaction number.

    Example:
        Attempt 1: Send with TXN=1, timeout (no response)
        Attempt 2: Send with TXN=2, receive response with TXN=1 (LATE)
                                     receive response with TXN=2 (ACTIVE)
    """

    # RDM transaction number valid range (E1.20 spec)
    RDM_TXN_MIN = 1
    RDM_TXN_MAX = 255

    def __init__(self) -> None:
        """Initialize correlator with empty active set"""
        self._active_txn_numbers: set[int] = set()
        self._logger = logging.getLogger(self.__class__.__name__)

    def register_transaction_numbers(self, txn_numbers: list[int]) -> None:
        """
        Register transaction numbers for this transaction.

        Args:
            txn_numbers: List of transaction numbers across all attempts

        Raises:
            ValueError: If list is empty or contains invalid numbers
        """
        if not txn_numbers:
            raise ValueError("Transaction numbers list cannot be empty")

        for txn in txn_numbers:
            if not (self.RDM_TXN_MIN <= txn <= self.RDM_TXN_MAX):
                raise ValueError(
                    f"Invalid transaction number {txn}, "
                    f"must be in range [{self.RDM_TXN_MIN}, {self.RDM_TXN_MAX}]"
                )

        self._active_txn_numbers = set(txn_numbers)
        self._logger.debug(f"Registered transaction numbers: {txn_numbers}")

    def classify_response(
        self, response_txn_number: int, current_attempt_txn_number: int
    ) -> ResponseClassification:
        """
        Classify a response based on its transaction number.

        Args:
            response_txn_number: Transaction number from device response
            current_attempt_txn_number: Transaction number of current attempt

        Returns:
            ACTIVE if response matches current attempt
            LATE if response matches previous attempt
            ANOMALOUS if response doesn't match any attempt

        Raises:
            ValueError: If response transaction number is invalid
        """
        if not (self.RDM_TXN_MIN <= response_txn_number <= self.RDM_TXN_MAX):
            raise ValueError(f"Invalid response transaction number {response_txn_number}")

        if not self._active_txn_numbers:
            self._logger.debug(
                f"No active transactions, response TXN={response_txn_number} is ANOMALOUS"
            )
            return ResponseClassification.ANOMALOUS

        # Response matches current attempt
        if response_txn_number == current_attempt_txn_number:
            self._logger.debug(
                f"Response TXN={response_txn_number} matches current attempt - ACTIVE"
            )
            return ResponseClassification.ACTIVE

        # Response from an earlier attempt in this transaction
        if response_txn_number in self._active_txn_numbers:
            self._logger.debug(
                f"Response TXN={response_txn_number} matches previous attempt - LATE"
            )
            return ResponseClassification.LATE

        # Response doesn't match any known transaction number
        self._logger.debug(
            f"Response TXN={response_txn_number} does not match any known TXN - ANOMALOUS"
        )
        return ResponseClassification.ANOMALOUS
