# Sunny P2 offline HTTP/MCP adapter proposal

**Status: contract prototype only. Not production code. No network backend.**

This package creates outbound HTTP request descriptions and parses fake responses through a caller-supplied `exchange` callback. It has no built-in `urllib`, sockets, retry loop, file-system writes, process launch, or Stardew calls. It is **not imported** by the P10–P13 ZIP scripts or the C# mod and cannot control the game by itself.

The current C# server **does not** support the required game credential, meaningful P2 session ownership, or the proposed `X-Sunny-Save-Epoch` response header. Likewise, the proposed `/api/companion/v1/p2/safety` route is **not implemented**. All tests use synthetic credentials and responses.

## Why this prototype exists

The public PR #25 static audit reports that its privately supplied v0.3.11 ZIP talks directly to `http://127.0.0.1:8770/mcp/p2` from several modules without `initialize`, `Mcp-Session-Id`, or game-side authentication. It reads unscoped `/api/state`/feed and infers reload from observed state. Applying a fail-closed server security policy before migrating the client would break Sunny.

This adapter specifies a future **P2-only** connection: explicit loopback port (e.g. 8770 or 18770), independent local game credential, `initialize`, server-issued owner session, authoritative load epoch, no automatic mutation retry, and minimal authenticated P1-safety status rather than raw P1 private data. JSON-RPC ids are correlation only, not action deduplication. The calling application must supply an actually durable, duplicate-rejecting `claim_dispatch` journal before sending any mutation; this class only offers an in-memory second guard. If an action outcome becomes unknown, it blocks further mutations while still allowing status reads; it deliberately has no automatic replay or recovery method. A future controller must provide an externally reviewed evidence-based reconciliation flow.

## Test

From repository root:

```sh
python -m pytest -q mod/tests/test_sunny_transport_adapter.py
```

The repo's existing CI command `python -m pytest -q mod/tests reference/sunny_gift/tests` will also collect it. Tests perform no network I/O. Never supply a real key to the tests.

## Blocking work before integration

1. Inspect current installed controller revision and preserve its STOP/no-blind-retry behavior. Add an optional game URL (validated loopback), without changing existing live defaults until reviewed.
2. Decide and implement server-side authentication grants, header names, epoch/session lifecycle, typed errors, multi-day/reload cancellation, and safe long-lived bedtime actions. `X-Sunny-Save-Epoch` and the safety route here are **proposals**, not agreed shipped contracts.
3. Define the minimal Guy→Sunny safety projection, including active human P1, nearby/giver-waiting facts, without sharing raw dialogue, paths or diary; separate OBS/public replay access.
4. Add real adapter integration tests and concurrency tests, and only then stage a Windows/SMAPI build and a disposable Test_ save pilot by explicit operator approval.
5. Never copy the OpenAI Responses API key into the local MCP credential, put secrets in URL/CLI/logs/repo, or retry a mutation merely because its reply was lost.

No original v0.3.11 ZIP content is committed or reproduced in this reference implementation.

## Independent review changes (2026-11-07)

The prototype now reserves initialization before exchange. A lost initialize or
DELETE reply raises `OwnershipOutcomeUnknown` and blocks another initialize on
that object, including after `invalidate()`. Malformed handshake replies also
retain this fence. There is deliberately no lease-recovery API: bounded lease
expiry, authenticated recovery and retirement of running work need a server
contract and operator review. Constructing another object does not retire a lease.

Only empty-argument `status` can be classified as a read. Every other tool must
use the mutation path, even a future tool whose name is unknown. This is a
conservative client classification, not evidence that current server status is
free of contact/clock side effects. Concurrent and reentrant operations on one
adapter are refused rather than queued; a 1200-second bedtime call does not gain
a parallel shutdown/cancellation path.

A dispatch claim is reserved locally **before** the caller's journal callback.
If persistence commits and then raises, nothing is sent by this invocation and
all later mutations remain fenced. A successful callback is a caller assertion
that an atomic, durable, duplicate-rejecting claim has committed. This prototype
cannot verify fsync, database transactions or crash consistency. The journal must
bind owner, instance, epoch, tool, canonical arguments and attempt; on restart it
must reject reused attempts **and block new attempts while any earlier outcome
is unresolved**. A new adapter object alone cannot provide restart safety. Tests
use an in-memory synthetic journal, not a real durable-store proof.

All non-2xx mutation responses, including 401/403/409/429/503, preserve unknown
outcomes: no agreed pre-dispatch rejection proof is implemented. Read denials
retain HTTP classification; 401/403 stop future use of that object's credential.
A result-level tool error, malformed/duplicate JSON, invalid callback return,
lost response or epoch change also fences mutations. Successful tool
acknowledgment is still not observed effect or persisted-save evidence. The
adapter now deliberately **retains the unresolved-mutation fence even after
`isError=false`**: a second game action requires future separately reviewed,
authoritative effect reconciliation; it cannot be authorized by an ACK.
Release, reinitialize and epoch changes never clear an unresolved mutation.

Header lookup is case insensitive and rejects case-variant duplicates. Session
requests include the **proposed** epoch header as a precondition as well as
requiring it in responses. Server enforcement must check this before effects and
at later game-thread/coroutine boundaries; a client response check is too late to
prevent execution in the wrong world. The adapter does not implement full MCP
negotiation, `notifications/initialized`, SSE, batches, lease renewal, server
cancellation, discovery or a network backend.

The safety JSON adds **proposal-only** `p1Consent: bool`. Denial is exactly
`{"epoch":"synthetic-epoch","p1Consent":false}`. A consented projection requires
all seven boolean safety facts (`ready`, P1/P2 roles/activity, proximity and
`giverWaiting`); optional day/time must be nonnegative integers. Missing or
wrongly typed facts cannot become truthy defaults. This marker is not a consent
mechanism: the future server must verify a separately scoped human consent grant,
filter before serialization, and handle revocation. A caller must use fresh
prompt/offer identity before `respond`; these coarse facts do not prove which
menu is open, and do not authorize automatic acceptance or speech.

Port choice is explicit and never falls back between 8770 and 18770.
The constructor now accepts only canonical lowercase `http://localhost:PORT` or
`http://127.0.0.1:PORT`, with an optional trailing slash removed once. It
rejects IPv6, alternative numeric host forms, userinfo, paths, redirects encoded
as URLs, queries, fragments, leading-zero ports and whitespace. This is
**syntax validation only**: there is no network backend, trusted provisioning,
DNS/peer verification, proxy/redirect enforcement or server authentication.
An epoch mismatch fences a connected session; an opaque epoch alone cannot
authenticate the intended instance on first contact. Actual address resolution,
listener identity, redirects and credential delivery remain future backend
obligations.
The constructor accepts an opaque synthetic game token; it cannot determine
whether a caller has improperly supplied a model key. Credential provenance and
separation require independently reviewed provisioning, with no real key access
in this review.

See [REVIEW.md](REVIEW.md) for source provenance, findings and validation limits.

## DELETE retirement remains fail-closed (PR #26 blocker)

Every attempted DELETE retains ownership uncertainty and disconnects locally.
A 2xx response raises `OwnershipOutcomeUnknown`, including legacy bare 200,
202/204, epoch-only responses and even matching, quiescent-looking acknowledgment
bodies. No retirement acknowledgment schema or verifier is approved or implemented;
the adapter intentionally accepts none. Lost responses raise the same ownership
error; malformed responses and HTTP denials retain their existing classifications
while also keeping the ownership fence. There is no automatic DELETE retry.

`invalidate()`, a repeated disconnected `release()`, and observed epoch changes
cannot clear this fence. New initialization and tool calls on this object remain
blocked. Release also preserves unresolved mutation state and all dispatch claims.
Creating a new object is not recovery: callers still require durable per-owner/epoch
claims and a global unresolved-operation barrier across restarts.

A future independently reviewed server-side recovery flow must define authenticated
owner+session+epoch-bound retirement evidence and the disposition of queued/running
mutations (quiescent retirement or separately fenced cleanup). It must not clear an
unresolved mutation merely because ownership was retired. The current C# DELETE
returns 200 without owner teardown; neither it nor this fake proves server safety.


## Offline crash-persistent pending barrier (next G0 slice, **not Controller wiring**)

`durable_pending.py` is a small **real SQLite-on-disk** companion to the
existing injected fake `GameTransport`, not another simulated action planner.
Tests use temporary local SQLite files and fake exchange callbacks only. The
user's private v0.3.10 scripts, SMAPI, game, installed DLL and API are never
opened or contacted.

- **Explicit first provision:** `PendingLedger.initialize_new(absolute_path)`
  creates a file exclusively; a second call fails rather than replacing it.
- **Restart:** `PendingLedger.open_existing(absolute_path)` requires the
  *same existing DB*. Missing, corrupt, redirected or incompatible databases
  STOP rather than silently recreating empty operation history.
- **Write-ahead claim:** `reserve(PendingClaim(...))` uses a SQLite
  `BEGIN IMMEDIATE` transaction with `synchronous=FULL`, committing **one
  singleton unresolved operation** before the caller's fake exchange may
  attempt an effect. Any prior pending operation blocks every later attempt,
  including a *different attempt ID, owner or epoch*, even after a new
  process opens the DB. No `clear` API exists: even positive tool ACK, DELETE,
  a changed epoch or manual file/owner labels **cannot** reconcile the effect.
- **Confidentiality:** the DB stores only bounded caller-supplied opaque
  identifiers, tool name and SHA-256 of canonical arguments, **never raw
  arguments, P1 dialogue, model keys, bearer/session tokens or game logs**.
  Hashing is not a privacy/security boundary against inference; choose
  private identifiers and protect the actual DB from unrelated filesystem
  writers/readers.
- **Trust limit:** caller-provided instance/epoch/owner/operation strings
  are **not authenticated**; a journal row is not proof of source provenance,
  actual send, outcome or durable save effect. `claim_for()` receives only
  the adapter's attempt ID, **not** independently verified tool/arguments or
  a signed host identity. The eventual integration must bind these at the
  host boundary and audit the full private v0.3.10 call chain.
- **Platform/recovery limit:** SQLite uses a strong local durability
  configuration, and a subprocess test commits then abruptly exits, but
  tests **do not prove resistance to power loss, hostile file deletion,
  alternate DB paths, filesystem tampering, network shares, Windows file
  sharing behavior or independent STOP/queued-action retirement**. A future
  trusted runner must pin and protect one stable DB path before choosing any
  target, and implement independently reviewed reconciliation/retirement.
  Opening another new DB must not be used to bypass a pending row.

This slice deliberately **does not** modify the actual v0.3.10 controller or
automatically clear pending to support another game activity. The old
`reference/sunny_p11_journal_contract.py` remains the separate inert
provenance/shape classifier, **not** a crash-durable storage component.

Focused offline test: `python -m pytest -q mod/tests/test_sunny_durable_pending.py`.

Independent persistence review: SQLite connections use URI `mode=rw`, including
provisioning after exclusive file creation, so disappearance at open cannot
silently create an empty replacement. Ledger objects also check device/inode
identity before and after connecting and reject detected replacement. These
checks do not secure a directory against hostile writers or authenticate a
newly constructed ledger's path. Canonical argument objects require string keys
recursively; Python key coercion must not alias a distinct argument object.
Additional temporary-file tests exercise concurrent reservations and process
exit immediately before/after COMMIT and before a fake send. Pre-commit exit
leaves no reservation and no dispatch; post-commit exit leaves the barrier.
These remain process-crash tests on the test platform, not power-loss or Windows
validation. An explicit mismatched tool test demonstrates that the attempt-only
callback cannot authenticate the stored tool or arguments.
