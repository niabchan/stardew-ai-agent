# Sunny Phase 2K — Windows transport feasibility and independent stop (G0)

**OFFLINE SOURCE REVIEW ONLY — transport not selected — G1 START NO-GO.** This phase performs **no listener creation, socket traffic, Windows probe, OS change, credential work, real game launch, runtime integration or deployment**. Evidence here is from public Microsoft API documentation and the checked-in source of [AgentHttp.cs](../../mod/StardewMCP/Agent/AgentHttp.cs) at Draft PR #22 commit \`a2c23e272a3da3ed3d6b6c613aecfdf8d723efa5\`.

The [feasibility matrix](../../reference/sunny_g1_transport_feasibility/matrix.json) enumerates **four approaches × five required properties**. Its [independent-stop sketch](../../reference/sunny_g1_transport_feasibility/independent_stop_sketch.json) describes **G1E-05 and G1E-06** in parallel with **G1E-03/04/02**. Neither is an executable implementation or an operator sign-off. The [Phase 2J resolution plan](G1_BLOCKER_RESOLUTION_PLAN.md) still records **11 open entry gates**, with numeric parameters unratified. The 50 [Phase 2F cases](../../reference/sunny_windows_http_acceptance/cases.json) are all \`not_run\` (37 future G1 isolated transport, 13 separate G2 real Sunny/Luna/privacy).

## Source-backed findings: important differences

1. The **existing \`HttpListener\` implementation** in \`AgentHttp.cs\` has \`GetContextAsync\` at source line 92 and launches per-context \`Task.Run\` at 94, routes through \`req.Url?.AbsolutePath\` at 105, sets wildcard CORS at 102 and calls \`ReadToEndAsync\` on several endpoints. These are *source observations*, not edits in this PR. The .NET [GetContextAsync documentation](https://learn.microsoft.com/en-us/dotnet/api/system.net.httplistener.getcontextasync?view=net-10.0) specifies a received request/context, not first-byte or partial-header arrival. [RawUrl](https://learn.microsoft.com/en-us/dotnet/api/system.net.httplistenerrequest.rawurl?view=net-10.0) describes URL path/query after domain, **not** original Host duplicate syntax, header line order or unparsed HTTP.sys wire frames.
2. The **ASP.NET Core HTTP.sys server** has documented \`MaxConnections\`, \`RequestQueueLimit\` and \`TimeoutManager\` settings ([HTTP.sys options](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/servers/httpsys?view=aspnetcore-10.0)). **Important caveat:** Microsoft's [HeaderWait documentation](https://learn.microsoft.com/en-us/dotnet/api/microsoft.aspnetcore.server.httpsys.timeoutmanager.headerwait) says that timer is enforced **only after the first request on a connection has been routed to the application**. Its [EntityBody timer](https://learn.microsoft.com/en-us/dotnet/api/microsoft.aspnetcore.server.httpsys.timeoutmanager?view=aspnetcore-10.0) resets when further body data indications arrive. Consequently, neither documents the needed **non-resetting, first-byte-to-finished-ingress** budget for the first request. Server options might require URL prefix/OS configuration; unapproved global settings are prohibited.
3. **ASP.NET Core Kestrel** documents \`RequestHeadersTimeout\`, \`MaxConcurrentConnections\`, body-size and minimum body-rate limits ([Kestrel options](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/servers/kestrel/options?view=aspnetcore-10.0)), plus header count/aggregate-size and request-line limits ([Kestrel limits](https://learn.microsoft.com/aspnet/core/fundamentals/servers/kestrel/security-considerations)). These constitute a **promising pre-handler design-control candidate**, **not** an approved transport. Its features expose \`IHttpRequestFeature.RawTarget\` and a \`Headers\` value collection ([ASP.NET Core request feature](https://learn.microsoft.com/en-us/dotnet/api/microsoft.aspnetcore.http.features.ihttprequestfeature?view=aspnetcore-10.0)); neither fact is by itself proof of *original byte-for-byte Host spelling, duplicate header syntax, CL/TE refusal attribution or HTTP.sys reception*. Kestrel is not HTTP.sys; choosing it would change the future **G1 experiment's** instrumentation and scope, requiring a new reviewed variant, not silently treating G1 HTTP.sys cases as measured. The [IHttpConnectionFeature](https://learn.microsoft.com/en-us/dotnet/api/microsoft.aspnetcore.http.features.ihttpconnectionfeature?view=aspnetcore-10.0) exposes local/remote endpoint and a diagnostic connection identifier; a proxy or unverified middleware still requires independent provenance checks.
4. **Raw \`TcpListener\` / self-written HTTP parsing** could theoretically expose bytes *to the app before the HTTP parser*, but making a strict HTTP/1.1 parser and framing rules would introduce additional request smuggling, slow-header and ownership risks. [Microsoft notes](https://learn.microsoft.com/dotnet/api/system.net.sockets.tcplistener.start) that stopping \`TcpListener\` **does not close accepted connections**. This is a high-effort **comparison only**, *not* a recommendation to replace the installed Sunny transport with a custom parser.

In particular, \`RawTarget\` from an ASP.NET Core request feature is documented as the **request target as sent, without URL decoding**, exposed through a mutable feature, not automatically the first bytes delivered to a TCP endpoint; HTTP.sys and Kestrel have distinct parsing layers. A client-side trace can prove what the client attempted/wrote, not what the server's kernel/user-mode parser received. Each future observation needs provenance and may be \`unobservable\`. Unknown mandatory security properties stay **BLOCK/NO-GO**, not silent exceptions.

## Matrix: five mandatory properties, no winner declared

| Gate | Question that must be resolved by reviewed method | Current G0 outcome |
| --- | --- | --- |
| **G1E-03** | How is a trusted first-byte/connection clock or enforceable equivalent established *before* \`GetContextAsync\`, including slow headers, queues and total ingress? | Partial documented Kestrel header control; HTTP.sys first-request caveat; **no complete method selected** |
| **G1E-04** | How do we bound pre-auth sockets, incomplete headers, HTTP.sys queues and outstanding reads before any principal is known? | Kestrel/ASP.NET Core HttpSys have documented knobs; actual safe isolation and entire occupancy bound **unproven** |
| **G1E-02** | Can we distinguish original target/Host/header multiplicity and trusted transport peer from transformed listener fields and kernel refusals? | Parsed features exist; **raw-line fidelity and negative outcomes unverified** |
| **G1E-05** | Which abort is request/connection-scoped, which terminates listener, and can an **external** operator stop a saturated test? | Abort interfaces documented; actual stuck-read completion, collateral and independent stop **not demonstrated** |
| **G1E-06** | Can we observe task quiescence, response-write completion, buffer ownership and bounded teardown before releasing capacity? | **No real evidence**; keep pending capacity held and halt latched |

A **source-backed method verdict** does not close any gate automatically. For each, the future independent reviewer must name the API version, precise scope, unresolved platform assumptions, required design constraints and fallback. If a mandatory property cannot be adequately provided or safely tested, the prospective transport is **blocked**. Selecting an alternate transport also requires a **reviewed update to Phase 2F/2I expectations**, preserving exact cases, not manipulating statuses.

## G1E-05/06 independent stop and cleanup — design in parallel

Documented transport APIs provide important but **different** scopes:

- [\`HttpListenerResponse.Abort\`](https://learn.microsoft.com/en-us/dotnet/api/system.net.httplistenerresponse.abort?view=net-10.0) closes that response/context and client connection; [\`HttpListener.Abort\`](https://learn.microsoft.com/en-us/dotnet/api/system.net.httplistener.abort?view=net-10.0) immediately terminates a listener and discards queued requests. Neither is independent evidence that an uncooperative application \`ReadAsync\` finished, its task/callback is observed, or its pooled buffers can be reused.
- [ASP.NET Core \`HttpContext.Abort\`](https://learn.microsoft.com/en-us/dotnet/api/microsoft.aspnetcore.http.httpcontext.abort) aborts the connection underlying a request (including Kestrel / ASP.NET Core HttpSys contexts), not an absolute guarantee that unrelated application work stops. Observe its actual effect only in a **separately authorized G1**, not this PR.
- [\`TcpListener.Stop\`](https://learn.microsoft.com/dotnet/api/system.net.sockets.tcplistener.start) does not close accepted connections. All accepted socket references and tasks would need explicit lifecycle owners.

The **non-executable** [independent-stop schema](../../reference/sunny_g1_transport_feasibility/independent_stop_sketch.json) separates externally owned stop from server/recovery/evidence-writer workers. Proposed order: independent stop latches halt → stop future synthetic traffic → invalidate pending and collateral candidates → request a known-scoped abort → observe reads, writes, transport quiescence and buffer ownership → quarantine unresolved work → finite escalation/independent process control if separately approved → manual rollback → **no automatic restart**.

A \`408\` response, cancellation-token signal, completed \`HttpContext.Abort\` call, closed listener or process exit is **never sufficient proof of per-request task/ownership cleanup**. No capacity/lease/effect may be automatically released or retired on that basis. The sketch leaves **operator owner, independent control path, abort method/scope, finite escalation deadlines, process inventory and stop evidence unset**. It does not implement them or ratify the candidate 8s/2s/5s/2s thresholds.

## Deliberate restrictions and next action

This PR's Python tests are **offline schema/negative mutation checks only**, not C# socket/network tests or Windows transport measurements. No listener, process, OS privilege, port choice, URLACL/firewall change, P1 diary/consent/data or native Luna interaction is allowed. Do not modify real \`AgentHttp\`, \`McpDispatcher\`, \`AgentRuntime\`, \`SunnyP2Preflight\`, installed game/mod, saves, controller or \`main\`.

**Recommended next decision after independent review:** determine whether Kestrel's documented bounded header/connection controls justify a **separately specified disposable G1 variant**, while evaluating original Host/CL-TE fidelity and an operator-owned external stop on paper. Alternatively keep HTTP.sys if the required pre-handler and raw evidence can be supported by an independently reviewed method. Do **not** select a transport or start G1 based on this PR.

All 11 G1 start gates remain open, the full 50-case acceptance plan is \`not_run\`, numerical values remain **unratified**, and the user's previous consent to G0 work is not approval to run any network test. **G1: NO-GO. G2 real Sunny/Luna: separately pending.**

## Independent Issue #52 review (G0 only)

All 20 transport/property combinations were reviewed. **No complete mandatory
method exists in this reference; no transport is selected.** HttpListener still
lacks a documented pre-context clock/admission method here. HTTP.sys HeaderWait
still does not establish first-request protection; EntityBody resets on data.
Kestrel limits are design inputs, not an entire pre-handler resource bound or a
non-resetting total ingress deadline. A custom parser remains a framing/smuggling
risk and requires ownership of every accepted connection separately from Stop.
Any mandatory provenance, occupancy, clock or cleanup property without a feasible
reviewed method disqualifies that candidate; an API gap cannot be waived by a
successful client fixture or a timeout response.

Material review corrections, ordered by severity within this inert reference:

- **Medium:** permissive regression checks accepted coordinated replacement of
  claims/source bindings, allowlisted but unrelated URLs, unknown nested fields,
  and intermediate stop edges bypassing observation or cycling through escalation.
  Independent canonical SHA-256 snapshots now pin the reviewed JSON content,
  including exact sources, fallbacks, graph and guards. Adversarial tests cover
  nested extra fields, coordinated forgery, skipped observation and cycles.
  These are drift guards, not a proof of source truth or protection against someone
  also editing the test pins; changing a pin requires renewed source review.
- **Medium:** the stop sketch mentioned finite escalation without explicit
  absolute-clock, blocked-control/evidence-writer failure and quiescence guards.
  It now requires non-resetting independently observed deadlines, a finite
  unresolved-quarantine outcome, and an enumerated read/write/callback and
  buffer/lease ledger before quiescence. Connection/listener abort collateral
  must be fenced, including complete bodies awaiting commit. This is a future
  design obligation, with no implemented stop path or approved numeric deadline.
- **Low:** describing RawTarget simply as interpreted understated its contract.
  The request feature documents the target as sent without URL decoding; Headers
  aggregates by name and does not split/merge values across header lines. Neither
  guarantees original header-name casing, whitespace or parser-rejected CL/TE
  bytes. The matrix now states this distinction explicitly.

The Learn URLs above could not be fetched during this review because the cloud
network policy denied that host. Each matrix source now includes a
`reviewed_source_url` for the independently fetched Microsoft GitHub backing
source: ASP.NET Core **v10.0.0** API comments, and pinned commits of
`dotnet/dotnet-api-docs` and `dotnet/AspNetCore.Docs`. Documentation snapshots are
not evidence for the installed game's .NET/Windows version; API availability,
protocol scope, non-elevated isolation and actual behavior still need separate
review. No Windows acceptance result was generated.

The smallest useful next step is an **offline field-by-field provenance and
resource-ownership design** for one prospective disposable variant: name each
observation source, pre-handler bound, immutable clock, abort scope and task/buffer
owner, marking unavailable mandatory evidence BLOCK. No listener is needed for
that step. This reference is suitable only as **inert G0 material for Draft PR
#22**; it grants no G1/G2 authority, P1 consent or native Sunny/Luna acceptance.
All 11 gates stay open and all 50 cases stay not_run (37 G1, 13 G2).
