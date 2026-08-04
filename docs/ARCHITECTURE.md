# rdm_dmx_async Architecture Documentation

## Overview
This document describes the 7-layer architecture of the rdm_dmx_async library, following SOLID principles and clean architecture patterns.

Note: the optional FastAPI REST API lives in the top-level `api/` folder, outside
the `rdm_dmx_async` package. It's a separate application that consumes the library
(same as `examples/`, `hardware_tests/`, `cli.py`) and is not part of this layering.
See `api/app.py`; requires the `api` extra (`pip install rdm-dmx-async[api]`).
A React frontend for this API lives in `frontend/` (Vite + TypeScript). See the
"Web UI" section in the top-level `README.md` for how to run both together.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  7. Application Layer                                        │
│     - Device discovery workflows                             │
│     - Fixture configuration                                  │
│     - Monitoring and diagnostics                             │
│     - Firmware/application workflows                         │
├─────────────────────────────────────────────────────────────┤
│  6. Device Service Layer                                     │
│     - RdmDevice: High-level device interface                 │
│     - DeviceRepository: Device lifecycle management          │
│     - DiscoveryService: Enhanced discovery coordination      │
│     - Parameter-specific services                            │
├─────────────────────────────────────────────────────────────┤
│  5. Transaction Layer                                        │
│     - TransactionManager: Transaction orchestration          │
│     - Transaction: Individual transaction execution          │
│     - RetryPolicy: Configurable retry strategies             │
│     - ResponseCorrelator: Request/response matching          │
│     - TransactionNumberAllocator: TXN numbering              │
├─────────────────────────────────────────────────────────────┤
│  4. Protocol Layer                                           │
│     - RDME120Protocol: RDM E1.20 protocol operations         │
│     - PacketEncoder: RDM packet encoding                     │
│     - PacketDecoder: RDM packet decoding                     │
│     - RdmValidator: Protocol validation                      │
│     - PID handlers: Parameter-specific codecs                │
│     - Discovery codec: DISC_UNIQUE_BRANCH handling           │
├─────────────────────────────────────────────────────────────┤
│  3. DMX/RDM Scheduling Layer                                 │
│     - DmxFrameScheduler: DMX frame timing control            │
│     - RdmRequestWindow: RDM window coordination              │
│     - Break/MAB timing control                               │
│     - Response timeout handling                              │
│     - Bus arbitration                                        │
├─────────────────────────────────────────────────────────────┤
│  2. Transport Layer                                          │
│     - AsyncSerialTransport: Serial transport                 │
│     - InterfaceAdapter: Hardware abstraction                 │
│     - EnttecAdapter: ENTTEC USB PRO implementation           │
│     - TransportConfig: Configuration management              │
├─────────────────────────────────────────────────────────────┤
│  1. Hardware / OS Layer                                      │
│     - pyserial: Serial port access                           │
│     - asyncio: Async I/O primitives                          │
│     - OS serial drivers                                      │
└─────────────────────────────────────────────────────────────┘
```

## Layer Responsibilities

### 1. Hardware / OS Layer
**Purpose**: Low-level system access
- Serial port communication via pyserial
- Async I/O via asyncio
- Hardware device enumeration

**Dependencies**: Python standard library, pyserial

### 2. Transport Layer
**Purpose**: Abstract hardware communication
- `AsyncSerialTransport`: Async serial communication with TX/RX queues
- `InterfaceAdapter`: Abstract base for hardware protocols
- `EnttecAdapter`: ENTTEC USB PRO API v1.44 implementation
  - All message types (Labels 1-11)
  - Widget parameters and serial number queries
  - Discovery packet routing (Label 11 vs Label 7)

**Key Files**:
- `transport/serial.py`
- `transport/interface_adapter.py`
- `transport/base.py`

**SRP Compliance**: Each transport handles only its communication method

### 3. DMX/RDM Scheduling Layer
**Purpose**: Timing control and bus arbitration
- `DmxFrameScheduler`: Controls DMX frame rate and timing
- `RdmRequestWindow`: Manages RDM windows between DMX frames
- Break and Mark-After-Break timing coordination
- Prevents bus conflicts

**Key Files**:
- `scheduling/dmx_scheduler.py`
- `scheduling/rdm_window.py`

**SRP Compliance**: Scheduling separated from protocol operations

**ANSI E1.20 Compliance**:
- RDM packets sent between DMX frames
- Proper break-to-break timing maintained
- Response timeout handling (2-3ms typical)

### 4. Protocol Layer
**Purpose**: RDM protocol implementation
- `RDME120Protocol`: Core protocol operations (refactored with SRP)
  - Simplified: only handles send/receive coordination
  - Delegates correlation to `ResponseCorrelator`
  - Delegates validation to `RdmValidator`
- `PacketEncoder/Decoder`: RDM packet serialization
- `RdmValidator`: Protocol validation logic
  - Request validation
  - Response validation
  - Request/response matching

**Key Files**:
- `protocols/rdm_e120.py` *(refactored)*
- `protocols/response_correlator.py` *(new)*
- `protocols/rdm_validator.py` *(new)*
- `packets/encoder.py`
- `packets/decoder.py`

**SRP Compliance**:
- Protocol operations separated from correlation
- Validation extracted to dedicated class
- Encoding/decoding separated from protocol logic

### 5. Transaction Layer
**Purpose**: Reliable request/response handling
- `AsyncTransaction`: Individual transaction with retries
- `TransactionManager`: Orchestrates multiple transactions
- `ResponseCorrelator`: Matches responses to requests *(extracted from protocol)*
- `RetryPolicy`: Configurable retry strategies
- `TransactionNumberAllocator`: TXN number management

**Key Files**:
- `transaction/async_transaction.py`
- `transaction/manager.py`
- `protocols/response_correlator.py` *(protocol layer but used by transactions)*
- `transaction/retry_policy.py`
- `transaction/allocator.py`

**SRP Compliance**: Each component has single responsibility
- Correlation separated from protocol
- Retry logic separated from transaction execution
- TXN allocation separated from transaction management

**Features**:
- Automatic retries with backoff
- Response correlation with 30s stale timeout
- Memory leak prevention via cleanup loop

### 6. Device Service Layer
**Purpose**: High-level device management
- `RdmDevice`: Clean device interface
  - Device state management
  - Parameter operations with caching
  - Transaction coordination
- `DeviceRepository`: Device collection management
  - Device registration and lookup
  - Lifecycle management
  - Stale device cleanup
- `DiscoveryService`: Enhanced discovery
  - Coordinates with repository
  - Handles discovery workflows

**Key Files**:
- `services/rdm_device.py` *(new)*
- `services/device_repository.py` *(new)*
- `services/discovery_service.py` *(new)*

**SRP Compliance**:
- Device operations separated from repository management
- Discovery coordination separated from device logic
- Each service has single clear purpose

**Domain-Driven Design**:
- `DeviceState` dataclass for state snapshots
- Repository pattern for collection management
- Service layer for coordination

### 7. Application Layer
**Purpose**: User-facing workflows
- Device discovery workflows
- Fixture configuration
- Monitoring and diagnostics
- Firmware programming
- Application-specific business logic

**Key Files**:
- `application/network_manager.py` *(to be refactored)*
- User application code

## SOLID Principles Applied

### Single Responsibility Principle (SRP)
**Before**: `RDME120Protocol` handled encoding, sending, receiving, decoding, correlation, and lifecycle
**After**:
- Protocol: Only send/receive coordination
- ResponseCorrelator: Only correlation logic
- RdmValidator: Only validation logic
- Encoder/Decoder: Only serialization

### Open/Closed Principle (OCP)
- `InterfaceAdapter` is abstract base, extended by `EnttecAdapter`, `DMXKingAdapter`
- New hardware can be added without modifying existing code
- Retry policies are extensible via `RetryPolicy` base class

### Liskov Substitution Principle (LSP)
- Any `InterfaceAdapter` can substitute for another
- Any `AsyncTransport` can substitute for another
- Polymorphic hardware support

### Interface Segregation Principle (ISP)
- Separate interfaces for different concerns:
  - `AsyncTransport` for communication
  - `InterfaceAdapter` for hardware framing
  - `RdmValidator` for validation
  - `ResponseCorrelator` for correlation

### Dependency Inversion Principle (DIP)
- High-level modules depend on abstractions:
  - Protocol depends on `AsyncTransport` (abstract)
  - Service layer depends on `RDME120Protocol` (interface)
  - Application depends on services (not concrete implementations)
- Dependency injection throughout (constructor injection)

## Key Design Patterns

### Strategy Pattern
- `RetryPolicy`: Different retry strategies
- `InterfaceAdapter`: Different hardware protocols

### Repository Pattern
- `DeviceRepository`: Manages device collection
- Abstracts device persistence and lifecycle

### Adapter Pattern
- `InterfaceAdapter`: Adapts hardware-specific protocols to common interface
- `EnttecAdapter`: Adapts ENTTEC USB PRO protocol

### Observer/Callback Pattern
- Response correlation uses Futures (async observer)
- Event-driven receive loops

### Factory Pattern
- Device creation via repository
- Transport configuration factories

## Data Flow Example

```
User Request
    ↓
Application Layer (NetworkManager)
    ↓
Service Layer (RdmDevice.get_device_label())
    ↓
Transaction Layer (AsyncTransaction with retry)
    ↓
Protocol Layer (RDME120Protocol.send_get_command())
    ↓ (registers with ResponseCorrelator)
    ↓ (validates with RdmValidator)
    ↓
Scheduling Layer (RdmRequestWindow pauses DMX)
    ↓
Transport Layer (AsyncSerialTransport.send())
    ↓
Hardware Layer (EnttecAdapter frames → pyserial)
    ↓
[RDM Device]
    ↓
Hardware Layer (pyserial → EnttecAdapter parses)
    ↓
Transport Layer (AsyncSerialTransport.receive())
    ↓
Protocol Layer (_receive_loop)
    ↓ (decodes with PacketDecoder)
    ↓ (validates with RdmValidator)
    ↓ (correlates with ResponseCorrelator)
    ↓
Transaction Layer (AsyncTransaction receives response)
    ↓
Service Layer (RdmDevice caches result)
    ↓
Application Layer (User receives result)
```

## Benefits of This Architecture

### Testability
- Each layer can be tested independently
- Mock interfaces for unit testing
- Integration testing at layer boundaries

### Maintainability
- Clear separation of concerns
- Easy to locate bugs (layer isolation)
- Changes localized to specific layers

### Extensibility
- New hardware: Add `InterfaceAdapter` implementation
- New protocols: Add protocol layer implementation
- New features: Add to appropriate layer

### Reusability
- Transport layer reusable for different protocols
- Protocol layer reusable for different transports
- Service layer provides clean API for applications

### Scalability
- Async throughout for high-performance
- Transaction layer handles concurrency
- Scheduling prevents bus conflicts

## Migration from Old Architecture

### Key Changes
1. **Protocol Layer**: Refactored with SRP
   - `ResponseCorrelator` extracted
   - `RdmValidator` extracted
   - `RDME120Protocol` simplified

2. **Service Layer**: New abstraction
   - `RdmDevice` replaces direct `AsyncDevice` use
   - `DeviceRepository` for device management
   - `DiscoveryService` for enhanced discovery

3. **Scheduling Layer**: New layer
   - `DmxFrameScheduler` for timing control
   - `RdmRequestWindow` for coordination
   - Proper ANSI E1.20 timing compliance

### Backward Compatibility
**Clean slate design** - User authorized full refactoring without backward compatibility requirements.

### Testing Status
- ✅ Hardware tests passing (COM6, ENTTEC Mk2)
- ✅ ENTTEC API v1.44 fully implemented
- ✅ Auto-discovery functional
- ✅ ResponseCorrelator implemented with memory leak prevention
- ✅ RdmValidator implemented with E1.20 compliance
- ⚠️ Service layer needs integration testing
- ⚠️ Scheduling layer needs integration testing

## Next Steps

1. **Complete Protocol Layer**:
   - PID handler framework
   - Discovery codec improvements

2. **Integrate Scheduling Layer**:
   - Connect DmxFrameScheduler to transport
   - Use RdmRequestWindow in transactions

3. **Refactor Application Layer**:
   - Update NetworkManager to use services
   - Add monitoring/diagnostics support

4. **Testing**:
   - Unit tests for new components
   - Integration tests across layers
   - Hardware validation

5. **Documentation**:
   - API reference updates
   - Usage examples
   - Migration guide

## References

- ANSI E1.20: RDM Protocol Standard
- ANSI E1.11: DMX512-A Standard
- ENTTEC DMX USB PRO API v1.44
- SOLID Principles (Robert C. Martin)
- Clean Architecture (Robert C. Martin)
