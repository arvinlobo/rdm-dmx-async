"""Network-wide device discovery service."""

import asyncio
import logging
import struct
from enum import IntEnum

from ..domain.parameters import BROADCAST_UID, StandardPID
from ..packets.types import UID
from ..protocols.base import RdmProtocol
from .binary_search import BinarySearchNode
from .device_repository import DeviceRepository
from .rdm_device import RdmDevice


class DiscoveryResult(IntEnum):
    """Discovery branch result codes"""

    NO_RESPONSE = 0  # No device responded
    ADDRESS_FOUND = 1  # Single device found and muted
    COLLISION = 2  # Multiple devices responded (checksum failed)


class DiscoveryService:
    """Network-wide device discovery service with full binary search."""

    # RDM UID address space bounds (48-bit)
    LOWER_BOUND_ADDRESS = 0x000000000000
    UPPER_BOUND_ADDRESS = 0xFFFFFFFFFFFF

    def __init__(self, protocol: RdmProtocol, repository: DeviceRepository):
        self._protocol = protocol
        self._repository = repository
        self._logger = logging.getLogger(self.__class__.__name__)
        self._discovered_uids: list[UID] = []

    async def unmute_all(self) -> None:
        """
        Send DISC_UN_MUTE broadcast to all devices.
        Prepares devices for normal RDM communication.
        """
        self._logger.info("Broadcasting DISC_UN_MUTE to all devices")

        try:
            await self._protocol.send_discovery_command(
                destination_uid=BROADCAST_UID,
                pid=StandardPID.to_pid(StandardPID.DISC_UN_MUTE),
                transaction_number=self._protocol.allocator.allocate(),
                data=b"",
                timeout=0.5,
            )
        except Exception:
            # Broadcast - timeout is expected
            pass

        await asyncio.sleep(0.2)

    async def mute_device(self, uid: UID) -> bool:
        """
        Send DISC_MUTE to a specific device.

        Args:
            uid: Device UID to mute

        Returns:
            True if device acknowledged mute
        """
        self._logger.debug(f"Muting device {uid:012X}")

        try:
            response = await self._protocol.send_discovery_command(
                destination_uid=uid,
                pid=StandardPID.to_pid(StandardPID.DISC_MUTE),
                transaction_number=self._protocol.allocator.allocate(),
                data=b"",
                timeout=0.5,
            )
            return response is not None
        except Exception as e:
            self._logger.debug(f"Failed to mute {uid:012X}: {e}")
            return False

    async def discover_known_devices(self, uids: list[UID]) -> list[RdmDevice]:
        """
        Query known device UIDs and add responsive devices to repository.

        Args:
            uids: List of UIDs to check

        Returns:
            List of responsive devices
        """
        self._logger.info(f"Discovering {len(uids)} known device(s)")

        devices = []

        for uid in uids:
            self._logger.info(f"Querying device {uid:012X}...")

            try:
                # Try DEVICE_INFO query to check presence
                response = await self._protocol.send_get_command(
                    destination_uid=uid,
                    pid=StandardPID.to_pid(StandardPID.DEVICE_INFO),
                    transaction_number=self._protocol.allocator.allocate(),
                    timeout=1.5,
                )

                if response:
                    self._logger.info(f"  Device {uid:012X} is present")

                    # Add to repository and initialize
                    device = self._repository.add_device(uid)
                    await device.initialize()
                    devices.append(device)
                else:
                    self._logger.debug(f"  Device {uid:012X} did not respond")

            except Exception as e:
                self._logger.debug(f"  ✗ Device {uid:012X} error: {e}")

        self._logger.info(f"Found {len(devices)} responsive device(s)")
        return devices

    @staticmethod
    def uid_to_address(uid: UID) -> int:
        """Convert 6-byte UID to 48-bit integer address"""
        return int(uid)

    @staticmethod
    def address_to_uid(address: int) -> bytes:
        """Convert 48-bit integer address to 6-byte UID bytes"""
        return struct.pack(">Q", address)[2:]  # Skip first 2 bytes (keep lower 6)

    async def discover_unique_branch(self, address_low: int, address_high: int) -> DiscoveryResult:
        """
        Execute DISC_UNIQUE_BRANCH on a UID range.

        Args:
            address_low: Lower bound of UID range (48-bit)
            address_high: Upper bound of UID range (48-bit)

        Returns:
            Discovery result (NO_RESPONSE, ADDRESS_FOUND, or COLLISION)
        """
        self._logger.info(f"DUB 0x{address_low:012X} - 0x{address_high:012X}")

        # Convert addresses to UID bytes
        uid_low = self.address_to_uid(address_low)
        uid_high = self.address_to_uid(address_high)

        # Build DISC_UNIQUE_BRANCH data (12 bytes: lower + upper bounds)
        data = uid_low + uid_high

        try:
            # Send discovery request - bypasses transaction layer for Manchester decoding
            response = await self._protocol.send_discovery_command(
                destination_uid=BROADCAST_UID,
                pid=StandardPID.to_pid(StandardPID.DISC_UNIQUE_BRANCH),
                transaction_number=self._protocol.allocator.allocate(),
                data=data,
                timeout=0.5,
            )

            if response and response.source_uid:
                # Valid UID decoded from Manchester response
                discovered_uid = response.source_uid  # Already a UID (int)
                self._logger.info(f"  → Device found: {discovered_uid:012X}")

                # Mute the device to confirm (retry up to 5 times)
                MAX_MUTE_RETRIES = 5
                for _attempt in range(MAX_MUTE_RETRIES):
                    if await self.mute_device(response.source_uid):
                        self._logger.info(f"  Device {discovered_uid:012X} muted successfully")
                        if response.source_uid not in self._discovered_uids:
                            self._discovered_uids.append(response.source_uid)
                        return DiscoveryResult.ADDRESS_FOUND

                # Mute failed - treat as collision
                self._logger.warning(
                    f"  Failed to mute {discovered_uid:012X}, treating as collision"
                )
                return DiscoveryResult.COLLISION

            elif response:
                # Got response but couldn't decode UID - shouldn't happen with new code
                self._logger.info("  → Unexpected response format")
                return DiscoveryResult.COLLISION
            else:
                # response is None only on a genuine collision (data was
                # received but Manchester decode failed). A true "nothing
                # responded" timeout raises instead and is handled below,
                # so it's safe to always split here.
                self._logger.info("  → Collision detected")
                return DiscoveryResult.COLLISION

        except Exception as e:
            self._logger.debug(f"  → Error during DUB: {e}")
            return DiscoveryResult.NO_RESPONSE

    async def full_discovery(
        self, only_new: bool = False, skip_uids: list[UID] | None = None, max_devices: int = -1
    ) -> list[RdmDevice]:
        """
        Perform full network discovery using DISC_UNIQUE_BRANCH binary search.

        Args:
            only_new: If True, mute previously discovered devices before searching
            skip_uids: List of UIDs to mute before searching
            max_devices: Maximum devices to find (-1 for unlimited)

        Returns:
            List of discovered RdmDevice instances
        """
        self._logger.info("=" * 60)
        self._logger.info("Starting full RDM network discovery")
        self._logger.info("=" * 60)

        skip_uids = skip_uids or []

        # Unmute all devices
        await self.unmute_all()

        # Mute previously discovered devices if only_new mode
        if only_new:
            self._logger.info("Muting previously discovered devices...")
            for uid in self._discovered_uids:
                await self.mute_device(uid)
        else:
            # Clear discovery list
            self._discovered_uids.clear()

        # Mute skipped devices
        for uid in skip_uids:
            self._logger.info(f"Skipping UID: {uid:012X}")
            await self.mute_device(uid)

        if max_devices > 0:
            self._logger.info(f"Search limit: {max_devices} devices")

        # Initialize binary search tree
        root = BinarySearchNode(None, self.LOWER_BOUND_ADDRESS, self.UPPER_BOUND_ADDRESS, depth=0)
        current_node: BinarySearchNode | None = root
        saved_node: BinarySearchNode | None = None
        remaining_searches = max_devices

        MAX_RETRIES = 3

        while current_node:
            address_low = current_node.address_low
            address_high = current_node.address_high

            # Retry branch up to MAX_RETRIES times
            result = None
            for attempt in range(MAX_RETRIES):
                result = await self.discover_unique_branch(address_low, address_high)

                if result == DiscoveryResult.ADDRESS_FOUND:
                    # Device found - save current node and restart from root
                    if saved_node is None:
                        saved_node = current_node
                        current_node = root
                    break

                elif result == DiscoveryResult.COLLISION:
                    # Collision - split branch
                    if saved_node is None:
                        current_node.split()
                    else:
                        # Restore saved node and continue
                        current_node = saved_node
                        saved_node = None
                    break

                # NO_RESPONSE - retry
                if attempt < MAX_RETRIES - 1:
                    self._logger.debug(f"  Retry {attempt + 1}/{MAX_RETRIES - 1}")

            # After retries, if still no response, mark complete
            if result == DiscoveryResult.NO_RESPONSE:
                current_node.mark_complete()
                current_node = current_node.get_next_root()

            # Check device limit
            if max_devices > 0:
                remaining_searches -= 1
                if remaining_searches <= 0:
                    self._logger.info("Search limit reached")
                    break

            # Get next node to search (if not address found - which already moved to root)
            if result != DiscoveryResult.ADDRESS_FOUND:
                branch_low = current_node.branch_low if current_node else None
                branch_high = current_node.branch_high if current_node else None

                if branch_low and not branch_low.is_complete:
                    current_node = branch_low
                elif branch_high and not branch_high.is_complete:
                    current_node = branch_high
                elif current_node:
                    current_node = current_node.get_next_root()
                else:
                    break

        # Discovery complete - create RdmDevice objects
        self._logger.info("=" * 60)
        self._logger.info(f"Discovery complete: {len(self._discovered_uids)} device(s) found")
        self._logger.info("=" * 60)

        devices = []
        for uid in self._discovered_uids:
            self._logger.info(f"Initializing device {uid:012X}...")
            device = self._repository.add_device(uid)
            await device.initialize()
            devices.append(device)

        return devices
