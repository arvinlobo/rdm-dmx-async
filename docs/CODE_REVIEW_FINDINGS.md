# Brutal Code Review — Findings & Fixes

Date: 2026-08-03
Scope: Full read-through of `rdm_dmx_async/` (packets, protocols, scheduling,
transport, transaction, services, application, cli, utils, domain), plus a
targeted sweep of `services/device_apis/`, `examples/`, and `hardware_tests/`.

All 88 existing unit tests passed before these changes; 84 pass after (4
tests that only covered now-deleted dead code were removed — see finding A)
(`.venv\Scripts\python.exe -m pytest -q`). Test coverage is thin outside the
protocol/packet layer (~47% overall), which is exactly why several of these
bugs were never caught — the layers with the least coverage
(`application/`, `services/device_apis/`, `utils.py`, `scheduling/`) are where
most of the real bugs were hiding.

27 new unit tests were later added for `scheduling/dmx_scheduler.py` and
`scheduling/rdm_window.py` (previously 19%/38% covered, now 97%/100%) as part
of wiring that layer into production use — see finding B and
`tests/test_dmx_scheduler.py`/`tests/test_rdm_window.py`. 111 tests pass
total as of that point.

A further audit pass (targeting frame fragmentation/timeout corner cases and
the transaction/retry layer) added 75 more tests across
`tests/test_frame_buffer.py`, `tests/test_transaction_number_allocator.py`,
`tests/test_late_response_classifier.py`, `tests/test_async_transaction.py`,
`tests/test_retry_policy.py`, and two new tests in
`tests/test_serial_transport_e2e.py`. This pass caught a real bug (#7 below)
— `AsyncTransaction`'s permanent-failure short-circuit silently never
triggered for `NAKReason.UNKNOWN_PID` — and confirmed (rather than fixed) two
narrower `FrameBuffer` limitations documented under finding #7. 186 tests
pass total as of this point; overall coverage rose from ~49% to ~54%, with
the `transaction/` package now at 89-100% per file and `frame_buffer.py` at
95%.

One bug (#1 below) was caught only by testing against the user's real
connected ENTTEC + fixture hardware — `discover_devices()` hung for several
minutes with no fixture powered on, which led to root-causing a discovery
algorithm bug that unit tests (all of which use fakes/mocks) never exercised.

---

## Bugs fixed

### 1. CRITICAL — Discovery hangs almost indefinitely on any empty address branch
**Files:** `rdm_dmx_async/protocols/rdm_e120.py`,
`rdm_dmx_async/services/discovery_service.py`

**Found via live hardware testing**, not static review: running
`manager.discover_devices()` with no RDM fixture powered on hung for several
minutes instead of returning an empty list.

Root cause: `RDME120Protocol.send_discovery_command()` for DISC_UNIQUE_BRANCH
collapsed two completely different outcomes into the same `None` return
value:

- **True no-response** (nothing on the bus in that address range at all) —
  `asyncio.wait_for(self._discovery_queue.get(), timeout)` raises
  `TimeoutError`, which was caught and converted to `return None`.
- **True collision** (2+ devices respond, Manchester decode fails on the
  garbled overlapping signal) — also `return None`.

`DiscoveryService.discover_unique_branch()` had no way to tell these apart,
so its own comment admitted the ambiguity ("None response = collision or no
response") and it unconditionally guessed `COLLISION` for both. On a real
collision that's correct — but on a true empty branch, guessing `COLLISION`
causes `full_discovery()`'s binary search to **split that branch instead of
terminating it**, and every resulting half is *also* empty and *also* gets
misclassified as a collision, and split again — recursing toward leaf nodes
of the full 48-bit UID space. With zero devices on the bus this never
practically completes. The existing `MAX_RETRIES = 3` retry loop didn't help
because it only retries on genuine exceptions, which this path never raised
(the ambiguity was already flattened to a plain `None`, not an exception).

Every *other* RDM command (`send_get_command`, `send_set_command`,
DISC_MUTE/DISC_UN_MUTE via `_send_and_receive`) already raises
`ProtocolTimeoutError` on a true timeout — only the DISC_UNIQUE_BRANCH path
swallowed it to `None` instead, breaking the pattern the rest of the codebase
relies on.

**Fix:** `send_discovery_command()` now raises `ProtocolTimeoutError` on a
genuine timeout (no data arrived), and reserves the `None` return value
exclusively for the collision case (data arrived, decode failed).
`discover_unique_branch()` already had a top-level `except Exception ...:
return DiscoveryResult.NO_RESPONSE` — that now correctly catches the newly
raised timeout, so empty branches terminate immediately (`mark_complete()`)
instead of being split. Updated the one test that asserted the old (buggy)
behavior (`test_discovery_unique_branch_no_response_returns_none` →
`test_discovery_unique_branch_no_response_raises_timeout`) to match the
corrected contract.

**Validated on hardware:** with the fixture powered on,
`manager.discover_devices()` now completes in ~3 seconds (previously hung
indefinitely with the fixture off, confirming the empty-branch case was the
trigger). Concurrent `batch.query_all_device_labels()` and
`batch.identify_all(True)` against the discovered device also confirmed
working (see bug #3 for why these previously would have been unreliable
too).

---

### 2. CRITICAL — Batch operations crashed: wrong method names on `RdmDevice`
**File:** `rdm_dmx_async/application/batch_operation_service.py`

`RdmDevice` exposes PID operations only through composed sub-APIs
(`device.control`, `device.dmx_config`, etc.), but `BatchOperationService`
called non-existent methods directly on the device object:

- `device.identify(enable)` → should be `device.control.identify(enable)`
- `device.reset(warm_reset)` → should be `device.control.reset(warm_reset)`
- `device.get_personality()` → should be `device.dmx_config.get_personality()`
- `device.set_dmx_start_address(address)` → should be `device.dmx_config.set_start_address(address)`

`identify_all()`, `reset_all()`, and `get_all_personalities()` raised
`AttributeError` immediately (attribute access happens while building the
task list, before `asyncio.gather` even runs, so `return_exceptions=True`
never had a chance to catch it). `set_all_dmx_addresses()` failed more
quietly — the `AttributeError` was swallowed by its per-device `try/except
Exception`, silently returning `False` for every device.

**Impact:** four of the six methods on `BatchOperationService` — a
documented, public API — were completely non-functional.
**Fix:** call the correct sub-API methods. Verified no unit test covered this
(coverage was 12% on this file), which is why it went unnoticed.

---

### 3. CRITICAL — Transaction numbers collide across concurrent operations
**Files:** `rdm_dmx_async/transaction/transaction_manager.py`

`AsyncTransactionManager.get()`/`.set()` created a new `AsyncTransaction` on
every call **without passing an allocator**, so `AsyncTransaction.__init__`
fell back to `allocator or TransactionNumberAllocator()` — a **brand-new
allocator starting at TXN=1 for every single command**.

The RDM wire protocol has exactly one shared `ResponseCorrelator` per
`RDME120Protocol` instance, keyed only by transaction number
(`self._handlers: dict[int, Future]`), globally, not per-device. Any two
concurrent commands (e.g. `BatchOperationService.query_all_device_labels()`,
`identify_all()`, `reset_all()`, `get_all_personalities()` — all of which use
`asyncio.gather()` across multiple devices) would very likely both allocate
TXN=1 as their first attempt. The second `register_handler(1)` call would
raise `CorrelationError("Handler already registered for transaction 1")`,
breaking one of the two concurrent commands.

`services/discovery_service.py` already does this correctly — it calls
`self._protocol.allocator.allocate()` directly, reusing the protocol's single
shared allocator instance. `AsyncTransactionManager` just never adopted the
same pattern.

**Fix:** `AsyncTransactionManager.__init__` now stores `self._allocator =
protocol.allocator` and passes it into every `AsyncTransaction` it creates,
so all in-flight transactions — across all devices — draw from one shared
pool of transaction numbers, matching how the correlator is actually scoped.

**Why this matters for your hardware session:** this bug specifically hits
concurrent multi-device operations (batch label queries, batch identify,
batch reset). Single-device sequential operations mostly worked by luck
(each fresh allocator only collides with *itself*, and only when truly
concurrent).

---

### 4. HIGH — Serial RX could stall forever on a single stray byte
**File:** `rdm_dmx_async/transport/frame_buffer.py`

`FrameBuffer.extract_frame()` only discarded a leading garbage byte once the
buffer exceeded `max_size` (1024 bytes):

```python
else:
    # No valid frame at start of buffer - discard one byte
    self._handle_overflow()   # only pops if len(buffer) > 1024!
    return None
```

If a single noise byte, partial frame remnant, or misaligned read ever
landed at the front of the buffer, and total traffic stayed under 1024
bytes, **the receive path would never recover** — `find_frame_length()`
would keep failing to match `buffer[0]` against the adapter's start marker
forever, and no further RDM/DMX responses would ever be parsed until ~1KB of
data piled up (and even then only one byte was discarded per overflow
check).

**Fix:** track the buffer length across calls. If no new bytes have arrived
since the last "no frame found" check, the byte at the front cannot belong
to a still-arriving frame, so it's discarded immediately. If the buffer grew
(more data may still be arriving to complete a valid frame), no byte is
discarded — this avoids the opposite regression of chopping the front off a
legitimate frame that's still being read in multiple chunks. The hard
`max_size` cap is kept as a backstop for continuous noise.

**Impact on your hardware testing:** this is the kind of bug that shows up
as "discovery/GET just stops responding after a while" with no obvious
cause, especially over long-running sessions or noisy USB-serial links.

---

### 5. HIGH — Public utility functions crash when used as documented
**File:** `rdm_dmx_async/utils.py`

`get_enttec_serial_uid()` and `get_enttec_widget_params()` both default
`adapter=None` and then do:

```python
if adapter is None:
    adapter = EnttecAdapter(use_mk2_protocol=True)   # missing required `port` arg!
```

`EnttecAdapter.__init__(self, port: str, use_mk2_protocol: bool = True)`
requires `port` positionally — this raises `TypeError` immediately. The
function's own docstring example (`uid = await
get_enttec_serial_uid("COM3")`) calling it with no adapter would crash
today. `NetworkManager.start()` happens to always pass its own adapter
explicitly, which is why this was never hit through that path.

**Fix:** `EnttecAdapter(port, use_mk2_protocol=True)` in both functions.

---

### 6. MEDIUM — RDM window pause could permanently freeze DMX output
**File:** `rdm_dmx_async/scheduling/dmx_scheduler.py`

```python
async def pause_for_rdm(self, duration_ms):
    self._rdm_pause_event.clear()
    await asyncio.sleep(duration_ms / 1000.0)   # <- cancelled here...
    self._rdm_pause_event.set()                  # <- ...never runs
```

`RdmRequestWindow.execute_in_window()` deliberately cancels this task early
when the RDM operation completes before the window's full duration:

```python
finally:
    if self._scheduler and not pause_task.done():
        pause_task.cancel()
```

Cancelling `pause_for_rdm` mid-`sleep` raises `CancelledError` right through
the `await asyncio.sleep(...)` line, skipping `self._rdm_pause_event.set()`.
Once that happens, `DmxFrameScheduler._schedule_loop()` — which `await
self._rdm_pause_event.wait()`s before every frame — blocks forever, and DMX
output never resumes.

**Fix:** wrapped the sleep in `try/finally` so the event is always re-set,
even on cancellation.

**Note:** `DmxFrameScheduler`/`RdmRequestWindow` are exported publicly
(`rdm_dmx_async.DmxFrameScheduler`, `RdmRequestWindow`) and are now wired
into `NetworkManager`/`RDME120Protocol` — see finding B below.

---

### 7. LOW — Off-by-one in minimum-packet-size check
**File:** `rdm_dmx_async/packets/decoder.py`

`decode_rdm_response()` checked `len(data) < 25` before parsing, but the
real minimum valid RDM response (24-byte header + 0-byte PD + 2-byte
checksum) is **26 bytes**. A 25-byte input passed the initial check, then
failed deeper inside the `try` block and raised `PacketDecodeError` instead
of cleanly returning `None` for "not a valid/complete response" the way
every other undersized/malformed input does.

**Fix:** changed the guard to `< 26`.

---

### 8. LOW — `get_dmx_startup_mode()` silently discarded the real value
**File:** `rdm_dmx_async/services/device_apis/dmx_modes.py`

```python
value = struct.unpack(">H", bytes(response_data[:2]))[0]
mode = int(value == 1)   # collapses every value except 1 down to 0
```

`set_dmx_startup_mode(mode)` sends the actual integer mode to the device,
but `get_dmx_startup_mode()` mapped every response value other than `1` to
`0`. Round-tripping `set_dmx_startup_mode(2)` followed by
`get_dmx_startup_mode()` returned `0`, not `2` — silent data loss for any
device with more than two startup modes.

**Fix:** return the actual unpacked 16-bit value.

---

## Findings documented — updates

### A. [FIXED] Two independent, mutually-inconsistent Manchester DUB decoders
- `rdm_dmx_async/protocols/manchester_codec.py::ManchesterDiscoveryDecoder` —
  **used in production** by `RDME120Protocol.send_discovery_command()`.
  Decodes each UID byte from a *byte pair* using bitwise AND
  (`manchester_data[i] & manchester_data[i+1]`).
- `rdm_dmx_async/packets/decoder.py::PacketDecoder.decode_discovery_response()`
  / `_decode_manchester()` — **was dead code, not called anywhere in the
  production path** (only from its own unit tests). It decoded UID bytes
  from 16-bit words using an entirely different bit-interleaving scheme.

Both had their own passing unit tests, but only because each test built
its input using the *same* (mismatched) encoding assumption as the code
under test — the tests were self-consistent, not cross-validated against
each other or against real hardware captures.

Since only `ManchesterDiscoveryDecoder` was on the live discovery path, this
wasn't actively causing bugs, but it was a landmine: `PacketDecoder`
(`packets/decoder.py`) is part of the documented public API surface
(`PacketDecoder` is re-exported from the top-level package) and its
discovery-decoding methods looked production-ready but implemented a
different (and unverified against real hardware) algorithm than the one
actually used.

**Action taken:** deleted `decode_discovery_response()` and
`_decode_manchester()` from `PacketDecoder`, and their matching tests
(`TestDecodeDiscoveryResponse` and its `_encode_manchester_byte`/
`_build_discovery_frame` helpers) from `tests/test_packet_decoder.py`. Left
the `RDMDiscoveryResponse` dataclass (`packets/rdm.py`) and its public
export in place, since it's a plain data type, not itself buggy — it's just
no longer constructed by the library (removing a public export was out of
scope for this cleanup).

### B. [FIXED] Scheduling layer (`scheduling/dmx_scheduler.py`, `scheduling/rdm_window.py`) is unwired
Per `docs/ARCHITECTURE.md`'s own "Next Steps" section, this was already
known-incomplete. Confirmed by reading the code: `DmxFrameScheduler`'s frame
loop never actually calls `transport.send()` (`# TODO: Send frame via
transport`), and `NetworkManager.send_dmx()` bypasses the scheduler/window
entirely, sending frames directly. There is currently **no bus arbitration
between continuous DMX output and RDM request/response windows** beyond
whatever implicit serialization the transport's single TX queue provides.
If you run `send_dmx()` in a tight loop while also doing RDM discovery/GETs,
there's no guarantee of ANSI E1.20-compliant break/MAB spacing around RDM
requests — they're just interleaved in the TX queue. Worth checking during
your hardware session if you do simultaneous DMX+RDM traffic.

**Action taken:**
- `DmxFrameScheduler` gained a `send_callback` constructor param and
  `_schedule_loop()` now actually calls it instead of leaving the
  `# TODO: Send frame via transport` gap — the class is no longer
  non-functional if used standalone.
- `RdmRequestWindow.execute_in_window()` had a latent bug fixed: it paused
  DMX for a hardcoded `DEFAULT_WINDOW_MS` (10ms) regardless of the caller's
  `timeout_ms`, so DMX would auto-resume mid-operation for any RDM round
  trip longer than 10ms. Now it pauses for the full `timeout_ms`, relying on
  the already-fixed early-cancel-on-completion behavior in `pause_for_rdm()`
  to resume DMX immediately once the operation actually finishes rather than
  waiting out the full window. (This class still isn't called from
  production code — `RDME120Protocol` implements the same
  pause/cancel-early pattern directly, see next point — but the bug is fixed
  for anyone who does use it.)
- `RDME120Protocol` gained an optional `dmx_scheduler` constructor
  parameter. `_send_and_receive()` and the DISC_UNIQUE_BRANCH branch of
  `send_discovery_command()` now pause the scheduler (bounded by the
  operation's own `timeout`) around the send+wait, so continuous DMX output
  and RDM requests no longer just interleave arbitrarily in the transport's
  TX queue. This preserves the exact existing `ProtocolTimeoutError`
  exception contract (no new timeout/exception layer was introduced).
- `NetworkManager.start()` now creates a `DmxFrameScheduler` and passes it
  to `RDME120Protocol`. Its background refresh loop is **lazily started on
  the first `send_dmx()` call** rather than unconditionally — starting it
  unconditionally was tried first and measurably slowed down RDM-only
  discovery on real hardware (continuous background DMX frames on the
  shared serial line interfered with RDM timing), so it's off until a
  caller actually sends DMX. `send_dmx()` still sends the given frame
  immediately (preserving current one-shot-call behavior relied upon by
  README.md/DMX_QUICK_START.md/DMX_TROUBLESHOOTING.md and the example/
  hardware-test scripts that manually loop it), but now *also* updates the
  scheduler's buffer so output keeps being refreshed automatically
  afterward — additively closing the documented "Sends only ONCE!" gotcha
  without breaking existing callers.
- Verified on real hardware: with no `send_dmx()` call, `discover_devices()`
  still completes in ~3s (unaffected). After calling `send_dmx()`, the
  scheduler visibly refreshes frames every ~25ms in the background while
  concurrent `batch.query_all_device_labels()` and `batch.identify_all()`
  calls complete correctly and quickly.
- All 84 tests still pass.

### C. [FIXED] `TransactionNumberAllocator` and `ResponseCorrelator` naming collision
There were **two unrelated classes named `ResponseCorrelator`**:
- `rdm_dmx_async/protocols/response_correlator.py::ResponseCorrelator` — matches
  futures to incoming wire responses (protocol-level, one shared instance).
- `rdm_dmx_async/transaction/correlator.py::ResponseCorrelator` — classified a
  response as ACTIVE/LATE/ANOMALOUS for retry bookkeeping (transaction-scoped,
  one new instance per `AsyncTransaction`).

Both were correctly instantiated for their own separate purposes (this was
not a bug — the fix in item 3 above only concerned `TransactionNumberAllocator`,
not these), but the identical class name across two modules was a
maintainability trap.

**Action taken:** renamed `transaction/correlator.py::ResponseCorrelator` →
`LateResponseClassifier` (via language-server rename, updating all
imports/usages in `transaction/__init__.py`, `async_transaction.py`, and the
class definition itself). `protocols/response_correlator.py::ResponseCorrelator`
is untouched. All 84 tests pass after the rename.

### D. `DMXKingAdapter` is a stub
Every method raises `NotImplementedError`. This matches the README
("DMXKing adapter types are present as extension points, but their framing
implementation is not yet complete") — not a bug, just confirming it's not
secretly broken silently; it fails loudly and immediately if selected.

---

### 7. Transaction/retry layer + frame-buffer corner-case audit
**Files:** `rdm_dmx_async/transaction/async_transaction.py`,
`rdm_dmx_async/transaction/result.py`, `rdm_dmx_async/transport/frame_buffer.py`

Prompted by the question "what if the middle byte comes late / is there a
serial timeout / does the transaction layer actually work / do the
integration tests cover real scenarios", a full audit of these layers plus
new regression tests turned up:

**Bug fixed — `NAKReason.UNKNOWN_PID` (value `0`) silently bypassed the
permanent-failure short-circuit.** `AsyncTransaction.execute()` had
`if nak_reason and self.policy.is_permanent_failure(nak_reason):` — since
`NAKReason.UNKNOWN_PID == 0`, Python treats it as falsy, so this check was
skipped whenever a device responded with the single most common NAK reason
("I don't support this PID"). Instead of failing fast, every such GET/SET
would burn through all `max_attempts` retries (each waiting the full
`timeout`) before finally giving up — for `STANDARD_POLICY` that's up to 3x
the timeout wasted per query for parameters a device simply doesn't support.
Fixed by checking `nak_reason is not None` instead of truthiness. The same
falsy-zero mistake also existed in `Attempt.__str__` and
`TransactionResult.nak_reasons` (both cosmetic/reporting only) and was fixed
there too. Caught by `tests/test_async_transaction.py::TestPermanentFailure::test_permanent_failure_nak_short_circuits_retries`,
which failed against the original code before the fix.

**Fixed — `FrameBuffer` couldn't fully clear leading garbage in two cases.**
Two real, verified-by-test gaps in the garbage-discard heuristic, both now
fixed in `frame_buffer.py`:
- Once the stall-detection discard shrank a run of leading garbage down to
  fewer than 5 bytes (the hard-coded minimum frame size), `extract_frame()`'s
  early-return (`if len(buffer) < 5: return None`) bypassed the discard logic
  entirely, so the last few garbage bytes got stuck until more data arrived
  to push the buffer back over the 5-byte floor. Fixed by having the
  early-return path still advance the same stall-tracking/discard logic
  (factored into `_advance_stall_tracking()`), just skipping the frame-length
  lookup itself.
- If unrelated valid traffic kept arriving right behind a leading garbage
  byte (rather than the link going genuinely idle), the stall check
  (`len(buffer) == stalled_length`) never fired because the buffer kept
  growing — recovery depended entirely on the 1024-byte `max_size` overflow
  cap. Fixed by adding `_find_resync_offset()`: before falling back to the
  stall check, scan forward for a complete, recognizable frame already fully
  present at a later offset in the buffer; if found, the garbage before it is
  provably garbage (a real frame can't start mid-noise) and is discarded
  immediately, without waiting for growth to stop.

Both fixes are covered by `tests/test_frame_buffer.py`
(`test_stalled_garbage_below_minimum_frame_size_still_fully_clears`,
`test_growing_garbage_is_resynced_once_a_valid_frame_follows`), plus a
retained test confirming the overflow cap still backstops the case where no
valid frame ever resumes (pure, unrecoverable noise).

**Confirmed working — partial/fragmented delivery, at both layers.** New
tests prove a frame split across multiple `FrameBuffer.append()` calls (down
to one byte at a time) assembles correctly
(`tests/test_frame_buffer.py::TestPartialFrameArrivesOverTime`), and — more
importantly — a real RDM response frame split across two separate serial
`read()` calls (simulating slow UART pacing) is still correctly parsed
end-to-end through `AsyncSerialTransport` + `RDME120Protocol`
(`tests/test_serial_transport_e2e.py::test_response_split_across_multiple_reads_is_still_parsed`).

**Confirmed working — serial-level timeout.**
`AsyncSerialTransport.receive(timeout=...)` correctly raises `TimeoutError`
when no data arrives in time, and returns promptly when data does arrive
before the timeout (`tests/test_serial_transport_e2e.py::test_transport_receive_times_out_with_no_response`,
`..._returns_once_data_arrives_within_timeout`) — this is independent of and
in addition to the existing protocol-level `ProtocolTimeoutError` coverage.

## Files changed in this pass

| File | Change |
|---|---|
| `rdm_dmx_async/protocols/rdm_e120.py` | `send_discovery_command()` now raises `ProtocolTimeoutError` on a true no-response instead of collapsing it to `None` (same value used for genuine collisions) |
| `rdm_dmx_async/services/discovery_service.py` | Updated stale comment now that no-response/collision are distinguishable; no logic change needed (existing exception handler already does the right thing once the protocol layer stopped hiding the distinction) |
| `rdm_dmx_async/application/batch_operation_service.py` | Fixed 4 calls to use correct sub-API methods (`device.control.*`, `device.dmx_config.*`) |
| `rdm_dmx_async/transaction/transaction_manager.py` | Share `protocol.allocator` across all transactions instead of a fresh allocator per call |
| `rdm_dmx_async/transport/frame_buffer.py` | Fixed RX stall on leading garbage byte; added stall-detection instead of only discarding on 1024-byte overflow; removed unused dead `_consume_frame()` method |
| `rdm_dmx_async/utils.py` | Fixed `EnttecAdapter` construction missing required `port` arg in two default-adapter code paths |
| `rdm_dmx_async/scheduling/dmx_scheduler.py` | Wrapped `pause_for_rdm`'s sleep in `try/finally` so cancellation can't permanently freeze the DMX pause event; added `send_callback` and made `_schedule_loop()` actually transmit frames (finding B) |
| `rdm_dmx_async/scheduling/rdm_window.py` | Fixed `execute_in_window()` pausing DMX for a hardcoded 10ms instead of the caller's `timeout_ms` (finding B) |
| `rdm_dmx_async/protocols/rdm_e120.py` | Added optional `dmx_scheduler` param; `_send_and_receive()`/DUB branch of `send_discovery_command()` now pause it around wire operations (finding B) |
| `rdm_dmx_async/application/network_manager.py` | Creates a `DmxFrameScheduler`, passes it to `RDME120Protocol`, lazily starts its refresh loop on first `send_dmx()`, and has `send_dmx()` also update the scheduler buffer for continuous refresh (finding B) |
| `tests/test_dmx_scheduler.py` | New: 17 unit tests for `DmxFrameScheduler` (buffer get/set, loop start/stop idempotency, send-callback invocation and error tolerance, `pause_for_rdm` pause/resume and cancel-safety) |
| `tests/test_rdm_window.py` | New: 10 unit tests for `RdmRequestWindow` (`execute_in_window` timeout/pause behavior including a regression test for the fixed hardcoded-10ms-window bug, `request_window`, window-lock serialization) |
| `rdm_dmx_async/transaction/async_transaction.py` | Fixed `NAKReason.UNKNOWN_PID` (falsy `0`) bypassing the permanent-failure short-circuit (finding #7) |
| `rdm_dmx_async/transaction/result.py` | Fixed same falsy-zero bug in `Attempt.__str__` and `TransactionResult.nak_reasons` (finding #7) |
| `tests/test_frame_buffer.py` | New: unit tests for `FrameBuffer` covering partial/fragmented frame assembly, garbage-byte stall discarding, and the resync-offset fix for growing-garbage-behind-valid-data (finding #7) |
| `rdm_dmx_async/transport/frame_buffer.py` | Fixed leftover garbage below the 5-byte floor getting stuck, and growing garbage behind valid traffic no longer waiting on the overflow cap (added `_find_resync_offset()`) (finding #7) |
| `tests/test_serial_transport_e2e.py` | New: fragmented multi-read frame delivery test and two `AsyncSerialTransport.receive()` timeout tests (finding #7) |
| `tests/test_transaction_number_allocator.py` | New: allocate/release/wraparound/exhaustion tests for `TransactionNumberAllocator` |
| `tests/test_late_response_classifier.py` | New: `LateResponseClassifier` registration/classification tests |
| `tests/test_async_transaction.py` | New: retry/timeout/permanent-failure/late-response/allocator-release tests for `AsyncTransaction` and `AsyncTransactionManager` |
| `tests/test_retry_policy.py` | New: `RetryPolicy` validation and `is_permanent_failure()` tests, including the `UNKNOWN_PID` regression guard |
| `rdm_dmx_async/packets/decoder.py` | Fixed off-by-one minimum RDM response length (25 → 26 bytes); removed dead/duplicate `decode_discovery_response()`/`_decode_manchester()` (finding A) |
| `rdm_dmx_async/services/device_apis/dmx_modes.py` | `get_dmx_startup_mode()` now returns the real value instead of collapsing it to a boolean |
| `tests/test_rdm_e120_protocol_e2e.py` | Updated one test to match the corrected timeout/collision contract (`test_discovery_unique_branch_no_response_returns_none` → `..._raises_timeout`) |
| `tests/test_packet_decoder.py` | Removed `TestDecodeDiscoveryResponse` and its helper functions, which tested the now-deleted dead code (finding A) |

All 84 remaining tests pass after these changes
(`.venv\Scripts\python.exe -m pytest -q`; 88 minus 4 removed dead-code tests),
and bug #1 (discovery hang) plus the batch operation fixes (#2) were
additionally validated live against the user's connected ENTTEC interface +
RDM fixture: discovery completed in ~3s and found 1 device,
`batch.query_all_device_labels()` and `batch.identify_all(True/False)` both
completed correctly and concurrently.

## Suggested next steps (not done here — flagging for your decision)
1. Consider adding a fuzz/property-based test that feeds `FrameBuffer`
   randomized garbage+valid-frame interleavings to build more confidence
   beyond the current hand-picked scenarios.

## Hardware validation + `hardware_tests/` cleanup pass

Ran the retained/updated `hardware_tests/` scripts live against the user's
ENTTEC USB Pro Mk2 (COM5) + RDM fixture to confirm this session's fixes
(FrameBuffer resync/stall, `NAKReason.UNKNOWN_PID` permanent-failure fix,
`DmxFrameScheduler` wiring) hold up outside of fakes/mocks:

- `hardware_device_api_test.py --port COM5`: **22/22 passed**, including a
  real `NAK UNKNOWN_PID` permanent-failure (PID `0x51`, unsupported by this
  device) correctly short-circuiting retries instead of exhausting them.
- `dmx_output_test.py --port COM5`: all 4 static-payload sends passed.
- `dmx_continuous_output.py --mode simple --port COM5`: single `send_dmx()`
  call held the fixture on for the full duration via the background
  `DmxFrameScheduler`, then turned off cleanly.
- `dmx_discover_and_control.py --port COM5`: discovered the fixture, read its
  DMX address, held output, and blacked out correctly.
- `quick_device_test.py --test info --port COM5`: basic info fetch passed.
- Full `pytest -q --no-cov` suite: still 187/187 passing after these changes.

**Removed — `hardware_tests/hardware_test.py`.** Redundant with
`hardware_device_api_test.py`, which already exercises the same 16 API
modules (and does so more robustly, via dynamic capability detection instead
of a fixed test list). It also had a hardcoded `port="COM6"` with no
`--port`/auto-detect CLI support (unlike every other script here), and its
`run_with_context_manager()` demo path never actually discovered a device
(`devices = []`, dead code). Its three genuinely unique checks — parameter
cache hit/miss timing, `manager.batch.query_all_device_labels()`, and
invalid-address rejection/recovery — were ported into
`hardware_device_api_test.py` as `_test_caching_behavior()`,
`_test_batch_operations()`, and `_test_error_recovery()`. Porting that last
one over also caught that the original code called a nonexistent
`manager.query_all_device_labels()` (should be `manager.batch.query_all_...`)
— confirmed via Pylance and fixed in the ported version.

**Updated — `dmx_continuous_output.py` and `dmx_discover_and_control.py`.**
Both scripts pre-date the `DmxFrameScheduler` wiring (finding B) and manually
looped `send_dmx()` at a fixed rate to hold a static DMX level. Since
`NetworkManager.send_dmx()` now lazily starts a background scheduler that
keeps re-transmitting the last buffer automatically (~40 Hz), that manual
loop was dead weight (and the `--refresh-rate` CLI flags no longer did
anything meaningful). Simplified both to a single `send_dmx()` call followed
by `asyncio.sleep(duration)`. `dmx_continuous_output.py`'s `fade` mode was
left alone — it genuinely needs to keep pushing new (changing) values every
step, which is a different scenario than holding a static level.

**Updated — `dmx_diagnostic.py`.** This diagnostic tool's entire premise was
now factually wrong: it taught that a single `send_dmx()` call would only
make a fixture "flash briefly" and that a manual `while True` loop was
required for the light to stay on. Since finding B's fix, a single call now
holds the fixture on indefinitely via the background scheduler — the
opposite of what the tool claimed. Rewrote `test_single_packet()` (now
documents/expects the fixture staying ON), `test_continuous_transmission()`
(now demonstrates sustained output via one call, not a manual send loop),
and `show_solution()` (the old "WRONG pattern (will only flash)" is now
actually the recommended pattern; the old "CORRECT pattern" with a manual
`while True` loop is no longer necessary except when the DMX values
themselves are changing over time, e.g. fades/chases).
