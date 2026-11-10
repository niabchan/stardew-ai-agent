# A1 + A3 — Observation and save lifecycle research

Research/design proposal, 2026-11-05 (Asia/Bangkok). **No runtime behavior is implemented or approved.**

Inspected target `docs/sunny-agentic-design-review-round1` at **24f5f5caf29d466bace2dec48998b7f78b046c72** (merged #11). Read Sunny companion notes, root agent instructions, all seven architecture documents, the A1/A3 reports in [#6](https://github.com/niabchan/stardew-ai-agent/pull/6) (head `cb99879e612a22b071201bc11c82d1cc90d6b01a`) and [#8](https://github.com/niabchan/stardew-ai-agent/pull/8) (head `6dc8b9916641fea006f1d4d0f86d7cff06089156`), and the merged reference implementation, tests and synthetic fixture. Findings from earlier reports are attributed where not freshly inspected. Git transport failed at the workspace proxy; GitHub connector reads supplied the pinned source. The older local checkout was not used as the target baseline.

**Fact** = inspected source behavior; **Proposal** = future interface or handling; **Unknown/Hypothesis** = requires additional source or operator evidence. No live tools, saves, installed assemblies, private logs, deployed files or external pilot ZIP were accessed. Only this documentation is proposed for publication.

## 1. Observed code map

All source links below pin the inspected commit; methods identify the relevant seam.

| Source | Fact and limit |
| --- | --- |
| [ModEntry.cs:52](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/ModEntry.cs#L52), `Entry/OnSaveLoaded` | Subscribes to SaveLoaded, ReturnedToTitle, DayStarted/DayEnding and UpdateTicked. No Saving/Saved subscription in this entry point. OnSaveLoaded explicitly documents a callback on joining farmhand screens before their character exists; host-only work follows the ScreenId check. The handler also changes options/starts brains: do not invoke it as an observation API. |
| [ModEntry.cs:105](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/ModEntry.cs#L105), `OnUpdateTicked` | Runs per-screen runtime, then captures seat state every 15 ticks; host refreshes HTTP JSON every 15 ticks. Runtime and watchers can change the menu before capture. Nominal cadence is not freshness under stalls. |
| [Players.cs:23](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/Agent/Players.cs#L23), `PlayerSlot/ScreenState.Capture` | Screen identifies a seat; Active means it ticked in the last two seconds. Capture must run on that screen's game thread. Ready, menu, day and position exist; Dialogue is speaker display name, not prompt text. No prompt identity, capture sequence, typed inventory or load identity. Active alone does not prove character readiness. |
| [WorldText.cs:67](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/Agent/WorldText.cs#L67), `MenuState` | Reads current DialogueBox string, isQuestion and ordered responseText values. Flattens newlines/carets in display. Does not expose response keys, menu instance or revisions; text output cannot recover original raw structure. |
| [AgentTools.cs:834](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/Agent/AgentTools.cs#L834), `Respond` | Uses the current DialogueBox and option index, checks range, sets selectedResponse and clicks while not transitioning. No expected-token/mapping guard. It checks box/text changes during its coroutine but can try repeated clicks. “Dialogue closed/continued” proves neither semantic choice nor transfer. |
| [AgentHttp.cs:98](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/Agent/AgentHttp.cs#L98), `Handle/RefreshState` | MCP accepts AI-role seats; bare /mcp selects host. Human P1 must not be role-switched for observation. /api/state returns cached StateJson; RefreshState combines cached seats with live host fields. Top-level dialogue is host context. Heartbeat does not version P2 capture. |
| [McpDispatcher.cs:9](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/Agent/McpDispatcher.cs#L9), `IMcpSeat/Dispatch` | Existing interface is a control/transport seam, not a pure observer. Every message calls MarkContact, including ping/list, affecting connection/freeze bookkeeping. Instant observations can run during actions. JSON-RPC correlation and seat session header do not identify a game load or deduplicate attempts. |
| [SplitScreen.cs:52](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/Agent/SplitScreen.cs#L52), `OnSaveLoaded/JoinNext/GuestTick` | Host load restarts joining timer. Join completion uses ready cached seat state excluding FarmhandMenu/CharacterCustomization. GuestTick activates slots/creates characters: this is mutation, not a read-only join probe. |
| [DebugApi.cs:672](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/Agent/DebugApi.cs#L672), `SaveFolder` | Name is Loaded or Constants.SaveFolderName when world-ready. Pending becomes Loaded on host initialization. This preserves requested folder spelling, not checkpoint identity. Do not call debug load/save routes to manufacture research evidence. |
| [Perception.cs:263](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/mod/StardewMCP/Agent/Perception.cs#L263), `Tick/SyncSave` | Tick exits when not ready; SyncSave only clears when SaveFolder.Name differs. Same-folder reload does not establish a reset. Earlier A3 audit additionally documents bounded/drained mail and caches outside Clear; no canonical replay/lineage can be inferred. |
| [contract.py](https://github.com/niabchan/stardew-ai-agent/blob/24f5f5caf29d466bace2dec48998b7f78b046c72/reference/sunny_gift/contract.py), `Record/Reference` | Immutable records and lookup use complete world + local ID/revision. dispatch is inert and compares current_offer to offer; fresh is supplied Boolean. reload takes caller-supplied world, increments fence and retains history. It discovers no real epoch/checkpoint and provides no game protection. |

### Existing read-only evidence: what can actually be reused

**Fact:** ScreenState.Capture and WorldText.MenuState show accessible reads on the correct screen. The latter is a formatting helper, not a typed observation contract. Game1.player.Items is an accessible collection (ModEntry's DayStarted handler iterates it), but that handler actually removes zero stacks. Reuse direct reads in a new sampler, never execute the handler. A2 must specify actual variant metadata and completeness.

**Proposal:** Capture human P1 on P1's own update without changing its role, selecting items, opening inventory or sending tools. P2 capture runs on P2's update. Copy scalar/typed values into immutable DTOs; HTTP threads never dereference live Game1/menu/farmer objects. Each seat's result is independently ordered; no claim of atomic P1/P2 simultaneity. Synced remote Farmer reads may be useful secondary evidence but must disclose source and synchronization limits.

**Fact:** /api/state is a passive read of cached JSON, but it is insufficient for prompt or inventory proof. MCP status/look can deliver useful current text through runtime; they are unsuitable as a strictly observational transport because MarkContact and result mail consumption affect bookkeeping. Existing IMcpSeat cannot promise “no gameplay impact.” A new passive cached evidence route is preferable to polling status for this spike.

## 2. Proposed prompt observation interface

These are design signatures/DTO fields, **not existing C# APIs**:

```text
ISeatEvidenceSampler.CaptureOnCurrentScreen(context) -> SeatEvidence
IEvidenceSnapshotReader.TryRead(seat, expectedLoad, afterSequence) -> capture | unavailable
IWorldLifecycleReader.Current -> WorldLifecycle
```

The sampler reads only; identity counters/cache updates belong to adapter bookkeeping. Reader returns the exact immutable capture with its original timestamp, never restamps cached data as fresh. No calls to MarkContact, click/close/claim, menu setters, movement, freeze release, speech, journal or runtime tool queue. Background HTTP GET reads cache only. A later request for a newer capture waits boundedly for an ordinary screen update or reports unavailable; it must not advance game time.

| DTO group | Proposed fields and invariant |
| --- | --- |
| World/seat | adapter instance/version, opaque save_id/load_id/branch_id, nullable parent_checkpoint_id, seat_id, screen_id, farmer alias, seat_incarnation, readiness and lifecycle reconciliation status. Rejoin changes incarnation; it cannot reuse a pre-leave token. |
| Capture | capture_id, source, per-seat sequence, screen tick, process-local monotonic timestamp, diagnostic UTC, complete, unavailable reason. Sequence advances per sample; cached reads preserve it. Compare clocks only within their declared source/process. |
| Prompt | menu family/type, prompt_instance_id, prompt_revision, raw question text (restricted local), is_question, transitioning, ordered responses with index/key/label, mapping digest, classification status/evidence/version. Missing menu differs from unavailable screen. |
| Inventory | seat/container incarnation, entries with qualified item ID, quality, stack quantity, slot and A2-defined metadata signature, completeness/source/capture metadata. Unknown differs from empty. No persistent item UUID inferred from slot or signature. |

**Prompt identity algorithm proposal:**

1. At each ready P2 update observe active menu reference and prompt fields. Allocate a process/load/seat-incarnation-scoped opaque instance when a menu opens or is replaced. Preserve identity across polls of the same instance; do not allocate per HTTP request.
2. Increment prompt_revision when raw content, question status or ordered mapping changes, including changes within one DialogueBox. Record transition state as capture evidence; never permit dispatch while transitioning. New identical-looking menu gets a new instance. Never use text hash/day/item as instance identity.
3. Inspect a candidate read-only menu-change event (SMAPI Display.MenuChanged) plus the per-tick sampler to close replacement gaps. **Unknown:** its ordering/coverage and in-place vanilla gift prompt reuse have not been verified here. Polling/reference equality alone can miss close/reopen between samples or in-place reuse with equal text. If lifecycle coverage cannot distinguish this, classify identity as ambiguous and disable guarded capability; do not advertise a safety guarantee.
4. Copy response indices and labels already demonstrated in WorldText. Reading the game's semantic response key (candidate responseKey) and distinguishing gift accept/decline requires checking the actual supported game API/version. This report has not inspected game assemblies. Yes/No text or index zero alone cannot certify semantics. Unavailable keys/classification yield unclassified/unsupported, zero mutation.
5. Offer identity binds world, seat incarnation and prompt instance/revision plus classification/mapping. A capture sequence is **not** a prompt revision: unchanged subsequent samples can refresh evidence without creating a second offer. Retain immutable captures and exact offer revisions.
6. Derive freshness from age, ready/current epoch, seat identity, completeness and observation coverage under an explicit negotiated policy. No universal “250 ms means safe.” Any capture can become stale immediately.

**Boundary:** even a perfectly fresh passive capture cannot make Python preflight atomic with execution. Future guarded dispatch must re-read identity, mapping, transition state, epoch and fence on P2's game thread immediately before mutation, and guard every subsequent click. Observation-only instrumentation must advertise guarded_dispatch=false until that work exists. Review Respond, CloseMenu, sleep/watchdog/overlay and broad proposal responders identified in A1 #6; guarding only external respond leaves competing mutation routes.

## 3. Proposed host load, join, save and restore lifecycle

Do not overload “session.” Four different transitions need separate evidence:

| Transition | Existing evidence | Proposed authority and handling |
| --- | --- | --- |
| Host loads a world | Host OnSaveLoaded branch, ScreenId 0, main-player/world-ready checks | Host adapter allocates new load_id and provisional continuation branch once per verified host load. Invalidate prior tokens/decision eligibility immediately; reconcile checkpoint before continuity claims. Verify callback multiplicity/order in actual SMAPI. |
| P2 joins/rejoins | Farmhand SaveLoaded and subsequent own-screen readiness | Attach seat incarnation/readiness to existing host load. Never mint a second world branch from this callback. Before character ready, capture unavailable. Host identity absent -> quarantined attachment, not a guessed epoch. |
| Game saving | No save-completion evidence in inspected entry point | Candidate host Saving/Saved event subscriptions in a future observation spike. Saving -> in_progress only; Saved -> completion candidate, subject to verified semantics. Neither implies every transient predicate serialized or an OS-durable transaction. |
| Earlier checkpoint restored | No folder/day/version discriminator | New host load always; map loaded artifact to a locally registered checkpoint if supported evidence proves it. Select that checkpoint's ancestry, exclude later descendants from active facts. Unknown match stays unknown. Day rollback is diagnostic, never authority. |
| Python reconnects | Transport/session contact | Reattach current adapter/world after negotiation and reconcile attempts. No new load/branch merely because the controller restarts. Lost adapter authority -> quarantine, not continuity from folder/day. |

**Proposed lifecycle record:** adapter_instance_id, host lifecycle sequence, transition kind, world/load IDs, phase (loading/ready/saving/reconciling/unavailable), optional save_operation_id/checkpoint_id/parent, evidence refs and reconciliation status. Seat-ready is separate from world-ready. Title return seals current eligibility; it does not prove queued/running effects stopped or rolled back.

**Checkpoint strategy to investigate:** an external, access-controlled local registry mapping stable save aliases and checkpoint lineage to fingerprints of the complete relevant saved artifact set. Capture fingerprints only after a supported stable completion boundary; compare the loaded incarnation using a load-time observation tied to that boundary. Do not hash “whatever is on disk later” and assume those bytes were what the game loaded. Checkpoint storage is local evidence, never committed to GitHub.

A save completion callback is not a unique content identity. An identical artifact can represent multiple save operations; keep save-operation identity separate and treat multiple checkpoint matches explicitly. Hashes alone cannot distinguish intentionally cloned worlds, identical restored copies or establish lineage. Folder path, file mtime, day/time and the save's intrinsic identifier are hints, not sufficient identity. A full-byte hash may change for irrelevant serialization differences; incomplete fingerprints can miss meaningful changes. A per-save mod-data marker would alter saved state and is outside this read-only proposal. Do not silently adopt it.

Failure windows remain: save succeeds before sidecar registration, sidecar write fails, bytes change during read, process crashes, earlier copy replaces files under the same name. Preserve uncertainty; no automatic action replay. Hash matches identify candidate saved state, not historical giver provenance or which transient queues persisted. If exact mapping is unavailable, a fresh isolated branch can collect observations with parent_checkpoint_id=null, but continuity-dependent memory/actions remain quarantined.

On a proven older load, preserve audit history; select only eligible ancestor events for supported persisted predicates, exclude abandoned descendants and their dependent reflections/plans/reaction decisions. Reobserve current possession. Do not erase unknown attempts or label historical execution ended. Controller fencing must span built-in and Python routes; an expired lease is not proof of termination.

## 4. Python gift contract consumption

[CONTRACT_REVIEW.md](./CONTRACT_REVIEW.md) remains the broader review candidate. The merged [reference README](../../reference/sunny_gift/README.md) explicitly excludes runtime binding, durable claims/cursors and checkpoint discovery.

| Existing reference seam | Safe adapter mapping / required extension |
| --- | --- |
| Record.read/make | Preserve sunny.gift/1.0.0 envelope, exact refs and opaque world identity. Validate real adapter payloads before entry: Record.read is not a full wire validator. Do not use producer.adapter_version="synthetic" for actual captures. |
| offer payload token/responses/fresh | Encode authoritative instance/revision in opaque token; map validated semantic accept/decline keys to exact indices. Store capture ref, ordered raw mapping/classifier evidence in a separately reviewed observation extension. Current offer subset has no mandatory seat/capture metadata. Never turn English regex into typed item identity. |
| Reference.dispatch(attempt, current_offer) | Equality test is a synthetic guard, not a live guard. New captures with unchanged identity should not rewrite an immutable offer merely to refresh age. Maintain capture provenance separately and supply the canonical current offer; a real server must independently validate it at execution. No call from this reducer should be connected directly to legacy respond. |
| observe_reply | Keep reply_completed, execution and observed_choice independent. A non-unknown choice needs actual evidence; an arbitrary evidence string accepted by the toy API is not a production verifier. Tool acknowledgment cannot certify acceptance/receipt. |
| publish | A2 owns typed ordered P1/P2 deltas plus causal attestation. Actual competing mutation exclusion must be established externally. Missing source/destination/causality -> unknown verification. A1/A3 never fabricate the attestation. |
| reload(world) | Caller must supply authoritative reconciled world; this function cannot discover it. It excludes all prior epochs conservatively, including legitimate ancestors. Checkpoint-ancestor eligibility needs a separate reviewed reducer. |
| context/context_is_current | Freeze event revisions per decision, retain unresolved outcomes and optional silence/STAY. Current possession remains unknown until observed. In-memory publication position is not durable ingestion or save acknowledgment. |

**Proposed negotiation/recovery protocol:** Python first checks supported observation schema, adapter instance, epoch authority, P2 identity, classification/mapping support and guarded-dispatch capability. Unknown major/version or missing safety capability fails closed for mutation; passive observation may continue. No fallback from safe mode to legacy index respond or forced decline.

Deduplicate observations by world/source/seat/capture sequence; reject out-of-order, wrong-seat and old-load records. Canonical prompt identities survive polling; two real equal prompts get distinct offers. Record decisions against exact offer/context revisions. At eventual dispatch, server claims an attempt bound to canonical arguments and fence before effects. Lost reply -> status reconciliation, never resend an ambiguous mutation. dispatch call result's stale_epoch/dispatched_now must be consumed separately from historical attempt_status; historical dispatched does not mean dispatched now.

Separate durable evidence/event publication from local Python activities and Luna-authored notes. Replayed events/corrections update the next context without another response or mandatory speech. The audited pilot's folder/day/question dedup and transient respond_answered are migration inputs, not authoritative facts. Actual pilot source remains uninspected here; no implementation prescription assumes its internal APIs.

## 5. Gaps, risks and proposed tests

Severity is design priority; these are possible failures, not reproduced incidents.

| Priority / precondition | Risk | Required evidence or fixture |
| --- | --- | --- |
| Critical: prompt replaced after capture | Wrong unrelated choice clicked | Same-text replacement, reordered options, in-place mutation, transition and old seat incarnation all invalidate token; zero clicks. |
| Critical: response lost or old controller still running | Duplicate mutation/two controllers | Historical attempt lookup, conflicting args, old fence, early reply/running, crash windows; no redispatch or inferred termination. |
| High: host load and P2 join callbacks | Two false world epochs or premature readiness | Simulated host load followed by delayed join/rejoin yields one load, distinct seat incarnations; late old capture quarantined. |
| High: same-folder same-day reload/older restore | Abandoned gift becomes active memory or new gift suppressed | New load/branch, parent matching/ambiguity, ancestor selection, identical fresh gift; old decisions invalid. |
| High: save-start or sidecar append treated as save | False persistence | Saving without Saved, failed/duplicate callbacks, crash after save before registry, incomplete/unstable fingerprints all retain uncertainty. |
| High: two inventory deltas without causality | False giver/receipt attribution | Competing harvest/chest/spend and missing P1 evidence remain unknown; capacity/partial/debris tested independently. |
| Medium: cache restamped/HTTP polling affects clock | False freshness or observation changes behavior | Cached sequence/time stable; stalled/absent screen unavailable; passive reader invokes no tool/contact/freeze/mail APIs. |
| Medium: raw prompts/fingerprints published | Private data leak | Only synthetic/redacted fixtures committed; identifiers, hashes, saves, paths and private text stay local. |

### Actual validation in this research

Static GitHub source/document review only. Read the merged reference tests and fixture; no automated behavior suite, C# build, live tool, model call or integration test was run. Prior results in reference/VALIDATION.md are historical recorded results, not new passes. Documentation publication is limited to this report. All following tests are proposed and unrun.

### Operator-only Test_ save matrix

A future explicitly authorized operator uses a backed-up Test_ save, one controller, known source/DLL/config/SMAPI/game versions, and local restricted evidence capture. Research does not execute these steps.

1. Load host with delayed P2 join, then rejoin P2. Record actual callback screen/main-player/readiness ordering, menu-change coverage, seat incarnation and host epoch. Confirm passive capture never marks AI contact, drains mail, clicks or changes freeze policy.
2. Human Guy offers known Daffodil/Potato. Record P2 exact menu type, raw question, semantic response keys, indices and locale. Repeat identical offers; cancel/reopen between samples, replace with unrelated dialogue, change options within a box and exercise transitioning. Determine whether an instance can be reused invisibly. A missing lifecycle discriminator blocks safe prompt capability.
3. Independently select accept, decline or silence/STAY under the reviewed flow. Test capacity constraints and cancellation races, P1/P2 typed before/after visibility and synchronization. Identify trustworthy causal evidence; mere equal deltas remain correlation. Validate vanilla behavior separately from AI queue/debris. No obligation to speak or journal.
4. Observe normal overnight saving: compare Saving/Saved/DayStarted order per screen, successful save versus interruption/failure and delayed callback. Establish which predicates are persisted, including inventory versus prompt/queues. Day change and sleep reply alone must never set checkpoint-linked.
5. Receive a gift without saving, reload same folder/day; then save/reload, and restore an older backed-up checkpoint. Repeat with same-name copied artifacts and ambiguous matches. Confirm new host load, correct ancestry/unknown state, no abandoned gift in active context and a new equal offer remains eligible.
6. Restart only Python while game stays loaded, separately restart game/mod, and simulate lost acknowledgments in an isolated harness. Preserve world on controller reconnect; new adapter authority cannot assume continuity. Old running/unknown attempts remain historical and are never replayed. Test registry write failure/crash after save without forcing a real destructive game fault.

No claim about actual SMAPI Saved/MenuChanged semantics, vanilla response keys, complete inventory visibility, stable fingerprint timing or checkpoint persistence is established until these tests or corresponding versioned source evidence close the gap.

## 6. Dependencies and questions for review

- **A1/A3:** agree token lifecycle, capture versus prompt revisions, host epoch authority and ambiguity handling. Review every internal menu mutation route before advertising guarded dispatch.
- **A2:** define variant signature/completeness and persisted predicates; demonstrate read-only P1 source capture and causal proof without controlling Guy. Human gift semantics remain separate from SocialTools AI give.
- **A4:** consume immutable event/context revisions and corrections; negotiate capabilities and one controller mode. Keep accept/decline/defer/STAY and optional speech independent of verification.
- **Integrator/operator:** approve the checkpoint evidence strategy only after host/farmhand callback ordering and artifact matching are proven. Review privacy, durable recovery and all shared AgentHttp/Perception/runtime/controller changes. This report is not joint sign-off.

## 7. Small implementation plan (future PRs, no implementation here)

1. **Smallest first PR:** extend only the unwired reference fixture with a pure observation-normalizer/lifecycle reducer and synthetic records. Model separate host-load, seat-join, save-start/completion and ambiguous older-checkpoint inputs; test capture ordering, prompt-instance/revision mapping and token invalidation. Do not discover checkpoints, call game code or make new runtime guarantees. Review envelope compatibility with A2/A4.
2. **Separate opt-in read-only spike:** add immutable own-screen prompt/inventory DTO capture and host lifecycle event recording; expose a passive cache reader and explicit capabilities. No dispatch wiring, save markers, gameplay cleanup or deployment. Verify no bookkeeping contact/freeze/mail effects. Use operator-captured redacted evidence to resolve Test_ assumptions.
3. **Separate checkpoint adapter review:** local stable-artifact registry/fingerprint feasibility, ambiguity/lineage and crash recovery fixtures. Keep parent unknown until proven; add ancestor eligibility without weakening current conservative reference behavior.
4. **Only after evidence/review:** guarded C# dispatch and controller fencing, then A2 transfer proof, durable A3 event/context bridge and A4 integration in separate scopes. Runtime/behavior validation and operator approval precede risky merges. No PR is merged by this task.

Source set: [charter](./README.md), [baseline](./ARCHITECTURE_BASELINE.md), [track briefs](./RESEARCH_TRACKS.md), [Round 1](./DESIGN_REVIEW_ROUND1.md), [decision log](./DECISION_LOG_ROUND1.md), [contract review](./CONTRACT_REVIEW.md), [sanitized pilot audit](./PILOT_AUDIT_V0311.md), [reference tests](../../reference/sunny_gift/tests/test_contract.py), [synthetic fixture](../../reference/sunny_gift/tests/fixtures/gift.json). Historical research findings are not installed-version certification.
