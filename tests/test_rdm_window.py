"""
Unit tests for `RdmRequestWindow` (scheduling/rdm_window.py).
"""

import asyncio
import time

import pytest

from rdm_dmx_async.scheduling.dmx_scheduler import DmxFrameScheduler
from rdm_dmx_async.scheduling.rdm_window import RdmRequestWindow


class TestRdmRequestWindowAttachment:
    def test_has_scheduler_false_by_default(self):
        window = RdmRequestWindow()

        assert window.has_scheduler is False

    def test_attach_scheduler_sets_has_scheduler_true(self):
        window = RdmRequestWindow()
        scheduler = DmxFrameScheduler()

        window.attach_scheduler(scheduler)

        assert window.has_scheduler is True


@pytest.mark.asyncio
class TestExecuteInWindow:
    async def test_without_scheduler_just_runs_the_operation(self):
        window = RdmRequestWindow()

        async def op():
            return 42

        result = await window.execute_in_window(op, timeout_ms=50.0)

        assert result == 42

    async def test_resumes_scheduler_soon_after_operation_completes(self):
        scheduler = DmxFrameScheduler()
        window = RdmRequestWindow(scheduler)

        async def fast_op():
            await asyncio.sleep(0.01)
            return "done"

        start = time.monotonic()
        result = await window.execute_in_window(fast_op, timeout_ms=200.0)
        elapsed = time.monotonic() - start

        assert result == "done"
        # Must not block for the full 200ms window once the op is done.
        assert elapsed < 0.1

    async def test_stays_paused_beyond_old_hardcoded_10ms_window(self):
        """Regression test: execute_in_window used to hardcode the DMX pause
        to DEFAULT_WINDOW_MS (10ms) regardless of timeout_ms, so DMX would
        resume mid-operation for anything slower than 10ms. It must now stay
        paused for the operation's actual (bounded) duration."""
        scheduler = DmxFrameScheduler()
        window = RdmRequestWindow(scheduler)

        async def slow_op():
            await asyncio.sleep(0.03)  # longer than the old 10ms window
            assert not scheduler._rdm_pause_event.is_set()
            return "done"

        result = await window.execute_in_window(slow_op, timeout_ms=100.0)

        assert result == "done"

    async def test_raises_timeout_error_when_operation_is_too_slow(self):
        window = RdmRequestWindow()

        async def slow_op():
            await asyncio.sleep(1.0)

        with pytest.raises(TimeoutError):
            await window.execute_in_window(slow_op, timeout_ms=10.0)

    async def test_resumes_scheduler_after_timeout(self):
        scheduler = DmxFrameScheduler()
        window = RdmRequestWindow(scheduler)

        async def slow_op():
            await asyncio.sleep(1.0)

        with pytest.raises(TimeoutError):
            await window.execute_in_window(slow_op, timeout_ms=10.0)

        await asyncio.sleep(0.001)  # let the cancelled pause task's finally run
        assert scheduler._rdm_pause_event.is_set()

    async def test_serializes_concurrent_calls_via_window_lock(self):
        window = RdmRequestWindow()
        order: list[str] = []

        async def make_op(name, delay):
            async def op():
                order.append(f"{name}-start")
                await asyncio.sleep(delay)
                order.append(f"{name}-end")
                return name

            return op

        op_a = await make_op("a", 0.02)
        op_b = await make_op("b", 0.0)

        results = await asyncio.gather(
            window.execute_in_window(op_a, timeout_ms=100.0),
            window.execute_in_window(op_b, timeout_ms=100.0),
        )

        assert set(results) == {"a", "b"}
        # "b" must not start until "a" has fully finished (exclusive window).
        assert order == ["a-start", "a-end", "b-start", "b-end"]


@pytest.mark.asyncio
class TestRequestWindow:
    async def test_with_scheduler_pauses_and_resumes(self):
        scheduler = DmxFrameScheduler()
        window = RdmRequestWindow(scheduler)

        await window.request_window(10.0)

        assert scheduler._rdm_pause_event.is_set()

    async def test_without_scheduler_sleeps_for_the_duration(self):
        window = RdmRequestWindow()

        start = time.monotonic()
        await window.request_window(20.0)
        elapsed = time.monotonic() - start

        assert elapsed >= 0.015
