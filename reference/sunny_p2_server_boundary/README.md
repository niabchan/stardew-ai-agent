# Sunny P2 Phase 2C — real-server seam inventory and **fake-only** side-effect ordering

**Status: source-grounded integration preparation, NOT secure runtime wiring.**

This document inventories the **actual checked-in legacy HTTP/MCP/game-thread code** at PR #22 base commit `b1acd27083cfd5ad560ed8e91dc038ce39419010`. The new C# fixture and tests validate only a *proposed ordering of synthetic counters*. They do not execute `AgentHttp`, `McpDispatcher`, `AgentRuntime`, `SessionBreaks`, `WorldClock` or SMAPI.

## Exact file boundary

- `mod/StardewMCP.Tests/FakeP2ServerBoundary.cs`: fake boundary wraps the already-tested `FakeP2AtomicIntake` and records synthetic accepted context-break starts, validated owner presence, admitted tool-start contact, per-operation execution-budget assignment, action start logging, freeze eligibility and synthetic game step counts.
- `mod/StardewMCP.Tests/P2ServerBoundaryOrderingTests.cs`: verifies denials and lifecycle transitions cause **no attributable fake request side effects** before admission; acquired owner presence is explicitly distinct from started work.
- This Markdown audit is the only other addition. No changes to `AgentHttp.cs`, `McpDispatcher.cs`, `McpSeat.cs`, `AgentRuntime.cs`, `SessionBreaks.cs`, `Players.cs`, `ModEntry.cs`, `WorldClock.cs`, deployed DLL, external Luna scripts or `main`.

## Checked-in source call flow — verified legacy behavior, **not** recommended behavior

| Source evidence (line references at audited base) | Current behavior / risk | Future P2-specific integration boundary |
| --- | --- | --- |
| [`AgentHttp.cs:61–95`](../../mod/StardewMCP/Agent/AgentHttp.cs#L61) | Attempts localhost/127.0.0.1 `HttpListener` prefixes, falling back to localhost on `HttpListenerException`; accepts requests and spawns unbounded `Task.Run(() => Handle(ctx))`. | Limit connections/tasks; establish a trusted raw-request adapter with true socket peer, raw Host and HTTP framing/body bounds **before any dispatch**. Do not trust parsed aliases or silently drop duplicate headers. |
| [`AgentHttp.cs:98–129`](../../mod/StardewMCP/Agent/AgentHttp.cs#L98) | Sets `Access-Control-Allow-Origin: *` on all responses; routes `/mcp` to P1, selects seats from URL, and returns **DELETE 200 with no owner retirement**. | Separate viewer, watchdog, operator, P2 control, P2 observation and private replay grants; reject noncanonical aliases for P2; never treat a bare DELETE 200 as quiescence. Remove wildcard CORS only in a coherent, reviewed route-wide migration. |
| [`AgentHttp.cs:131–212`](../../mod/StardewMCP/Agent/AgentHttp.cs#L131) | Serves `/api/state`, feed/day, memory, briefings, replay and control/meta/release-freeze routes with no per-route grant boundary in this source. | Define and enforce route-to-grant policy for **all** endpoints; securing only `/mcp/p2` leaves exposure and write side doors. Minimal P1 safety projection remains separately consent-controlled. |
| [`AgentHttp.cs:279–301`](../../mod/StardewMCP/Agent/AgentHttp.cs#L279) | Optional debug handler reads body then directly calls `seat.Runtime.Enqueue`. | Gate debug by operator-only grant and production-off default; no bypass around the P2 owner/epoch queue admission. |
| [`AgentHttp.cs:306–320`](../../mod/StardewMCP/Agent/AgentHttp.cs#L306) | MCP body is read without preflight bound; `SessionBreaks.Observe` and the seat-wide volatile `ReplyWithinSeconds` mutate **before** `_mcp.Handle`. | Bounded raw read, strict auth and policy admission FIRST; authenticated context-break state only for successfully acquired sessions; per-operation deadline, not overwriteable per-seat shared mutable request timeout. |
| [`McpDispatcher.cs:62–83`](../../mod/StardewMCP/Agent/McpDispatcher.cs#L62) | Batch entries are processed sequentially; `Dispatch` calls `seat.MarkContact()` **before** method/params validation; invalid or discovery messages can affect contact/freeze. | Prevalidate/reject batches atomically under a defined profile; discovery/invalid requests must not signal control contact. Validated controller presence may precede tool start; action-start effects require revalidation at start. No old session reintroduction. |
| [`McpSeat.cs:17–26`](../../mod/StardewMCP/Agent/McpSeat.cs#L17) | `MarkContact` calls `PlayerSlot.MarkContact`; tool calls dispatch to `seat.Runtime.EnqueueCall(..., observation:true)`. | Introduce an authenticated, owner/role/epoch/budget-checking admission seam **before** `EnqueueCall`. Keep human P1 separate and AI seat routing explicit. |
| [`Players.cs:31–82`](../../mod/StardewMCP/Agent/Players.cs#L31) | Shared `Connected`, `TimedOut`, `ReplyWithinSeconds`, `Released`; `MarkContact` sets connected, clears timeout and freeze-release state (method at lines 77–82). | Denied, stale, discovery and unauthorized requests cannot set any of these. Reset epoch-scoped contact state on verified host transitions without affecting unrelated seats. |
| [`AgentRuntime.cs:96–115`](../../mod/StardewMCP/Agent/AgentRuntime.cs#L96) | `EnqueueCall` sends to action or observation `ConcurrentQueue` with no bounded per-epoch P2 owner claim in this method; stop control is checked for AI-sourced calls. | Atomic queue capacity+owner+epoch+role+tool schema preflight, with durable claim *before* mutation dispatch. Purge **both** pending lanes promptly on retirement; don't confuse pending call completion with quiescence. |
| [`AgentRuntime.cs:203–284`](../../mod/StardewMCP/Agent/AgentRuntime.cs#L203) | `Lane.Tick` dequeues and `Start` records stats/logs before/while checking session breaks and world/loop conditions. | Revalidate the same immutable owner/grant/epoch/role at dequeue→start **before** stats/contact/log or tool runner invocation. Recheck before later coroutine steps. |
| [`AgentRuntime.cs:285–399`](../../mod/StardewMCP/Agent/AgentRuntime.cs#L285) | `Step` can execute nested `IEnumerator.MoveNext` repeatedly in one tick; `Interrupt` disposes stack (whose finally handlers may mutate logs/world); `Finish` emits hints, logs and completion. | Fence at **each nested MoveNext** and before cleanup/response projections; tool-specific safe disposal and partial/outcome-unknown evidence. A reply timeout, disconnect or Dispose does **not** prove rollback. P12 bedtime requires separately bounded long execution. |
| [`SessionBreaks.cs:63–90`](../../mod/StardewMCP/Agent/SessionBreaks.cs#L63) | A request containing initialize can reset/arm context breaks; `?breaks=1` opts in. | Only authenticated + acquired P2 initialize may update context breaks. Context-window reset is not a security lease and is not a host save epoch. Migration must address legacy query controls intentionally rejected by PR #31. |
| [`ModEntry.cs:54–60,95–113`](../../mod/StardewMCP/ModEntry.cs#L54) | SaveLoaded callback fires on host and guest; host path checks screen 0 before role resolution. ReturnedToTitle currently stops brains/split screen but has no new P2 lease coordinator. | Establish authoritative host-only save incarnation at true transition; dedupe host callback while not conflating a fresh load of the **same** save/day/time; fence old queues, started work, grants, projected data and contact **before** next world effects. Guest callbacks must not rotate epoch. |
| [`ModEntry.cs:116–156`](../../mod/StardewMCP/ModEntry.cs#L116) / [`WorldClock.cs:74–99`](../../mod/StardewMCP/Agent/WorldClock.cs#L74) | Each screen ticks a runtime; host ticks freeze/WorldClock; a connected AI can cause pause/timeout behavior. | Implement per-game-thread boundary checks with role-appropriate P2-only freeze eligibility, no stale or denied control, and no direct P1 automation. |

## Proposed future request ordering — **design only**

```text
trusted socket/raw HTTP adapter
  -> route grants (including NON-P2 routes) and bounded body/framing/Host checks
  -> exact P2 preflight (PR #31, currently dormant)
  -> authenticated principal + credential incarnation + host epoch + role
  -> one atomic owner/queue/capacity/dispatch claim (PR #33 model, not real)
  -> return denial without contact, deadlines, logs, context-break mutation or queue
  -> acquired control-owner initialize: session issuance, context bookkeeping, owner presence
  -> presence can make idle P2 eligible to freeze BEFORE its first tool starts
  -> accepted tool request: atomic queue claim + immutable per-operation response deadline
  -> game-thread dequeue/start: revalidate grants/owner/epoch/role and game-run guards
  -> only then execution budget, permitted timeout/release rearm, stats and action-start log
  -> nested coroutine MoveNext: recheck before EVERY step/world effect
  -> outcome journal (completed | cancelled_before_start | interrupted_partial | unknown)
  -> scoped response, no-store; never infer verified DELETE retirement from HTTP 200
```

**Review decision: moving the whole `MarkContact` operation to tool start is unsafe for gameplay.** `WorldClock.IsThinking` requires `Connected` and no action running; an initialized controller planning its first action would otherwise allow game time to advance. Once connected, thinking after an action can still freeze, so the defect is especially visible on first attachment or after contact reset. `MarkContact` also clears `TimedOut` and the day's explicit release: those are separate permissions, not harmless liveness.

Use two events: **validated control-owner presence** at successful lease acquisition (and a separately specified, bounded owner renewal if needed), and **admitted tool start** after game-thread revalidation. Presence is scoped to P2's credential incarnation, session, host epoch and role generation. It must not by itself clear a timeout or explicit operator release. Discovery, notifications, denied calls and stale sessions neither create presence nor renew it. Queued work is not a started action; while an authorized owner is idle or waiting for its first start, presence may support freeze under the existing world/menu/operator rules. Freeze eligibility is not a command to pause: active seat, AI role, `ActionRunning`, `TimedOut`, `Released`, night menus, waking and operator hold still matter (`WorldClock.cs:47–103`). Do not allow observation traffic to rearm a timed-out controller indefinitely. Choose and test an explicit recovery/rearm policy for authenticated actions and operator release; the fixture does not simulate these flags.

A separate response deadline must be captured **at atomic admission**, including queue wait, rather than created only at start. An execution budget can begin at start. `Perception.cs:449–478` uses `Queued` age for both pending replies and the active call; replacing it with a start-only budget could strand waiting requests. A 1200-second P12 bedtime HTTP wait is neither a 1200-second thinking lease nor cancellation. The fake has no wall-clock deadline, real pause or client migration test.

## What the new fake tests actually assert

- Denied bad Origin, wrong Host/port, P1 aliases/seats, duplicate Host, unsupported protocol/query, invalid UTF-8 and unknown credentials leave **synthetic** contact, reply-budget, freeze-eligibility and action-log counters unchanged.
- Successful control-owner acquisition increments synthetic context-break and presence counters, making idle freeze eligible before any tool starts. Rejected initialize cannot do that. Discovery and notifications do not refresh presence; trusted lease expiry may still clear eligibility.
- Accepted queue admission alone does not count as a start or fake world step; owner presence already exists. Valid simulated start updates tool-start contact/execution-budget/rearm counters in either lane; only action-lane starts increment action logs. These rearm counters do not simulate timeout/release state. Only a subsequent `FakeStep` changes the fake step count.
- Revocation, host reload, role change and unverified DELETE fence queued/running work; tests preserve prior step counts (no false rollback) and distinguish old unknown effects from successful completion.
- Discovery does not refresh provisional lease. Guest join and duplicate current host callback do not destroy a valid lease.
- All counters are created by the test fixture, **not observed from the real sources above**. They cannot establish that no gameplay side effects occur in the running mod. CI's success is proof of the internal model only.

## Independent review of PR #35 for Issue #36

Reviewed original head `385bd1c821142e95f953bcbd07ae25458f3c06fb` against checked-in source (runtime files unchanged by this correction).

| Severity | Finding and exact source | Resolution / remaining boundary |
| --- | --- | --- |
| High (design) | Original fixture `FakeP2ServerBoundary.cs:107–135` and original README ordering postponed all contact/freeze until start. `WorldClock.cs:77–82` requires connected idle AI; `Players.cs:77–82` also rearms timeout/release. | Split acquired owner presence from tool-start counters. First planning interval now has a regression assertion. Presence alone never models timeout/release rearm. Production integration remains unimplemented. |
| Medium (design) | Original fixture `FakeP2ServerBoundary.cs:129–131` assigned all reply budget at start; `Perception.cs:451–478` answers pending and running calls by age since queue admission. | Specify immutable response deadline at admission, execution budget at start. The renamed synthetic counter represents execution budget only; no deadline arithmetic is claimed. |
| Medium (fixture) | Original fixture `FakeP2ServerBoundary.cs:74–90` cleared freeze for unrelated credential revocation/grant removal; `Provision` did not clear it when replacing the owner's credential. | Derive eligibility from current owner, clear invalidated presence, retain it for unrelated principal changes. Added regression coverage for both cases. |
| Low (source precision) | Original runtime range ended at result logging (`AgentRuntime.cs:394`), before outcome/task completion at `396–397`. | Expanded finish anchor; all listed HTTP/MCP claims are confirmed, with the route/role qualifications described here. |

### Side effects and coroutine fences

- **Before authority:** bounded parsing and isolated, redacted security diagnostics only. Never invoke gameplay `PlayerLog.Add`, `SessionBreaks.Observe`, per-seat reply budget, `MarkContact`, `RunControl.Handle`, release-freeze, debug enqueue or private projections on a denial. Wildcard CORS at `AgentHttp.cs:102`, P1 alias/role gate at `113–128`, unscoped routes at `141–207`, and debug enqueue at `279–301` are existing exposure, not corrected runtime behavior. `/mcp` selects the host but is refused when P1 is Human. DELETE 200 follows the same seat gate and does not tear down anything.
- **Acquired owner:** context-break reset/arming and bounded P2 owner presence only. `SessionBreaks.cs:66–90` also arms an existing session for a wanted non-initialize request; blindly retaining that call before dispatch preserves the side door. Session context and save epoch must remain separate. Successful discovery must not renew owner authority.
- **Atomic admission:** validate immutable credential/session/epoch/role/grants, schema and both lane capacities; capture response deadline and durable attempt identity. Queue denial does not publish presence refresh or per-call effects. Recheck and serialize invalidation with publication. A positive preflight alone grants nothing.
- **Own-screen game-thread start:** verify actual host incarnation and exact P2 screen (never fallback to host), owner/grants/role/brain and world/stop/session-break/loop conditions before starting tool code. `AgentRuntime.cs:105–112` routes only `observation && Instant` to observations; other calls use actions. `Start:247–277` currently records stats and clears sights before session-break refusal, logs before world/loop guards, and invokes `Tool.Run`. Guard refusal and session-break refusal themselves may mutate counters (`SessionBreaks.cs:101–118`), so they too require authorized context. Authorized refusals may have intentional accounting; denied authority must not reach it.
- **Every executable frame:** `AgentRuntime.cs:324–337` can enter a child and resume its parent in one tick. Fence each `MoveNext`, runner invocation and effect boundary, including side-effecting completion/cleanup; a check once per tick is insufficient. Concurrent retirement must serialize with a safe step or cooperatively fence inside a step that contains multiple effects. A check followed by an unsynchronized revocation race is not protection.
- **Retirement/finish:** purge both pending lanes immediately and release capacity; marking `Done` alone is insufficient (`AnswerQueued:120–129` only answers action entries, which remain until dequeue). Fence running work before the next effect. `Interrupt:348–359` disposes iterators; `Finish:363–399` instead clears the stack then updates Guard, mail, SessionBreaks, stats and result logs. Neither is generic rollback or safe disposal. Keep authorized historical accounting in an epoch-scoped outcome journal without modifying a successor's Guard/session/caches. Tool-specific cleanup may be mandatory after authority loss; execute only narrowly reviewed cleanup, record partial/unknown effects, and withhold reuse until quiescence/reconciliation. `AgentTools.cs:1352–1362` sleep cleanup cancels a ready check, unseals briefing and changes stats/logs: disposal can affect the world.
- **Bedtime/HTTP:** `AgentRuntime.cs:78,294–303` exempts `go_to_bed` from ordinary runtime timeout/new-day interruption; `WorldClock.cs:53–54` permits waking/night transitions. `Perception.cs:455–470` may answer bedtime early while its action continues. Preserve those semantics with an independently bounded execution/cleanup contract. Do not freeze merely because the HTTP waiter returned, release ownership on HTTP timeout, or claim DELETE response proves quiescence. The test labelled bedtime uses `say` and synthetic time 1200; it is not a bedtime coroutine test.

### Lifecycle and model limits

`ModEntry.cs:95–113` runs diagnostic invalidation, split-screen load helpers, world-progress reset and focus configuration on guest callbacks before the screen-0 return; only then host role resolution and brain startup run. It supplies no new authoritative P2 host epoch. `ReturnedToTitle:55–63` stops brains/split screen and resets some state, but does not clear the new lease/contact/queues because they are not wired. `Players.Resolve:184–210` retains runtime instances and changes roles; cached state, thinking stopwatches and contact cannot be assumed reset. A future authoritative host transition must distinguish a duplicate callback from a distinct reload of the same save/day/time. Guests must not rotate it. Fence old grants, queues, started work, projections, freeze and caches before new effects; brain/role changes also invalidate P2. Restrict this exclusive lease to P1 Human / P2 AI / external brain none; do not capture other upstream AI seats.

The outer fixture lock serializes concurrent invalid requests; the concurrent test establishes deterministic final denial state, not a production lock schedule. The privileged `betweenPhases` hook tests an actual stale-admission interleaving. Synthetic Start updates counters before FakeStep, so zero world-step count never implies no prior bookkeeping effects. Historical counters survive invalidation intentionally. Expiry/retirement can clear presence during an otherwise denied call; independent trusted lifecycle housekeeping is not a request-authorized mutation. No test proves that autonomous unrelated game ticks have no effects. No verified DELETE recovery for PR #26, native credential issuer, real deadline, coroutine disposal, raw HTTP framing or installed-client compatibility is supplied here.

**Disposition:** with these material model/document corrections, suitable only as a source map and game-free design reference stacked on PR #22's Draft design branch. Keep PR #35 Draft and unmerged. This does not secure the listener or establish compatibility with the current Sunny/Luna pilot. All production gates below remain open.

## Next mandatory integration gates

The **next PR must not yet enable P2 authentication on an otherwise permissive listener**. First implement/test a raw boundary adapter and **all-routes denial inventory** that does not accidentally break current pilot or private P1 data; mock or isolated localhost protocol tests can be added without Stardew, but should not use the user's live mod or private logs. Then implement a real, server-owned credential+session/epoch/atomic queue coordinator with game-thread checks/cleanup. Native Luna client initialization/bearer/session/epoch migration must be ready before any switch; current supplied v0.3.11 is snapshot evidence only. Real retirement proof, unknown-outcome reconciliation, P1 consent projection, OBS roles, secure token storage, P12 long-running cancellation and Windows SMAPI acceptance remain separate gates.

## Review validation (2026-11-08)

- Local game-free C#: **619 passed, 0 failed/skipped**, using .NET SDK 8.0.100 and the .NET 6 runtime. The SDK 6.0.428 attempt failed on existing raw string literals in `BrainTests.cs` (CS8652); no project/source workaround was applied.
- Local Python: **286 passed, 1 existing xfailed**, using an isolated pytest environment.
- All 15 relative source links and line-anchor bounds resolve; `git diff --check` passes. The diff against PR #22's base contains exactly the three permitted paths. No private attachment or credential material was added.
- Final pushed-head CI must be checked independently; these local results do not predict a workflow result or instrument the real game.

## Validation commands

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

Run in PR CI; never infer actual pass counts before checking job logs. Do not build/deploy the installed mod, launch Stardew, connect to a live HTTP endpoint, request credential material or merge to `main`. Keep this PR Draft until an independent review of its checked-in source inventory and proposed test ordering.
