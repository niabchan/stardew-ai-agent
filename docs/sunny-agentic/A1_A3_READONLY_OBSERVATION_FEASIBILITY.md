# A1/A3 — C# read-only observation feasibility

Research/design only, 2026-11-05 (Asia/Bangkok). Guy is human P1; Sunny is AI P2; Luna chooses Sunny's actions. No runtime implementation or approval is implied.

Baseline: `docs/sunny-agentic-design-review-round1` at **5f537945288919d7373c737b5a5d999d12863638** (merged #13). Read [PR #12](https://github.com/niabchan/stardew-ai-agent/pull/12), head `29f0a030010c8b8ba033587138bc40e0fc54b83c`, including its report and discussion (no comments returned). #12 remains a draft, not merged authority. Read root AGENTS.md, SUNNY_COMPANION.md, charter, track briefs and architecture baseline. The six requested C# files and adjacent paths below were inspected through GitHub; the older local checkout was not used as baseline. Local Git fetch failed because its proxy was unreachable.

**Recommendation:** a disabled-by-default sampler on each screen's ordinary update, publishing independent immutable snapshots through a dedicated passive GET cache. Do not expose it as an MCP tool or run it through AgentRuntime. Initial capability is diagnostic evidence subject to explicit seat/field disclosure grants; raw content is off by default: guarded dispatch, certified gift classification, checkpoint reconciliation and transfer verification remain false.

## 1. Observed code map

All C# links below pin the baseline. These are source facts, not claims about an installed DLL or actual SMAPI event semantics.

| Source and seam | Observed behavior and feasibility consequence |
| --- | --- |
| [ModEntry.cs](https://github.com/niabchan/stardew-ai-agent/blob/5f537945288919d7373c737b5a5d999d12863638/mod/StardewMCP/ModEntry.cs#L88), OnSaveLoaded | Comments explicitly say farmhand SaveLoaded occurs before its character exists. Calls SplitScreen.OnSaveLoaded, resets WorldProgress, changes pauseWhenOutOfFocus before the screen check; host then resolves roles, initializes save metadata/economy and starts brains. Never call this handler as a probe. A P2 callback cannot mint a second host load. |
| ModEntry.OnUpdateTicked | seat.OnTick precedes split-screen setup and Runtime.Tick; watchers then run, ScreenState captures every 15 ticks, host WorldClock.Tick and HTTP refresh follow. Existing sample is after potential menu mutation. Capture placement must be documented, not presented as pre-action evidence. |
| [Players.cs](https://github.com/niabchan/stardew-ai-agent/blob/5f537945288919d7373c737b5a5d999d12863638/mod/StardewMCP/Agent/Players.cs#L23), PlayerSlot | Id is p{screen+1}; Current uses Context.ScreenId, game thread only. Active means a tick within two seconds, not ready farmer, new incarnation, or fresh prompt. MarkContact sets Connected=true, TimedOut=false and clears released-day. |
| Players.ScreenState.Capture | Correct own-screen read pattern. Ready is world readiness; Dialogue is speaker display name, not question. Contains no load identity, prompt instance/revision, semantic mapping, inventory or capture timestamp. Do not infer a gift from this field. |
| [WorldText.cs](https://github.com/niabchan/stardew-ai-agent/blob/5f537945288919d7373c737b5a5d999d12863638/mod/StardewMCP/Agent/WorldText.cs#L67), MenuState | DialogueBox.getCurrentString, isQuestion and ordered responseText are demonstrated reads. Output flattens newline/caret and adds tool advice. No response key or lifecycle identity. Copy raw fields directly; do not parse formatted prose. WorldText.Look also remembers observation state; it is not a pure evidence copier. |
| [AgentHttp.cs](https://github.com/niabchan/stardew-ai-agent/blob/5f537945288919d7373c737b5a5d999d12863638/mod/StardewMCP/Agent/AgentHttp.cs#L98), Handle/RefreshState | /api/state returns cached StateJson without tool dispatch. RefreshState combines host live fields and independent seat caches; heartbeat advances on host refresh, not P2 capture. Top-level dialogue belongs to host. Human P1 is excluded from MCP routing; preserve this role. |
| [McpDispatcher.cs](https://github.com/niabchan/stardew-ai-agent/blob/5f537945288919d7373c737b5a5d999d12863638/mod/StardewMCP/Agent/McpDispatcher.cs#L84), Dispatch | Calls MarkContact before checking method/id. Ping, initialize, list, notification, unknown method and each dispatched batch element can change contact bookkeeping. An empty batch dispatches no element. JSON-RPC id and stardew-seat session header are transport correlation, not prompt/load identity. |
| [AgentTools.cs](https://github.com/niabchan/stardew-ai-agent/blob/5f537945288919d7373c737b5a5d999d12863638/mod/StardewMCP/Agent/AgentTools.cs#L834), Respond | Captures current box/text/question and range-checks an option; sets selectedResponse and clicks up to 40 iterations with waits. No expected world/seat/prompt/revision/mapping. Text or reference checks during the coroutine cannot certify the original offer. Closed/continued is not choice or receipt proof. |

## 2. Side-effect paths excluded from the sampler

This is the relevant call-path inventory for the requested six files and the adjacent runtime/menu paths inspected to assess reuse. It is not an exhaustive audit of every partial AgentTools file or every game/mod hook. The sampler must have a narrow allowlist of scalar reads and its own bookkeeping; all gameplay helpers are outside that allowlist.

| Path | Effect or hazard |
| --- | --- |
| AgentHttp.HandleMcp → SessionBreaks.Observe, ReplyWithinSeconds assignment → McpDispatcher → McpSeat.MarkContact → PlayerSlot.MarkContact | Session/deadline/contact changes occur even before a tool is useful. Contact clears freeze release and timeout; WorldClock can subsequently freeze a connected idle AI. No passive request may enter this path. |
| McpSeat.CallTool/CallToolReply → Runtime.Enqueue/EnqueueCall(observation:true) | Instant tools use an observation lane, which is still runtime execution. Lane start/end update stats/guards; Finish can append footer/session notices and drain mail. Instant is a scheduling property, not a no-side-effects guarantee. |
| AgentRuntime.Lane.Finish → Perception.TakeMail → SocialTools.TakeMail | Dequeues perception events and chat. Footer and other helpers may touch additional observation state. Do not call Finish, TakeMail, Clear, SyncSave, or a tool just to collect evidence. |
| AgentTools.Respond; CloseMenu → ClaimBeforeClose | Selected option/click changes question state. CloseMenu claims letter quests/attachments and grab-menu items before closeDialogue/exitThisMenu/exitActiveMenu. Closing is not harmless cleanup. |
| AgentTools.Interact, travel/walk, use/plant/harvest, Buy/Ship/Eat and other action registry delegates | Movement, action buttons, item selection, inventory, currency, world or menus can change. All tool delegates, including menu read mode, are excluded from the capture call graph. |
| MenuTools.Menu actions → Click/PressOk/Cancel/Take/Put/ChooseFloor/ChooseFromList/Amount/TypeName | General menu operations can click, claim, transfer or select. RomanceTools.AnswerProposal is another response route; generic Yes/No classification cannot certify an incoming gift. |
| AgentTools.GoToBed/LieDown/AnswerNightAlone/ClickShippingOk | Closes menus, moves farmer, chooses defaults, sets bed state, answers Sleep_Yes, clicks shipping/level-up/night dialogue, auto-names and may cancel ready check during coroutine disposal. UnknownMenuWatch in RunControl closes an unexpected persistent menu, including a force-exit fallback. |
| AgentRuntime.Tick → AutoHandleOverlays | Shipping/level-up actions; event skip and dialogue option zero/click fallback. Also invokes SocialTools.Tick (queued gifts/speech), Perception.Tick (notifications, deadline replies and interruptions), Story/Romance/NightEvents etc. Never tick a runtime to obtain a sample. |
| ModEntry.OnUpdateTicked → SleepWaitWatch.Tick | Can close lingering sleep-blocking dialogue. A sampler observes the result, never invokes this watcher. Existing automation remains a competing source of mutation. |
| ModEntry load/title/day/tick helpers | AutoLoadSave loads save/exits title menu; DayStarted removes nonpositive item stacks; camera handling writes requestingTimePause and parks/warps farmer; split-screen host/guest setup joins/creates/activates characters and may build cabins; brains start/stop. Sampler does none of these. |
| AgentHttp /api/release_freeze, POST /api/control, /api/debug; ModEntry mcp_freeze/mcp_brain commands | Release/run-control/config/brain changes or enqueued debug mutations. Debug enablement is not authorization for evidence collection. GET /api/state is the existing passive precedent; other HTTP routes are not implicitly passive. |
| WorldClock.Tick / RunControl.Tick | Host pause/time interval, thinking/timeout state and run-control behavior. Read diagnostics if needed; never invoke these for freshness or release a frozen game to acquire a sample. |

Adjacent inspected sources: [McpSeat.cs](../../mod/StardewMCP/Agent/McpSeat.cs), [AgentRuntime.cs](../../mod/StardewMCP/Agent/AgentRuntime.cs) (EnqueueCall, Tick, AutoHandleOverlays, Lane.Finish), [Perception.cs](../../mod/StardewMCP/Agent/Perception.cs) (TakeMail, Clear, Tick), [WorldClock.cs](../../mod/StardewMCP/Agent/WorldClock.cs), [SplitScreen.cs](../../mod/StardewMCP/Agent/SplitScreen.cs), [MenuTools.cs](../../mod/StardewMCP/Agent/MenuTools.cs), [CloseMenuTools.cs](../../mod/StardewMCP/Agent/CloseMenuTools.cs), [SleepWaitWatch.cs](../../mod/StardewMCP/Agent/SleepWaitWatch.cs), [RunControl.cs](../../mod/StardewMCP/Agent/RunControl.cs), [SocialTools.cs](../../mod/StardewMCP/Agent/SocialTools.cs), [RomanceTools.cs](../../mod/StardewMCP/Agent/RomanceTools.cs).

Read-only here means no intentional game/control/message-consumption writes. CPU, allocations and serialization can still affect frame timing; zero performance impact is not a defensible guarantee.

## 3. Proposed interfaces and evidence contract

Illustrative signatures only; no C# implementation in this PR:

```text
ISeatEvidenceSampler.CaptureOnCurrentScreen(readContext) -> SeatEvidence
IObservationLifecycle.ObserveHostLoad / ObserveSeatReady / ObserveSeatLost / ObserveTitle
IEvidenceSnapshotReader.Read(seat, expectedAdapter?, expectedLoad?) -> SnapshotReply
```

Sampler owns copying; pure lifecycle reducer owns identity/revisions; reader owns only immutable cache access. No interface exposes a Farmer, Item, menu, Runtime or mutation delegate to HTTP.

| DTO | Proposed fields/invariants |
| --- | --- |
| Capabilities | schema, adapter_version, adapter_instance_id, enabled, passive_snapshot, own_screen_prompt, own_screen_inventory, lifecycle_coverage, response_keys, gift_classification, guarded_dispatch=false, transfer_verification=false, checkpoint_reconciliation=false. Unsupported differs from temporarily unavailable; publish reasons and field-specific completeness. |
| Scope | adapter, opaque save_id/load_id/branch_id, parent_checkpoint_id=null, seat_id, screen_id, farmer_alias, seat_incarnation, role, readiness phase. p1/P1 casing is normalized explicitly at the adapter boundary. No role switch for Guy. |
| Capture | capture_id, sequence per scope, screen tick, monotonic timestamp and clock identity/frequency, diagnostic UTC, source=own_screen, ready, complete, coverage, unavailable_reason. Timestamp at capture, not GET time. Copied arrays are immutable. |
| Prompt | status absent/present/unavailable, concrete menu type, instance_id?, revision?, identity_known, raw question, is_question, transitioning, ordered responses {index, raw_key?, label}, classification status/version/evidence, mapping digest. Null prompt with ready=true means observed absence only if prompt capture completed. |
| Inventory | optional independently complete component; slot, QualifiedItemId, quantity, quality, A2-approved variant metadata/signature, container/seat identity. Copy only; no getOne, item mutation, selection or normalization of zero stacks. Unknown is not empty; slot/signature is not a persistent item UUID. |
| SnapshotReply | capabilities, current lifecycle generation, requested seat, exact cached capture or unavailable status, server clock sample, age/stale diagnostic and policy version. Cached sample sequence/time never changes on reads. |

Start with P1/P2 only. A missing screen or mismatched configured role/identity yields unavailable evidence, never silently substitutes host data. Name alone cannot establish Guy/Sunny identity. Validate the configured seat and bound farmer incarnation; expose an opaque local alias rather than private names in exported fixtures.

### Prompt identity, lifecycle coverage and mapping

Allocate a new prompt instance within adapter/load/seat incarnation on observed open/replacement; retain it for continuous observations of that same prompt. Same-looking replacement must get a new instance. Increment revision for raw question, question flag, family/classification or ordered key/label mapping changes. Hashes are change diagnostics, never lifecycle authority.

Inspect a candidate Display.MenuChanged subscription plus ordinary own-screen sampling. This research has not verified actual event coverage/order, nested menus or same-object in-place prompt reuse. A menu reference plus text equality cannot distinguish a hidden close/reopen or equal-content reuse between samples. Lifecycle uncertainty, transitions, incomplete samples, stalls, seat loss or callback gaps break continuity. Mark identity/coverage unknown and retire or revise identity on both entry to and recovery from uncertainty; never revive an old token because matching text returns. Keep object references private on the game thread and release them on retirement.

WorldText demonstrates labels and indices, not semantic response keys. Candidate game responseKey availability and the vanilla human-gift discriminator require supported-version API/source or operator evidence. Raw keys are not automatically the reference's semantic accept/decline keys. Duplicate, missing, reordered, extra or unknown semantic options fail classification. Localized Yes/No or option zero cannot establish gift identity. Unknown mapping remains useful diagnostic evidence, with no actionable offer.

Capture sequence advances each actual sample; prompt revision does not advance for unchanged continuous content. Stable prompt identity survives repeated GETs and ordinary unchanged samples. Capture freshness never certifies that the prompt remains unchanged after capture. A future action requires a separate server-side guard immediately before every mutation, including subsequent clicks and competing internal routes. It is explicitly outside this sampler.

### Freshness and passive delivery

Propose GET /api/evidence?seat=p1|p2, separate from MCP/debug and independent of AI role routing. Disabled returns an explicit disabled capability response; invalid seat is rejected; not ready/no sample returns unavailable. Request handlers read only published data. No on-demand capture, runtime enqueue, contact marking, wake-up, polling of live Game1, or waiting for an action. HTTP polling must not advance game time.

Publish each seat as one atomic immutable reference (or pre-serialized immutable JSON); bounded latest-only storage avoids an unbounded history. Publish lifecycle generation independently and ensure reader rejects a capture whose scope differs from current generation. A load/title invalidation must prevent serving an old capture as current. No P1/P2 atomic simultaneity claim: return separate sequences/timestamps and let consumers enforce acceptable skew.

Use process monotonic elapsed time; Python must not subtract its own monotonic clock from C# timestamps. Return capture age plus server clock identity/time in a documented unit; network transit can only increase age. Clients use local receive elapsed time conservatively and request fresh evidence for decisions. A host heartbeat cannot refresh a stalled P2; two-second Active is insufficient. Freshness also requires matching adapter/load/seat incarnation, latest capture, readiness, component completeness and continuity coverage. A numerical age threshold is negotiated policy, not a safety proof.

Initial sampling proposal: cheap bounded prompt inspection on every ordinary P1/P2 update when enabled, inventory and publication at a configurable lower cadence (15 ticks is an existing precedent, not a guarantee of 250 ms). Track component capture times if cadences differ. Bound response count/text/inventory payloads; truncation sets incomplete and cannot produce eligible offers. Measure capture/serialization duration and allocations in a future spike; skip/report gaps rather than blocking frames or growing queues. No disk log, save hashing, durable history or automatic export in the smallest scope.

### Privacy and HTTP access security — additional design gate

Added design review, 2026-11-05 (Asia/Bangkok). Reinspected the complete [AgentHttp.cs at PR #14's initial head](https://github.com/niabchan/stardew-ai-agent/blob/92a35ea3046766d6a8f06434f1185087e525de4e/mod/StardewMCP/Agent/AgentHttp.cs). These are static findings; no listener, browser exploit or game was run.

**Observed listener and restrictions:** Start registers explicit `http://localhost:{port}/` and `http://127.0.0.1:{port}/` prefixes (lines 64–65), falling back to localhost alone after HttpListenerException (line 74). There is no wildcard listener prefix or explicit IPv6 prefix here. These are local-address intentions, not verified binding behavior across platforms. Loop accepts contexts and schedules Handle tasks. Handle sets `Access-Control-Allow-Origin: *` before routing (line 102), including errors. It contains no requester authentication, bearer-token check, Origin allowlist, explicit Host/authority validation or RemoteEndPoint loopback check; no AuthenticationSchemes configuration is present. Actual HttpListener prefix matching, URL ACLs, OS/network exposure and reverse proxies were not tested.

Existing restrictions are route-specific: MCP requires an AI seat, enabled split-screen for guests and POST (DELETE returns an empty success); debug requires EnableDebugApi, a known operation, POST and an active seat. These are feature/role/method gates, not requester authorization. Many switch routes, including /api/state, lack an explicit GET-only check. There is no dedicated preflight handler in this file. Json/Text helpers serialize/write replies without an evidence privacy policy. /api/state and /api/feed already expose cached state; RefreshState includes saveFolder, logDir and seat state. A protected new route does not secure these legacy routes or establish confidentiality for overlapping fields. Broader listener hardening needs a separate compatibility/security review; do not claim it is implemented by this report.

**Threats:** raw P1/P2 dialogue, prompt questions/labels and inventory can disclose private conversation, choices, possessions and activity. Farmer names, map/location, timestamps, stable identifiers and lifecycle history can identify or correlate a person/save. P2 dialogue can contain Guy's words/name, so a P2 seat grant alone does not eliminate P1 content. Prompt/token fields and hashes can also encode or correlate sensitive data; the Python synthetic token serializes scope, so it must not be assumed opaque or redacted. Passive reads still disclose information.

A malicious webpage may attempt requests to a local service. Wildcard CORS can permit reading simple cross-origin GET responses when the browser allows the connection; preventing preflight is insufficient for simple GET. Browser private/local-network protections, mixed-content rules and their versions vary; none is assumed universal. CORS controls browser response access, not all request delivery or native clients. Other local processes can reach loopback too. DNS rebinding may map an attacker-controlled hostname to loopback and defeat origin assumptions if the server accepts that authority. Exact HttpListener prefixes may reject some such requests, but this is not a proven universal rebinding defense. Origin may be absent or forged by nonbrowser clients. **Binding to localhost limits network reachability; it does not authorize a requester. Origin checks alone are not complete authentication.**

**Proposed least-privilege policy (future implementation requirement):**

- Separate collection enablement from HTTP disclosure. Both default off; enabling sampling alone must not expose raw snapshots. Enabling evidence HTTP requires local operator configuration of credentials and explicit seat/field scopes. No HTTP request can enable collection or broaden grants.
- Safe discovery returns only a static schema/support/auth-required description; disabled mode may return a fixed disabled description. Anonymous discovery must not disclose whether a world/P1/P2 is present, names, adapter/load IDs, clock/activity, capabilities derived from current play or cached evidence. Per-seat readiness and dynamic capabilities require authorization. Discovery and disabled/error responses have no data-bearing fallback to /api/state.
- For the smallest spike, prefer a local native reader with an endpoint-specific, high-entropy bearer credential delivered through restricted local provisioning. Send it in Authorization, never query strings, URLs, committed config, logs or browser storage. Bind its authorization to read-only evidence, allowed seats and field groups; it grants no MCP/debug/control access. Require explicit additional permission for P1 collection/disclosure and raw text/inventory. Rotation/revocation and disabling invalidate access and clear retained evidence; do not return previously serialized bodies after revocation. Avoid ambient cookie authentication. A bearer token protects access, not confidentiality against a compromised same-user process; plain loopback HTTP is not a remote transport. Any remote proxy/TLS deployment is outside this scope.
- Default projection is metadata-only with generated aliases; omit raw dialogue/questions/labels, inventory, farmer names/IDs, save paths/logDir and world identifiers unless specifically granted. Only serialize an allowlisted DTO projection, never the full internal capture/StateJson. Mark redacted components explicitly as redacted/unavailable, not observed absence or empty inventory. Preserve original capture identity/time; report projection/completeness separately. Redaction cannot certify gift classification or produce an actionable offer. Raw text permission acknowledges that another person's information can appear within the authorized seat's text.
- Validate loopback peer and exact configured Host/authority and port before data access, rejecting attacker-controlled names even if they resolve to loopback; do not trust forwarded-host/address headers or arbitrary DNS resolution as authorization. Validate methods and unambiguous seat selection; require explicit seat, reject duplicate/conflicting parameters and never default to P1. These controls supplement credentials. Supported IPv4/IPv6/localhost forms must be explicit and tested, not broad hostname suffix matches.
- Deny browser cross-origin access by default. For the native-reader mode, reject requests carrying Origin, including `null`; absence of Origin still requires the credential. If a browser reader is later approved, require both authentication and an exact scheme/host/port Origin allowlist. Never reflect arbitrary origins, permit wildcard/null origins or treat an allowed Origin as a credential. Reject a disallowed Origin even with a valid token. Preflight may describe only approved GET/Authorization behavior, with no snapshot or game access.
- Evidence routing must run before the existing global wildcard-CORS assignment, or use a response policy that reliably removes/replaces it on every evidence/discovery/error/preflight path. Prefer no CORS headers in native-only mode; an approved browser response uses only its exact allowed Origin and `Vary: Origin`. Do not rely on a missing allow-credentials header to protect bearer or unauthenticated GETs.
- Use `Cache-Control: no-store`, JSON content type and `X-Content-Type-Options: nosniff`; omit secrets/raw data from redirects, errors, request/exception logs and metrics. No JSONP or automatic export. Bound request/header/payload sizes and concurrency/rate budgets to limit local probing/load; these limits must not schedule game work.

Suggested policy order: validate request envelope/authority/method/origin; handle fixed discovery or disabled response without reading capture; authenticate and authorize seat/field scope; read immutable cache; project authorized fields; serialize with private response headers. Invalid credentials receive a generic unauthorized response; authenticated scope denial receives a generic forbidden response without confirming seat existence. Unsupported methods and preflight never fall through to other routes. Every branch remains passive: zero MCP/tools, MarkContact, runtime queues, mailbox consumption, freeze/run-control or game mutation calls.

**Proposed fake HTTP security tests (unrun):**

| Fake request/setup | Required assertion |
| --- | --- |
| Disabled, including a retained prior capture; anonymous capability discovery | Fixed minimal response only; no P1/P2 presence, IDs, names, text, inventory or cache access. Toggle off/revoke in a fake lifecycle and prove old bodies cannot be served. |
| Missing, malformed, invalid, expired/revoked credential; valid Origin without credential | Generic denial with no snapshot serialization or seat-existence leak; Origin alone never authorizes. Token in query string does not authenticate. |
| Untrusted Origin, `null`, near-match origin, wrong scheme/port; valid token plus disallowed Origin | Denial; no wildcard/reflected CORS on success, errors or OPTIONS. Approved-browser fixture requires both exact origin and valid credential; native missing-Origin fixture still requires credential. |
| Simple cross-origin GET and OPTIONS preflight | Simple GET is protected independently of preflight. OPTIONS contains no evidence, does not enable anything and never calls capture/runtime. |
| Rebinding-style hostile Host resolving to loopback, wrong authority/port, nonloopback peer, spoofed forwarding headers | Rejection by explicit envelope policy; no dependence on DNS, CORS or real browser protections. Fake tests do not prove actual platform binding behavior. |
| P2-only grant, request for P1/all/missing/duplicate/conflicting seat; mixed-seat cached object | Deny invalid/scope-expanding requests; no host fallback. Distinct synthetic P1 canary text/items/name/path never appears in P2 metadata, errors, discovery or serialized nested fields. |
| Redacted P2 grant with P1 canary embedded in P2 prompt/label/token; raw-field request without raw permission | Omit raw text, labels and identity-bearing token representation; no substring-based assurance of arbitrary text redaction. Explicit raw grant is separately tested and documented as able to contain P1 information. |
| Success/error/cache variants and excessive requests | no-store/nosniff/JSON policy, no credential/log leakage, bounded work. All paths assert zero tools, MarkContact, enqueue, TakeMail and game writes; GET leaves sample time/sequence and gameplay bookkeeping unchanged. |

These fixtures belong to a future pure request-policy/projection layer and fake cache transport, without constructing AgentRuntime or starting Stardew Valley. Real HttpListener/OS prefix behavior and any approved browser mode require separate non-game integration/security validation. Privacy review of legacy routes remains an explicit residual dependency.

## 4. Host load, P2 ordering and Python mapping

Host authority allocates a fresh load_id and branch_id at each host load, including same-folder/same-day reload; process restart changes adapter identity. save_id can be provisional/unknown without reliable read-only world identity. Never derive checkpoint ancestry from folder/day/name. Unknown ancestry remains null. Python reconnect does not allocate a game load.

P2 SaveLoaded records joining evidence attached to the current host generation; if host authority is absent, quarantine attachment. Require an own-screen ready farmer after character/join menus before allocating a ready seat incarnation. Readiness loss/rejoin retires the old incarnation. Existing Active timeout is diagnostic and may conservatively invalidate evidence, but does not prove leave/rejoin. Verify actual callback screen/main-player ordering before making authority guarantees. Title return invalidates current eligibility without canceling actions or claiming rollback.

[observation.py](https://github.com/niabchan/stardew-ai-agent/blob/5f537945288919d7373c737b5a5d999d12863638/reference/sunny_gift/observation.py) is a merged **game-free synthetic reducer**, not a C# adapter:

| Reference behavior | Required mapping / limitation |
| --- | --- |
| Scope, host_load, join, leave | Map explicit authoritative events. host_load rejects reused load/branch IDs and clears current seats; join advances incarnation; leave changes generation. Do not invoke join per poll or on each unready tick. |
| Capture/Observation.capture | Validates source-local ordering, identical duplicates and conflicting IDs; rejects retired prompt reuse. Copies known synthetic identity/coverage inputs. C# must establish these inputs; the reducer cannot discover missed lifecycle changes. |
| Prompt.content and revision | Includes question, ordered responses, is_question, family, classified. Transition/identity/coverage gaps cause revisions on both sides of uncertainty. Keep this behavior in cross-language fixtures. |
| cached/fresh | Returns original latest capture; checks clock, current scope/latest capture, ready/complete/coverage and bounded age. No cache restamping. Generic fresh does not itself certify a gift; current_offer applies prompt checks. |
| token/current_offer/offer | Token serializes scope, prompt instance and revision. current_offer requires P2, known/classified stable gift question and exactly unique accept/decline mapping, plus exact world/token/mapping/open/fresh offer. Agree canonical wire token representation or treat token as opaque; do not independently invent incompatible C# JSON. |
| ObservedReference.sync/dispatch | Load change reloads; seat generation changes fence. dispatch is inert contract logic with guarded_dispatch=false. It must never be wired directly to legacy respond. |
| save_started/save_completed | Explicit fixture evidence only. Completion records completion_observed, not loaded-byte identity or ancestry; checkpoint candidates remain uncertainty. No C# saving/saved instrumentation is necessary for first prompt sampler. |

Wire schema needs separate validation: finite clock values, safe integer ranges, enums, null/absent semantics, ordered mappings, version compatibility and unknown fields. The reference's immutable offer should retain identity across refreshed captures; offer fresh=true is not a substitute for current capture checks. Repeated GET is not consumption/acknowledgment; deduplicate by scope+sequence. No claims of durable replay, durable cursor, receipt, save persistence or model memory follow from this latest-only route.

## 5. Gaps, failure modes and test boundaries

All tests below are proposed and unrun. Research validation was static source/report review only; no build, automated behavior tests, live game, controller, model, save or deployed files were accessed.

| Severity / precondition | Failure | Future isolated test |
| --- | --- | --- |
| Critical: equal-looking replacement or in-place reuse | Wrong prompt accepted as old offer | New instance despite equal text; reorder/change raw mapping; close/reopen between samples; gap/transition recovery invalidates both old and uncertain tokens. Unsupported lifecycle coverage stays false. |
| High: host load then delayed P2 join/rejoin | False new world or stale seat | One host load, joining/unavailable P2, new incarnation only on attachment; old callbacks/captures rejected; same-folder/day reload creates new load. |
| High: stale P2 while host/HTTP continues | False freshness | Frozen/stalled screen, cached reads, slow network, wrong clock, negative/NaN age, old scope and partial components; no host-heartbeat substitution. |
| High: reuse of tool/HTTP helper | Observation changes play or consumes messages | Spy/fake route test: zero MarkContact, enqueue, TakeMail, SetReleased, RunControl.Handle mutation, click/close/claim/save calls; roles/contact/timeout/release/mail unchanged across GETs. Assert exact bytes/sequence/time unchanged on cached reads. |
| High: unknown response semantics | Wrong gift classification | Localized labels, unrelated Yes/No, duplicate keys, extra responses and unavailable keys stay unclassified. No fallback response. |
| Medium: partial publication/load race | Mixed epoch or torn payload | Concurrent readers see one immutable capture; lifecycle mismatch yields unavailable; P1/P2 clocks/skew disclosed; bounded payload/retention under repeated GET. |
| Medium: enabled sampling overhead | Frame-time regressions | Pure copier budgets, payload bounds, publication cadence and no blocking I/O; truncation/gaps produce incomplete evidence. Measure real overhead separately. |

Future game-free C# tests should exercise a pure lifecycle/normalization reducer and fake read-only screen source, not replicate property getters. Share synthetic sequences with the Python reducer: unchanged prompt, replaced equal prompt, revision change, transition/gap recovery, absent/unavailable distinction, duplicate/out-of-order/conflicting capture, rejoin, load/title invalidation and clock mismatch. An HTTP integration fixture must prove passive cache delivery without constructing a game runtime or invoking tool lanes.

An explicitly authorized operator later uses a backed-up Test_ save, known source/DLL/SMAPI/game versions and one controller. Observe actual host→farmhand callbacks and menu events; human Guy opens/cancels/repeats Daffodil/Potato offers, unrelated dialogues and overnight menus; verify keys, exact screen binding, same-object reuse and coverage. Compare enabled versus disabled sampling for menu/contact/freeze/mail behavior and frame load. Manually test delayed join, P2 stall/rejoin, title return and same-day reload. Preserve silence/STAY and optional speech. None of these actions is run or authorized by this research PR.

## 6. Boundaries and dependencies

External P10–P13 Python/PowerShell ZIPs, installed game assemblies and operator save state remain uninspected. Vanilla gift response keys, menu lifecycle coverage and actual SMAPI callback ordering remain unknown. #12's checkpoint strategy is separate future research; this scope reads no save bytes and writes no markers. Two inventory snapshots are correlation, not giver/receipt proof.

A1/A3 must review identity retirement, lifecycle authority and every competing response route before any guarded capability. A2 must define inventory variant/completeness and causal transfer evidence; no inventory delta is promoted here to receipt. A4 must consume observation uncertainty and permit decline/defer/STAY/silence without automatic cleanup or speech. Integrator review is required for shared AgentHttp/Players/ModEntry changes; this report is not cross-track sign-off.

## 7. Smallest safe future C# implementation PR

After design review, scope one opt-in diagnostic spike to:

1. One disabled-by-default config flag, immutable DTOs and pure identity/lifecycle reducer/cache in a new narrowly scoped evidence module.
2. Minimal ModEntry subscriptions/hooks for host/title invalidation, candidate menu lifecycle evidence and own-screen P1/P2 sampling. Fail closed on unsupported coverage; leave all existing gameplay paths untouched.
3. One independent passive GET route in AgentHttp with explicit capabilities, bounded latest-only snapshots and unavailable reasons, gated by the privacy/authentication/projection policy above and fake HTTP security tests. No McpDispatcher/AgentTools/Perception behavior changes.
4. Isolated reducer/copier/route tests and documented operator-only validation criteria. Prompt/seat capture first; optional inventory component can remain unsupported until A2 specifies it.

Exclude guarded response dispatch, controller fencing implementation, gift classifier claims without evidence, receipt verification, durable memory/cursors, checkpoint discovery, save markers, save hashing, cleanup/default answering, automatic export and deployment. This spike can establish evidence feasibility while guarded_dispatch remains false. A later guarded-action PR is a separate design and validation task.

This PR changes documentation only. No gameplay code, running Stardew Valley, mod deployment, save modification or merge.
