"""
Unit tests for `DmxFrameScheduler` (scheduling/dmx_scheduler.py).
"""

import asyncio

import pytest

from rdm_dmx_async.scheduling.dmx_scheduler import DmxFrameScheduler


class TestDmxFrameSchedulerData:
    """Synchronous tests for the DMX universe buffer, no event loop needed."""

    def test_set_and_get_dmx_data_round_trip(self):
        scheduler = DmxFrameScheduler()
        scheduler.set_dmx_data(1, bytes([10, 20, 30]))

        assert scheduler.get_dmx_data(1, 3) == bytes([10, 20, 30])

    def test_set_dmx_data_truncates_beyond_slot_512(self):
        scheduler = DmxFrameScheduler()
        scheduler.set_dmx_data(510, bytes([1, 2, 3, 4, 5]))

        assert scheduler.get_dmx_data(510, 3) == bytes([1, 2, 3])
        assert scheduler.get_dmx_data(1, 512)[509:512] == bytes([1, 2, 3])

    @pytest.mark.parametrize("start_address", [0, 513, -1])
    def test_set_dmx_data_invalid_address_raises(self, start_address):
        scheduler = DmxFrameScheduler()

        with pytest.raises(ValueError):
            scheduler.set_dmx_data(start_address, b"\x01")

    @pytest.mark.parametrize("start_address", [0, 513, -1])
    def test_get_dmx_data_invalid_address_raises(self, start_address):
        scheduler = DmxFrameScheduler()

        with pytest.raises(ValueError):
            scheduler.get_dmx_data(start_address, 1)


@pytest.mark.asyncio
class TestDmxFrameSchedulerLoop:
    """Async tests exercising the background scheduling loop."""

    async def test_start_invokes_send_callback_periodically(self):
        sent_frames: list[bytes] = []

        async def send_callback(frame):
            sent_frames.append(frame)

        scheduler = DmxFrameScheduler(frame_interval_ms=5.0, send_callback=send_callback)
        await scheduler.start()
        try:
            await asyncio.sleep(0.08)
        finally:
            await scheduler.stop()

        assert len(sent_frames) >= 3
        assert all(len(frame) == 512 for frame in sent_frames)

    async def test_frame_callback_supplies_frame_data(self):
        sent_frames: list[bytes] = []

        def frame_callback():
            return b"\xab" * 512

        async def send_callback(frame):
            sent_frames.append(frame)

        scheduler = DmxFrameScheduler(
            frame_callback=frame_callback, frame_interval_ms=5.0, send_callback=send_callback
        )
        await scheduler.start()
        await asyncio.sleep(0.03)
        await scheduler.stop()

        assert sent_frames
        assert all(frame == b"\xab" * 512 for frame in sent_frames)

    async def test_start_is_idempotent(self):
        scheduler = DmxFrameScheduler(frame_interval_ms=5.0)
        await scheduler.start()
        first_task = scheduler._task

        await scheduler.start()

        assert scheduler._task is first_task
        await scheduler.stop()

    async def test_stop_halts_the_loop(self):
        scheduler = DmxFrameScheduler(frame_interval_ms=5.0)
        await scheduler.start()
        await asyncio.sleep(0.03)

        await scheduler.stop()
        count_after_stop = scheduler.frame_count
        await asyncio.sleep(0.03)

        assert scheduler.frame_count == count_after_stop

    async def test_stop_without_start_is_a_noop(self):
        scheduler = DmxFrameScheduler()

        await scheduler.stop()  # must not raise

    async def test_send_callback_error_does_not_kill_the_loop(self):
        call_count = 0

        async def flaky_send(_frame):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("boom")

        scheduler = DmxFrameScheduler(frame_interval_ms=5.0, send_callback=flaky_send)
        await scheduler.start()
        await asyncio.sleep(0.05)
        await scheduler.stop()

        assert call_count >= 3  # kept running past the first callback error

    async def test_pause_for_rdm_suspends_frame_sends_during_window(self):
        sent_frames: list[bytes] = []

        async def send_callback(frame):
            sent_frames.append(frame)

        scheduler = DmxFrameScheduler(frame_interval_ms=5.0, send_callback=send_callback)
        await scheduler.start()
        await asyncio.sleep(0.02)  # let a few frames go out first

        pause_task = asyncio.create_task(scheduler.pause_for_rdm(30.0))
        await asyncio.sleep(0.005)  # give the pause a moment to take effect
        assert not scheduler._rdm_pause_event.is_set()

        count_during_pause = len(sent_frames)
        await asyncio.sleep(0.015)
        assert len(sent_frames) == count_during_pause  # no frames while paused

        await pause_task
        assert scheduler._rdm_pause_event.is_set()
        await scheduler.stop()

    async def test_pause_for_rdm_resumes_event_even_when_cancelled(self):
        """Regression test: cancelling pause_for_rdm mid-sleep must not
        permanently freeze DMX output (the event must still get set)."""
        scheduler = DmxFrameScheduler()

        pause_task = asyncio.create_task(scheduler.pause_for_rdm(100.0))
        await asyncio.sleep(0.005)
        assert not scheduler._rdm_pause_event.is_set()

        pause_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pause_task

        assert scheduler._rdm_pause_event.is_set()

    async def test_frame_count_starts_at_zero(self):
        scheduler = DmxFrameScheduler()

        assert scheduler.frame_count == 0
