"""Unit tests for LateResponseClassifier."""

import pytest

from rdm_dmx_async.transaction.correlator import (
    LateResponseClassifier,
    ResponseClassification,
)


class TestRegisterTransactionNumbers:
    def test_empty_list_raises(self):
        classifier = LateResponseClassifier()
        with pytest.raises(ValueError):
            classifier.register_transaction_numbers([])

    @pytest.mark.parametrize("bad_txn", [0, -1, 256])
    def test_out_of_range_number_raises(self, bad_txn):
        classifier = LateResponseClassifier()
        with pytest.raises(ValueError):
            classifier.register_transaction_numbers([1, bad_txn])

    def test_valid_list_is_accepted(self):
        classifier = LateResponseClassifier()
        classifier.register_transaction_numbers([1, 2, 3])
        # No exception - and classify_response should now recognize these.
        assert (
            classifier.classify_response(2, current_attempt_txn_number=3)
            == ResponseClassification.LATE
        )


class TestClassifyResponse:
    def test_no_active_transactions_is_anomalous(self):
        classifier = LateResponseClassifier()
        assert classifier.classify_response(1, 1) == ResponseClassification.ANOMALOUS

    def test_matches_current_attempt_is_active(self):
        classifier = LateResponseClassifier()
        classifier.register_transaction_numbers([5])
        assert classifier.classify_response(5, current_attempt_txn_number=5) == (
            ResponseClassification.ACTIVE
        )

    def test_matches_previous_attempt_is_late(self):
        classifier = LateResponseClassifier()
        # Attempt 1 used txn=1, attempt 2 (current) uses txn=2.
        classifier.register_transaction_numbers([1, 2])
        assert classifier.classify_response(1, current_attempt_txn_number=2) == (
            ResponseClassification.LATE
        )

    def test_unknown_txn_is_anomalous(self):
        classifier = LateResponseClassifier()
        classifier.register_transaction_numbers([1, 2])
        assert classifier.classify_response(99, current_attempt_txn_number=2) == (
            ResponseClassification.ANOMALOUS
        )

    @pytest.mark.parametrize("bad_response_txn", [0, -5, 256])
    def test_invalid_response_txn_raises(self, bad_response_txn):
        classifier = LateResponseClassifier()
        classifier.register_transaction_numbers([1])
        with pytest.raises(ValueError):
            classifier.classify_response(bad_response_txn, current_attempt_txn_number=1)

    def test_re_registering_replaces_active_set(self):
        classifier = LateResponseClassifier()
        classifier.register_transaction_numbers([1, 2])
        classifier.register_transaction_numbers([3, 4])
        # 1 and 2 are no longer tracked at all -> anomalous, not late.
        assert classifier.classify_response(1, current_attempt_txn_number=4) == (
            ResponseClassification.ANOMALOUS
        )
