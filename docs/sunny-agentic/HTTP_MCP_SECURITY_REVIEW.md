# PR #19 HTTP/MCP security review

Reviewed 2026-11-07. Recommendation: retain Draft; correct and expand the design before implementing security enforcement.

## Scope and evidence

PR #19 head: `329fc6d62ef53b50d1229ba8e76a542ff5c33f26`; base: `9f2cb29f6a5e71362d0d0da2bb9547faff88b997`. The PR adds only the 79-line boundary document. Runtime findings below are pre-existing, not vulnerabilities introduced by this documentation PR. Source links below resolve against that immutable head.

**Confirmed** means established by inspected source, not a live exploitation result. **Reported** means asserted by the document/operator history but not independently verified here. **Hypothesis** means an impact requiring additional validation. Priorities describe remediation/design urgency, not a CVSS score.

No runtime code changed; no game, listener, live HTTP/MCP call, credential store, save, or deployment was accessed. GitHub repository operations and source fetching only. No PR merged. No game build/test launched. The game-free C# suite could not be run because `dotnet` is absent (`command -v dotnet` returned 1). This documentation review makes no passing-test claim.

## Prioritized findings

### P1 — Browser protection requires request rejection, not just CORS removal

**Confirmed:** AgentHttp.Handle sets wildcard ACAO before routing and has no application authentication, Origin, peer, authority, request Content-Type, or body-size policy. Legacy reads and mutations remain available with debug disabled. Removing ACAO alone cannot prevent a request from executing.

**Hypothesis:** A webpage able to reach this listener may read noncredentialed responses and submit JSON text using a safelisted Content-Type such as text/plain; parsing does not require application/json. Browser private-network/local-network permissions, preflight, mixed-content rules and HTTP.sys matching determine actual delivery. Failed application/json preflight does not establish safety for all request forms. Neither LAN exposure nor DNS-rebinding exploitation is established by source alone.

**Correction:** Explicitly test simple POSTs, no-cors requests and Origin null, alongside OPTIONS/preflight. Deny disallowed requests before *any* mutation, including metadata and contact. Specify a same-origin browser policy for overlay/replay rather than a native-only rule that silently breaks them. Origin is not a native-client credential.

Evidence: [AgentHttp.cs](../../mod/StardewMCP/Agent/AgentHttp.cs), lines 98–229, 272–318.

### P1 — MCP session headers provide no ownership or epoch protection

**Confirmed:** McpDispatcher.Handle emits predictable `stardew-{seat.Id}` for a single response; batch replies omit it. AgentHttp does not validate incoming Mcp-Session-Id, require initialize, or bind sessions to a caller/save epoch. MCP DELETE returns 200 without session teardown. Tools can be called without a handshake. These are transport conventions, not authentication or revocation.

**Hypothesis:** Competing or stale controllers can interfere with a seat or submit into a later save. Exact queued-action effects across reload/role changes require lifecycle tests; no cross-save exploit was demonstrated.

**Correction:** Define single-controller ownership, epoch binding, cancellation, role recheck at execution, and meaningful DELETE/revocation behavior. Credential revocation must account for already queued work; avoid implying that revocation can undo a completed game mutation.

Evidence: AgentHttp.cs 113–129, 306–318; McpDispatcher.cs 69–129; McpSeat.cs 24–31; AgentRuntime.cs 103–113, 225–280; ModEntry.cs 55–63, 95–113. ReturnedToTitle does not visibly reset the HTTP session mechanism; it has no such mechanism.

### P1 — Contact and pre-dispatch side effects are broader than discovery

**Confirmed:** Dispatch calls MarkContact *before* examining method, id or params. Notifications, unknown methods, unknown tools, inactive-seat tool requests and JSON values that reach Dispatch but fail shape validation can change contact first. Invalid JSON text fails earlier and is not equivalent. PlayerSlot.MarkContact sets Connected, clears TimedOut and release state. HandleMcp first calls SessionBreaks.Observe and overwrites seat-wide ReplyWithinSeconds from an unbounded signed integer query (invalid/missing becomes zero). Initialize can reset session-break counters; breaks=1 can arm the seat.

**Correction:** Place authorization and shape checks before SessionBreaks.Observe, reply-deadline updates and MarkContact, not just before tool dispatch. Define which accepted calls mutate each lifecycle field. Decoupling three discovery methods alone is insufficient.

Freeze is conditional: WorldClock requires an eligible connected AI, no running action, active split-screen seat (or host in single-screen), enabled freeze, ready world and other night/wakeup gates. Operator RunControl.Holding can independently freeze with FreezeTimeWhileThinking=false. MarkContact clears TimedOut but does not itself reset the thinking stopwatch. Do not promise a fresh timeout window on every ping.

Evidence: McpDispatcher.cs 87–129; Players.cs 64–82; AgentHttp.cs 312–315; SessionBreaks.Observe/EnsureStarted; WorldClock.Tick/IsThinking.

### P1 — Configuration and role routing do not establish a human privacy boundary

**Confirmed:** Defaults are port 8770, SplitScreen=false, FreezeTimeWhileThinking=true, EnableDebugApi=false, P1–P3 AI, Brain=none; diagnostic booleans default false. Missing/short seat arrays are padded with defaults. Unknown non-off/non-camera/non-human role strings resolve as AI; P1 off/camera is coerced to AI. Brain=none means external MCP control, not disabled MCP. Built-in brain presence does not gate the MCP route.

Resolved human P1 is rejected by MCP routing; aggregate state/feed still include human host data. RefreshState includes host even if inactive, plus active seats. Human role does not remove global runtime control or P2's effects on shared world/resources. Debug uses role-independent Active checking and is a separate risk if enabled.

**Correction:** Document defaults and role fallbacks explicitly; do not describe the pilot's human-P1 configuration as a safe global default. Test missing/misspelled roles, P1 coercion, P4 AI routing, built-in/external controller conflicts and debug-enabled human targeting. No key value was read; ApiKey schema presence alone does not prove HTTP credential disclosure.

Evidence: ModConfig.Seats/Seat and SeatConfig; Players.Resolve; AgentHttp.Handle/HandleDebug/RefreshState; Brains.Describe returns provider/model, not ApiKey.

### P2 — Availability and action ambiguity need explicit acceptance gates

**Confirmed:** One Task.Run per accepted context, unbounded ReadToEndAsync bodies, no application batch-length/concurrency/rate bound, and unbounded runtime queues. JSON parse/shape exceptions generally fall through to HTTP 500 rather than controlled protocol errors. A batch can execute earlier calls before a later element fails. No HTTP disconnect cancellation is wired into enqueued MCP calls. OS/runtime defaults may impose additional limits; this is an absence of application bounds, not proof of unlimited resources.

**Hypothesis:** Slow bodies, large batches/results, parallel clients or disconnected callers can exhaust resources or leave delayed mutations. Concurrent metadata writers/feed serialization and HTTP/game-thread state changes also deserve race testing; no observed race is claimed.

**Correction:** Specify byte/read-time limits, batch and queue bounds, fairness, cancellation boundaries and ambiguous-outcome responses. Test partial batch success followed by failure and prohibit blind retries of mutation batches. Authentication must not substitute for resource limits on reads or authorized clients.

Evidence: AgentHttp.Loop, HandleMcp, ReleaseFreeze and meta/control body reads; McpDispatcher.Handle; AgentRuntime.EnqueueCall.

### P2 — Compatibility needs concrete browser, port and protocol cases

**Confirmed:** Overlay and replay fetch APIs without an Authorization header. Both choose same-origin only when location.port is "8770"; otherwise they default to http://localhost:8770 unless ?api= overrides it. Serving those pages on the pilot's custom port can therefore read the wrong listener or fail. Adding bearer grants requires a browser-compatible provisioning design without URL secrets. Cross-origin/file/OBS usage may depend on current CORS. New method/media-type restrictions can break lenient existing clients.

**Uninspected:** External Luna/Python/PowerShell ZIPs and runner/watchdog sources are absent from this checkout; docs mention them, which is not consumer verification. No claim of their header/session/retry compatibility is justified.

**Correction:** Inventory same-origin default/custom port pages, explicit ?api= source, localhost versus 127.0.0.1, fallback registration, OBS/file-origin behavior, header-based sessions, 202 notifications, batches and DELETE. Do not pass new secrets through ?api=. Ensure auth errors are distinguished from game hangs in watchdogs.

Evidence: assets/overlay.html 657–659, 685; assets/replay.html 150, 213–246; docs/api.md consumer discussion.

## Claim-by-claim disposition of PR #19

| Original claim/group | Verdict and qualification |
| --- | --- |
| Design-only, no runtime security fix | Confirmed by base-to-head diff: one documentation file only. |
| localhost/127.0.0.1 prefixes and fallback; wildcard ACAO; absent app credentials/Origin/Host/peer checks | Confirmed in AgentHttp.Start/Handle. Exact Windows URL ACL, socket and peer behavior remain untested. |
| An observed :: socket does not prove remote access | Sound limitation. The socket observation itself is reported, not reproduced. |
| State exposes host paths/resources/dialogue and seats; local projection does not reduce response | Confirmed in RefreshState and Handle. Before world ready, shape is smaller; host is included even if inactive. Dialogue snapshot is speaker/question metadata, not necessarily raw dialogue text. |
| Feed/day/memory/briefing disclose additional data | Confirmed route behavior. Also inventory relationships, stats, days, static pages and metadata. This is not arbitrary filesystem read evidence. |
| MCP, control, release_freeze and meta can mutate; debug flag is narrow | Confirmed. Role, world readiness and method gates vary; no universal security switch exists. |
| initialize/ping/tools/list mark contact | Confirmed, incomplete; see P1 contact finding. McpSeat delegates to PlayerSlot; WorldClock applies conditions. |
| human P1 GET 404; AI P2 GET 405 | Confirmed conditional on resolved role, seat existence and SplitScreen=true for P2. Same gate applies to POST; routing is not caller authorization. |
| Diagnostic HTTP disabled/inoperative; P1 consent false does not disable legacy routes | Confirmed: HttpDisclosureEnabled participates in diagnostic metadata, not legacy route authorization. FakeEvidenceHttp exists only in tests. |
| Backed-up Test_ pilot/reload/status success and exact deployed configuration | Reported only. Source review cannot establish deployed DLL, save backup, live config or smoke-test result. Freeze=false alone is not a complete explanation if operator hold exists. |
| Loopback/CORS not authentication; same-user malware limitations; no inferred remote exposure | Supported threat-model limitations. No browser or remote exploit verified here. |
| S0–S3 and negative-test lists | Proposals, not implemented protections or passing tests. Amend with findings above. |
| Suggested PR-A request policy "without changing existing routes" | Ambiguous: extract/test policy with enforcement disabled versus enforce new validation. Specify baseline production behavior remains unchanged in PR-A; enforcement belongs to reviewed PR-B. |
| Current branch not production-hardened | Supported by absent application controls. This is not a claim that PR #19 introduced exposure. |

## Actual route/method inventory

Trailing slashes are stripped. Methods below reflect the handler, not its comments; HTTP.sys/runtime can impose earlier behavior.

| Routes | Current handler method behavior | Main effect |
| --- | --- | --- |
| / and /replay; /overlay | No method check | Static replay/overlay assets |
| /api/state, /api/feed | No method check | Cached host/seat state; feed also logs/meta |
| /api/days, /api/day?n=, /api/memory | No method check | Day index, logs/diaries, seat memory |
| /api/briefing?seat=, /api/relationships, /api/stats?n= | No method check | Briefing, friendship and statistics reads; helper validation applies |
| /api/control | GET snapshot; POST mutation; other methods 400 | Global pause/stop flags |
| /api/meta | POST; others fall through 404 | Overlay metadata and optional system-log event |
| /api/release_freeze | POST; others 404 | Selected AI/all-AI per-day release state; requires loaded world |
| /mcp, /mcp/{seat} | Role/split gate first; POST RPC; DELETE 200 no-op; others 405 | Tools, contact, session-break/reply-deadline state |
| /api/debug/{op}, /api/debug/{seat}/{op} | Config and known-op gate 404; then non-POST 405; Active check | Debug operations; default host when no recognized seat prefix |
| Unknown | 404 | No route response body |

MCP routing uses Players.ById rather than an explicit p1–p3 allowlist; a configured AI P4 is not excluded by that advertised range. OPTIONS is not globally implemented as a CORS preflight handler. Wildcard ACAO does not imply all preflights succeed or that Mcp-Session-Id is readable by cross-origin JavaScript.

## Missing tests and evidence

Existing McpDispatcherTests cover discovery replies, inactive-seat errors, unknown tools/methods, notifications, batches and predictable session labels. The test Every_message_marks_the_seat_as_having_an_ai_attached_even_a_notification explicitly preserves today's side effect and must change deliberately with the contract. FakeEvidenceHttp tests exercise a separate proposed policy, not AgentHttp. The game-free csproj includes McpDispatcher but not real AgentHttp, McpSeat, Players, WorldClock or ModConfig.

Prioritized additions for a later authorized implementation PR:

1. **P1 transport adapter:** real handler-to-policy integration plus no/wrong/revoked credentials, hostile/null Origin, simple POST Content-Types, methods/OPTIONS, authority/peer variants and malformed requests. Assert no data, metadata update, SessionBreaks change, ReplyWithinSeconds change, contact or enqueue on denial.
2. **P1 identity/lifecycle:** absent/foreign/stale session, direct tools/call, DELETE, concurrent controllers, Title→Load including a different save and same-day replay, queued request during role change/revocation, P1 human and malformed config. Assert role/epoch at execution and safe completion/cancellation.
3. **P1 clock/contact:** discovery, notifications, unknown/invalid messages, released/timed-out/inactive seat, enabled/disabled freeze, operator hold and night/wakeup exclusions. Test stopwatch semantics separately from TimedOut reset.
4. **P2 availability/protocol:** oversized/slow bodies, huge/empty/malformed batches, partial execution, invalid ids/params, duplicate headers/query, queue saturation, disconnect and ambiguous timeout. Verify no duplicate mutation on retry.
5. **P2 privacy/compatibility:** response-field allowlists across all read routes including host/global information; overlay/replay at 8770 and custom ports, ?api= and OBS origin; notifications/202, batches and session header visibility. External controller tests remain blocked on exact source.
6. **Later operator-only evidence:** Windows HTTP.sys prefixes/fallback, IPv4/IPv6/Host/peer behavior and approved isolated-save lifecycle checks. These were not run in this review and are not authorized by this report.

## Proposed documentation corrections

This report is a documentation-only supplement. Update the boundary draft to label pilot evidence as reported, link this route inventory and findings, expand S1 to cover every pre-dispatch side effect and browser simple requests, expand S2/S3 to specify actual session/epoch/queue behavior, and explicitly mark external consumer compatibility uninspected. Keep implementation and operator validation in separate future work. Retain both PR #19 and its parent as Draft; do not deploy or merge as part of this review.
