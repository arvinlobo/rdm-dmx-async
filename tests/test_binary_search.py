"""
Unit tests for BinarySearchNode (RDM discovery binary tree traversal).
"""

from rdm_dmx_async.services.binary_search import BinarySearchNode


class TestBinarySearchNode:
    def test_root_node_initial_state(self):
        root = BinarySearchNode(root=None, address_low=0, address_high=0xFFFFFFFFFFFF)

        assert root.depth == 0
        assert not root.is_complete
        assert root.branch_low is None
        assert root.branch_high is None

    def test_split_creates_two_halves(self):
        root = BinarySearchNode(root=None, address_low=0, address_high=9)

        assert root.split() is True
        assert root.branch_low.address_low == 0
        assert root.branch_low.address_high == 4
        assert root.branch_high.address_low == 5
        assert root.branch_high.address_high == 9
        assert root.branch_low.depth == 1
        assert root.branch_high.depth == 1

    def test_split_single_address_fails(self):
        node = BinarySearchNode(root=None, address_low=42, address_high=42)

        assert node.split() is False
        assert node.branch_low is None
        assert node.branch_high is None

    def test_split_is_idempotent(self):
        root = BinarySearchNode(root=None, address_low=0, address_high=9)
        root.split()
        first_low, first_high = root.branch_low, root.branch_high

        assert root.split() is True
        assert root.branch_low is first_low
        assert root.branch_high is first_high

    def test_mark_complete(self):
        node = BinarySearchNode(root=None, address_low=0, address_high=1)

        assert not node.is_complete
        node.mark_complete()
        assert node.is_complete

    def test_get_next_root_walks_up_when_both_children_complete(self):
        root = BinarySearchNode(root=None, address_low=0, address_high=3)
        root.split()
        low, high = root.branch_low, root.branch_high

        low.mark_complete()
        high.mark_complete()

        # Both children of root are complete, so walking up from either child
        # should mark root complete and return None (root has no parent).
        assert low.get_next_root() is None
        assert root.is_complete

    def test_get_next_root_returns_incomplete_sibling_subtree(self):
        root = BinarySearchNode(root=None, address_low=0, address_high=7)
        root.split()
        low = root.branch_low
        low.split()

        # Mark the low branch's own children complete but leave `high` pending.
        low.branch_low.mark_complete()
        low.branch_high.mark_complete()

        next_node = low.branch_low.get_next_root()

        # low is now complete (both its children done) but root is not,
        # since `high` is still pending - get_next_root stops at root.
        assert low.is_complete
        assert not root.is_complete
        assert next_node is root
