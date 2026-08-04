"""
Network Manager for orchestrating RDM operations across multiple devices.

Provides high-level network management including device discovery, batch operations,
and device lifecycle management.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from ..packets.types import UID
from ..protocols.base import RdmProtocol
from ..protocols.rdm_e120 import RDME120Protocol
from ..scheduling.dmx_scheduler import DmxFrameScheduler
from ..services import DeviceRepository, DiscoveryService, RdmDevice
from ..transaction.allocator import TransactionNumberAllocator
from ..transport.adapters import DMXKingAdapter, EnttecAdapter
from ..transport.base import AsyncTransport
from ..transport.interface_adapter import InterfaceAdapter, InterfaceType
from ..transport.serial_transport import AsyncSerialTransport
from ..utils import get_enttec_serial_uid
from .batch_operation_service import BatchOperationService
from .device_collection_manager import DeviceCollectionManager

# SRP-compliant services
from .port_detection_service import PortDetectionService


@dataclass
class NetworkConfig:
    """Configuration for a `NetworkManager` instance."""

    port: str | None = None
    """Serial port to connect to (e.g. "COM6"). If None, auto-detect an Enttec port."""

    baudrate: int = 250000
    """Serial baud rate. 250000 matches the Enttec USB DMX/RDM PRO widgets."""

    timeout: float = 1.5
    """Seconds to wait for a request/response round trip before timing out."""

    cache_max_age_seconds: int = 30
    """Seconds a cached device parameter stays valid before a fresh GET is issued."""

    discovery_timeout: float = 5.0
    """Seconds to wait for RDM discovery (DISC_UNIQUE_BRANCH) to complete."""

    interface_type: InterfaceType = InterfaceType.ENTTEC_USB_PRO_MK2
    """Hardware interface adapter to use. See `InterfaceType` for supported widgets."""


class NetworkManager:
    """
    Network stack lifecycle management and coordination.

    Single Responsibility: Initialize, coordinate, and shutdown the RDM network stack.
    All specialized operations are delegated to dedicated services.

    Features:
    - Network stack lifecycle (start/stop)
    - Device discovery coordination
    - Service coordination and dependency injection

    Services (access via properties):
    - manager.devices: DeviceCollectionManager - device tracking and access
    - manager.batch: BatchOperationService - multi-device operations

    Example:
        config = NetworkConfig()  # Auto-detect port

        async with NetworkManager(config) as manager:
            # Discover devices
            devices = await manager.discover_devices()

            # Access devices via device manager
            device = manager.devices.get_device(uid)

            # Batch operations via batch service
            labels = await manager.batch.query_all_device_labels()
            await manager.batch.set_all_dmx_addresses(start_address=1)
    """

    # Registry of adapter factories keyed by interface type. New hardware
    # support can be added via register_adapter() without modifying this class.
    _ADAPTER_FACTORIES: dict[InterfaceType, Callable[[str], InterfaceAdapter]] = {
        InterfaceType.ENTTEC_USB_PRO: lambda port: EnttecAdapter(port, use_mk2_protocol=False),
        InterfaceType.ENTTEC_USB_PRO_MK2: lambda port: EnttecAdapter(port, use_mk2_protocol=True),
        InterfaceType.DMXKING_ULTRA_DMX: lambda port: DMXKingAdapter(port),
    }

    @classmethod
    def register_adapter(
        cls, interface_type: InterfaceType, factory: Callable[[str], InterfaceAdapter]
    ) -> None:
        """
        Register a factory for a new hardware interface type.

        Allows new adapters to be supported without modifying NetworkManager
        (Open/Closed Principle).

        Args:
            interface_type: The InterfaceType to register
            factory: Callable that takes a port string and returns an InterfaceAdapter
        """
        cls._ADAPTER_FACTORIES[interface_type] = factory

    def __init__(self, config: NetworkConfig):
        self._config = config
        self._logger = logging.getLogger(self.__class__.__name__)

        # SRP-compliant services
        self._port_detector = PortDetectionService()
        self._device_manager = DeviceCollectionManager()
        self._batch_ops = BatchOperationService(self._device_manager)

        # Transport and protocol
        self._transport: AsyncTransport | None = None
        self._protocol: RdmProtocol | None = None
        self._discovery: DiscoveryService | None = None
        self._repository: DeviceRepository | None = None
        self._scheduler: DmxFrameScheduler | None = None

        # Shared with the protocol so DMX frame writes (below) can never
        # race with RDM request/response writes on the same physical wire.
        self._wire_lock = asyncio.Lock()

        # State
        self._active = False

    @property
    def is_active(self) -> bool:
        """Check if network manager is active"""
        return self._active

    @property
    def config(self) -> NetworkConfig:
        """Return the configuration this manager was constructed with."""
        return self._config

    @property
    def devices(self) -> DeviceCollectionManager:
        """Access device collection manager."""
        return self._device_manager

    @property
    def batch(self) -> BatchOperationService:
        """Access batch operation service."""
        return self._batch_ops

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop()

    async def start(self) -> None:
        """
        Start network manager and initialize transport.

        Raises:
            RuntimeError: If already started
        """
        if self._active:
            raise RuntimeError("NetworkManager already started")

        # Resolve port (auto-detect if not specified)
        port = self._port_detector.resolve_port(self._config.port, auto_detect=True)
        self._config.port = port

        self._logger.info(
            "Starting network manager on %s with %s",
            self._config.port,
            self._config.interface_type.value,
        )

        try:
            # Create interface adapter based on type
            adapter = self._create_adapter(self._config.interface_type)
            self._logger.info("Using adapter: %s", adapter.interface_type.value)

            # Get controller UID (currently only for Enttec)
            source_uid = None
            if self._config.interface_type in [
                InterfaceType.ENTTEC_USB_PRO,
                InterfaceType.ENTTEC_USB_PRO_MK2,
            ]:
                # Port is guaranteed to be set by resolve_port
                assert self._config.port is not None, "Port should be set by resolve_port"
                source_uid = await get_enttec_serial_uid(
                    self._config.port, self._config.baudrate, self._config.timeout, adapter
                )
                if not source_uid:
                    raise RuntimeError(f"Could not get Enttec UID from {self._config.port}")
                self._logger.info("Controller UID: %012X", source_uid)
            else:
                # For non-Enttec interfaces, generate appropriate UID
                raise NotImplementedError(
                    f"Interface type {self._config.interface_type.value} not yet implemented"
                )

            # Create transport with adapter
            self._transport = AsyncSerialTransport(adapter)
            await self._transport.connect()

            # Scheduler pauses/resumes around RDM requests for proper bus
            # arbitration between DMX output and RDM traffic. Its background
            # frame loop is only started lazily on the first send_dmx() call
            # (see send_dmx()) - starting it unconditionally would stream
            # DMX frames continuously even for RDM-only sessions, adding
            # unnecessary traffic on the shared serial line.
            self._scheduler = DmxFrameScheduler(send_callback=self._send_scheduled_frame)

            # Create protocol with source UID
            self._protocol = RDME120Protocol(
                self._transport,
                source_uid,
                allocator=TransactionNumberAllocator(),
                dmx_scheduler=self._scheduler,
                wire_lock=self._wire_lock,
            )
            await self._protocol.start()

            # Create repository and discovery service
            self._repository = DeviceRepository(self._protocol)
            self._discovery = DiscoveryService(self._protocol, self._repository)

            self._active = True
            self._logger.info("Network manager started successfully")

        except Exception as e:
            self._logger.error("Failed to start network manager: %s", e)
            await self._cleanup()
            raise

    def _create_adapter(self, interface_type: InterfaceType) -> InterfaceAdapter:
        """
        Factory method to create the appropriate interface adapter.

        Args:
            interface_type: Type of hardware interface

        Returns:
            InterfaceAdapter instance

        Raises:
            ValueError: If interface type not supported
        """
        # Port is guaranteed to be set by resolve_port
        assert self._config.port is not None, "Port should be set by resolve_port"

        factory = self._ADAPTER_FACTORIES.get(interface_type)
        if factory is None:
            raise ValueError(f"Unsupported interface type: {interface_type}")
        return factory(self._config.port)

    async def stop(self) -> None:
        """Stop network manager and cleanup resources"""
        if not self._active:
            return

        self._logger.info("Stopping network manager")
        self._active = False

        await self._cleanup()

        self._logger.info("Network manager stopped")

    async def _cleanup(self) -> None:
        """Cleanup all resources"""
        # Clear devices
        self._device_manager.clear()

        # Stop DMX scheduler
        if self._scheduler:
            await self._scheduler.stop()
            self._scheduler = None

        # Stop protocol
        if self._protocol:
            await self._protocol.stop()
            self._protocol = None

        # Close transport
        if self._transport:
            await self._transport.disconnect()
            self._transport = None

        self._discovery = None
        self._repository = None

    def _ensure_active(self) -> None:
        """Ensure manager is active"""
        if not self._active:
            raise RuntimeError("NetworkManager not started")

    async def _send_scheduled_frame(self, dmx_data: bytes) -> None:
        """Frame and transmit one DMX frame via the transport (scheduler callback)."""
        assert self._transport is not None, "Transport not initialized"
        async with self._wire_lock:
            await self._transport.send_dmx_frame(dmx_data, port=1)

    async def send_dmx(self, dmx_data: bytes, port: int = 1) -> None:
        """
        Send DMX512 data to output.

        Also updates the background scheduler's frame buffer so output keeps
        being refreshed automatically (per DMX512 spec) until the next call
        to `send_dmx()`/`stop()`, instead of going stale after a single frame.

        Args:
            dmx_data: DMX channel values (1-512 bytes, values 0-255)
            port: Physical port number (for multi-port interfaces)

        Raises:
            RuntimeError: If network manager not started
            ValueError: If dmx_data is invalid (wrong length)
        """
        self._ensure_active()
        assert self._transport is not None, "Transport not initialized"
        assert self._scheduler is not None, "Scheduler not initialized"

        self._scheduler.set_dmx_data(1, dmx_data)
        # Lazily start the background refresh loop on first use, so sessions
        # that never call send_dmx() (e.g. RDM-only discovery) don't pay for
        # continuous DMX traffic on the shared serial line.
        await self._scheduler.start()

        # Frame and send via the transport's DMX-output abstraction. Shares
        # the RDM wire lock since both write to the same physical serial port.
        async with self._wire_lock:
            await self._transport.send_dmx_frame(dmx_data, port=port)

        self._logger.debug("Sent DMX data: %d channels", len(dmx_data))

    async def discover_devices(self, known_uids: list[UID] | None = None) -> list[RdmDevice]:
        """
        Discover RDM devices on the network.

        Args:
            known_uids: Optional list of known device UIDs to check.
                       If None, performs full network discovery (DISC_UNIQUE_BRANCH).

        Returns:
            List of discovered RdmDevice instances
        """
        self._ensure_active()
        assert self._discovery is not None, "Discovery service not initialized"

        if known_uids is None:
            # Perform full network discovery
            self._logger.info("Performing full network discovery...")
            rdm_devices = await self._discovery.full_discovery(only_new=False)
        else:
            # Query specific known UIDs
            self._logger.info("Discovering %d known devices", len(known_uids))

            # Unmute all devices first
            await self._discovery.unmute_all()

            # Query known devices (returns RdmDevice objects from repository)
            rdm_devices = await self._discovery.discover_known_devices(known_uids)

        discovered: list[RdmDevice] = []

        for rdm_device in rdm_devices:
            # Device is already created and initialized by DiscoveryService
            # Add to device collection manager
            self._device_manager.add_device(rdm_device)
            state = rdm_device.state
            discovered.append(rdm_device)
            self._logger.info(
                "Discovered: %s - %s [%012X]", state.manufacturer, state.device_label, state.uid
            )

        self._logger.info("Discovery complete: %d devices found", len(discovered))
        return discovered

    def __str__(self) -> str:
        return (
            f"NetworkManager(port={self._config.port}, active={self._active}, "
            f"devices={self._device_manager.get_device_count()})"
        )

    def __repr__(self) -> str:
        return self.__str__()
