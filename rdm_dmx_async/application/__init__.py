"""
Application layer - high-level RDM/DMX management

Provides SRP-compliant services for network management:
- NetworkManager: Network stack lifecycle and coordination
- PortDetectionService: COM port detection and validation
- DeviceCollectionManager: Device collection tracking
- BatchOperationService: Multi-device concurrent operations
"""

from .batch_operation_service import BatchOperationService
from .device_collection_manager import DeviceCollectionManager
from .network_manager import NetworkConfig, NetworkManager
from .port_detection_service import PortDetectionService

__all__ = [
    "NetworkManager",
    "NetworkConfig",
    "PortDetectionService",
    "DeviceCollectionManager",
    "BatchOperationService",
]
