# Sunny — Cross-agent design review, Round 1

> **Status:** orchestrator synthesis / proposal for peer review (2026-11-04). Not architecture approval, not a code change, not evidence that four agents are executing in a shared runtime.
> **Game roles:** Guy = human P1, Sunny = AI P2, Luna = decision model in the external Sunny pilots.
> **Base:** `docs/sunny-agentic-architecture-phase1` at `11c4aa2`, after PR #4 was merged into fork `main`.
> **Inputs:** [A1 / PR #6](https://github.com/niabchan/stardew-ai-agent/pull/6), [A2 / PR #7](https://github.com/niabchan/stardew-ai-agent/pull/7), [A3 / PR #8](https://github.com/niabchan/stardew-ai-agent/pull/8), [A4 / PR #9](https://github.com/niabchan/stardew-ai-agent/pull/9). All are separate draft reports, not yet integrated into the architecture branch.

## Executive finding

The four reports substantially **converge** on the direction for evidence-backed companion autonomy:
**propose/observe → model decides (possibly STAY/decline/silence) → guard and dispatch once → observe actual effect → verify → publish a branch-aware event → make it available to a later model decision**.

However, convergence is on *principles*, not a finalized schema or safe runtime. No report has inspected the external P10–P13 Python/PowerShell source. Do **not** start a cross-language behavior refactor, auto-merge these PRs or claim that any proposed safety guarantees exist.

## Evidence-backed discoveries across tracks

| Area | Reported C# source fact | Implication |
| --- | --- | --- |
| A1 / action | `respond` operates on current P2 dialogue/index, without a stable expected-prompt token; reply/ack can precede termination, and `Ok=true` need not mean verified effect. | New intent must bind to the exact prompt and dispatch attempt. Never blindly retry an ambiguous mutation. Also review other menu cleaners/watchdogs. |
| A2 / resources | `SocialTools.Give` targets other AI seats, not human Guy; its sender removal precedes recipient tick/insertion. `ChestLedger` records bounded net changes, not complete attribution. Building material checks use the executor's pack/money, not arbitrary shared chest stock. | Treat human gift routes as unverified; receiving, transferring, depositing, withdrawing, spending, and building are distinct facts. |
| A3 / evidence | `Perception` queues and `SocialTools` mailbox are bounded/drained, diary is authored text, and same-save-folder reload lacks a robust load-epoch branch identity. | Transient notification is not durable factual memory. Save/load lineage, evidence provenance, cursor replay and correction matter. |
| A4 / agency | Guy's chat is filtered by human screen/visibility and delivered through a transient inbox; built-in brain's no-tool path nudges/releases, unlike the desired external STAY behavior. Speech is queued but not semantic-deduplicated. | Keep conversation and game-world decisions independent; permit silence, STAY, deferral and voluntary cooperation. Inspect actual external pilot behavior before changing prompts/controller. |

**Scope caution:** These are findings from source inspection and historical operator logs, not independently reproduced game outcomes of the proposed architecture.

## Proposed ownership boundaries (review candidate)

- **A1 Interaction:** owns request/attempt identity, lease/preconditions, exact prompt revalidation, execution state, effects of mutation dispatch, cancellation uncertainty. **Cannot certify inventory receipt.**
- **A2 Inventory:** owns typed snapshots, transfer/resource evidence and verification predicates, actual disposition and project material availability. **Cannot publish canonical memory or infer consent.**
- **A3 Perception & memory:** owns canonical event publication, stable event/revision identity, local evidence store/cursors, save/load branches, correction and factual projections. **Cannot infer a gift from dialogue alone.**
- **A4 Companion:** owns model-facing contextual projection, decision/reaction and optional social response, conversational preferences, consent proposals and STAY conditions. **Cannot unilaterally certify world state or spend resources.**
- **Orchestrator:** reviews cross-domain contracts, operational safety, PR integration, operator-led gameplay tests and approvals. Shared `AgentHttp`, `Perception`, `SocialTools` and external Sunny controller require cross-track review.

## Three independent state axes for a gift

An overloaded `gift_accepted` flag loses critical distinctions. Propose separate identities:
1. **Choice:** `gift_offer_observed` candidate → `gift_choice_resolved` (accepted / declined / unresolved). A1+A4 must validate exact prompt and actual selected choice. `respond` acknowledgment alone is not receipt.
2. **Effect:** A2 verifies `item_transfer_observed` with source/destination, item variant/count, evidence freshness and causal limits. Possible dispositions include inventory receipt, stash, debris, partial, unknown, contradicted.
3. **Memory/persistence:** A3 publishes one grounded, branch-aware fact if verification supports it; tracks whether game save checkpoint is confirmed. A4 may later mention it or stay silent. Current possession and historical receipt are different predicates.

These event names are **candidates**. A1–A4 must sign off on exact states/IDs and the minimum evidence required to classify a result.

### Example trace — human Guy → Sunny Potato (design only)

```text
P2 exact offer observed [A1] --fresh prompt--> Luna chooses accept/decline [A4]
       |                                           |
       +--- stale/canceled/unclassified ------------+--> NO CLICK; outcome unknown
                                                   |
                     guarded one-time respond [A1] |  (choice resolution != transfer)
                                                   v
                 source+destination effect evidence [A2]
                                                   |
                      verified / unknown / partial  |
                                                   v
             branch-aware canonical event + cursor [A3]
                                                   |
                    model context at NEXT decision [A4]
                                                   |
                            optional SAY or SILENCE; STAY permitted
```

If Guy cancels before Luna's answer, no automatic click or generic dialogue dismissal; if accepted but recipient inventory cannot be verified, record an unresolved transfer, not a fabricated receipt. If the game reloads an unsaved day, old observed events must be quarantined from the present branch, retaining historical audit only.

## Provisional interfaces to review together (not final)

| Interface | Candidate minimum identifiers | Questions to settle |
| --- | --- | --- |
| `ActionAttempt v1` | schema, attempt, save/load/branch, seat, lease, tool/args, expected prompt, execution state vs effect state, reply-completed | Who creates the load/lease identity? How to gate all menu mutation paths, including internal cleanup? |
| `InventoryObservation/TransferEvidence v1` | capture/seat/container, item stable ID/variant/count, freshness, source/destination before/after, route, disposition, causal justification | Can human P1 source evidence be obtained read-only, without taking control? What if observations cannot be atomic? |
| `GroundedEvent v1` | event/revision/transition, source evidence refs, save/load/branch/checkpoint, verification, correction, publication cursor | Which storage format and checkpoint hook are reliable? What is preserved vs abandoned on same-day reload? |
| `CompanionContext/Decision v1` | context+source cursor, branch+lease, observed facts vs authored claims, event revisions, activity and social choices, expected action refs | How do quiet/sleep, STAY re-evaluation and deferred prompt expiration work without fixed gratitude/talk quotas? |
| `CooperationProposal v1` | proposer, named goal/affordance, permissions, contributions, executor, resource evidence, independent participants' choices | How to represent mutually agreed chest use without assuming null ownership means communal? |

The proposed interfaces have not been implemented or peer-approved. Early adapters should remain additive/compatible; pure reducers need synthetic tests before any game hooks.

## Design-review decisions still open (no silent default)

1. **External controller audit — blocking for wiring:** Obtain exact **P10–P13 Python/PowerShell** ZIP/source used in live tests (especially P11 next-decision prompt and P13 gift handling/ledger, plus P10/P12 lifecycle). Examine *read-only* first. Record local versions/hashes; do not publish API secrets, private paths, raw game saves or chat logs. Separate built-in `SeatBrain` from the external Luna controller.
2. **Save/load checkpoint authority:** Confirm SMAPI/Game save/load hooks and whether a committed checkpoint can be recognized across reload, copy and crash. Farm day, folder name, log append and overnight text are insufficient. Identify one host authority and P2 seat attachment rules.
3. **Human inventory and giving:** Validate what P1/P2 inventories/prompts can be observed without controlling Guy. Current `give(to=Guy)` is **not supported**; a held-item interaction and an agreed shared chest are *candidate* routes, not confirmed. Do not bypass with a role switch.
4. **Exactly-once boundary:** An attempt ledger can prevent known duplicate dispatch, but cannot atomically commit all game-world effects; unknown outcomes require reconciliation, not forced replay. Specify what UI/menu cleaners may touch.
5. **Companion behavior policy:** Distinguish a voluntarily selected STAY/refusal from model budget exhaustion, world freeze and bed rest. Separate event notification from waking/interruption, plus context latency and language consistency.
6. **Resource cooperation semantics:** Verify real Stardew construction/catalog rules, executor/wallet and pack requirements. Proposals/agreement are not mechanical reservations, chest deposit is not delivery, and an unspecific bridge request must not trigger irreversible spending.

## Candidate first vertical slice and test gates

Start with a **game-free contract fixture** rather than a feature implementation:

- A1: synthetic offer identity, guarded one-time response and unknown-on-timeout.
- A2: synthetic typed inventory changes, accepted-but-unverified versus actual verified receipt, debris and resource origin.
- A3: one canonical event ID per verified transition; duplicate cursor delivery does not create a second event; unsaved Day 24 reload excludes abandoned receipt from active memory.
- A4: next-decision context includes verified gift; model may choose SILENCE/STAY, optional mention or another action; no gratitude rule and no second acceptance.

Only after contracts are reviewed, write **small separate implementation PRs**, in approximate dependency order: pure shared types/reducers and fixtures → additive observation/epoch instrumentation → A1 guarded dispatch → A2 evidence verification → A3 grounded event + save lineage → A4 context/decision bridge → operator-approved `Test_` scenario. Refine ordering after the external-pilot audit; some interfaces may require revisiting sooner.

### Suggested acceptance tests after implementation
- Guy offers Daffodil/Potato; accept and verify actual transfer, receive grounded context without forced chat.
- Decline and canceled/replaced prompt; no unrelated menu click, no invented receipt; bedtime still operable.
- Two equal gifts on same farm day produce two separate events; repeat polls never duplicate one event.
- Save, restart controller, reload *unsaved* day, and load an older checkpoint: evidence/memory stays on correct branch, actions do not replay.
- Sunny proposes a specific cooperative task; Guy may agree or decline. A shared chest contributes only after verified deposit **and** retrieval; actual building cost/permission rules respected.

## Round 1 outcome and review questions

**Result:** four research inputs are complete and their primary architectural recommendations are compatible. **Not approved:** final schema, save-checkpoint implementation, cross-language controller integration, gameplay automation or merge to `main`.

**Questions for human owner and A1–A4 review:**
- Is it acceptable to make the external P10–P13 pilot source available for *read-only* joint research (sanitized as needed), before implementing bridge changes?
- Which minimum real-game acceptance scenario should be selected first: verified Guy→Sunny gift with optional silence (recommended), or an agreed chest handoff? Neither should spend irreversible resources.
- Which unresolved assumptions need a proof-of-capability spike before adopting the contract? Particularly human→AI vanilla offer identity, read-only human inventory evidence, and save checkpoint persistence.

Keep PRs #6–#9 in draft until reviewed. If consolidating their reports into the architecture branch later, merge only after checking each base/head and reviewing the documentation changes. Merging these drafts into the **architecture branch** is distinct from merging PR #5 into `main`.

## Sources

- [Research charter](./README.md)
- [Baseline source inventory](./ARCHITECTURE_BASELINE.md)
- [Four agent prompts](./RESEARCH_TRACKS.md)
- [A1](https://github.com/niabchan/stardew-ai-agent/pull/6) · [A2](https://github.com/niabchan/stardew-ai-agent/pull/7) · [A3](https://github.com/niabchan/stardew-ai-agent/pull/8) · [A4](https://github.com/niabchan/stardew-ai-agent/pull/9)
