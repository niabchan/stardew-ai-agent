# Sunny Phase 2I — Disposable Windows HTTP transport experiment specification

**G0 DESIGN ONLY · G1 START: NO-GO · NOT EXECUTED · NOT OPERATOR APPROVED**

This document specifies an evidence-oriented experiment to **review before** requesting permission for G1 Windows HTTP.sys / HttpListener testing. It is not a runnable server, test harness, Windows acceptance report, numeric signoff, or production change. **Do not start a listener, connect to another service, alter OS configuration, launch Stardew, access installed Sunny/Luna, or merge into main.**

Source baseline: Draft PR #22 compatibility/design branch at commit `83609912c36f20e8e7d4b325e749c0a4399d9b02`, including [Phase 2H NO-GO review](G1_READINESS_REVIEW.md), [Phase 2F 50-case acceptance plan](WINDOWS_HTTP_TRANSPORT_ACCEPTANCE.md), [Phase 2G proposed budgets](../../reference/sunny_http_resource_limits/README.md), and the actual unchanged [AgentHttp.cs](../../mod/StardewMCP/Agent/AgentHttp.cs).

The [non-executed experiment plan](../../reference/sunny_g1_experiment/experiment_plan.json) describes **37 one-to-one G1 cases**, each with a conceptual synthetic fixture and required observation fields, not sendable HTTP bytes. The [empty evidence template](../../reference/sunny_g1_experiment/evidence_template.json) is deliberately not a set of measurements. All 50 source acceptance cases remain `not_run` (37 G1 transport, 13 G2 game/credential/privacy/Luna). The **11 G1 entry prerequisites remain open** and Phase 2G numeric limits remain unratified. Completion of this G0 document PR is not authority to begin G1.

## Experiment objective and acceptance boundary

**Question:** Can a separately approved, disposable Windows loopback transport expose or enforce a trustworthy original request-target, Host, duplicate header and peer/framing boundary **and** bounded first-byte-to-ingress timing, actual abort, task completion and safe buffer release?

A small future test application should have **no access to Stardew, SMAPI, installed AgentHttp, the Luna client, user saves, personal data or production credentials**. It should expose no game command. Test output must be sanitized and attributed to independent client, kernel and listener observations. It cannot demonstrate actual P1 human consent, P2 controller lease, role/host epoch, game-step safety, viewer privacy or P12 bedtime compatibility (G2).

### G0 → G1 start, G1 completion and G2 remain separate

| Stage | What may establish readiness? | What remains unresolved? |
| --- | --- | --- |
| **G0 now** | Independently reviewed experiment design, conceptual fixture catalog, empty ledger and offline structural tests | No approval to bind a port; no Windows observation |
| **G1 entry — future explicit decision** | All **11 G1E** design/approval prerequisites independently closed: inspected test source, approved executable/endpoint inventory, bounded probe rates, separately ratified experiment limits, feasible independent stop and rollback, and a **new explicit operator approval** | No requirement to have already passed the future 37 Windows tests |
| **G1 exit — future measured evidence** | All **37 G1 transport cases** independently reviewed with actual Windows/HTTP.sys evidence and stop/unknown rules | Does not certify real Sunny or Luna security |
| **G2 — separate implementation** | Real all-route authorization and safe P1/P2/game/lifecycle/retirement tests, plus Windows/SMAPI and Luna migration | Requires separate permission and PR; never inferred from G0/G1 |

If the future team cannot design a safe way to measure raw provenance, pre-handler occupancy or stop a stuck read, **do not begin G1**. If the test method is feasible but actual Windows results are inconclusive, the measured case is **BLOCK**, not a pass. The G0 document does not preapprove any experiment.

## Proposed minimal component boundaries (interface sketch, NOT executable)

A source review of a future *isolated* testbed should identify equivalent interfaces with independently verified data ownership. The names here are design placeholders, not live .NET implementations:

```text
ISyntheticFixtureCatalog
  - Describe(caseId) -> fixture description + allowed endpoint set
  - IdentifyFixture(fixtureId) -> safe content hash + expected conceptual outcome

IClientWireRecorder
  - RecordAttempt(fixtureId, connectionAlias, intendedDisposableEndpoint)
  - RecordActualWrites(bytesConfirmedSent, monotonicTimestampSource)
  - RecordResponse(status, interimResponses, sanitizedHeaders, closure)

IWindowsTransportObserver
  - RecordKernelRejectionOrDelivery(if observable, with observation source)
  - GetPreHandlerFirstByteOrEnforceableEquivalent() -> Proven | Unobservable
  - GetQueueAndConnectionBounds() -> Proven | Unobservable

IListenerMetadataObserver
  - RecordRawUrlAsExposed / ParsedUrl / ProtocolVersion / HeaderValuesAsExposed
  - RecordRemoteAndLocalEndPointFromTrustedTransport()
  - MarkUnobservableForOriginalWireFieldsNeverActuallyExposed()

IAbortOwner
  - RequestAbort(requestId, scope=request|whole_listener)
  - ObserveActualReadTaskCompletion()
  - VerifyTransportQuiescenceAndBufferOwnership()
  - EscalateToIndependentOperatorStopIfStillPending()

IEvidenceWriter
  - ProduceSanitizedThreeLayerRecord(caseId, fixtureHash, observations, cleanup)
  - Never turn unknown/unobservable fields into "verified"
  - Never write tokens, P1 conversations, raw private data or game logs
```

**Critical limitation:** `HttpListenerRequest.Url.AbsolutePath` may be normalized and `RawUrl` or `Headers` may not preserve the complete original bytes or header multiplicity. `RemoteEndPoint` proves only the peer endpoint exposed by that transport API, not an arbitrary forwarded address. A client-side byte hash says what the client attempted, **not what HTTP.sys delivered to the handler**. Observations must say where each value originated. Synthetic `FakeHttpCaptureEvidence.All` from Phase 2E is not trusted evidence and must not be recreated by an adapter.

The underlying [legacy AgentHttp](../../mod/StardewMCP/Agent/AgentHttp.cs) currently uses broad unscoped endpoints and `Task.Run` / `ReadToEndAsync`. **Do not attach this experiment to it.** A successful G1 isolated candidate is never an authenticated game or private-data response.

## 37 conceptual probes — no sendable payloads or port addresses

The [plan](../../reference/sunny_g1_experiment/experiment_plan.json) maps each existing G1 case to an `FX-...` conceptual fixture, an expected **outcome class** and required evidence fields. Its scope includes:

- **ENV:** isolated launch/teardown design and wrong-instance negative probe. For `ENV-02` use an **offline simulated mismatch by default**, or a second explicitly authorized *disposable* endpoint. Never search for a free port by probing existing services or contact a running Sunny port.
- **RAW/HOST/HDR:** sent bytes vs parser/handler observations for encoded paths, Host ambiguity, duplicate/case-varied headers, spoofed peer values, Origin, cookies, malformed header lines, request versions and `Expect: 100-continue`.
- **FRM:** individual declared-length and Content-Length/Transfer-Encoding cases; 16,383 / 16,384 / 16,385 byte probes; premature disconnect; explicitly separate **valid pipelining** from malformed trailing bytes; never use one-extra-byte EOF read as a production framing guarantee.
- **TIME:** pre-`GetContextAsync` slow header occupancy and HTTP.sys queue delay, body trickle, read ignoring cancellation, late completion, independent stop, bounded concurrency and cleanup ownership.

The case catalog remains **a description**; it contains no actual raw request bytes, sockets, script invocations, credentials or network targets. A future G1 fixture implementation must be independently reviewed and mapped to the same case IDs. Reject arbitrary traffic generators or unconstrained fuzzing. Source results remain `not_run` until a separately authorized experiment.

### Outcome classes are not universal HTTP status codes

`deny_before_effects` permits an evidenced **kernel rejection before the handler** or a trusted adapter denial with zero protected effects. A kernel 400 alone does not prove the application's parser was safe. `authorized_synthetic_candidate_only` concerns allowed *isolated* probes; it does **not** allow queueing a game action. `measure_platform_behavior` means observations can be `unobservable` and cause BLOCK; it is not automatically successful just because an API returned something. `separate_requests_isolated` requires distinct request attribution, no principal inheritance. `bounded_abort_and_cleanup` requires observed abort and completion, not merely a 408, cancelled token or process exit.

## Three independent evidence layers, lifecycle, and privacy

Every future observation must separate:

1. **Client transmitted:** fixture identifier and hash, actual byte-write count, synthetic connection alias, intended approved destination and response/interim headers (scrubbed).
2. **HTTP.sys pre-handler:** directly observable kernel refusal/queue/first-byte information, **or the explicit value `unobservable`**. Never infer these fields solely from what a client sent or a handler saw.
3. **Listener exposed:** field name/value **as exposed** by the approved API, original-wire fidelity assessed separately, handler-entry counter, trusted transport peer vs client-supplied headers.

The [evidence template](../../reference/sunny_g1_experiment/evidence_template.json) also leaves slots for synthetic candidate/auth/contact/queue/private-field counters, a monotonic timeline, abort request and scope, **actual read-task completion**, transport quiescence, buffer ownership and operator stop. It contains only `null`/`not_run`/`unobserved` defaults. **Do not fill it inside this PR**. Future evidence belongs in separately reviewed sanitized artifacts, with any missing field explicitly labeled as unknown.

No actual provider token, native bearer secret, P1 dialogue, diary, private log, installed game path, human-identifying metadata or unredacted Authorization/cookie header should enter a GitHub PR. Avoid personal location or game-save data entirely. Record a reproducible fixture hash instead of reproducing sensitive inputs.

## Timing, resource limits and the independent stop path

The Phase 2G candidate profile suggests **8s first-byte anchored total ingress / 2s header / 5s body / 2s abort-and-cleanup**, 16 KiB request, 256 KiB response and **32 held slots (28 general + 4 recovery)**, 8 per authenticated principal, 4 unresolved aborts and backlog 16. All remain **unratified**. The G1 entry reviewer must choose or reject exact finite limits **before binding any port**, including response write, pre-auth connections, HTTP.sys queue occupancy and process-level abort. The separate 95s normal response and 1200s P12 bedtime game-action budgets do **not** extend the short HTTP ingress budget.

Pre-handler slow headers and queue wait begin before `GetContextAsync` hands a request to .NET. Starting a stopwatch there does **not** enforce the whole budget. An uncooperative `ReadAsync` that ignores cancellation may remain alive after a timeout. A test-method proposal must identify a verifiable transport-owned abort, a finite cleanup deadline, held-slot and buffer quarantine semantics and an operator-owned stop **outside the listener** even if all request/recovery slots are saturated. If safe pre-handler limits or independent stop cannot be designed without forbidden OS-wide changes, the G1 entry decision remains **NO-GO**.

Future emergency stop sequence must be independently reviewed: **stop new synthetic traffic → latch halt → invalidate collateral candidates → request scoped abort or listener shutdown → quarantine unresolved buffers → independently observe task completion/teardown → manual rollback and require new explicit restart approval**. A whole-listener abort may interrupt unrelated *synthetic* requests; this collateral must be recorded. Process termination can be a last-resort stop **only if separately approved**, and does not itself prove individual cleanup or a passed case.

## Review checklist and explicit hard stops

Prior to asking for new G1 approval, the owner/reviewer should be able to name the exact disposable executable source/build hash and signed permission, every approved endpoint/process, finite traffic fixture set, experiment-specific numerical caps, client/server evidence schema, Windows observation feasibility, loss-of-provenance fallback, independent stop owner and escalation route, no-OS-change/rollback steps, and sanitized evidence handling.

**Stop / NO-GO conditions:** any unknown port or running service; P1/game data; unapproved URLACL/firewall/elevation; inability to bound pre-auth headers/queue; missing first-byte provenance without a reviewed equivalent; unresolved read/abort cleanup; unknown buffer ownership; unexpected synthetic protected candidate; private response; failure to shut down; or operator stop not available independently of the test listener. Repeated runs require a **new explicit approval**, never an implicit restart.

This document is one **G0 design artifact**, not closure of all 11 Phase 2H readiness gates. The exact transport observation and numerical capabilities remain platform questions. A green Python CI only proves internal consistency of reference files. **Current decision: NO-GO for G1 start. G2 is separate.**
