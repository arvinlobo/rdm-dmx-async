"""
Serial transport implementation for RDM communication.

Generic async serial transport supporting multiple hardware interfaces
through the adapter pattern.
"""

import asyncio
import logging

import serial

from .base import ConnectionFailedError, NotConnectedError, TransportError
from .frame_buffer import FrameBuffer
from .interface_adapter import InterfaceAdapter
from .protocol_detector import RdmProtocolDetector


class AsyncSerialTransport:
    """
    Generic async serial transport for RDM interfaces.

    Uses an InterfaceAdapter to support different hardware interfaces
    (Enttec, DMXKing, etc.) without changing the transport code.

    Features:
    - Non-blocking serial I/O
    - Adapter pattern for multiple interfaces
    - Background tasks for RX/TX
    - Proper resource cleanup
    - Queue-based communication

    Example:
        # DMX hardware (adapter provides config)
        from .adapters import EnttecAdapter
        adapter = EnttecAdapter("COM3")
        transport = AsyncSerialTransport(adapter)

        # Generic serial device
        from .adapters import GenericSerialAdapter, FramingMode
        adapter = GenericSerialAdapter("COM4", baudrate=115200, framing=FramingMode.LINE_BASED)
        transport = AsyncSerialTransport(adapter)

        async with transport:
            await transport.send(data, "")
            response, _ = await transport.receive(timeout=1.0)
    """

    def __init__(self, adapter: InterfaceAdapter):
        """
        Initialize serial transport with interface adapter.

        Args:
            adapter: Hardware interface adapter (Enttec, DMXKing, etc.)
        """
        self._adapter = adapter
        self._config = adapter.serial_config
        self._logger = logging.getLogger(self.__class__.__name__)

        # Helper components
        self._protocol_detector = RdmProtocolDetector()
        self._frame_buffer = FrameBuffer(adapter, max_size=1024)

        # Serial port
        self._serial: serial.Serial | None = None

        # Queues for async communication
        self._rx_queue: asyncio.Queue[tuple[bytes, str]] = asyncio.Queue(
            maxsize=self._config.queue_maxsize
        )
        self._tx_queue: asyncio.Queue[tuple[bytes, str, bool]] = asyncio.Queue(
            maxsize=self._config.queue_maxsize
        )

        # Background tasks
        self._tasks: set[asyncio.Task] = set()

        # Connection state
        self._connected = asyncio.Event()
        self._shutdown = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        """Return whether the serial transport is connected."""
        return self._connected.is_set()

    @property
    def adapter(self) -> InterfaceAdapter:
        """Get the interface adapter."""
        return self._adapter

    async def connect(self) -> None:
        """Establish serial connection"""
        if self.is_connected:
            return

        try:
            # Open serial port
            self._serial = serial.Serial(
                port=self._config.port,
                baudrate=self._config.baudrate,
                bytesize=self._config.bytesize,
                parity=self._config.parity,
                stopbits=self._config.stopbits,
                timeout=self._config.timeout,
                write_timeout=self._config.write_timeout,
            )

            if not self._serial.is_open:
                raise ConnectionFailedError(f"Failed to open port {self._config.port}")

            # Clear buffers
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()

            # Start background tasks
            self._tasks.add(asyncio.create_task(self._rx_loop()))
            self._tasks.add(asyncio.create_task(self._tx_loop()))

            self._connected.set()
            self._logger.info(
                f"Serial connected on {self._config.port} @ {self._config.baudrate} baud"
            )

        except serial.SerialException as e:
            raise ConnectionFailedError(f"Failed to connect serial: {e}") from e
        except Exception as e:
            raise ConnectionFailedError(f"Failed to connect serial: {e}") from e

    async def disconnect(self) -> None:
        """Close connection and cleanup resources"""
        if not self.is_connected:
            return

        self._logger.info("Disconnecting serial transport...")

        # Signal shutdown
        self._shutdown.set()
        self._connected.clear()

        # Cancel all background tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Close serial port
        if self._serial and self._serial.is_open:
            self._serial.close()
            self._serial = None

        self._shutdown.clear()

        self._logger.info("Serial transport disconnected")

    async def send(self, data: bytes, destination: str = "", bypass_framing: bool = False) -> None:
        """
        Queue data for transmission.

        Args:
            data: Bytes to send (RDM packet or pre-framed data)
            destination: Not used for serial (kept for interface compatibility)
            bypass_framing: If True, send data as-is without adapter framing (for DMX output)
        """
        if not self.is_connected:
            raise NotConnectedError("Transport not connected")

        try:
            # For DMX output (bypass_framing=True), use put_nowait and handle queue full
            # For RDM (bypass_framing=False), block if queue is full
            if bypass_framing:
                # DMX output: drop old frames if queue is full (only latest frame matters)
                try:
                    self._tx_queue.put_nowait((data, destination, bypass_framing))
                except asyncio.QueueFull:
                    # Queue full - this is normal for high-rate DMX
                    # Just skip this frame, next one will be sent
                    self._logger.debug("TX queue full, dropping DMX frame (normal for high rate)")
            else:
                # RDM: must deliver, so use put_nowait and raise error if full
                self._tx_queue.put_nowait((data, destination, bypass_framing))
        except asyncio.QueueFull as exc:
            raise TransportError("TX queue full") from exc

    async def send_dmx_frame(self, dmx_data: bytes, port: int = 1) -> None:
        """
        Frame and transmit one DMX512 output frame via the interface adapter.

        Args:
            dmx_data: DMX channel values (1-512 bytes, values 0-255)
            port: Physical port number (for multi-port interfaces)
        """
        framed_data = self._adapter.frame_dmx_output(dmx_data, port)
        await self.send(framed_data, destination="DMX_OUTPUT", bypass_framing=True)

    async def receive(self, timeout: float | None = None) -> tuple[bytes, str]:
        """
        Receive data from queue.

        Args:
            timeout: Max time to wait (None = wait forever)

        Returns:
            Tuple of (data, source) - source is empty string for serial
        """
        if not self.is_connected:
            raise NotConnectedError("Transport not connected")

        if timeout is not None:
            data, addr = await asyncio.wait_for(self._rx_queue.get(), timeout=timeout)
        else:
            data, addr = await self._rx_queue.get()

        return data, addr

    def _assert_break_and_write(self, data: bytes) -> None:
        """
        Toggle the UART break condition immediately before writing a frame.

        Used for adapters with no onboard BREAK/MAB generator (see
        `InterfaceAdapter.requires_manual_break`) - asserting then clearing
        `break_condition` produces the DMX BREAK signal on the wire that a
        purpose-built widget's firmware would otherwise generate itself.
        """
        assert self._serial is not None
        self._serial.break_condition = True
        self._serial.break_condition = False
        self._serial.write(data)

    async def _tx_loop(self) -> None:
        """Background task for transmitting queued packets"""
        self._logger.debug("TX loop started")

        try:
            while not self._shutdown.is_set():
                try:
                    # Wait for data with short timeout to check shutdown
                    data, _, bypass_framing = await asyncio.wait_for(
                        self._tx_queue.get(), timeout=0.1
                    )

                    if bypass_framing:
                        # Data is already framed (e.g., DMX output), send as-is.
                        # Not logged: this runs per DMX frame (up to ~40 Hz
                        # when repeating), which would flood the log file.
                        framed_packet = data
                    else:
                        # Frame RDM data using interface adapter
                        self._logger.debug(
                            "[TX_RDM] Raw RDM packet (%d bytes): %s",
                            len(data),
                            " ".join(f"{b:02X}" for b in data),
                        )

                        # Detect packet type and use appropriate framing
                        try:
                            is_discovery = self._protocol_detector.is_discovery_packet(data)
                            self._logger.debug(f"[DETECTOR] is_discovery={is_discovery}")
                        except Exception as e:
                            self._logger.error(f"[DETECTOR] Error detecting packet: {e}")
                            is_discovery = False

                        if is_discovery:
                            framed_packet = self._adapter.frame_rdm_discovery_request(data, port=1)
                            self._logger.debug("[TX_TYPE] Discovery packet detected")
                        else:
                            framed_packet = self._adapter.frame_rdm_request(data, port=1)

                        self._logger.debug(
                            "[TX_FRAMED] Framed packet (%d bytes) via %s: %s",
                            len(framed_packet),
                            self._adapter.interface_type.value,
                            " ".join(f"{b:02X}" for b in framed_packet),
                        )

                    # Write to serial port (blocking, but fast)
                    if self._adapter.requires_manual_break:
                        await asyncio.get_event_loop().run_in_executor(
                            None, self._assert_break_and_write, framed_packet
                        )
                    else:
                        await asyncio.get_event_loop().run_in_executor(
                            None, self._serial.write, framed_packet
                        )

                    # Small delay between packets (skip for DMX to maximize throughput)
                    if not bypass_framing:
                        await asyncio.sleep(0.01)

                except TimeoutError:
                    continue  # Check shutdown flag
                except serial.SerialException as e:
                    self._logger.error(f"Serial write error: {e}")
                except Exception as e:
                    self._logger.error(f"Error in TX loop: {e}")

        except asyncio.CancelledError:
            self._logger.debug("TX loop cancelled")
        finally:
            self._logger.debug("TX loop stopped")

    async def _rx_loop(self) -> None:
        """Background task for receiving packets"""
        self._logger.debug("RX loop started")

        try:
            while not self._shutdown.is_set():
                try:
                    # Read available data (non-blocking due to timeout)
                    data = await asyncio.get_event_loop().run_in_executor(
                        None, self._serial.read, self._config.buffer_size
                    )

                    if not data:
                        await asyncio.sleep(0.01)
                        continue

                    self._logger.debug(
                        "[RX_RAW] Received %d raw bytes: %s",
                        len(data),
                        " ".join(f"{b:02X}" for b in data[:50]),
                    )

                    # Add to buffer and extract all available frames
                    self._frame_buffer.append(data)
                    frames = self._frame_buffer.extract_all_frames(max_iterations=10)

                    # Queue all extracted frames
                    for rdm_packet in frames:
                        self._logger.debug(
                            "[RX_RDM] Parsed RDM packet (%d bytes) via %s: %s",
                            len(rdm_packet),
                            self._adapter.interface_type.value,
                            " ".join(f"{b:02X}" for b in rdm_packet[:50]),
                        )

                        try:
                            self._rx_queue.put_nowait((rdm_packet, ""))
                        except asyncio.QueueFull:
                            self._logger.warning("RX queue full, dropping packet")

                except serial.SerialException as e:
                    self._logger.error(f"Serial read error: {e}")
                    await asyncio.sleep(0.1)
                except Exception as e:
                    self._logger.error(f"Error in RX loop: {e}")
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            self._logger.debug("RX loop cancelled")
        finally:
            self._logger.debug("RX loop stopped")

    async def __aenter__(self) -> "AsyncSerialTransport":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
