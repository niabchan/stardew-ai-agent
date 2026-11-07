# Sunny — legacy HTTP/MCP security boundary (design draft)

> Status: **proposal / source review only**, 2026-11-07. No production security fix is implemented by this document. This draft does not approve external network access, new diagnostic evidence routes, or unattended gameplay. Parent: Design Review branch after PRs #17–#18. Guy = human P1; Sunny = AI P2.

## Why this is a separate workstream

The successful backed-up `Test_` pilot verified P2 diagnostic observation across repeated Title→Load cycles and one post-reload `/mcp/p2` `tools/call status` without P1 role takeover. It did **not** validate security of the legacy HTTP transport. Keep the working logical-seat fix separate from security changes and avoid hiding newly introduced behavior inside an Observation merge.

## Code-grounded current state

Reviewed on branch head `9f2cb29`:

- `mod/StardewMCP/Agent/AgentHttp.cs` registers `http://localhost:{port}/` and `http://127.0.0.1:{port}/` with `HttpListener` (fallback to localhost only). The handler assigns `Access-Control-Allow-Origin: *` to responses; there are no app-level bearer credentials, Origin allow/deny checks, or explicit peer/Host checks in that handler. Windows HTTP.sys URL registration and the observed TCP `::` listener do **not** by themselves prove off-machine reachability.
- `GET /api/state` returns an aggregate game snapshot, including host fields such as `saveFolder`, `logDir`, `money`, `energy`, `dialogue` and all active seat states. `/api/feed`, `/api/day`, `/api/memory` and `/api/briefing` return additional data. An operator's PowerShell projection can avoid printing this data, but **does not limit what the server sends**.
- `POST /mcp/pN` dispatches tool calls for AI seats; `POST /api/control`, `/api/release_freeze` and `/api/meta` can change runtime state. `EnableDebugApi=false` gates only `/api/debug/*`; do not treat it as a universal API security switch.
- `McpDispatcher.Dispatch` calls `IMcpSeat.MarkContact()` **even for** `initialize`, `ping` and `tools/list`. On the real seat this sets `Connected=true`, resets `TimedOut` and clears a released clock state; `WorldClock` may freeze time when the feature is enabled. Thus MCP discovery is **not passive**.
- P1 with resolved `Role=human` gets `404` on `GET /mcp/p1`; P2 with `Role=ai` gets `405` for GET. This role routing is important but is **not authentication**. It does not prove that all clients are authorized to operate P2.
- `DiagnosticObservation.HttpDisclosureEnabled` is reserved/inoperative. Its default `false` and `AllowHumanP1Collection=false` do not disable legacy HTTP read/write endpoints. `FakeEvidenceHttp` is a **test-only policy model**, not a live authenticated server.
- Live operator pilot config used local port `18770`, `EnableDebugApi=false`, P1 human, P2 AI / Brain none, P1 consent false, diagnostic disclosure false, and `FreezeTimeWhileThinking=false`. These are observations about the test configuration, not globally enforced defaults.

## Threat model and boundaries

**Protect:** human P1 privacy and control, P2 identity, save/log path metadata, diaries and chat, runtime control, local model credentials, save integrity. Prevent a third-party webpage, untrusted local process, LAN peer or unrelated automation from casually reading or driving the session.

**Attack surfaces:** browser cross-origin requests, DNS rebinding and misleading Host headers; local programs connecting to loopback; OS HTTP.sys URL ACL/binding behavior; accidental scripts hitting `/mcp/p1` or stale ports; unauthenticated API mutations and read endpoints; replay/feed endpoints containing authored or human-origin information.

**Explicit limitations:** Loopback-only routing and CORS headers are not authentication. Browser private-network restrictions vary. OS users/malware with access to the same local credentials or game process are outside the scope of a network-token-only defense. Do not claim a local token protects against same-user malware, nor claim remote exposure without an explicit network test.

## Proposed implementation gates (separate small code PRs; none authorized here)

### S0 — Endpoint/consumer inventory and baseline

1. Enumerate routes, exact HTTP methods, sensitive output fields, mutation effects and the consumers (in-game overlay/replay, external P2 controller, watchdog, runner, OBS).
2. Verify port-specific IPv4/IPv6 URL registration, peer and Host behavior on supported Windows/SMAPI, using only a backed-up test save; record minimal status codes, not full player payload.
3. Retain `/mcp/p1` rejection when P1 is human, P2 role binding, no P1 automation, and disabled debug routes. Record legacy compatibility tests before changing transport.
4. Document the difference between normal-game local API and any future `/api/evidence`; do not route raw diagnostic snapshots through the legacy endpoint.

### S1 — Fail-closed native request policy

1. Centralize method, path, authority/Host, remote-peer, Origin and payload-size validation **before any state read, runtime dispatch, or MarkContact**.
2. Default to loopback-only native callers, reject arbitrary browser Origin headers/cross-origin access and remove wildcard CORS for protected routes. Validate the actual `HttpListenerRequest`/HTTP.sys behavior on Windows, not just fake request strings. Do not trust forwarded headers.
3. Apply explicit allowlists for route methods and response types. Unknown/malformed/duplicate headers or invalid request shapes must fail without a tool call or state leak.
4. Test exact IPv4/localhost and IPv6 policy intentionally; avoid unreviewed wildcard prefixes, changes to global URL ACLs, LAN listeners or Windows Firewall.

### S2 — Authentication, authorization and privacy projection

1. Define a local operator-controlled, high-entropy credential provisioning and rotation scheme (never commit keys; never put secrets in URLs, log text, SMAPI console, game chat or screenshots). Specify filesystem/OS ACLs and recovery if the credential is unavailable.
2. Separate least-privilege grants: diagnostics metadata (not yet served), P2 MCP control, operator runtime control, logs/replay reads, and P1-sensitive reads. **Authenticated P2 MCP must not imply P1 authority**.
3. Prefer a minimum-fields status endpoint for test scripts rather than reading a full `/api/state` and filtering locally. Keep P1 dialogue, identifiers and raw Observation evidence out of ordinary P2 metadata.
4. Revocation/rotation must invalidate prior credentials and in-flight sessions safely; timeouts must not retry an ambiguous game mutation. Preserve explicit P2 logical-seat checks at game-thread dispatch time.
5. Decide deliberate compatibility behavior for existing runner/OBS tools before enforcing auth. Fail closed on missing credentials rather than silently enabling a legacy unrestricted fallback.

### S3 — MCP contact and clock semantics

1. Decouple `MarkContact` from `initialize`, `ping` and `tools/list` unless there is an explicit, documented reason those requests should count as P2 attachment. No discovery request should freeze or release clock state by accident.
2. Keep real `tools/call` per-seat authorization, active-seat checks and audited action/observation lanes. A `status` call may be read-only for gameplay while still mutating contact state under current code; acceptance must check both.
3. Establish a safe rejoin/session-expiry policy so a stale client cannot take control of a new save epoch or resume old actions after Title→Load.

## Required tests before any merge of implementation

- **Game-free:** fake HTTP denial matrix for no/wrong/expired/revoked credentials; wrong Host/peer/Origin, invalid IPv6, CORS, unexpected methods, malformed JSON, duplicate ambiguous query/headers, oversized bodies, unknown route, rate/connection limits; assert no sensitive response and **zero MarkContact/tool calls** on denial.
- **Seat isolation:** P1 human is never MCP-controlled, wrong-seat P2 credentials cannot access P1, no diagnostic P1 projection without explicit separate consent, no role mutation by observation or MCP discovery.
- **Protocol behavior:** allowed `ping`/`tools/list` are side-effect free for clock/contact; allowed P2 `tools/call status` has a response, no in-game move/item/save change, and correct P2 identity. Verify repeated same-process Title→Load and deny stale sessions.
- **Compatibility:** document and test external Luna client, native launcher/PowerShell, in-game overlay and replay, runner/watchdog; credentials passed via secure local configuration, not URL. Separate tests from production data and secrets.
- **Windows operator pilot:** supported full-mod build with automatic deployment disabled; isolated DLL and backed-up `Test_` save; verify HTTP status and narrow response projections only. No first test on the user's original farm. Stop on a role shift, unexpected freeze, uncontrolled move, or save alteration.
- **Documentation:** security limitations and tested/untested claims updated in `docs/api.md`, `docs/configuration.md` and PR descriptions. Do not claim production HTTP security from test-only policy fixtures.

## Suggested narrow PR order

- **Security PR-A (source/docs/tests):** endpoint audit plus native request policy and negative tests, without changing existing routes yet; design choice review before feature flags.
- **Security PR-B (runtime enforcement):** fail-closed policy + explicit credentials and route grants on local API, including compatibility with Python runner/overlay; operator-approved Windows build/test.
- **Security PR-C (MCP lifecycle):** make discovery not mark contact, enforce seat-bound session lifecycles, verify Title→Load and clock behavior.
- **Security PR-D (optional, later):** metadata-only, authenticated diagnostic HTTP evidence *only if actually needed*. Default remains off; raw P1 evidence is not in scope.

The order is a proposal: an implementation PR can split further if it would mix credential provisioning, auth enforcement and gameplay behavior. Never change `main` or auto-deploy as part of this design draft.

## Decision

**Current branch is not production-hardened.** Keep the existing PR #10 as Draft and working PR #17/#18 behavior intact. This document defines risk and acceptance criteria only; it neither grants permission to access other networks nor enables data disclosure.
