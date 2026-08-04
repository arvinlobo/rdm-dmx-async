"""Unit tests for TransactionNumberAllocator."""

import pytest

from rdm_dmx_async.transaction.allocator import TransactionNumberAllocator


class TestInit:
    def test_default_starting_number_is_one(self):
        allocator = TransactionNumberAllocator()
        assert allocator.allocate() == 1

    @pytest.mark.parametrize("bad_start", [0, -1, 256, 1000])
    def test_invalid_starting_number_raises(self, bad_start):
        with pytest.raises(ValueError):
            TransactionNumberAllocator(starting_number=bad_start)

    @pytest.mark.parametrize("good_start", [1, 128, 255])
    def test_valid_starting_number_accepted(self, good_start):
        allocator = TransactionNumberAllocator(starting_number=good_start)
        assert allocator.allocate() == good_start


class TestAllocateAndRelease:
    def test_allocate_returns_sequential_numbers(self):
        allocator = TransactionNumberAllocator()
        assert allocator.allocate() == 1
        assert allocator.allocate() == 2
        assert allocator.allocate() == 3

    def test_allocate_marks_number_in_use(self):
        allocator = TransactionNumberAllocator()
        allocator.allocate()
        assert allocator.in_use_count == 1
        assert allocator.available_count == 254

    def test_release_frees_number_for_reuse(self):
        allocator = TransactionNumberAllocator()
        first = allocator.allocate()
        allocator.release(first)
        assert allocator.in_use_count == 0

    def test_release_invalid_range_raises(self):
        allocator = TransactionNumberAllocator()
        with pytest.raises(ValueError):
            allocator.release(0)
        with pytest.raises(ValueError):
            allocator.release(256)

    def test_release_number_not_in_use_raises(self):
        allocator = TransactionNumberAllocator()
        with pytest.raises(ValueError):
            allocator.release(5)  # never allocated

    def test_release_all_ignores_unknown_numbers_silently(self):
        allocator = TransactionNumberAllocator()
        allocated = allocator.allocate()
        # 999 was never allocated; release_all must not raise for it.
        allocator.release_all([allocated, 999])
        assert allocator.in_use_count == 0

    def test_release_all_empty_list_is_noop(self):
        allocator = TransactionNumberAllocator()
        allocator.allocate()
        allocator.release_all([])
        assert allocator.in_use_count == 1


class TestWraparoundAndExhaustion:
    def test_wraps_from_255_back_to_1_skipping_zero(self):
        allocator = TransactionNumberAllocator(starting_number=255)
        assert allocator.allocate() == 255
        assert allocator.allocate() == 1  # wraps, skips 0

    def test_skips_numbers_still_in_use_when_allocating(self):
        allocator = TransactionNumberAllocator()
        first = allocator.allocate()  # 1
        second = allocator.allocate()  # 2
        allocator.release(first)  # free up 1, but cursor has moved past it
        third = allocator.allocate()  # 3
        assert {first, second, third} == {1, 2, 3}
        # 1 was released, so it should be reused only after wrapping around.
        assert allocator.in_use_count == 2

    def test_exhaustion_raises_runtime_error(self):
        allocator = TransactionNumberAllocator()
        for _ in range(255):
            allocator.allocate()
        assert allocator.in_use_count == 255
        assert allocator.available_count == 0
        with pytest.raises(RuntimeError):
            allocator.allocate()

    def test_allocation_resumes_after_release_when_exhausted(self):
        allocator = TransactionNumberAllocator()
        allocated = [allocator.allocate() for _ in range(255)]
        allocator.release(allocated[0])
        # Now exactly one slot is free; allocate() must find it via wraparound.
        reused = allocator.allocate()
        assert reused == allocated[0]


class TestProperties:
    def test_in_use_and_available_counts_track_correctly(self):
        allocator = TransactionNumberAllocator()
        assert allocator.in_use_count == 0
        assert allocator.available_count == 255

        allocator.allocate()
        allocator.allocate()
        assert allocator.in_use_count == 2
        assert allocator.available_count == 253
