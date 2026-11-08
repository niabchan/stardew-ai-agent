# Sunny Phase 2F — Windows HTTP.sys / HttpListener transport acceptance plan

**DESIGN ONLY · NOT EXECUTED · No sockets, Windows live tests, game launches, credentials or deployment.**

This plan describes a **future, separately approved** experiment on an isolated disposable Windows loopback test application. It is **not** a working transport adapter. Source baseline: PR #22 Draft branch at `31da033372b2a8586cd39ec0855550b23b41f7e0`. The checked-in legacy `AgentHttp` remains permissive. Every case in the [machine-readable manifest](../../reference/sunny_windows_http_acceptance/cases.json) is explicitly `not_run`: 50 required cases, including 17 blocker-priority cases. The expected outcome is a **future acceptance requirement**, not an observed HTTP status.

## The decision and three separate gates

**Question:** Can the selected Windows HTTP API supply trustworthy original target, Host, peer, header multiplicity, framing and bounded cancellation evidence **before** any protected authorization or game effects?

| Gate | What may happen | Exit proof | Not established |
| --- | --- | --- | --- |
| **G0 — Phase 2F now** | GitHub documents, case manifest and offline test of manifest invariants | Complete, independently reviewed **non-executed** plan | No Windows transport or security |
| **G1 — future, separate approval** | Temporary isolated Windows loopback test server, synthetic bytes only | Observed HTTP.sys vs listener metadata, bounded reads, cancellation/cleanup and trace ledger | No installed Sunny/SMAPI authorization |
| **G2 — separate runtime implementation and approval** | Real server/client + reviewed Windows/SMAPI acceptance | End-to-end C/O/A/H/R/V and P1 privacy/lease/epoch/coroutine controls | Cannot be inferred from G0 or G1 |

**G1 is NOT authorized by creating or reviewing this plan.** Obtain explicit operator approval for disposable test executable, fresh unused port and bounded synthetic traffic. Never access the existing Sunny listener/port, installed mod, saves, real user logs, OpenAI keys or game. Do not alter URLACL, firewall, port reservations or machine-wide settings without separate explicit permission. If elevated privileges are needed, stop.

## Audited existing sources — not changed in this PR

- [AgentHttp.cs](../../mod/StardewMCP/Agent/AgentHttp.cs) attempts localhost and 127.0.0.1 prefixes with localhost fallback. It uses `req.Url?.AbsolutePath.TrimEnd('/')`, wildcard CORS, unrestricted `Task.Run` per accepted context and unbounded `StreamReader.ReadToEndAsync`, plus legacy unscoped raw `/api/*`, debug/control, and host/P1 alias MCP routes. Its DELETE 200 does not prove quiescence.
- [Phase 2D route-grant reference](../../reference/sunny_p2_http_routes/README.md) is an **all-routes fake candidate** classification, not native credential validation or permission to expose P1 data.
- [Phase 2E ingress reference](../../reference/sunny_http_stream_ingress/README.md) tests bounded `MemoryStream` reads; it has no total time bound. Its one-byte EOF probe could hang on `HttpListenerRequest.InputStream` or fail to detect hidden pipelined bytes. The fake `Evidence.All` bits are supplied by tests, not Windows.
- [P2 server design](SERVER_AUTH_SESSION_EPOCH_CONTRACT.md) and [Phase 2C freeze/ordering](../../reference/sunny_p2_server_boundary/README.md) require atomic principal/grants/owner/host epoch/queue rechecks and game-thread step fences. P2 validated **owner presence** for first thinking freeze is distinct from tool-start contact and budget. P1 remains human.

## G1 prerequisites and testbed (none performed)

1. A disposable **minimal Windows-only server**, not `AgentHttp` or the game, with independently approved unused loopback port, separate synthetic client, recorded bound prefixes, OS/HTTP.sys/.NET versions and process instance. Keep concurrency low and payloads finite; do not execute unbounded fuzzing or stress another process.
2. Client records known **synthetic** sent bytes with a fixture ID and SHA-256. No bearer secret, personal content, P1 dialogue or game diary. Test handler records only sanitized observations: `HttpMethod`, `RawUrl`, `Url.AbsolutePath`, query, exposed header names/values and multiplicity, `ContentLength64`, `HasEntityBody`, `ProtocolVersion`, `RemoteEndPoint`, `LocalEndPoint`, bound listener, safe response status and lifecycle events. Fields absent/unprovable are labeled `unobservable`, **not inferred**.
3. Evidence must compare **sent bytes** with **what HTTP.sys rejected, forwarded, merged, decoded or hid**. Do not presume `RawUrl` is original bytes, `Headers` preserves duplicates, or a caller-supplied peer string proves socket identity. A kernel rejection can satisfy a *denial outcome* with independent evidence but **does not prove the application saw the raw malformed header**.
4. Synthetic instrumentation only: `handler_entered`, `auth_lookup`, `candidate`, `contact`, `queue`, `private_response_fields` and `cleanup_complete`. No game access. Every denied/unauthorized probe has zero protected effects and no private output.
5. Define abort and teardown before traffic: bound wall-clock ingress deadline, headers/body time, concurrency/backlog cap, transport-owned abort, observation of outstanding read completion, no early reuse of buffers and listener disposal. All numeric bounds below remain **TBD** pending separate design approval. No machine-wide changes.

## Outcome ledger: evidence, not status-code guessing

| Classification | Meaning | Gate |
| --- | --- | --- |
| `os_rejected_pre_handler` | HTTP.sys rejects before handler; trusted observations show no protected handler effects | May satisfy **denial** only, not raw-header fidelity |
| `adapter_denied_pre_effect` | Trusted adapter receives and denies before credential/data/contact/queue | May satisfy case after independent review |
| `authorized_test_candidate` | Explicitly approved synthetic probe reaches candidate-only test path | May satisfy its positive test; **never** real tool authorization |
| `ambiguous_transform` | Required raw Host/target/header/framing provenance hidden, normalized or merged | **BLOCK** selected adapter or redesign; never manufacture `Evidence.All` |
| `unexpected_candidate` | Unauthorized or ambiguous request reaches protected candidate | **FAIL** |
| `timeout_unaborted` | Deadline fires but read/task/connection remains pending or buffers could be reused unsafely | **FAIL** |
| `not_run` / `unobserved` | No accepted Windows evidence or unresolved result | **NOT PASS** |

A client-visible 400, 403, 408, 413, 500 or 200 **alone is not acceptance evidence**. Each case needs the layer of rejection, exact sent test bytes, exposed handler metadata, absence of protected side effects and cleanup outcome.

## Coverage families (all 50 cases required)

The [case manifest](../../reference/sunny_windows_http_acceptance/cases.json) is the source of case IDs and scenario definitions:

- **ENV / RAW:** disposable listener setup/teardown, raw request target versus parsed URL, percent/slash/dot/absolute form, ambiguous query, host/P1 alias.
- **HOST / HDR:** exact port and peer provenance, duplicated/case-varied Host/Origin/Authorization, obs-fold/control chars, forwarded spoof, browser cookies and native-only C/O profile, unapproved IPv6 alias.
- **FRM:** missing/equal/conflicting Content-Length, CL+TE and chunked, signed/overlong size, 16 KiB boundary, early EOF, visible extra bytes and pipelined/keepalive behavior. **FRM-12 measures the real InputStream boundary and EOF behavior; it does NOT endorse an extra-byte production probe.**
- **TIME:** slow-drip requests, hanging reads ignoring cancellation, stalled extra-byte read, disconnects, bounded concurrency and late completion cleanup.
- **AUTH / PRIV:** wrong/revoked instance credentials, separated C/O/A/H/R/V, atomic queue recheck, no unverified DELETE retirement, P1 consent and default-denied viewer/OBS.
- **COMP:** deliberate legacy `?breaks=1` / `?reply_within=1200` migration, P12 bedtime long action distinct from short ingress, validated owner presence while Luna thinks, never control P1.

The manifest's 17 `priority=blocker` cases are highlighted stop conditions; **all 50 must have reviewed outcomes**. Do not change its baseline `status=not_run` flags simply to show completion. G1 results belong in separately approved, dated evidence artifacts.

## Time/resource limits are deliberately not specified numerically

The design **requires** a finite **total monotonic ingress deadline** including slow/chunked input and a separately bounded cleanup phase; a timeout reset by every fragment is insufficient. Merely passing a `CancellationToken` or racing `ReadAsync` against a timer is not enough: the underlying transport read **must actually abort or complete**, and buffers must not be released/reused until their ownership is known.

**G1 signoff is blocked until these numerical limits are approved:** total ingress deadline, header idle deadline, maximum concurrent reads, backlog bound, abort/cleanup deadline and response size limit. The P12 bedtime **1200-second game-action** context is not a permissible HTTP request-read allowance; response deadline including queue wait and per-tool execution budget are distinct clocks. Do not set them equal without reviewed behavior/compatibility evidence.

For TIME cases, capture monotonic start, deadline, abort initiation, actual completion, outstanding-task count, buffer release and listener teardown. An ignoring stream that eventually returns 408 is **not** proof of an elapsed-time bound. Any unbounded pending I/O means **FAIL**.

## Unfilled per-case evidence template — NOT TESTED

```text
case_id:                 (e.g., FRM-03)
execution_status:        not_run
operator approval / date: none
OS / .NET / HTTP.sys / test server build: none
disposable bound process and test port: none
sent synthetic fixture ID + SHA-256: none
raw bytes / scrubbed trace location: none
observed HttpListener and HTTP.sys fields: unobserved
rejection layer (OS/handler/unknown): unobserved
response, handler, auth, candidate and effects counters: unobserved
monotonic read/deadline/abort/cleanup evidence: unobserved
reviewer, finding, remediation link: none
```

Never upload real secrets, actual P1 or game data, private logs, local paths or personal content as evidence.

## Hard stop and exit criteria

**G0 exit (this PR):** docs + manifest + offline validation pass and independent Codex review checks coverage, platform unknowns, deadlines and no unintended real testing. Any green CI from this PR means **plan structure validated**, not Windows acceptance.

**G1 start:** separate explicit user approval for the exact disposable Windows test app and port, traffic scope, caps and rollback. **G1 pass:** every required case has dated, independent transport evidence; 17 blocker cases conclusive; no unprovable mandatory original-wire field, protected-effect violation, unbounded read or cleanup failure. If Windows `HttpListener` cannot provide a required security property, reject that adapter and evaluate a different transport mechanism before any production wiring.

**G2 start/pass:** separate review/approval of all-route real credential issuance, immutable principal and grants, P2 server-owned lease/save epoch + atomic queue/game-thread admission, verified DELETE retirement and unknown effect journal, P1 consent-safe projection, safe browser/OBS, actual Luna client migration and Windows/SMAPI gameplay acceptance. **No merge to `main` or deployment** based on G0/G1 alone.

**Current state:** G0 plan only. G1/G2 not started. PR #22/#19/#10 stay Draft; Sunny/Luna installed game unchanged.
