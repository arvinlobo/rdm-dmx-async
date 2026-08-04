"""
Unit tests for `FrameBuffer` (transport/frame_buffer.py), especially the
"middle bytes arrive later" and stalled-garbage-byte corner cases.

Uses a minimal fake adapter (not a real hardware adapter) with a simple
STX/LEN/payload/ETX framing scheme, so these tests exercise FrameBuffer's own
buffering/stall-detection logic in isolation from any specific hardware
framing format.
"""

from rdm_dmx_async.transport.frame_buffer import FrameBuffer


class _FakeAdapter:
    """Minimal framing: STX(1) + LEN(1) + payload(LEN) + ETX(1)."""

    STX = 0x7E
    ETX = 0xE7

    def find_frame_length(self, buffer: bytes) -> int:
        if len(buffer) < 5 or buffer[0] != self.STX:
            return 0
        payload_len = buffer[1]
        total_len = 3 + payload_len
        if len(buffer) < total_len or buffer[total_len - 1] != self.ETX:
            return 0
        return total_len

    def parse_rdm_response(self, raw_data: bytes) -> bytes | None:
        frame_len = self.find_frame_length(raw_data)
        if frame_len == 0:
            return None
        payload_len = raw_data[1]
        payload = raw_data[2 : 2 + payload_len]
        if payload == b"UNHANDLED":
            return None  # simulates a recognized-but-unparseable message type
        return bytes(payload)


def _frame(payload: bytes) -> bytes:
    return bytes([_FakeAdapter.STX, len(payload)]) + payload + bytes([_FakeAdapter.ETX])


class TestExtractFrameHappyPath:
    def test_complete_frame_in_one_append(self):
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(_frame(b"hello"))

        assert buffer.extract_frame() == b"hello"
        assert len(buffer) == 0

    def test_too_small_buffer_returns_none_without_consuming(self):
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(bytes([_FakeAdapter.STX, 2]))  # only 2 bytes total

        assert buffer.extract_frame() is None
        assert len(buffer) == 2  # nothing discarded

    def test_extract_all_frames_returns_multiple_frames(self):
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(_frame(b"one") + _frame(b"two") + _frame(b"three"))

        frames = buffer.extract_all_frames()

        assert frames == [b"one", b"two", b"three"]
        assert len(buffer) == 0


class TestPartialFrameArrivesOverTime:
    """Covers "what if the middle byte(s) arrive some time later?"."""

    def test_frame_split_across_two_appends_is_not_corrupted(self):
        buffer = FrameBuffer(_FakeAdapter())
        full_frame = _frame(b"0123456789")  # 13 bytes total, >= 5 byte minimum

        first_chunk, second_chunk = full_frame[:6], full_frame[6:]

        buffer.append(first_chunk)
        # Not enough bytes yet for the declared payload length - must wait,
        # not discard byte 0 (which is a legitimate frame start marker).
        assert buffer.extract_frame() is None
        assert len(buffer) == len(first_chunk)

        # The rest of the frame arrives on a later read.
        buffer.append(second_chunk)
        assert buffer.extract_frame() == b"0123456789"
        assert len(buffer) == 0

    def test_frame_split_across_many_single_byte_appends(self):
        buffer = FrameBuffer(_FakeAdapter())
        full_frame = _frame(b"XY")

        # Deliver one byte at a time, as if each arrived after a delay.
        for i in range(len(full_frame) - 1):
            buffer.append(full_frame[i : i + 1])
            assert buffer.extract_frame() is None

        buffer.append(full_frame[-1:])
        assert buffer.extract_frame() == b"XY"


class TestGarbageByteDiscarding:
    def test_leading_garbage_discarded_once_stream_truly_stalls(self):
        """If the buffer stops growing between checks (no more bytes are
        coming), a leading byte that can't start a valid frame must be
        discarded so real frames aren't blocked forever."""
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(bytes([0x99, 0x99, 0x99, 0x99, 0x99]))  # 5 bytes of noise

        assert buffer.extract_frame() is None  # first check: just recorded, not discarded yet
        assert len(buffer) == 5

        # No new data arrives (stream stalled) - the next check on the same
        # unchanged buffer must discard the leading garbage byte.
        assert buffer.extract_frame() is None
        assert len(buffer) == 4

    def test_stalled_garbage_below_minimum_frame_size_still_fully_clears(self):
        """Stall tracking now runs even below the 5-byte frame-size floor,
        so a run of pure garbage eventually drains to an empty buffer
        instead of getting stuck a few bytes above zero."""
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(bytes([0x99] * 5))

        for _ in range(10):
            buffer.extract_frame()
            if len(buffer) == 0:
                break

        assert len(buffer) == 0

    def test_valid_frame_still_recovered_behind_stuck_garbage(self):
        """A real frame arriving after a run of pure noise must still be
        recognized and extracted once the noise fully clears."""
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(bytes([0x99] * 5))
        for _ in range(10):
            if buffer.extract_frame() is None and len(buffer) == 0:
                break
        assert len(buffer) == 0

        buffer.append(_frame(b"ok"))

        extracted = None
        for _ in range(10):
            result = buffer.extract_frame()
            if result is not None:
                extracted = result
                break

        assert extracted == b"ok"

    def test_valid_frame_recovered_after_garbage_prefix_stalls_out(self):
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(bytes([0x99, 0x99]) + _frame(b"ok"))

        # The complete frame is already fully present behind the garbage
        # prefix, so the resync scan finds and discards it immediately -
        # no need to wait for repeated stall checks.
        assert buffer.extract_frame() is None
        assert buffer.extract_frame() == b"ok"

    def test_growing_garbage_is_resynced_once_a_valid_frame_follows(self):
        """If valid traffic arrives right behind a leading garbage byte
        while the buffer is still growing, the stall heuristic alone would
        never fire (the buffer never stops growing) - the resync scan must
        catch this instead of waiting on the max_size overflow cap."""
        buffer = FrameBuffer(_FakeAdapter(), max_size=1024)
        buffer.append(bytes([0x99]))  # 1 garbage byte
        buffer.append(bytes([0x41] * 3))  # a few more unrelated bytes trickle in
        buffer.append(_frame(b"ok"))  # then a real, complete frame arrives

        extracted = None
        for _ in range(10):
            result = buffer.extract_frame()
            if result is not None:
                extracted = result
                break

        assert extracted == b"ok"
        assert len(buffer) < 1024  # recovered well before the overflow cap

    def test_continuously_growing_pure_noise_falls_back_to_overflow_cap(self):
        """When nothing recognizable ever appears (no valid frame ever
        resumes), recovery still correctly falls back to the max_size
        overflow backstop rather than growing unbounded."""
        buffer = FrameBuffer(_FakeAdapter(), max_size=20)
        buffer.append(bytes([0x99]))  # 1 garbage byte

        for _ in range(10):
            buffer.append(bytes([0x41]))  # more noise keeps trickling in
            buffer.extract_frame()

        assert len(buffer) <= 20


class TestUnhandledFrameStillConsumed:
    """A recognized frame whose parse comes back None (e.g. an unhandled
    message type) must still be removed from the buffer, not left stuck at
    the front blocking subsequent frames."""

    def test_unparseable_frame_is_consumed_and_returns_none(self):
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(_frame(b"UNHANDLED"))

        assert buffer.extract_frame() is None
        assert len(buffer) == 0  # consumed, not stuck waiting for more data

    def test_next_frame_still_extracted_after_unhandled_one(self):
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(_frame(b"UNHANDLED") + _frame(b"ok"))

        frames = buffer.extract_all_frames()

        assert frames == [b"ok"]  # the unhandled frame is silently dropped


class TestHandleOverflow:
    """Direct coverage of `_handle_overflow()`, which the stall-tracking
    path only exercises indirectly."""

    def test_no_discard_when_buffer_within_max_size(self):
        buffer = FrameBuffer(_FakeAdapter(), max_size=10)
        buffer.append(bytes(range(10)))

        buffer._handle_overflow()

        assert len(buffer) == 10  # exactly at the cap - not over it, no discard

    def test_discards_oldest_byte_when_over_max_size(self):
        buffer = FrameBuffer(_FakeAdapter(), max_size=10)
        buffer.append(bytes(range(11)))  # 1 byte over the cap

        buffer._handle_overflow()

        assert len(buffer) == 10
        assert bytes(buffer._buffer) == bytes(range(1, 11))  # byte 0 dropped, not the newest

    def test_only_pops_one_byte_per_call_even_when_far_over_cap(self):
        buffer = FrameBuffer(_FakeAdapter(), max_size=10)
        buffer.append(bytes(range(15)))  # 5 bytes over the cap

        buffer._handle_overflow()

        assert len(buffer) == 14  # only one byte discarded per call

    def test_repeated_calls_drain_down_to_max_size(self):
        buffer = FrameBuffer(_FakeAdapter(), max_size=10)
        buffer.append(bytes(range(15)))

        for _ in range(5):
            buffer._handle_overflow()

        assert len(buffer) == 10


class TestClearAndLen:
    def test_clear_empties_buffer_and_resets_stall_tracking(self):
        buffer = FrameBuffer(_FakeAdapter())
        buffer.append(bytes([0x99] * 5))
        buffer.extract_frame()  # records a stall length

        buffer.clear()

        assert len(buffer) == 0
        assert buffer._stalled_length is None

    def test_len_reflects_buffered_byte_count(self):
        buffer = FrameBuffer(_FakeAdapter())
        assert len(buffer) == 0

        buffer.append(b"\x01\x02\x03")
        assert len(buffer) == 3
