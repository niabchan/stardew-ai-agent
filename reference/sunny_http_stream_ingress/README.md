# Sunny Phase 2E — offline HTTP stream-ingress harness

**Status: test-only. No real `HttpListener`, sockets, authenticated transport, game, credentials or deployed security enforcement.**

This phase advances beyond Phase 2D's wholly materialized `FakeRouteRequest` by exercising a **real .NET `Stream.ReadAsync`** over synthetic memory streams, with conservative input gating and a handoff to the existing fake all-routes grant classifier. It does **not** prove that `HttpListenerRequest` can provide the raw evidence required by PR #28. No production source or test project configuration was modified; the new source is automatically included only by the xUnit test project.

## Files and purpose

- `mod/StardewMCP.Tests/FakeHttpStreamIngress.cs` — test-only `FakeHttpCapture` and `FakeHttpStreamIngress.ProcessAsync` pump using `Stream.ReadAsync`, caller-supplied cancellation, strict declared body-size limit (16 KiB), header/authority/frame checks before reading, and the previously reviewed Phase 2D `FakeAllRoutesBoundary.Check` at the end. Returns only a **candidate status** and non-sensitive synthetic route ID — no JSON response/body, operation ID, logging, contact or gameplay action.
- `mod/StardewMCP.Tests/HttpStreamIngressTests.cs` — memory-stream fragmentation, missing/duplicate/overflowing Content-Length, premature EOF, simulated trailing bytes, bad Host/Origin/peer, wrong instance/port, unsafe raw targets, bad method/body, cancellation, `IOException`, header snapshotting and credential revocation during a read.
- This README — precise statement of simulated properties, known omissions and a future isolated Windows/HTTP.sys acceptance gate.

No `AgentHttp.cs`, `SunnyP2Preflight.cs`, `McpDispatcher`, `AgentRuntime`, `ModEntry`, P1, Lua/Luna Python controller, installed mod, saves, `main` or PR #22 head were modified.

## Simulated request pipeline (NOT a deployment)

```text
synthetic FakeHttpCapture
  -> all fake provenance flags required
  -> preserve raw target (split ? without URL normalisation)
  -> copy raw header pairs (case-insensitive duplicate detection)
  -> reject Origin / Cookie / proxy or transfer framing headers
  -> require explicitly configured loopback Host, port and peer
  -> reject unusable native Bearer header (not credential verification)
  -> exact Content-Type for POST; strict one-value decimal Content-Length
  -> reject missing POST length or length >16KiB *before* reading body
  -> bounded Stream.ReadAsync loop with caller CancellationToken
  -> synthetic EOF check; deny early EOF or visible trailing bytes
  -> Phase 2D fake route/grant classifier checks strict JSON, instance/role
  -> only a further-validation CANDIDATE (never tool execution/data access)
```

**Notably:** preflight ordering alone is not a stable authorization or a source-backed proof of a true raw wire request. The fake `FakeHttpCaptureEvidence.All` flags are **assertions supplied by tests**; the fixture cannot derive or validate them from Windows kernel/HTTP.sys. A real API must establish equivalent facts from authoritative transport metadata, or reject the request. If the chosen listener API cannot prove a required fact (e.g., raw header multiplicity and original Host before normalization), the correct decision is *not* to manufacture `Evidence.All`.

## Why the one-byte test probe MUST NOT be copied into a real listener

The in-memory stream fixture exposes EOF after a fixed byte array. We probe one extra byte to detect visible extra data beyond declared Content-Length. Real HTTP request input streams may already terminate at the transport-framed request boundary, may hide pipelined bytes or may block awaiting an additional byte. A real `HttpListenerRequest.InputStream` cannot by itself prove original socket framing by seeking one more byte. Never use the fake EOF probe as proof against CL/TE smuggling, and never block the game/controller HTTP handling without a proven cancellation/deadline mechanism. A real adapter needs evidence of HTTP.sys framing rules, request-body length, transfer coding policy, peer/Host, and what headers were normalized or combined.

## Explicit security limitations

- Synthetic Host, peer, raw target, header multiplicity, framing evidence, configured port and instance are **caller-supplied test data**, not authenticated OS proofs. IPv6 and alternate loopback aliases remain unapproved. If underlying `HttpListener` cannot provide lossless raw target/Host evidence, evaluate an appropriate different transport API or conservatively reject; do not silently convert `Url.AbsolutePath` into evidence of original raw bytes.
- The harness returns **candidate-only** status from Phase 2D. It does not create, compare, retire, re-provision or persist a P2 session, credential generation, host epoch, role owner tuple, operation journal or stable reading snapshot. Unknown action outcomes remain unresolved. A fake token string is not a real provisioned game credential or the provider API token.
- No limits on connection concurrency, slow headers, socket duration, pipelining, response size, actual HTTP body deadline, per-client rate budgets or request-task creation. Cancellation is supplied by tests; a real caller must create a bounded cancellation policy and ensure the stream respects it. The fake `ReadAsync` test shows *one* well-behaved implementation, not protection against a hung Windows input stream.
- GET/DELETE synthetic body probes detect visible memory bytes but do not establish wire-level absence of bytes. `HttpListener` may normalize Content-Length or transfer encoding; the dedicated raw adapter still needs a verified framing and multiplexing contract.
- Operator POST schemas, debug tool effects, C/O consented P1 safety, browser pairing/CSRF, replay and viewer redaction/publication, watchdog projection, real native Luna v0.3.11 compatibility, P12 1200-second action and WorldClock freeze semantics are outside this phase. Legacy wildcard CORS, unauthenticated `/api/control` and raw reads **remain unchanged**.
- Fake `MemoryStream` tests do not exercise Windows HTTP.sys, `HttpListenerRequest`, a real TCP socket, SMAPI, the installed game or any user's data. The presence of `using System.Net` in test code is not network activity.

## Future isolated Windows adapter acceptance questions (not executed)

1. What exact bytes/metadata for raw request-target, path/query, Host, peer endpoint, duplicate headers and Content-Length/Transfer-Encoding does Windows `HttpListenerRequest` actually expose? Are any rejected or merged before the C# handler? Verify empirically on a temporary loopback-only test endpoint with explicit user/operator approval — **not** the running Sunny port.
2. Can caller-controlled Connection, Host, Expect, forwarded headers, CL/TE combinations, HTTP/1.1 pipelining, percent-encoding and duplicate Content-Length reach the application differently than the fixture? No claim of protection should precede those measurements.
3. Can the chosen adapter enforce 16 KiB and a short bounded wall-clock/read deadline without reading unlimited bytes or blocking a game-tick worker? Does cancellation actually abort blocked reads, or require listener shutdown?
4. Preserve PR #35's owner-present → thinking-freeze eligibility separate from actual tool-start; and PR #33's atomic owner/role/epoch/queue admission before any contact, timeout, stats/log or game effect. Do not wire Phase 2D/2E candidate status to a runtime dispatcher.
5. Before turning on any real HTTP security, protect **every legacy route** under explicit grants, establish real operator/health/replay/viewer identities, consent-safe projections, verified DELETE retirement and unknown-effect reconciliation; migrate Lua/Luna native client and run Windows/SMAPI operator acceptance.

## Validation and review

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

GitHub CI runs only the game-free projects. No real listener or save should be exercised. Independent Codex review should focus on timeout/EOF behavior, authority/path/header evidence trust, cancellation, concurrent mutation of test captures, negative cases and false assertions. Keep the PR **Draft and unmerged** pending that review. Any merge should target PR #22's **Draft design branch** only, never `main` or an installed DLL.
