# Sunny Phase 2L — Provisional Kestrel Transport Decision Design

**G0 SOURCE/DESIGN ONLY · G1 START: NO-GO · Kestrel: CANDIDATE, NOT SELECTED · NEVER AN AUTHORIZATION**

This phase answers a narrower question than Phase 2K: **What exact field-level evidence, resource ownership and abort/stop design would need to exist before Kestrel could even be considered as a separately approved disposable Windows G1 test variant?**

It does **not** implement a server, start a listener, select or probe a port, execute Windows HTTP traffic, change OS URLACL/firewall, inspect real user data, launch Stardew, alter the native Luna controller, deploy a mod or touch \`main\`. No game/SMAPI process, real credential, P1 dialogue or diary is involved.

The parent is [Draft PR #22](https://github.com/niabchan/stardew-ai-agent/pull/22) at commit \`36d90ae0e814f94cb7266ff789f90a3ef3477bff\`. Existing reviewed [Phase 2K four-transport comparison](G1_TRANSPORT_FEASIBILITY_MATRIX.md), [Phase 2J 11-blocker plan](G1_BLOCKER_RESOLUTION_PLAN.md), [Phase 2I future HTTP.sys experiment design](G1_EXPERIMENT_SPECIFICATION.md) and [Phase 2F 50-case plan](WINDOWS_HTTP_TRANSPORT_ACCEPTANCE.md) remain intact. **All 11 G1 entry prerequisites are OPEN**, all **50 original cases remain \`not_run\`** (**37 future Windows G1 transport, 13 separate Sunny/Luna G2**, 17 priority blockers), numerical limits proposed in Phase 2G are **unratified**, and there is **no operator approval to begin G1**.

## Preliminary architecture decision: investigate, but do not select

| Option | What the reviewed source supports | Still BLOCKING |
| --- | --- | --- |
| Existing \`HttpListener\` | Received request contexts and path/query \`RawUrl\` exposure | First-byte/pre-handler queue observability and enforcement, exact raw Host/header evidence, scoped abort and task cleanup |
| ASP.NET Core HTTP.sys | Kernel connection/queue/time options | \`HeaderWait\` **first-request exception**, resetting \`EntityBody\` idle timer and original-wire provenance |
| **Kestrel (Phase 2L candidate)** | Header-receive timeout, connection count and header/body limits, \`RawTarget\` and \`IHttpConnectionFeature\` | Full first-byte→body ingress clock, pre-auth queue/resource accounting, original rejected-wire provenance, actual abort/owned task completion |
| Custom raw TCP parser | Application receives bytes before custom parsing and could timestamp its own received stream | High-risk HTTP parser/framing/smuggling and complete connection/resource ownership; **not a recommended production shortcut** |

Kestrel has documented independent configuration controls: [\`RequestHeadersTimeout\`, \`MaxConcurrentConnections\`, \`MaxRequestBodySize\` and minimum data rates](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/servers/kestrel/options?view=aspnetcore-10.0). The [endpoint binding guide](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/servers/kestrel/endpoints?view=aspnetcore-10.0) distinguishes an explicit IPv4 loopback \`Listen(IPAddress.Loopback, ...)\` from \`localhost\` dual-stack and wildcard bindings. **None has been configured or run.** In particular, header timeout and data-rate controls do **not by themselves** prove a non-resetting total ingress deadline covering all pre-handler work.

Connection-cap review must include upgrades: upgraded connections leave `MaxConcurrentConnections` and use the separate `MaxConcurrentUpgradedConnections` limit. A future HTTP/1.1-only variant must explicitly prohibit upgrades or independently bound them, and still account for OS backlog. No such policy is implemented.

**API-version caution:** the linked public descriptions are primarily ASP.NET Core v10; the current game-free mod tests target .NET 6. A future isolated testbed may choose a specific supported version after separate review; do not infer interoperability, runtime support, user-machine requirements or behavior simply by copying examples. No package/build/port was selected here.

## Eighteen reviewed-*design* questions, not eighteen passed controls

The [field provenance manifest](../../reference/sunny_g1_kestrel_decision/field_provenance.json) defines **18 entries**, all with \`actual_windows_observation=false\`, \`approved=false\`, and verdict \`BLOCK_PENDING_REVIEW\`. Grouped by G1 entry requirement:

| Gate | Field range | Review question |
| --- | --- | --- |
| **G1E-03** | FIELD-01–03 | Header timer, first-byte/queue clock, immutable whole-ingress/body deadline |
| **G1E-04** | FIELD-04–07 | Pre-auth TCP connections, header caps, body limits/rate, accept/queue occupancy |
| **G1E-02** | FIELD-08–13 | \`RawTarget\`, Host/header values, parser-rejected CL/TE, peer provenance, browser/100-continue, pipelining attribution |
| **G1E-05** | FIELD-14–15 | Connection abort vs independently operable emergency stop |
| **G1E-06** | FIELD-16–18 | Observed read/write/callback completion, buffer/lease owners, bounded teardown and restart |

Four source-specific distinctions are particularly important.

### 1. The exact original-wire boundary

ASP.NET Core [\`IHttpRequestFeature.RawTarget\`](https://raw.githubusercontent.com/dotnet/aspnetcore/v10.0.0/src/Http/Http.Features/src/IHttpRequestFeature.cs) explicitly describes the **request target as sent without URL decoding**. The same feature's \`Headers\` groups values **by header name**, retaining distinct values across lines. But neither promise is equivalent to an authoritative byte-for-byte copy of original Host header name casing, spacing, line order or malformed CL/TE bytes discarded by a parser.

A later G1 evidence ledger must **never collapse three levels**: (a) synthetic bytes the test client attempted/wrote, (b) actual parser/server rejection or delivery, and (c) the feature values seen by the test handler. Missing original-wire evidence is \`unobservable\`, **BLOCK**, rather than reconstructed from a client trace or transformed URL. Real P1 or game-state data cannot appear in this experiment.

### 2. Pre-handler timing is not a middleware stopwatch

The source documents Kestrel's \`RequestHeadersTimeout\`, but does not establish that a handler/middleware timestamp is the true first-byte anchor, that all OS accept-backlog waiting is bounded, or that sending small body chunks cannot keep the whole request alive past a fixed deadline. The **Phase 2G candidate 8s total/2s header/5s body/2s abort-cleanup** and **32 total / 28+4 reserved slots** are not ratified; post-handler ticket counts cannot substitute for bounding pre-auth kernel/socket resources.

If a future reviewer cannot specify an enforceable equivalent whole-ingress bound and safe stop method, **block selection** rather than waive this requirement. Distinguish a reviewed method **before G1 entry** from actual behavior **measured only in a separately approved G1**.

### 3. Abort does not settle ownership of live work

ASP.NET Core [\`HttpContext.Abort\`](https://raw.githubusercontent.com/dotnet/aspnetcore/v10.0.0/src/Http/Http.Abstractions/src/HttpContext.cs) aborts the underlying connection; [\`RequestAborted\` behavior](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/use-http-context?view=aspnetcore-10.0) notifies cooperative tasks of cancellation. A 408/closed connection/aborted token or even an externally killed **test process** is not proof that every application read, write, callback or buffer owner reached an observed safe terminal state.

The [separate ownership and stop contract](../../reference/sunny_g1_kestrel_decision/stop_ownership.json) describes **eight resource/role groups** and requirements for a stop channel not dependent on Kestrel's HTTP request/recovery workers or the evidence writer. It requires a monotonic non-resetting stop deadline, collateral fencing (including completed body but uncommitted candidate), terminal read/write task observations, buffer/lease quarantine if ambiguous, and new manual approval before another test run.

The JSON flow lists design milestones, not blocking sequential steps. After the stop latch, sender shutdown and transport abort proceed independently. An external watchdog must escalate at the immutable deadline from **every nonterminal state**, even if sender acknowledgement, abort invocation, task observation or the evidence writer stalls. Missing observations yield `UNRESOLVED_QUARANTINED`; manual rollback and `CLOSED_NO_RESTART` preserve that outcome and its ownership ledger, never authorize buffer/capacity reuse or convert it to quiescence.

No stop operator, process, abort mechanism, execution time limit, externally operable control, or evidence recorder is implemented or approved by this PR. A state machine in JSON is **not** a runnable emergency stop.

### 4. Kestrel cannot inherit HTTP.sys acceptance by analogy

The **37 Phase 2F/2I G1 probes were formulated for an HTTP.sys/HttpListener boundary**. If a future design proposes Kestrel for an isolated test variant, it must undergo a **separate case-by-case expectation, instrumentation and provenance review**. Keep the original 37 entries unchanged and \`not_run\`. A Kestrel test cannot automatically check off an HTTP.sys-specific result. In either variant, the **13 G2 cases** remain separate real all-route, consent, epoch/lease, unknown-outcome, Luna/SMAPI compatibility work.

## Decision points and next safe action

**No-GO conditions for even choosing Kestrel:** no viable reviewed pre-handler ingress/queue bound; mandatory original-wire provenance lost without a safe equivalent denial boundary; insecure accepted Host/CL-TE ambiguity; unowned hanging read/write tasks or buffers; external stop dependent on a saturated listener; or any unexpected potential access to game/P1 state. Unknowns never silently become passes.

The next useful small **G0-only** review artifact should choose *one field-level design hypothesis* for Kestrel's initial first-byte/queue and complete-ingress control, with an explicitly parallel ownership/abort sketch. A reviewer may conclude that Kestrel is unsuitable and that a different isolated approach needs examination. That result is acceptable: **there is no requirement to choose Kestrel**.

Before G1 can start, **all 11 entry gates need appropriate independently reviewed design/approval evidence**, finite experiment-only limits, an approved source/build and disposable loopback setup, a safe independent stop and **new explicit operator consent for that exact run**. G1 exit would then require the reviewed actual results of the 37 *applicable* Windows transport cases; G2 must independently cover Sunny/Luna runtime, P1 consent and all-route authorization.

**Status at close of this document: \`NO_GO_G1_START\`. This is an inert G0 candidate decision design, not a Kestrel selection, an executable program, a Windows result or a change to installed Sunny.**

The offline guards pin the complete reviewed semantic manifests and inherited readiness/case/limit artifacts, reject duplicate JSON keys, and exercise nested claim, source/case binding, unknown-key and stop-policy mutations. Pins detect drift; they are not signatures, authentic CI evidence, operator consent or proof of Windows behavior. Coordinated edits to the tests themselves still require independent review.
