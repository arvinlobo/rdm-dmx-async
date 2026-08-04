"""Unit tests for AsyncTransaction / AsyncTransactionManager retry logic.

These tests directly answer "is the transaction layer working correctly?" by
exercising: success on first attempt, retry-until-success, timeout handling,
generic-exception handling, late-response detection/skipping, permanent
failure short-circuiting, retry exhaustion, delay-between-attempts, and
guaranteed transaction-number release under every outcome (success, failure,
and exception).
"""

import asyncio

import pytest

from rdm_dmx_async.packets.rdm import RDMResponse
from rdm_dmx_async.packets.types import PID, UID, CommandClass, NAKReason, ResponseType
from rdm_dmx_async.transaction.allocator import TransactionNumberAllocator
from rdm_dmx_async.transaction.async_transaction import AsyncTransaction
from rdm_dmx_async.transaction.policy import RetryPolicy
from rdm_dmx_async.transaction.transaction_manager import AsyncTransactionManager

DEVICE_UID = UID(0x454E00000001)


def _response(
    txn: int,
    response_type: ResponseType = ResponseType.ACK,
    data: bytes = b"\x2a",
) -> RDMResponse:
    return RDMResponse(
        source_uid=DEVICE_UID,
        destination_uid=UID(0),
        transaction_number=txn,
        response_type=response_type,
        message_count=0,
        sub_device=0,
        command_class=CommandClass.GET_COMMAND_RESPONSE,
        pid=PID(0x1000),
        data=data,
        checksum_valid=True,
    )


class _Sleep:
    """Behavior marker: sleep for `seconds`, letting asyncio.wait_for's own
    timeout cancel us - a realistic timeout rather than a raised exception."""

    def __init__(self, seconds: float):
        self.seconds = seconds


class ScriptedOperation:
    """A fake RDM operation driven by a scripted list of behaviors, one per
    call. Records every transaction number it was invoked with."""

    def __init__(self, behaviors):
        self.behaviors = list(behaviors)
        self.calls: list[int] = []

    async def __call__(self, txn_number: int):
        self.calls.append(txn_number)
        behavior = self.behaviors.pop(0)
        if isinstance(behavior, _Sleep):
            await asyncio.sleep(behavior.seconds)
            raise AssertionError("wait_for should have cancelled this before it completed")
        if isinstance(behavior, Exception):
            raise behavior
        if callable(behavior):
            return behavior(txn_number)
        return behavior


@pytest.mark.asyncio
class TestSuccessAndRetry:
    async def test_succeeds_on_first_attempt(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation([_response])
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=3, timeout=1.0),
            allocator=allocator,
        )

        result = await transaction.execute()

        assert result.success
        assert result.attempt_count == 1
        assert result.final_response.is_ack
        assert allocator.in_use_count == 0  # released after completion

    async def test_retries_after_timeout_then_succeeds(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation(
            [
                _Sleep(10.0),  # first attempt times out
                _response,  # second attempt succeeds
            ]
        )
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=3, timeout=0.05),
            allocator=allocator,
        )

        result = await transaction.execute()

        assert result.success
        assert result.attempt_count == 2
        assert result.attempts[0].timeout is True
        assert result.attempts[1].success is True
        assert result.had_timeout is True
        assert allocator.in_use_count == 0

    async def test_generic_exception_is_recorded_and_retried(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation(
            [
                RuntimeError("serial write failed"),
                _response,
            ]
        )
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=3, timeout=1.0),
            allocator=allocator,
        )

        result = await transaction.execute()

        assert result.success
        assert result.attempts[0].success is False
        assert result.attempts[0].error == "serial write failed"
        assert result.attempts[1].success is True

    async def test_exhausts_after_max_attempts_all_timeout(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation([_Sleep(10.0), _Sleep(10.0), _Sleep(10.0)])
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=3, timeout=0.05),
            allocator=allocator,
        )

        result = await transaction.execute()

        assert result.success is False
        assert result.permanent_failure is False
        assert result.error_message == "All retry attempts exhausted"
        assert result.attempt_count == 3
        assert result.had_timeout is True
        assert allocator.in_use_count == 0  # released even on total failure

    async def test_delay_between_attempts_is_honored(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation(
            [
                RuntimeError("fails once"),
                _response,
            ]
        )
        policy = RetryPolicy(max_attempts=3, timeout=1.0, delay_between_attempts=0.1)
        transaction = AsyncTransaction(operation=operation, policy=policy, allocator=allocator)

        loop = asyncio.get_event_loop()
        start = loop.time()
        result = await transaction.execute()
        elapsed = loop.time() - start

        assert result.success
        assert elapsed >= 0.1


@pytest.mark.asyncio
class TestPermanentFailure:
    async def test_permanent_failure_nak_short_circuits_retries(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation(
            [
                lambda txn: _response(
                    txn,
                    response_type=ResponseType.NAK,
                    data=bytes([NAKReason.UNKNOWN_PID]),
                ),
                _response,  # should never be reached
            ]
        )
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=3, timeout=1.0),
            allocator=allocator,
        )

        result = await transaction.execute()

        assert result.success is False
        assert result.permanent_failure is True
        assert "UNKNOWN_PID" in result.error_message
        assert result.attempt_count == 1  # stopped immediately, no 2nd call
        assert len(operation.calls) == 1
        assert allocator.in_use_count == 0

    async def test_non_permanent_nak_retries_then_exhausts(self):
        allocator = TransactionNumberAllocator()
        # BUFFER_FULL is not in the default permanent_failures set... actually
        # it is by default; use a reason that's excluded from permanent set.
        policy = RetryPolicy(
            max_attempts=2,
            timeout=1.0,
            permanent_failures=set(),  # nothing is permanent for this test
        )
        operation = ScriptedOperation(
            [
                lambda txn: _response(
                    txn, response_type=ResponseType.NAK, data=bytes([NAKReason.DATA_OUT_OF_RANGE])
                ),
                lambda txn: _response(
                    txn, response_type=ResponseType.NAK, data=bytes([NAKReason.DATA_OUT_OF_RANGE])
                ),
            ]
        )
        transaction = AsyncTransaction(operation=operation, policy=policy, allocator=allocator)

        result = await transaction.execute()

        assert result.success is False
        assert result.permanent_failure is False
        assert result.attempt_count == 2
        assert result.had_nak is True
        assert NAKReason.DATA_OUT_OF_RANGE in result.nak_reasons


@pytest.mark.asyncio
class TestLateResponseHandling:
    async def test_late_response_is_skipped_and_still_consumes_an_attempt_slot(self):
        """A response bearing an earlier attempt's transaction number must be
        classified LATE and skipped (not treated as success/failure), but per
        the actual loop implementation (a `continue` inside a bounded `for`),
        it still consumes one of the `max_attempts` loop iterations - this
        pins down that real (if subtly surprising) behavior."""
        allocator = TransactionNumberAllocator()

        operation = ScriptedOperation(
            [
                _Sleep(10.0),  # attempt 1 (txn=1) times out
                lambda txn: _response(txn=1, response_type=ResponseType.ACK),  # late for txn=1
                _response,  # attempt 3 (txn=3) succeeds normally
            ]
        )
        policy = RetryPolicy(max_attempts=3, timeout=0.05)
        transaction = AsyncTransaction(operation=operation, policy=policy, allocator=allocator)

        result = await transaction.execute()

        assert result.success is True
        assert len(operation.calls) == 3  # all three scripted calls were made
        # The late response's attempt is still recorded (with is_late_response=True).
        late_attempts = [a for a in transaction.attempts if a.is_late_response]
        assert len(late_attempts) == 1
        assert allocator.in_use_count == 0


@pytest.mark.asyncio
class TestAsyncTransactionManager:
    class _FakeProtocol:
        def __init__(self):
            self.allocator = TransactionNumberAllocator()
            self.get_calls: list[dict] = []
            self.set_calls: list[dict] = []
            self.next_response_type = ResponseType.ACK
            self.next_data = b"\x2a"

        async def send_get_command(
            self, *, destination_uid, pid, transaction_number, data, timeout
        ):
            self.get_calls.append(
                {
                    "destination_uid": destination_uid,
                    "pid": pid,
                    "transaction_number": transaction_number,
                    "data": data,
                    "timeout": timeout,
                }
            )
            return _response(
                transaction_number, response_type=self.next_response_type, data=self.next_data
            )

        async def send_set_command(
            self, *, destination_uid, pid, transaction_number, data, timeout
        ):
            self.set_calls.append(
                {
                    "destination_uid": destination_uid,
                    "pid": pid,
                    "transaction_number": transaction_number,
                    "data": data,
                    "timeout": timeout,
                }
            )
            return _response(
                transaction_number, response_type=self.next_response_type, data=self.next_data
            )

    async def test_get_wraps_send_get_command_and_returns_result(self):
        protocol = self._FakeProtocol()
        manager = AsyncTransactionManager(protocol)

        result = await manager.get(DEVICE_UID, PID(0x1000))

        assert result.success
        assert len(protocol.get_calls) == 1
        assert protocol.get_calls[0]["destination_uid"] == DEVICE_UID
        assert protocol.get_calls[0]["pid"] == PID(0x1000)

    async def test_set_wraps_send_set_command_and_returns_result(self):
        protocol = self._FakeProtocol()
        manager = AsyncTransactionManager(protocol)

        result = await manager.set(DEVICE_UID, PID(0x1000), data=b"\x01")

        assert result.success
        assert len(protocol.set_calls) == 1
        assert protocol.set_calls[0]["data"] == b"\x01"

    async def test_manager_shares_protocols_allocator(self):
        protocol = self._FakeProtocol()
        manager = AsyncTransactionManager(protocol)

        await manager.get(DEVICE_UID, PID(0x1000))

        # The manager must reuse protocol.allocator (not create its own),
        # and release the number back when the transaction completes.
        assert manager._allocator is protocol.allocator
        assert protocol.allocator.in_use_count == 0


@pytest.mark.asyncio
class TestResultAndAttemptProperties:
    async def test_successful_attempt_property_finds_first_success(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation(
            [
                RuntimeError("fails"),
                _response,
            ]
        )
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=3, timeout=1.0),
            allocator=allocator,
        )
        result = await transaction.execute()

        assert result.successful_attempt is not None
        assert result.successful_attempt.attempt_number == 2
        assert result.attempts[0].is_ack is False
        assert result.attempts[1].is_ack is True

    async def test_is_nak_true_even_when_success_field_is_false(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation(
            [
                lambda txn: _response(
                    txn, response_type=ResponseType.NAK, data=bytes([NAKReason.HARDWARE_FAULT])
                ),
            ]
        )
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=1, timeout=1.0),
            allocator=allocator,
        )
        result = await transaction.execute()

        assert result.attempts[0].success is False
        assert result.attempts[0].is_nak is True  # is_nak checks response_type, not success


def _ack_timer_response(txn: int, delay_units: int = 0) -> RDMResponse:
    """ACK_TIMER response whose data encodes the estimated delay in 100ms units."""
    return _response(
        txn, response_type=ResponseType.ACK_TIMER, data=delay_units.to_bytes(2, byteorder="big")
    )


@pytest.mark.asyncio
class TestAckTimerHandling:
    """ACK_TIMER responses must trigger a GET QUEUED_MESSAGE follow-up per
    ANSI E1.20, not be treated as a plain retry-worthy failure."""

    async def test_ack_timer_then_ack_from_queued_message_succeeds(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation([lambda txn: _ack_timer_response(txn, delay_units=1)])
        queued_message = ScriptedOperation([_response])
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=3, timeout=1.0),
            allocator=allocator,
            queued_message_operation=queued_message,
        )

        loop = asyncio.get_event_loop()
        start = loop.time()
        result = await transaction.execute()
        elapsed = loop.time() - start

        assert result.success is True
        assert result.attempt_count == 1  # the ACK_TIMER/poll cycle counts as one attempt
        assert len(operation.calls) == 1
        assert len(queued_message.calls) == 1
        assert elapsed >= 0.1  # waited the 1*100ms delay indicated by the ACK_TIMER
        assert allocator.in_use_count == 0

    async def test_ack_timer_then_nak_from_queued_message_is_recorded_as_nak(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation([_ack_timer_response])
        queued_message = ScriptedOperation(
            [
                lambda txn: _response(
                    txn, response_type=ResponseType.NAK, data=bytes([NAKReason.DATA_OUT_OF_RANGE])
                )
            ]
        )
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=1, timeout=1.0, permanent_failures=set()),
            allocator=allocator,
            queued_message_operation=queued_message,
        )

        result = await transaction.execute()

        assert result.success is False
        assert result.attempts[0].is_nak is True
        assert result.attempts[0].nak_reason == NAKReason.DATA_OUT_OF_RANGE
        assert len(queued_message.calls) == 1

    async def test_ack_timer_can_repeat_before_resolving(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation([_ack_timer_response])
        queued_message = ScriptedOperation(
            [
                _ack_timer_response,  # still not ready
                _response,  # now ready
            ]
        )
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=1, timeout=1.0, max_ack_timer_polls=3),
            allocator=allocator,
            queued_message_operation=queued_message,
        )

        result = await transaction.execute()

        assert result.success is True
        assert len(queued_message.calls) == 2
        assert allocator.in_use_count == 0

    async def test_ack_timer_poll_budget_exhausted_falls_through_to_outer_retry(self):
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation(
            [
                _ack_timer_response,  # attempt 1: never resolves
                _response,  # attempt 2: succeeds normally
            ]
        )
        # queued_message always says "still not ready" - poll budget will exhaust
        queued_message = ScriptedOperation([_ack_timer_response, _ack_timer_response])
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=2, timeout=1.0, max_ack_timer_polls=2),
            allocator=allocator,
            queued_message_operation=queued_message,
        )

        result = await transaction.execute()

        assert result.success is True
        assert result.attempt_count == 2
        assert len(queued_message.calls) == 2  # exactly the poll budget, no more
        assert allocator.in_use_count == 0

    async def test_ack_timer_without_queued_message_operation_falls_back_to_generic_retry(self):
        """When no queued_message_operation is supplied (e.g. discovery-style
        transactions), an ACK_TIMER must not crash and must fall back to a
        plain retry of the original operation instead of hanging."""
        allocator = TransactionNumberAllocator()
        operation = ScriptedOperation(
            [
                _ack_timer_response,
                _response,
            ]
        )
        transaction = AsyncTransaction(
            operation=operation,
            policy=RetryPolicy(max_attempts=2, timeout=1.0),
            allocator=allocator,
        )

        result = await transaction.execute()

        assert result.success is True
        assert len(operation.calls) == 2
        assert allocator.in_use_count == 0

    async def test_manager_get_wires_queued_message_operation_to_send_get_command(self):
        protocol = TestAsyncTransactionManager._FakeProtocol()
        protocol.next_response_type = ResponseType.ACK_TIMER
        protocol.next_data = (1).to_bytes(2, byteorder="big")
        manager = AsyncTransactionManager(protocol)

        # After the first ACK_TIMER, flip subsequent responses (the
        # QUEUED_MESSAGE poll) to ACK so the transaction can succeed.
        original_send_get_command = protocol.send_get_command
        call_count = 0

        async def send_get_command(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                protocol.next_response_type = ResponseType.ACK
            return await original_send_get_command(**kwargs)

        protocol.send_get_command = send_get_command

        result = await manager.get(DEVICE_UID, PID(0x1000))

        assert result.success is True
        assert protocol.get_calls[-1]["pid"] == PID(0x0020)  # QUEUED_MESSAGE follow-up
