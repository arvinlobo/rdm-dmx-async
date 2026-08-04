"""Unit tests for RetryPolicy validation and predefined policies."""

import pytest

from rdm_dmx_async.packets.types import NAKReason
from rdm_dmx_async.transaction.policy import (
    AGGRESSIVE_RETRY_POLICY,
    DISCOVERY_POLICY,
    NO_RETRY_POLICY,
    STANDARD_POLICY,
    RetryPolicy,
)


class TestValidation:
    def test_defaults_are_valid(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.timeout == 3.0
        assert policy.delay_between_attempts == 0.0

    @pytest.mark.parametrize("max_attempts", [0, -1])
    def test_max_attempts_below_one_raises(self, max_attempts):
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=max_attempts)

    @pytest.mark.parametrize("timeout", [0, -1.0])
    def test_non_positive_timeout_raises(self, timeout):
        with pytest.raises(ValueError):
            RetryPolicy(timeout=timeout)

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError):
            RetryPolicy(delay_between_attempts=-0.1)

    def test_zero_delay_is_allowed(self):
        RetryPolicy(delay_between_attempts=0.0)  # should not raise

    @pytest.mark.parametrize("max_ack_timer_polls", [0, -1])
    def test_max_ack_timer_polls_below_one_raises(self, max_ack_timer_polls):
        with pytest.raises(ValueError):
            RetryPolicy(max_ack_timer_polls=max_ack_timer_polls)

    def test_max_ack_timer_polls_defaults_to_three(self):
        assert RetryPolicy().max_ack_timer_polls == 3


class TestIsPermanentFailure:
    def test_unknown_pid_is_permanent_by_default(self):
        """Regression guard: NAKReason.UNKNOWN_PID == 0, which is falsy in
        Python - is_permanent_failure() must use containment, not truthiness,
        or this (the most common NAK reason) would be silently excluded."""
        policy = RetryPolicy()
        assert policy.is_permanent_failure(NAKReason.UNKNOWN_PID) is True

    def test_non_configured_reason_is_not_permanent(self):
        policy = RetryPolicy(permanent_failures=set())
        assert policy.is_permanent_failure(NAKReason.UNKNOWN_PID) is False

    def test_custom_permanent_failures_set_is_respected(self):
        policy = RetryPolicy(permanent_failures={NAKReason.BUFFER_FULL})
        assert policy.is_permanent_failure(NAKReason.BUFFER_FULL) is True
        assert policy.is_permanent_failure(NAKReason.UNKNOWN_PID) is False


class TestPredefinedPolicies:
    def test_standard_policy_defaults(self):
        assert STANDARD_POLICY.max_attempts == 3

    def test_no_retry_policy_has_single_attempt(self):
        assert NO_RETRY_POLICY.max_attempts == 1

    def test_aggressive_retry_policy_has_more_attempts_and_timeout(self):
        assert AGGRESSIVE_RETRY_POLICY.max_attempts == 5
        assert AGGRESSIVE_RETRY_POLICY.timeout == 5.0

    def test_discovery_policy_has_single_attempt(self):
        assert DISCOVERY_POLICY.max_attempts == 1
        assert DISCOVERY_POLICY.timeout == 2.0
