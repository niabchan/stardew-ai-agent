# A1 — World interaction and action lifecycle research

Research only, 2026-11-04. Repository: `niabchan/stardew-ai-agent`; branch: `docs/sunny-agentic-architecture-phase1`; inspected HEAD: `11c4aa2fe12a2500d9ff9ad26e09437b40d93f92`. Refresh these references before implementation if the baseline changes. No gameplay calls, deployed files, saves, or external pilot ZIPs were accessed. No behavior was implemented.

Evidence labels: **Fact** means directly supported by inspected repository source; **Hypothesis** means a possible failure requiring reproduction; **Proposal** means a future contract or test, not an existing feature. Operator reports in the baseline are historical evidence, not tests executed by A1.

## 1. Observed code map

All paths below are relative to the repository root. Line numbers refer to the inspected HEAD.

### Entry, seat routing, execution and replies

| Source / method | Observed behavior and implication |
| --- | --- |
| `mod/StardewMCP/Agent/AgentHttp.cs:98`, `Handle`; `:306`, `HandleMcp` | `/mcp/p2` selects P2, checks its AI role and split-screen configuration. Bare `/mcp` selects the host, so callers must not assume it means Sunny. `reply_within` is stored on the seat from each request. DELETE returns 200 without canceling runtime work. |
| `mod/StardewMCP/Agent/McpDispatcher.cs:61`, `Handle`; `:78`, `Dispatch` | Batch requests execute sequentially within that batch. Every message marks contact; tools are resolved by name, then seat activity is checked. JSON-RPC `id` is echoed; no request-ID deduplication is performed here. Concurrent HTTP requests are not made exclusive by batch ordering. |
| `mod/StardewMCP/Agent/McpSeat.cs`, `CallToolReply` | Enqueues a `PendingCall`, awaits `Done`, then formats `ToolOutcome`. There is no transport-disconnect cancellation passed into the call. |
| `mod/StardewMCP/Agent/AgentRuntime.cs:14`, `PendingCall`; `:102`, `EnqueueCall` | Calls hold arguments, queued UTC time, instant/from-agent flags, completion task and optional outcome. There is no durable attempt ID or save-load identity. Non-instant work enters one action queue per seat; instant agent observations enter a separate lane. Stop-now rejects new agent work. |
| `AgentRuntime.cs:225–283`, `Lane.Tick/Start` | Starts a queued, unanswered call on the seat's screen. Checks session-break refusal, world readiness and loop guard. Coroutine execution happens on the game thread. A queue serializes effects for that seat, but does not enforce one controller per save or exclude another seat. |
| `AgentRuntime.cs:286–345`, `Lane.Step` | Non-instant work stops stepping under host pause. Its six-minute limit is 21,600 stepped ticks, not a wall-clock deadline while frozen. `go_to_bed` is exempt. Day advance can return a successful partial/interrupted result; damage can also finish a call. Exceptions can occur after effects. |
| `AgentRuntime.cs:348–397`, `Lane.Interrupt/Finish` | Explicit interruption disposes enumerators and returns `Ok=true`. Finish appends sightings, mail and current footer, logs the result and resolves `Done`. It does not generically verify a world postcondition. `Finish` itself clears the stack without the disposal loop used by `Interrupt`; timeout/exception cleanup deserves a separate audit. |
| `mod/StardewMCP/Agent/ToolDef.cs`, `CallContext`, `ToolDef`; `ToolResult.cs`, `ToolOutcome.From/Code`, `ToolResult.Structured/McpReply` | Context starts with `Ok=true`. Structured output has `ok/reason/text`, optionally `partial/data`; these classify tool execution, not transfer verification or save commitment. An unclassified successful result becomes reason `ok`. |
| `mod/StardewMCP/Agent/Brain/SeatBrain.cs:300`, `RunTool` | The built-in brain uses the same runtime queue and waits using `WaitAsync(ct)`. Canceling this wait is not a runtime rollback. This is distinct from the uninspected external Luna controller. |

`LoopGuard.Refuse/End` in `mod/StardewMCP/Agent/LoopGuard.cs` detects repeated failures/no progress. It is not exactly-once dispatch protection. `SessionBreaks.Observe/Refuse/Annotate` in `Agent/SessionBreaks.cs` handles conversational session boundaries; its session is not a unique game-load/timeline identity.

### Action categories and preconditions

`mod/StardewMCP/Agent/AgentTools.cs:67`, `All`, composes core, social, journal, economy, knowledge, NPC/romance, farming, crafting, building and other specialized tool definitions. This is a category map, not an exhaustive audit of every specialized tool's game rules.

| Category | Entry points and transitions | What the result establishes |
| --- | --- | --- |
| Observe / private thought | `Core` registers instant `status/look/inventory/think`; `MenuTools.cs:21`, `MenuTool`, makes `menu()` instant only when action is absent. | Observation or logged thought, not a world action. Mail can be consumed by tool results; instant does not mean side-effect-free data delivery. |
| Walk / travel | `AgentTools.cs:288`, `WalkToTool`; `:373`, `WalkTo`; `:451`, `WalkAdjacent`; `:885/:963`, `TravelTo` overloads. Blocked or occupied destination chooses adjacency; walking checks paths, stops on warp, replans after a stuck interval, and checks final tile on the same map. | Actual current tile is used in `Arrived at ...`; success need not mean the originally requested blocked tile. Warp exit from `WalkTo` is not proof of arrival at the original destination. Travel adds route/door logic. |
| Movement mechanics | `WalkController.cs`, constructor, `moveCharacter`, `Reached`, `ControlInput_Prefix`; `AgentTools.StartWalk/StopWalk`. | Controller follows the route using bounding-box tile reach; clears an old-map route after location change. It suppresses conflicting screen input while walking. |
| World interaction / held-item use | `AgentTools.cs:746`, `Interact`; `PressAction`, `JustRightClick_Prefix`. Requires a tile or a held item; resolves held item, walks adjacent, selects a tool when no holding was requested, presses the game action path, waits, compares labels/location/inventory totals. | `PressAction`'s boolean and text such as `Interacted` are not universal postcondition proof. Even `Nothing happened` leaves default `Ok=true`. The result may contain useful observed changes but no stable target identity. |
| Chair exit | `Interact` chair branch, `AgentTools.cs:758–781`. Requires current sitting furniture at the requested tile, no held item, and no menu/event/warp/fade. Calls `StopSitting`, waits up to 180 ticks, then checks `IsSitting`. | Verified clearing of the seated flag in this branch; not a general chair-sit verifier. A duplicate toggle after standing could sit down again. |
| Dialogue | `AgentTools.cs:834`, `Respond`. Requires a `DialogueBox` (or delegates to story wait). Questions require an in-range option. Captures current box/text, clicks while not transitioning, waits for text/box change. | `Dialogue closed/continued` describes progression only. Up to 40 loop iterations may click; the result has no selected response key, expected-prompt token or transfer evidence. A changed menu before execution can receive an option intended for an earlier one. |
| General menus | `MenuTools.cs:44`, `Menu`; `ReadMenu`, `PressOk`, `Cancel`, `ClickLabel`, `Take/Put`, `ChooseFloor`, `Amount`, `TypeName`. Rejects dialogue/shop/letter actions in favor of their own tools. Labels may match by substring. Take/put use clicks and before/after totals; cancel checks whether the original menu remained. | Some operations verify a local effect; `Pressed OK`/`Clicked` are acknowledgments. `ChooseFloor` can report no movement without failing. None binds an action to a prior observation of a specific prompt. |
| Close / claim | `AgentTools.cs:866`, `CloseMenu`; `CloseMenuTools.cs`, `ClaimBeforeClose/AcceptLetterQuest/ClaimGrabMenu`. Claims letter quests or fitting one-shot menu contents, excluding chest source, before closing; may force exit after 20 ticks. | Closing is a potentially resource-changing action. `No menu open` is benign, but `close_menu` is not generally safe to retry against a replacement menu. |
| Work / consumption / transaction | `UseTool`, `Plant`, `Harvest`, `Buy`, `Ship`, `Eat`, plus farm/crafting/building definitions registered by `All`. Requires relevant tool/item/energy/target/menu; batch effects can precede interruption. | Do not infer atomicity from one call. A2 owns detailed quantities/resource verification. |
| Time / rest / sleep | `Wait`, `Rest`, `DismissBedQuestion`; `GoToBed/LieDown`, `AgentTools.cs:1251–1390`. Rest differs from end-of-day sleep. | Waiting, resting, sleeping-ready, next day and persisted save are separate outcomes. |

`WaitIdle` (`AgentTools.cs:356`) exits when a menu opens so the model can handle it; expiration does not itself fail the context. `Snapshot/Diff` (`:509`) group inventory by **DisplayName**, collapsing quality and item-ID distinctions. They are useful text feedback, insufficient causal transfer evidence.

### P2 menus, P1 waiting, pause and bedtime

**Fact:** `p2_menu` appears in the research brief, not as an implemented C# state field in the inspected agent sources. The repository representation is `players[].state.menu`; it must be read for P2, not from the top-level host dialogue.

`Players.cs:129`, `ScreenState.Capture`, records menu type, tile, day/time, bed/sleep status, but `Dialogue` is the speaker name (or empty), not prompt text/options. `WorldText.cs:67`, `MenuState`, supplies dialogue text and numbered choices via a seat's tool result. No stable prompt revision is exposed.

**Fact:** `ModEntry.cs:104`, `OnUpdateTicked`, runs the seat runtime, then captures `seat.State` every 15 ticks; the host refreshes `AgentHttp.StateJson` every 15 ticks. `AgentHttp.RefreshState` serializes cached per-seat states plus live host fields/action names. HTTP `/api/state` serves the cached string. A fresh heartbeat does not prove a fresh P2 observation, and fields are not one atomic multi-seat snapshot. At nominal 60 Hz the cadence is about 250 ms, not a wall-time freshness guarantee under stalls. This is a concrete lag mechanism; it does **not** establish the cause of historical one-tile discrepancies.

`WorldClock.Tick/IsThinking` (`WorldClock.cs:46/:72`) freezes split-screen with host pause when a connected AI has no action, subject to config/timeouts/releases/night exceptions. Any MCP traffic can mark contact; even polling has clock implications. An observation can run during an action; it must not be treated as the final state of that action. A temporary P2 task is simply a queued/running action here; no inspected C# construct named “temporary P2 action” establishes the external pilot's pause/resume semantics.

`GoToBed` allows an absent journal and logs that fact; early healthy sleep before 17:00 is refused once per farm day. `LieDown` first invokes broad `CloseMenu`, travels home, calls `WalkTo`, then closes any remaining menu, sets bed state and invokes `Sleep_Yes`. **Fact:** it does not propagate the local `walk.Ok` before these steps. A reported path failure therefore does not by itself prevent the later sleep code. Actual game consequences require integration validation.

The sleep loop handles shipping/level-up screens, can return night questions for model choice, and waits for next-day readiness. Cancelable sleep-ready checks are canceled in its `finally` block on interruption. `Bedtime.Tick/StartStalledNight` (`Bedtime.cs`) configures required sleepers, warns AI seats, and can start a stalled night. It is not evidence that P1 accepted a gift or that a save committed.

`Perception.ReplyInTime` (`Perception.cs:445`) may resolve `Done=true` while `go_to_bed` **continues running** in bed. Later queued calls can be refused. `SafeToStop/TryInterrupt` (`:417/:484`) avoid stopping mid-tool/menu/warp/fade/event; permitted interruption clears walking and ends the action, possibly after partial effects. A response reaching the controller is therefore not identical to runtime termination.

Automatic menu paths already exist and need explicit review against the charter's unrelated-menu rule:

- `SleepWaitWatch.Tick` and `StaleMessage.ShouldClose`: close non-question AI dialogue after 2 seconds if empty, or 20 running seconds with another farmer waiting in bed; questions are spared, but canceled-gift text is not semantically identified.
- `UnknownMenuWatch.Tick` (`RunControl.cs:200`): during sleep, closes menu types outside its expected list after 600 stepped ticks, then forces exit on a later attempt. It does not verify gift provenance.
- `AgentRuntime.AutoHandleOverlays` (`:155`): automatic shipping/level-up handling and fallback cutscene question selection/clicking.
- `AgentTools.AnswerNightAlone` (`:1372`): after an early completed sleep reply, automatically picks the last response to night questions or names automatically. This is an existing fallback, not model choice or a safe generic gift responder.
- `RomanceTools.cs:550`, `AnswerProposal`, can answer generic Yes/No dialogue or confirmation/proposal boxes; `Romance.KindOf/MenuLine` classify broadly, excluding ready checks. It is not a validated incoming-item-gift classifier; do not repurpose marriage-proposal records as gift evidence.

### Two gift directions must remain distinct

**Human → Sunny:** the baseline reports external P13 detecting a vanilla gift prompt and sending `respond(option=0)`. The external recognizer, cancellation handling, ledger and decision loop are **uninspected**. Repository `Respond` accepts any current dialogue question with that index. It neither identifies giver/item nor confirms acceptance/transfer. Canceled text such as `Guy canceled the request.` must not become a fresh offer or automatic decline.

**Sunny → another seat:** `SocialTools.cs:156`, `Target`, selects only other active **AI-role** seats by ID/name. `Give` (`:287`) checks item count/ID/quality, same map, distance ≤4.5 tiles, and recipient capacity from the synced farmer; removes sender items, queues a copied item, logs and returns `You gave ...`. `SocialTools.Tick` (`:200`) later adds it on the recipient screen, or drops debris if capacity changed, then sends text/perception notification. It has no recipient acceptance choice. With Guy configured as human P1, `give(to=p1)` is not supported by this target selector. A2 must assess a separate supported vanilla path; A1 cannot claim this API hands an item to human Guy.

## 2. Boundaries / not inspected

- Read root `AGENTS.md`, `SUNNY_COMPANION.md` and all three pre-existing files in `docs/sunny-agentic/` in full. Inspected the A1 starting sources and adjacent routing, clock, sleep, proposal, social and test code above.
- P10–P13 Python/PowerShell ZIPs, including the actual `p2_menu` parser, controller lock, temporary-action handling and P13 gift ledger: **not supplied, not inspected**. No assumptions about their retries or persistence are facts.
- Stardew/SMAPI implementation assemblies, deployed DLL version/configuration, actual gift menu types/localized response keys, save files and live runtime: not inspected. Repository wrappers show calls into the game, not proof of underlying vanilla transfer semantics.
- Historical pilot/build results are documented claims; this report does not repeat them as current integration passes. Full inventories/resources, memory reconciliation and companion policy remain A2/A3/A4 responsibilities.

## 3. Gaps & failure modes

Severity is design-review priority: critical = possible duplicate irreversible effects/wrong consent; high = lost items, stalled control or false factual records; medium = misleading feedback/diagnostic weakness. None is a claim of a newly reproduced live incident.

| Priority / evidence | Preconditions and failure | Required handling |
| --- | --- | --- |
| Critical; fact + consequence hypothesis | Network reply lost after dispatch; client resends `respond/interact/give/buy/ship/craft`. No inspected attempt ledger prevents re-execution. | Treat outcome as unknown; reconcile, never blindly resend. JSON-RPC ID is correlation, not idempotency. |
| Critical; fact | A model observes a gift question, but cancellation/replacement occurs before queued `Respond` or generic `AnswerProposal` executes. Index/Yes can target unrelated current content. | Compare expected prompt identity at execution on the game thread; mismatch refuses before clicking. |
| High; fact | `CloseMenu`, sleep cleanup or watchdog meets an unrelated prompt/one-shot item menu. Cleanup can dismiss or claim contents without a gift-specific decision. | Specify which automation must be gated; merely guarding `respond` leaves other mutation routes. |
| High; fact + loss hypothesis | `Give` removes sender stack before recipient tick; runtime/process stops, capacity changes, or recipient stops ticking. | Model queue/delivery/debris separately; no transfer-confirmed event on sender acknowledgment. Crash-loss behavior needs controlled reproduction. |
| High; fact | Early sleep reply arrives while coroutine remains alive; observer/controller assumes it ended and starts a new activity/controller. | Expose reply-completed and execution-running separately; preserve one controller per save. |
| High; fact + stale-state hypothesis | Reload same save/day in same process or restart controller after an ambiguous dispatch. `Perception.SyncSave` keys on folder name; runtime call structures lack load epochs. | A3 defines a new load/session branch; quarantine stale attempts, do not reuse farm day as identity. Full cross-subsystem reset behavior remains unaudited. |
| High; fact + effect hypothesis | Bed path fails or menu changes during `LieDown`; walk outcome is ignored before forcing sleep state. | Review sleep postconditions and scoped menu handling separately; operator test required. |
| Medium; fact | Cached P2 state differs from immediate result/footer or host fields; display-name deltas merge item variants. | Stamp per-seat observations, distinguish stale/missing from negative evidence. |
| Medium; fact | Interrupt returns `Ok=true`, generic `Nothing happened` can be successful, timeout may follow partial work. | Separate execution status from verified effect; absence of error is not success evidence. |
| Medium; audit hypothesis | Timeout/exception uses `Finish` without explicit disposal/StopWalk used by perception interruption. | Test controller/enumerator cleanup; do not assert rollback or leaked movement without reproduction. |

Read-only observation is generally repeatable **as observation**, but mail consumption and clock contact matter. Walk/travel can be replanned only after checking current location/menu and old execution status. Toggle interactions, menu choices, item use/transfer, transactions and sleep are never automatically retried on ambiguous outcome. A known pre-dispatch rejection can permit a fresh attempt after eligibility changes; this is different from replaying a dispatched action.

## 4. Contracts proposed

All contracts below are **proposals**, requiring cross-track review. Preserve existing tool names and compatible output fields. A1 owns attempt/dispatch facts, not inventory truth, memory commitment or speech.

### Action envelope and two independent states

Proposed input: `schema_version`, opaque `attempt_id`, opaque `save_id`, `load_session_id`, `branch_id`, `controller_lease_id`, `seat_id`, tool/arguments, `intent_source`, optional `expected_observation_id` and `expected_prompt_id`. A new model choice creates a new attempt; transport retry preserves the same attempt ID.

Proposed output: same identities, `execution_state` (`not_started`, `queued`, `running`, `ended`, `rejected`), `effect_state` (`not_observed`, `unknown_outcome`, `verified`, `contradicted`), `reply_completed`, dispatch count/time/tick, tool acknowledgment, reason/partial, evidence references and verification predicate. Keep game tick/day/time separate from monotonic elapsed time and UTC diagnostics. `verified` always names a predicate (e.g. seated flag cleared), never universal action success. `persisted_after_save` remains unknown/unconfirmed until A3 supplies commitment evidence.

Lifecycle: intent → validate lease/session/preconditions → queue → revalidate expected prompt on execution → dispatch once → acknowledge → observe → verify or retain unknown. Timeout/disconnect is not cancellation or non-dispatch. Cancellation requests must distinguish removing never-started work from interrupting a running action with partial effects; no rollback promise. An early reply must not mark execution ended.

### Idempotency and persistence

- Key attempts by save/load/branch + seat + attempt ID, bind to canonical arguments. Same key/same arguments returns known status/result without dispatch; conflicting arguments reject. JSON-RPC session strings such as `stardew-p2` do not satisfy this identity contract.
- Record queued versus actually dispatched separately. Atomic claim before dispatch is required. After crash between claim/effect/evidence, conservatively classify unknown and reconcile; a ledger cannot guarantee atomic exactly-once game effects.
- A3 owns durable local storage and save/reload reconciliation; A1 supplies transitions. Persist metadata outside repository, with no raw private paths/save contents. Do not replay pending/dispatched work on a new load epoch. Revalidate old evidence before retaining memories. Retention/ledger pruning must not silently make old keys replayable.
- One controller lease per save must cover external and built-in controllers and seat-scoped actions; expiry does not prove in-flight work stopped. This is a proposed guard, not present enforcement.

### Prompt contract

Proposed `PromptObservation`: IDs above, seat, per-seat observation sequence/tick, menu family, question flag, response keys + labels + order, raw-content fingerprint, verified offer kind, giver/recipient, item identity/quantity/quality if evidence exists, transition/cancellation state, provenance and classifier confidence. Unknown fields stay null; a translated item label is not an authoritative ID.

`PromptDecision`: expected prompt token plus exact response key/index mapping and choice source. Tokens must change for content/options/replacement changes, not just new object references. Revalidate on the target screen immediately before dispatch; stale/missing/transitioning/unclassified prompts cause no click. No default ACCEPT/DECLINE. Non-question cancellation acknowledgment is a separate scoped action; unrelated menus remain untouched. Prompt disappearance alone cannot prove decline, cancellation or transfer.

### Handoffs and sole ownership

| Producer → consumer | Proposed fact/evidence contract |
| --- | --- |
| A1 → A4 | `gift_offer_observed` candidate with P2 prompt token, response mapping, source and known/unknown participants/item. A4 may choose accept, decline, defer or no action, independently of speech. |
| A4 → A1 | Decision bound to that exact prompt/session/attempt. Expired prompt returns stale, never silently maps the decision to the next box. |
| A1 → A2 | `response_dispatched`/dialogue-progressed evidence for human→AI; never `gift_accepted` as transfer truth. For AI `give`, sender removal/queued-delivery facts with item ID/quality/count and eventual recipient insertion/debris evidence. Distinguish this direct AI-seat path from vanilla human gifting. |
| A2 → A3/A1 | A2 alone verifies transfer outcome using before/after evidence and causal limits; inventory insertion, debris, nontransfer and uncertainty are distinct. Capacity precheck is not completion. |
| A1 → A3 | Attempt transitions, acknowledgment, unknown/verified predicate and observation IDs. A3 publishes/deduplicates grounded events, owns branch and save commitment. Avoid separate competing producers of `gift_accepted`. |
| A3 → A4 | Grounded, branch-aware outcome context; an optional model narrative never upgrades verification. |

## 5. Tests

### Baseline actually executed in this task

Working directory `/workspace/stardew-ai-agent`, inspected branch HEAD above:

```bash
.venv/bin/python -m pytest -q -p no:cacheprovider mod/tests
# 93 passed, 1 xfailed; exit 0
DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages DOTNET_CLI_TELEMETRY_OPTOUT=1 /workspace/.dotnet/dotnet test mod/StardewMCP.Tests --no-restore
# 268 passed, 0 failed, 0 skipped; exit 0
```

These are game-free checks, not mod compilation/gameplay validation. The C# project links selected game-free sources; `McpDispatcherTests` uses `FakeSeat` and `SampleTools`, not the real runtime/menu handlers. `StaleMessageTests` checks predicate timing/questions, not live dialogue closure. `WalkMathTests`/`PathfinderTests` cover movement helpers, not chair game state. Historical 267/268 documentation differs from this run; no source was changed to make it pass.

### Proposed isolated tests (not implemented or executed)

| Test seam | Required assertions |
| --- | --- |
| Pure attempt reducer / fake dispatch port | Duplicate ID dispatches once; argument conflict rejects; timeout leaves unknown; late acknowledgment reconciles same attempt; restart/reload never replays dispatched work. Include concurrent duplicate requests. |
| Prompt matcher with fake menu adapter | Correct P2 token chooses exact response; changed text/options/order/object/session refuses without a click. Cover stale question becoming non-question cancellation text, unrelated Yes/No, translated choices, transition and missing text. |
| Execution vs reply state | Early sleep `Done` does not end running state; repeated polling has zero dispatches; canceled wait/HTTP disconnect does not imply canceled game effect. |
| Verification reducer | `Ok=true`, `Dialogue closed`, `Nothing happened`, partial interruption and inventory label diff cannot establish transfer. Out-of-order snapshots remain stale; no observation is unknown, not failure. |
| Cleanup / clock adapters | Paused ticks do not consume action tick budget; wall deadline remains separate. Timeout/exception disposes or explicitly reports unfinished work; no assumed rollback. |
| Cross-track contract fixtures | A2 confirms only after recipient evidence; debris is not inventory receipt; A3 suppresses duplicate event publication and rejects abandoned-load evidence; A4 silence/decline remains valid. |

### Proposed operator integration matrix (all unrun)

Use a backed-up `Test_` save, one controller, explicit operator authorization, exact DLL/config/source version recorded locally. Observe the correct screen; never publish logs or saves to GitHub.

1. **Chair sit/stand:** locate chair; interact to sit, observe actual seated state, interact same chair to stand and check cleared flag; continue to another activity. Test different furniture, held-item case and blocked transition. Do not retry a lost toggle response.
2. **Human→AI gift:** Guy offers a known item; capture exact P2 prompt/options and stable item details. Let Luna accept or decline freely; dispatch once using the observed mapping. A2 verifies giver/recipient inventory changes. Acceptance without chat must pass; no transfer assertion from the response alone. Repeat with Daffodil and Potato without assuming option 0 universally means acceptance.
3. **Stale/canceled/replaced dialogue:** cancel before Luna's decision, replace with unrelated question/text, then submit the stale token. Expect zero clicks/new actions. Clear a positively identified cancellation message only by an explicit scoped operator/model choice. Verify no generic watchdog answers another question; current code may fail this proposed criterion.
4. **Timeout/no-repeat:** introduce controlled response loss after dispatch in a test harness; retry same attempt and observe one dispatch. Current code has no such guarantee. Confirm inventory/seat/menu before any new intent; do not test by blindly repeating live item actions.
5. **Bedtime and P1 waiting:** place P2 in the known canceled-message condition while P1 waits. Operator manually clears that exact message; request bedtime without journal and verify actual day change and awake state. Separately exercise freeze/resume, early reply while asleep, sleep cancellation, unexpected menus and full inventory. Next-day state alone is not persisted-save proof; A3 verifies save/reload.
6. **Result vs snapshot:** capture immediate result/footer, cached state heartbeat, P2 observation tick and subsequent stable tile/map. Reproduce one-tile discrepancy if possible; distinguish adjacency, warp, bounds and stale sampling. Do not “fix” coordinates by assumption.
7. **Give direction/capacity/reload:** verify human P1 targeting is rejected by current `give`; test AI-seat direct delivery, capacity change/debris and interruption between removal/delivery with A2. Reload the same farm day with A3; no stale attempt or gift memory may trigger an action.

## 6. Dependencies & questions for the other three agents

- **A2:** agree who alone confirms transfer; what exact item ID/quality/quantity/slot or stack identity is available on each screen? Can source and target evidence distinguish gift from unrelated item movement? What supported path could give to human Guy, and how are capacity/debris/cancel outcomes verified? Review the sender-removal/recipient-queue gap before changing `SocialTools`.
- **A3:** define save identity, fresh load epoch, abandoned branch, observation ordering and save commitment. Decide durable attempt/event storage, recovery retention, and what to do when source effect lacks an acknowledgment. Audit same-folder reload resets beyond `Perception.SyncSave`. How will consuming bounded mail coexist with replayable factual events?
- **A4:** obtain exact external P11/P13 sources before claiming cross-controller behavior. What prompt evidence reaches Luna today, how are external and built-in control made mutually exclusive, and how is a stale decision invalidated? Choice to STAY/say nothing/decline must remain independent of factual outcome. Agree on bounded decision context without hiding uncertainty.
- **Joint decisions:** scope every automatic menu mutation route, not only `Respond`; choose whether reviewed legacy compatibility may omit a prompt guard and under what explicit opt-in; agree on token/lease ownership and no-replay crash policy. Actual vanilla human gift menu classes/options need operator evidence. No other reports were supplied or peer-reviewed in this task.

## 7. Smallest safe first implementation PR proposal

**Proposal only, after architecture approval:** introduce a game-free, versioned attempt/verification reducer and synthetic contract fixtures covering duplicate IDs, unknown outcome, stale prompt, early reply/running distinction and reload invalidation. Limit ownership to the new pure contract module and its tests; explicitly leave it unwired, with no claims of active runtime protection. Review its schema with A2/A3/A4 first.

Then propose a separate, narrowly scoped additive observation PR for per-seat prompt revision/observation sequence and execution state, followed by an explicitly approved guarded-dispatch PR. Routing, `AgentHttp`, `Perception` and `SocialTools` changes require cross-track review. Do not bundle bedtime cleanup, gift transfer redesign, external pilot import or personality rules into that first PR. Operator integration gates remain mandatory before behavior merges. This report authorizes no implementation or merge.
