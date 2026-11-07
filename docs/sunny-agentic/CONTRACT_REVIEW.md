# Sunny contract review — A0 Architecture Contract Integrator

**Status: research/design proposal for review; not approved or implemented.**

Review date: 2026-11-04 (Asia/Bangkok). Guy is human P1, Sunny is AI P2, Luna is the external pilot decision model.

## 1. Scope and evidence

Reviewed `niabchan/stardew-ai-agent`, requested branch `docs/sunny-agentic-design-review-round1`, through GitHub at PR #10 head `ef0d2e2cda22e1cb96337918d4cc3426ceb0f51b`. Research reports were read from their separate PRs, not assumed integrated into #10. Local checkout remained on `work`; no checkout or repository file was changed. PRs #6–#10 were open drafts and fetched discussion timelines were empty. This review is not A1–A4 sign-off.

| Input | Pinned head / role |
| --- | --- |
| [A1 / #6](https://github.com/niabchan/stardew-ai-agent/pull/6) | `cb99879e612a22b071201bc11c82d1cc90d6b01a`; interactions and action lifecycle |
| [A2 / #7](https://github.com/niabchan/stardew-ai-agent/pull/7) | `180638791d747237a77f4537a9d4e5dee9d07877`; inventory and resource verification |
| [A3 / #8](https://github.com/niabchan/stardew-ai-agent/pull/8) | `6dc8b9916641fea006f1d4d0f86d7cff06089156`; events, memory and branches |
| [A4 / #9](https://github.com/niabchan/stardew-ai-agent/pull/9) | `8f727896e5a47f244071e448b7dd09bf7b76f915`; companion context and agency |
| [Round 1 / #10](https://github.com/niabchan/stardew-ai-agent/pull/10) | Head above; full `DESIGN_REVIEW_ROUND1.md`, `PILOT_AUDIT_V0311.md`, `DECISION_LOG_ROUND1.md` |

Also read [AGENTS.md](https://github.com/niabchan/stardew-ai-agent/blob/ef0d2e2cda22e1cb96337918d4cc3426ceb0f51b/AGENTS.md), [architecture charter](https://github.com/niabchan/stardew-ai-agent/blob/ef0d2e2cda22e1cb96337918d4cc3426ceb0f51b/docs/sunny-agentic/README.md) and [Sunny companion notes](https://github.com/niabchan/stardew-ai-agent/blob/ef0d2e2cda22e1cb96337918d4cc3426ceb0f51b/SUNNY_COMPANION.md) at #10 head.

The four reports inspect C# baseline `11c4aa2fe12a2500d9ff9ad26e09437b40d93f92`. Their source findings below are **attributed static evidence**, not fresh runtime verification by A0. Pilot facts are attributed to the sanitized audit. **The pilot ZIP is absent from the repository and was not directly inspected by A0.** Audit ZIP SHA-256 `662924ad5ca981b16425ca342bcabb3945a9867d10087ab969d3ea3c5a9521fb` identifies the Orchestrator's inspected artifact, not proof of the historically installed controller/DLL.

Research only: no gameplay code, deployed DLL, save, live game/model API, PR creation or merge. The decision log's suggested draft PR is superseded by the user's workspace-only instruction.

## 2. Implemented/reported behavior versus proposals

| Evidence | Reported existing behavior | Limit |
| --- | --- | --- |
| A1 §1: `AgentTools.Respond`, `AgentRuntime`, `Perception.ReplyInTime` | Respond operates on current dialogue/index. Runtime queues work; some sleep replies complete while execution continues. | No demonstrated expected-prompt execution guard or durable attempt dedup. `ok` and reply completion are not effect verification or termination. |
| A2 §1: `AgentTools.Snapshot/Diff`, `SocialTools.Give/Tick` | Some inventory deltas aggregate by display label. AI give removes sender items before later recipient insertion/debris and emits generic gift notification. | Not typed causal proof; debris is not receipt. AI-only target selector excludes human Guy. Vanilla incoming gifts are separate. |
| A3 §1: `Perception.TakeMail/SyncSave`, `AgentLog`, `JournalTools` | Bounded/drained mail, authored memory files, folder-based reset logic. | No demonstrated canonical event/cursor/checkpoint lineage. Local persistence can survive abandoned gameplay. |
| A4 §1: `SocialTools`, `SeatBrain`, `SpeechQueue` | Human chat can enter Sunny's tool-result context. Sunny can choose speech. Built-in no-tool handling nudges/releases. | Chat is a claim; queued speech is not attention. Built-in behavior is not voluntary resumable STAY. |
| Sanitized audit: `sunny_gifts.py:59,133,272,343–348` | English offer classifier; separate Boolean accept/decline Luna call; observed-state rechecks and dispatch marker; successful reply appends transient `respond_answered` choice activity. | P11 is partially informed, not wholly unaware. No verified receipt or durable grounded handoff. P13 has no speech/deferral output. Python preflight races C# execution. |
| Audit: `prior_dispatch:177`, cancellation handling `:187–270` | Save-folder/day/question-text dedup; narrow exact cancellation cleanup after prior successful decline and no P1 menu. Missing P1 menu forces decline. | Identical real second gifts and reloads are conflated. Cleanup exists in source, but live success is not certified. Forced decline conflicts with proposed no-default policy. |
| Audit: `sunny_loop.py`, `sunny_freeplay.py` | Per-save local lock; P11 sees last six activities; STAY waits for eligible snapshot/time, with bedtime exception. | Not shared authority against built-in brain, branch-aware memory or model-selected reconsideration semantics. |

Historical operator confirmation that particular Daffodil/Potato trials reached Sunny applies to those trials. It does not validate a general verifier, installed version, capacity/option behavior or save semantics. A1's reported baseline tests are not A0 tests and do not validate this interface.

## 3. Agreements, conflicts and missing evidence

All tracks agree on voluntary intent → guarded dispatch → observation → verification → canonical branch-aware outcome → next decision. They agree that silence, decline and STAY are valid; timeout never authorizes blind mutation retry; labels/day numbers are inadequate identity; authored prose cannot certify receipt.

The conflicts below are contract tensions rather than fundamental disagreement.

| Tension | A0 proposed resolution | Reviewers |
| --- | --- | --- |
| `gift_accepted` conflates intent, clicked option and receipt; A1 effect status overlaps A2 truth. | Separate requested choice, observed choice, execution, reply and transfer. A1 references A2 verdict without authoring transfer truth. No overloaded canonical `gift_accepted`. | All |
| A3 grounded event versus decision log's candidate/unresolved event. | One envelope can contain unknown outcomes, but only verified predicates enter verified-fact projection. Unknown transfer is not a receipt event. | A2/A3/A4 |
| P13 decline-on-missing-P1-menu versus no default choice. | Preserve as current audit fact. Proposed v1 rejects stale/unclassified offers with zero clicks; no conversion of ACCEPT to DECLINE. Cancellation needs positive evidence. | A1/A4 |
| Targeted cancellation cleanup versus unrelated-menu protection. | Separate notice-bound acknowledgment attempt, guarded on game thread. Never generic close/claim fallback. Audit sleep/watchdog/chest-error routes too. | A1/A2/A4 |
| A1 attempt ownership versus A3 durable storage/epoch ownership. | A1 owns attempt semantics and serialized dispatch claim. A3 supplies storage, lineage and event publication, not a second dispatcher. | A1/A3 |
| A3 event/outbox design versus D04 minimalism. | Define small shared records and recovery invariants first. Storage engine and global migration are deferred; no atomicity with game effects claimed. | A1/A3 |
| P13, P11 and built-in brain can all make decisions. | Provisionally retain Python orchestration/C# adapter per D01. Shared fenced ownership must cover every P2 mutation route. Python lock alone is insufficient. | All |
| Boolean P13 output versus defer/STAY and optional reaction. | New versioned decision contract; no silent parser expansion. Deferral does not click and expires with the offer. Speech is an independent later choice. | A1/A4 |

Missing evidence blocks runtime wiring, not this design:

- **A1:** authoritative vanilla offer identity, response keys/order/lifecycle, identical prompt replacement detection; complete auto-menu mutation and cleanup coverage.
- **A2:** typed P1/P2 observations without controlling Guy; stack metadata and actual quantities; causal evidence across non-atomic captures; vanilla capacity/partial/cancel behavior. AI queue mechanics cannot answer these questions.
- **A3:** host load/save/checkpoint authority, copy/restore identity, farmhand attachment, save/sidecar crash ordering, and which predicates actually persist.
- **A4:** immutable external prompt assembly and context receipt instrumentation, reaction recovery, quiet/sleep and STAY reconsideration semantics.
- **Joint:** installed controller/DLL hashes and exclusive mode, capability negotiation, storage failure/retention. A0 reviewed sanitized findings, not ZIP functions; direct cross-codebase review remains incomplete.

## 4. One minimal proposed interface: Sunny Gift Contract 1.0.0

This is a language-neutral documented interface, **not executable JSON Schema or runtime protection**. Scope is one Guy→Sunny vanilla offer, attempts, evidence, canonical outcome and next companion decision. No universal resource ledger, construction protocol, chest permissions or human-target `give` API.

Use one envelope with tagged records and immutable references. A3 maintains one future shared contract package; A1–A4 review their field semantics. Do not create four incompatible schema modules.

```json
{
  "schema": "sunny.gift/1.0.0",
  "kind": "attempt",
  "record_id": "A1",
  "revision": 1,
  "producer": {"track": "A1", "adapter_version": "fixture"},
  "world": {
    "save_id": "S", "load_id": "L1", "branch_id": "B1",
    "parent_checkpoint_id": "C23"
  },
  "refs": {"offer_id": "O1", "attempt_id": "A1"},
  "payload": {}
}
```

IDs are synthetic opaque aliases. Required envelope fields are schema/kind/record_id/revision/producer/world/refs/payload; references include exact ID/revision. Revisions increase per record. Unknown checkpoint is explicit null, never assumed continuity. Captures require source/seat, source-local sequence, game tick, process-local monotonic capture time, completeness and freshness. UTC/day/time are labels. Cross-process clocks and two screen captures are not assumed synchronized or atomic.

| Kind / producer | Required payload |
| --- | --- |
| `offer` / A1 | Offer ID, P2 capture ref, prompt instance/revision token, menu family/question flag, ordered response key/index/label mapping, classification evidence; nullable participant/item facts. Token changes on content/options change or replacement, including identical-looking new offers. Text hash alone is insufficient. |
| `decision` / A4 | Decision/context IDs, lease/fencing generation, exact event revisions considered, activity accept/decline/defer/stay/other, independent social intent silence/say/none, offer/token/mapping for gift choice, expiry and reconsideration conditions. Intent is not observed choice. Speech intent is not speech dispatch. |
| `attempt` / A1 | Decision ref, lease/fence, seat, tool/canonical args, expected offer/token/capture; execution not_started/queued/running/ended/rejected; dispatch not_dispatched/claimed/dispatched/unknown; reply_completed Boolean; ack/reason/partial; observed choice accepted/declined/canceled/unknown with evidence. Requested and observed choice stay separate. |
| `inventory` / A2 adapter | Observation ID, seat/farmer/container alias plus instance/revision, capture metadata/completeness; entries with qualified item ID, quality, metadata/signature, quantity, slot, display label. Unknown identity is null. Slot/signature is not a persistent item UUID. |
| `verification` / A2 | Offer/attempt refs, stable transition ID/movement ordinal, before/after inventory refs, actual variant/quantity, source/destination, causal evidence/intervening mutations, predicate/version; verdict unknown/verified/contradicted; disposition inventory_received/no_transfer/partial/debris/unknown. Nontransfer requires justification too. |
| `event` / A3 | Canonical event ID/revision, transition key, exact source record revisions, predicate/verification ref, observed scope, supersedes/corrects links; eligibility active/historical/quarantined; separate local record state and save state unconfirmed/checkpoint_linked/revalidated/unknown with checkpoint evidence. |
| `context` / A4 using A3 projection | Context ID, seat/lease/world identity, projection version, event revisions, cursor range/gaps; unresolved attempts/offers, current possession captures, labeled human claims/reflections, activity/quiet/STAY state. Immutable for one model request. |

These are variants of one interface. An offer/inventory capture can exist without an attempt: Guy acts as a human. A1 must not control P1 to manufacture evidence. Parsed display labels never fill unknown item IDs/counts.

### Transfer truth and event publication

1. A1 supplies prompt/dispatch facts; A2 alone supplies resource verdict; A3 validates references/lineage and publishes; A4 consumes and independently decides. A3 does not infer a transfer.
2. Verified Guy→Sunny inventory receipt requires matching actual variant/quantity source loss and destination gain **plus causality**: trustworthy game transaction evidence or a controlled observation window excluding competing changes. Net deltas alone are correlation. Missing P1 capture, source-only loss, recipient-only gain, display-label totals and `Dialogue closed` remain unknown for this predicate.
3. Observed acceptance is independent of receipt. Decline/cancel does not force no_transfer; contradictory inventory evidence remains visible. Zero net delta does not disprove a transient transfer.
4. Event vocabulary: `gift_offer_observed`, `gift_choice_resolved`, `gift_outcome_unresolved`, `item_transfer_observed`. Only verified causal inventory receipt supports “Guy gave Sunny one Potato.” Unknown outcomes are explicitly labeled. Later evidence revises the same canonical outcome ID; separately evidenced choice is a different transition.
5. Historical receipt and current possession are different. Consumption does not invalidate receipt. Stack merging prevents claims about the exact physical unit later returned. Save linkage does not imply prompts/queues were serialized.

### Dispatch, identity and recovery

- Host game adapter establishes authoritative load/branch and controller fencing; A3 owns lineage/checkpoint reconciliation; A4 attaches its controller. These responsibilities are proposed, with hooks still unproven. P2 join attaches to the host epoch, not a second branch.
- Attempt key = world identity + seat + attempt ID, bound to canonical arguments/decision. Same key/same payload returns status; conflicting payload rejects. Serialize claim before effect. On game thread immediately before mutation, recheck world/fence/prompt/mapping. Stale decisions get zero clicks. Expired lease does not prove old work ended.
- Persist claim before dispatch. Crash between claim/effect/record stays unknown. Never automatically replay claimed/dispatched/unknown work, including after load. Reconcile first; a newly eligible intentional action uses a new attempt. A known pre-dispatch rejection permits a newly validated attempt.
- Timeout, HTTP cancellation and early reply do not end execution or roll back effects. Keep reply and execution states separate. Missing acknowledgment never proves non-dispatch.
- Event key = world lineage + producer + stable transition ID + movement ordinal. Duplicate publication returns existing canonical event. Conflicting payload requires revision/quarantine. Never key on day/item/question text/prose. Polling one prompt preserves identity; a genuine new identical prompt gets a new identity.
- A3 preserves event identity/revision/publication position atomically in local storage where supported, without promising atomic game effects. Write failure remains recovery uncertainty. Retain dedup tombstones or explicitly close epochs; pruning must not reopen mutation keys.
- Unknown schema major versions or mutation-affecting enum values reject before dispatch. Compatible additive minor fields may be ignored; meanings cannot change. Python negotiates guarded-dispatch capability first. Legacy MCP is not advertised as v1-safe.

### Next decision and reaction

A3 provides replayable outcomes/corrections, durable cursors and explicit gaps. A4 acknowledges ingestion after storing the projection. This does not prove model understanding, speech or game save. Bounded mail/recent activity is notification, not authoritative storage. Gaps require resynchronization with uncertainty visible.

Before each model request, freeze current eligible events/unresolved outcomes in a context; record exact revisions with the decision. Events arriving in flight enter the next context. Epoch changes, prompt replacement and corrections invalidate dependent unsafe decisions before execution. No acceptance is repeated merely because an event is delivered again.

Track ingestion, model request, decision recording and reaction dispatch independently. Reaction intent is keyed by decision ID and cited event revisions. Replay does not create another reaction. Crash after speech dispatch but before completion recording is unknown; do not automatically repeat speech. Quiet/sleep may suppress interruption while retaining delivery. Voluntary STAY has reconsideration conditions; infrastructure timeout/budget exhaustion is a system state, not fabricated Luna choice.

## 5. Guy→Sunny example and case matrix

Synthetic nominal trace: C23 starts Day 24. On L1/B1, Guy offers one Potato. A1 captures O1 and exact P2 choice mapping. D1 chooses ACCEPT with social=SILENCE. A1 claims attempt A1 and guarded-dispatches once. A2 verifies matching typed P1 −1/P2 +1 with causal evidence. A3 publishes E1 revision 1, `item_transfer_observed`, save unconfirmed. A4's next context includes E1; Luna may STAY or pursue another activity. No journal, thanks or second response is required. This is proposed, not a tested pilot trace.

| Case | Required result | Prohibited inference/recovery |
| --- | --- | --- |
| Accepted, verified | Separate accepted choice and receipt; one E1 in next eligible context; save remains unconfirmed. | No mandatory speech or perpetual possession claim. |
| Accepted, uncertain | Ack/acceptance with missing or ambiguous evidence → unresolved; obtain fresh read-only evidence. | No receipt from `respond_answered`, source loss or elapsed time; never accept again to obtain proof. |
| Declined | Intent and guarded observed decline separately recorded; no_transfer only with causal support. Silence valid. | No assumption that absent positive delta proves no transient transfer. |
| Canceled before dispatch | Positive cancel evidence records canceled; stale token rejects. Replacement/unrelated dialogue receives zero clicks. Disappearance alone is unknown. | No forced decline/Yes/No/broad close. Exact notice acknowledgment is a separate guarded attempt. |
| Cancel race after dispatch | Retain dispatch and subsequent transfer/cancel evidence; unknown pending reconciliation. | Cancellation text does not undo effect or prove model decline. |
| Duplicate request/poll/delivery | Existing offer/attempt/event returned, no repeated reaction; conflicting args reject. | Event dedup cannot excuse duplicate dispatch. |
| Two genuine equal gifts | O1/O2, attempts and E1/E2 distinct despite same text/item/day. | P13's day/question key cannot be retained as v1 identity. |
| Lost reply/controller restart | Reattach to authoritative L1/B1, reconcile attempts, replay cursor without mutation or forced speech replay. | New connection/expired lock does not prove prior work stopped. |
| Unsaved reload C23 | L2/B2; E1 historical in B1, excluded from active facts/dependent plans/reflections/reactions. Invalidate leases/tokens/decisions, rebaseline and reconcile runtime/queues. New real gift becomes E2. | No current-branch thanks for E1, no dedup of E2 against abandoned E1. Cache clearing alone proves no rollback. |
| Save/reload or older checkpoint | Confirm lineage only for supported persisted predicates; retain eligible ancestor history, reobserve possession; older load excludes later descendants. | Day change, sleep ack, local append/save-start are not checkpoint proof. Ambiguous mapping quarantines continuity-dependent claims/actions. |
| Capacity/partial/debris | Actual quantity/disposition or unknown, with vanilla evidence. | Never apply AI-queue debris semantics to vanilla human gifts or call debris inventory receipt. |

## 6. Shared responsibility and next review gates

| Boundary | Accountable owner | Shared acceptance responsibility |
| --- | --- | --- |
| Offer → decision → dispatch | A1 prompt/attempt; A4 voluntary choice | Exact mapping, zero stale clicks, no default decline; all automatic cleaners reviewed. |
| Dispatch → inventory proof | A2 predicate; A1 execution facts | Actual variant/quantity, freshness/competing mutation limits; no receipt from ack. |
| Evidence → event | A3 publication/lineage; A2 verdict | Single canonical key, immutable evidence, unknown/correction semantics. |
| Event → next decision | A4 context/decision; A3 replay | Branch eligibility, gaps, exact revisions, optional silence/STAY, correction invalidation. |
| Epoch/lease/restart | A3 lineage; A1 fencing; A4 attachment | One owner across Python/built-in routes; reconcile old work before takeover. |
| Save commitment | A3 checkpoint adapter; A2 persisted-predicate review | Demonstrated host ordering/persistence; local durability stays separate. |

Shared `AgentHttp`, `Perception`, `SocialTools`, runtime cleanup and external controller changes require cross-track review. Research ownership is not an exclusive file lock or implementation approval.

Only after contract review, propose **one unwired game-free fixture package**, A1/A3 maintaining shared types with A2/A4 reviewing predicate/context cases. Cover the full matrix plus conflicting payloads, wrong seat/epoch, identical prompt replacement, out-of-order captures, late corrections, storage failure, cursor gaps and crash windows. Synthetic checkpoint evidence must be labeled simulated. No game hooks, pilot import, migration, model calls or personality rules belong in that first scope.

Before runtime wiring, resolve §3 evidence gaps. Exceptions needing explicit review include weaker causal proof, unguarded legacy dispatch, automatic cancellation cleanup, retention expiry, checkpoint ambiguity and controller ownership change. None is implicitly exempted here. Later operator-authorized backed-up `Test_` validation must cover accept/decline/cancel, uncertainty, identical second gifts, restart and unsaved reload, with silence accepted.

Sunny→Guy and shared-chest cooperation remain separate affordance/permission reviews: inspected `give(to=Guy)` is unsupported; do not switch Guy's role. Chest deposit is not Guy receipt, null ownership is not communal permission, and no project/spending commitment follows from a vague goal.

## 7. A0 disposition and validation

Recommend this interface as a **review candidate** aligning D01–D07. Vocabulary/ownership is provisionally resolved; runtime blockers remain. Sanitized audit is not full source access, transient choice activity is not grounded memory, and a local ledger cannot provide exactly-once game effects.

A0 performed document/PR review. No build, automated behavior suite, model API or live integration was run; all guarantees and acceptance fixtures above remain proposed. No repository files changed, PR created or merge performed. The designated projectless output path was read-only in the attached environment; this workspace deliverable is saved under `/workspace/output/CONTRACT_REVIEW.md`.