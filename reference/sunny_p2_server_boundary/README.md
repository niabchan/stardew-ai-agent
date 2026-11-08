# Sunny P2 Phase 2C — real-server seam inventory and **fake-only** side-effect ordering

**Status: source-grounded integration preparation, NOT secure runtime wiring.**

This document inventories the **actual checked-in legacy HTTP/MCP/game-thread code** at PR #22 base commit `b1acd27083cfd5ad560ed8e91dc038ce39419010`. The new C# fixture and tests validate only a *proposed ordering of synthetic counters*. They do not execute `AgentHttp`, `McpDispatcher`, `AgentRuntime`, `SessionBreaks`, `WorldClock` or SMAPI.

## Exact file boundary

- `mod/StardewMCP.Tests/FakeP2ServerBoundary.cs`: fake boundary wraps the already-tested `FakeP2AtomicIntake` and records synthetic accepted context-break starts, P2 contact, per-operation reply-budget assignment, action start logging, freeze eligibility and synthetic game step counts.
- `mod/StardewMCP.Tests/P2ServerBoundaryOrderingTests.cs`: verifies denials and lifecycle transitions cause **no attributable fake request side effects** before accepted work starts.
- This Markdown audit is the only other addition. No changes to `AgentHttp.cs`, `McpDispatcher.cs`, `McpSeat.cs`, `AgentRuntime.cs`, `SessionBreaks.cs`, `Players.cs`, `ModEntry.cs`, `WorldClock.cs`, deployed DLL, external Luna scripts or `main`.

## Checked-in source call flow — verified legacy behavior, **not** recommended behavior

| Source evidence (line references at audited base) | Current behavior / risk | Future P2-specific integration boundary |
| --- | --- | --- |
| [`AgentHttp.cs:61–95`](../../mod/StardewMCP/Agent/AgentHttp.cs#L61) | Starts both localhost/127.0.0.1 `HttpListener` prefixes; accepts requests and spawns unbounded `Task.Run(() => Handle(ctx))`. | Limit connections/tasks; establish a trusted raw-request adapter with true socket peer, raw Host and HTTP framing/body bounds **before any dispatch**. Do not trust parsed aliases or silently drop duplicate headers. |
| [`AgentHttp.cs:98–129`](../../mod/StardewMCP/Agent/AgentHttp.cs#L98) | Sets `Access-Control-Allow-Origin: *` on all responses; routes `/mcp` to P1, selects seats from URL, and returns **DELETE 200 with no owner retirement**. | Separate viewer, watchdog, operator, P2 control, P2 observation and private replay grants; reject noncanonical aliases for P2; never treat a bare DELETE 200 as quiescence. Remove wildcard CORS only in a coherent, reviewed route-wide migration. |
| [`AgentHttp.cs:131–212`](../../mod/StardewMCP/Agent/AgentHttp.cs#L131) | Serves `/api/state`, feed/day, memory, briefings, replay and control/meta/release-freeze routes with no per-route grant boundary in this source. | Define and enforce route-to-grant policy for **all** endpoints; securing only `/mcp/p2` leaves exposure and write side doors. Minimal P1 safety projection remains separately consent-controlled. |
| [`AgentHttp.cs:279–301`](../../mod/StardewMCP/Agent/AgentHttp.cs#L279) | Optional debug handler reads body then directly calls `seat.Runtime.Enqueue`. | Gate debug by operator-only grant and production-off default; no bypass around the P2 owner/epoch queue admission. |
| [`AgentHttp.cs:306–320`](../../mod/StardewMCP/Agent/AgentHttp.cs#L306) | MCP body is read without preflight bound; `SessionBreaks.Observe` and the seat-wide volatile `ReplyWithinSeconds` mutate **before** `_mcp.Handle`. | Bounded raw read, strict auth and policy admission FIRST; authenticated context-break state only for successfully acquired sessions; per-operation deadline, not overwriteable per-seat shared mutable request timeout. |
| [`McpDispatcher.cs:62–83`](../../mod/StardewMCP/Agent/McpDispatcher.cs#L62) | Batch entries are processed sequentially; `Dispatch` calls `seat.MarkContact()` **before** method/params validation; invalid or discovery messages can affect contact/freeze. | Prevalidate/reject batches atomically under a defined profile; discovery/invalid requests must not signal control contact. No per-tool effects until accepted start; no old session reintroduction. |
| [`McpSeat.cs:17–26`](../../mod/StardewMCP/Agent/McpSeat.cs#L17) | `MarkContact` calls `PlayerSlot.MarkContact`; tool calls dispatch to `seat.Runtime.EnqueueCall(..., observation:true)`. | Introduce an authenticated, owner/role/epoch/budget-checking admission seam **before** `EnqueueCall`. Keep human P1 separate and AI seat routing explicit. |
| [`Players.cs:31–82`](../../mod/StardewMCP/Agent/Players.cs#L31) | Shared `Connected`, `TimedOut`, `ReplyWithinSeconds`, `Released`; `MarkContact` sets connected, clears timeout and freeze-release state. | Denied, stale, discovery and unauthorized requests cannot set any of these. Reset epoch-scoped contact state on verified host transitions without affecting unrelated seats. |
| [`AgentRuntime.cs:96–115`](../../mod/StardewMCP/Agent/AgentRuntime.cs#L96) | `EnqueueCall` sends to action or observation `ConcurrentQueue` with no bounded per-epoch P2 owner claim in this method; stop control is checked for AI-sourced calls. | Atomic queue capacity+owner+epoch+role+tool schema preflight, with durable claim *before* mutation dispatch. Purge **both** pending lanes promptly on retirement; don't confuse pending call completion with quiescence. |
| [`AgentRuntime.cs:203–284`](../../mod/StardewMCP/Agent/AgentRuntime.cs#L203) | `Lane.Tick` dequeues and `Start` records stats/logs before/while checking session breaks and world/loop conditions. | Revalidate the same immutable owner/grant/epoch/role at dequeue→start **before** stats/contact/log or tool runner invocation. Recheck before later coroutine steps. |
| [`AgentRuntime.cs:285–394`](../../mod/StardewMCP/Agent/AgentRuntime.cs#L285) | `Step` can execute nested `IEnumerator.MoveNext` repeatedly in one tick; `Interrupt` disposes stack (whose finally handlers may mutate logs/world); `Finish` emits hints, logs and completion. | Fence at **each nested MoveNext** and before cleanup/response projections; tool-specific safe disposal and partial/outcome-unknown evidence. A reply timeout, disconnect or Dispose does **not** prove rollback. P12 bedtime requires separately bounded long execution. |
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
  -> accepted initialize: session issuance; only then context break bookkeeping
  -> accepted tool request: queued, but NO contact/log/deadline until start
  -> game-thread dequeue/start: revalidate grants/owner/epoch/role
  -> only then per-operation contact, timeout budget, safe action-start log
  -> nested coroutine MoveNext: recheck before EVERY step/world effect
  -> outcome journal (completed | cancelled_before_start | interrupted_partial | unknown)
  -> scoped response, no-store; never infer verified DELETE retirement from HTTP 200
```

The precise point to set `MarkContact` and reply timeout is **a proposed policy choice**, not a proven drop-in migration: `WorldClock`, P12's waiting behavior, current `SessionBreaks` and pause semantics may rely on contact on arrival. The real migration must preserve intentional gameplay semantics while ensuring denied calls never alter them, and test that with Windows/SMAPI. Do not implement by moving a single line without auditing the other routes/lanes.

## What the new fake tests actually assert

- Denied bad Origin, wrong Host/port, P1 aliases/seats, duplicate Host, unsupported protocol/query, invalid UTF-8 and unknown credentials leave **synthetic** contact, reply-budget, freeze-eligibility and action-log counters unchanged.
- Successful initialize increments a *synthetic context-break* counter but not gameplay contact; rejected initialize does not. Discovery and notifications do neither.
- Accepted queue admission alone does not count as a start or gameplay effect. Valid simulated start updates contact/deadline/freeze and action log only for action-lane starts. Only a subsequent `FakeStep` changes the fake step count.
- Revocation, host reload, role change and unverified DELETE fence queued/running work; tests preserve prior step counts (no false rollback) and distinguish old unknown effects from successful completion.
- Discovery does not refresh provisional lease. Guest join and duplicate current host callback do not destroy a valid lease.
- All counters are created by the test fixture, **not observed from the real sources above**. They cannot establish that no gameplay side effects occur in the running mod. CI's success is proof of the internal model only.

## Next mandatory integration gates

The **next PR must not yet enable P2 authentication on an otherwise permissive listener**. First implement/test a raw boundary adapter and **all-routes denial inventory** that does not accidentally break current pilot or private P1 data; mock or isolated localhost protocol tests can be added without Stardew, but should not use the user's live mod or private logs. Then implement a real, server-owned credential+session/epoch/atomic queue coordinator with game-thread checks/cleanup. Native Luna client initialization/bearer/session/epoch migration must be ready before any switch; current supplied v0.3.11 is snapshot evidence only. Real retirement proof, unknown-outcome reconciliation, P1 consent projection, OBS roles, secure token storage, P12 long-running cancellation and Windows SMAPI acceptance remain separate gates.

## Validation commands

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

Run in PR CI; never infer actual pass counts before checking job logs. Do not build/deploy the installed mod, launch Stardew, connect to a live HTTP endpoint, request credential material or merge to `main`. Keep this PR Draft until an independent review of its checked-in source inventory and proposed test ordering.
