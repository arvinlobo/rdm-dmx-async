"""
Binary search helper for RDM discovery.

Implements the binary tree traversal used in DISC_UNIQUE_BRANCH discovery.
"""

import logging
from typing import Optional


class BinarySearchNode:
    """
    Node in binary search tree for RDM UID discovery.

    Each node represents a range of UIDs to search. When collision occurs,
    the node splits into two children covering lower and upper halves.
    """

    def __init__(
        self,
        root: Optional["BinarySearchNode"],
        address_low: int,
        address_high: int,
        depth: int = 0,
    ):
        """
        Initialize search node.

        Args:
            root: Parent node (None for root)
            address_low: Lower bound UID address (48-bit)
            address_high: Upper bound UID address (48-bit)
            depth: Tree depth (0 for root)
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._root = root
        self._branch_low: BinarySearchNode | None = None
        self._branch_high: BinarySearchNode | None = None
        self._address_low = address_low
        self._address_high = address_high
        self._complete = False
        self._depth = depth

    @property
    def address_low(self) -> int:
        """Lower bound of this node's UID range"""
        return self._address_low

    @property
    def address_high(self) -> int:
        """Upper bound of this node's UID range"""
        return self._address_high

    @property
    def is_complete(self) -> bool:
        """Whether this branch has been fully searched"""
        return self._complete

    @property
    def depth(self) -> int:
        """Depth in the search tree"""
        return self._depth

    @property
    def branch_low(self) -> Optional["BinarySearchNode"]:
        """Lower half child node"""
        return self._branch_low

    @property
    def branch_high(self) -> Optional["BinarySearchNode"]:
        """Upper half child node"""
        return self._branch_high

    def mark_complete(self) -> None:
        """Mark this branch as fully searched"""
        self._complete = True

    def get_next_root(self) -> Optional["BinarySearchNode"]:
        """
        Get next uncompleted root node.

        Walks up the tree marking completed branches and finding
        the next node with work remaining.

        Returns:
            Next node to search, or None if entire tree is complete
        """
        node = self._root
        while node is not None:
            branch_high = node.branch_high
            branch_low = node.branch_low

            if branch_low and branch_high:
                if branch_low.is_complete and branch_high.is_complete:
                    node.mark_complete()
                    node = node._root
                else:
                    break
            else:
                break

        return node

    def split(self) -> bool:
        """
        Split this node into two child branches.

        Divides the UID range into lower and upper halves.
        Used when DISC_UNIQUE_BRANCH detects collision.

        Returns:
            True if split successful, False if cannot split (single UID)
        """
        if self._address_low == self._address_high:
            return False  # Cannot split single address

        if self._branch_low is not None or self._branch_high is not None:
            # Already split
            return True

        # Calculate midpoint
        midpoint = ((self._address_high - self._address_low) >> 1) + self._address_low

        # Create child nodes
        self._branch_low = BinarySearchNode(
            root=self, address_low=self._address_low, address_high=midpoint, depth=self._depth + 1
        )
        self._branch_high = BinarySearchNode(
            root=self,
            address_low=midpoint + 1,
            address_high=self._address_high,
            depth=self._depth + 1,
        )

        return True

    def display(self, offset: str = "") -> None:
        """
        Display tree structure for debugging.

        Args:
            offset: Indentation string
        """
        status = "COMPLETE" if self._complete else "PENDING"
        self._logger.debug(
            f"{offset}[0x{self._address_low:012X} - 0x{self._address_high:012X}] {status} (depth={self._depth})"
        )

        if self._branch_low:
            self._branch_low.display(offset + "  ")
        if self._branch_high:
            self._branch_high.display(offset + "  ")
