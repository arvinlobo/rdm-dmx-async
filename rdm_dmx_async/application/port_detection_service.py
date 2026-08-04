"""
Port detection and validation service.

Handles automatic detection of RDM interface hardware.
"""

import logging

from ..utils import find_enttec_port, list_available_ports


class PortDetectionService:
    """
    Detects and validates communication ports for RDM interfaces.

    Single Responsibility: Hardware port detection and validation
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    def auto_detect_enttec(self) -> str | None:
        """
        Automatically detect first available Enttec device.

        Returns:
            Port name (e.g., "COM3") or None if not found
        """
        self._logger.info("Auto-detecting Enttec COM port...")
        port = find_enttec_port()

        if port:
            self._logger.info("Auto-detected Enttec device on port: %s", port)
        else:
            self._logger.warning("No Enttec device found")

        return port

    def validate_port(self, port: str) -> bool:
        """
        Verify that a port exists and is accessible.

        Args:
            port: Port name to validate

        Returns:
            True if port exists and is accessible
        """
        available_ports = list_available_ports()
        is_valid = port in available_ports

        if is_valid:
            self._logger.debug("Port %s is valid", port)
        else:
            self._logger.warning("Port %s not found in available ports: %s", port, available_ports)

        return is_valid

    def list_all_ports(self) -> list[str]:
        """
        List all available serial ports on the system.

        Returns:
            List of port names
        """
        ports = list_available_ports()
        self._logger.debug("Found %d available ports", len(ports))
        return ports

    def resolve_port(self, port: str | None, auto_detect: bool = True) -> str | None:
        """
        Resolve port configuration - use provided port or auto-detect.

        Args:
            port: Explicit port name, or None for auto-detection
            auto_detect: Whether to auto-detect if port is None

        Returns:
            Resolved port name or None

        Raises:
            RuntimeError: If auto-detection is requested but fails
        """
        if port is not None:
            # Explicit port provided
            if self.validate_port(port):
                return port
            else:
                self._logger.warning(
                    "Specified port %s not available, will attempt auto-detection", port
                )
                if not auto_detect:
                    return None

        # Auto-detect
        if auto_detect:
            detected_port = self.auto_detect_enttec()
            if detected_port is None:
                raise RuntimeError("No Enttec device found. Please specify port manually.")
            return detected_port

        return None
