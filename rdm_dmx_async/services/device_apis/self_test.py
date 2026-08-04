"""Self-test PIDs - perform self-test and get test descriptions."""

import struct
from typing import TYPE_CHECKING

from ...domain.parameters import StandardPID

if TYPE_CHECKING:
    from ..rdm_device import RdmDevice


class SelfTestAPI:
    """API for self-test PIDs - PERFORM_SELFTEST and SELF_TEST_DESCRIPTION."""

    def __init__(self, device: "RdmDevice"):
        self._device = device

    async def perform(self, test_number: int = 0xFF) -> bool:
        """
        Perform device self-test.

        Args:
            test_number: Test number to perform (0xFF for default)

        Returns:
            True if successful
        """
        data = struct.pack("B", test_number)
        # Note: Self-test may take longer, but execute_set uses 2.0s timeout internally
        # If specific test needs longer timeout, this would need to be parameterized
        return await self._device.execute_set(
            pid=StandardPID.PERFORM_SELFTEST.value,
            data=data,
        )

    async def get_description(self, test_number: int) -> str | None:
        """
        Get description for a specific self-test.

        Args:
            test_number: Test number to query

        Returns:
            Test description string or None
        """
        data = struct.pack("B", test_number)
        response_data = await self._device.execute_get(
            pid=StandardPID.SELF_TEST_DESCRIPTION.value,
            data=data,
        )

        if response_data:
            # Response format: test_number (1 byte) + description (string)
            if len(response_data) > 1:
                description = response_data[1:].decode("utf-8", errors="ignore").strip("\x00")
                return description
        return None
