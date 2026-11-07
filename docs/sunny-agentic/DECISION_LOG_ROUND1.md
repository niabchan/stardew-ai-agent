# Sunny — Architecture decision log (review candidate, 2026-11-04)

**Status:** Orchestrator proposals informed by research PRs [#6](https://github.com/niabchan/stardew-ai-agent/pull/6), [#7](https://github.com/niabchan/stardew-ai-agent/pull/7), [#8](https://github.com/niabchan/stardew-ai-agent/pull/8), [#9](https://github.com/niabchan/stardew-ai-agent/pull/9), [Round 1](./DESIGN_REVIEW_ROUND1.md) and the [read-only v0.3.11 pilot audit](./PILOT_AUDIT_V0311.md). **Not implementation approval.** The four Codex agents have not jointly signed off on this file.

## Candidate decisions on shared principles

| ID | Proposed decision | Why | Status |
| --- | --- | --- | --- |
| D01 | Use **one active decision/controller owner for Sunny P2**. Initially keep external Python/Luna as orchestration and C# SMAPI as the game/MCP adapter; treat built-in `SeatBrain` as a separately configurable mode, not a second P2 actor. | Avoid duplicate prompts/dispatch; aligns with existing P10–P13 pilot. Verify the actual installed mode before coding. | Candidate |
| D02 | Separate **choice, command acknowledgment, verified game effect, local event recording and game save commitment**. Never say `respond` or `gift_accept` means inventory receipt. | A1/A2/A3 agree; v0.3.11 P13 adds only a temporary `respond_answered` hint to P11. | Candidate |
| D03 | A1 owns mutation attempt/prompt identity; A2 owns resource-verification predicates; A3 owns evidence/event lineage and correction; A4 owns model-facing context, voluntary decisions and speech. | Prevent dual producers of `gift_accepted` and incompatible interfaces. | Candidate |
| D04 | Prefer **small typed, versioned contract objects** with opaque save/load/attempt/event IDs and explicit unknown states. Do not retrofit all tools or create a new global event-sourcing subsystem in one PR. | Keep an independently testable vertical slice; avoid overengineering before observing the actual API affordances. | Candidate |
| D05 | A gift reaction is **optional**, including silence. STAY, declining and changing goals are normal, not errors. Consent to a transfer or shared project is explicit; no spending on vague goals. | Core Sunny companion design. A4 agrees with A1/A2/A3 boundaries. | Candidate |
| D06 | **Never repeat an ambiguous game mutation automatically**, and never answer an unverified or changed menu. Local JSONL acknowledgment is not exactly-once game semantics. | P13's per-day/text guard misses same-day repeats/reloads; C# currently has no game-thread expected-prompt token. | Candidate |
| D07 | Keep **real source files, API secrets, saves, private chats and personal runtime logs out of repository**; publish synthetic fixtures, redacted summaries, hashes and contract docs. | Pilot audit was performed read-only; preserve user privacy and rollback safety. | Candidate |

## Pending technical choices (block runtime integration, not a pure fixture)

1. **Game save/checkpoint identity.** Need a verified load epoch / save checkpoint strategy that distinguishes an unsaved same-day reload from a continuation. Treat missing proof as unknown; avoid designing durable behavior around `saveFolder + day`.
2. **P1/P2 typed inventory observations.** Demonstrate what both screens and SMAPI expose without taking control of human Guy. One display-label delta does not establish giver/item/quality/provenance.
3. **Human gift affordance.** `SocialTools.give` is AI-to-AI; test actual human→AI offer classification and potential Sunny→Guy held-item offer on a controlled `Test_` save before proposing a public tool contract.
4. **Prompt freshness guard.** Decide where to attach a game-thread P2 prompt revision and how it interacts with `Respond`, `CloseMenu`, sleep auto-cleaners and other Yes/No responders. A Python preflight is valuable but not atomic with execution.
5. **Compatibility and deploy strategy.** Inspect installed DLL/controller hashes and command mode; an additive C# capability flag may gate Python behavior. No automatic replacement of deployed mod.
6. **Speech/STAY and interrupt design.** Define an explicit social preference versus system deadline, so timeout/credit constraints cannot masquerade as Luna's choice. Do not require gratitude or speech.

## Minimal shared contract fixture: explicit examples

The first code PR, if approved, should be **unwired/game-free** with synthetic fixtures. No C# game hooks, no real game calls and no model API.

Case A — accept choice, transfer unknown:
```text
offer O1 seen in session L1
Luna decision: ACCEPT
A1 responds to O1 once; tool replies 'Dialogue closed'
A2: recipient inventory not yet observed
A3: publishes candidate/unresolved event, never "Guy gave Sunny item"
A4: no mandatory speech, can STAY; may ask to inspect status
```

Case B — actual verified receipt:
```text
fresh source/destination observations + causal transfer evidence
A2: verified variant and quantity, explicit actor/recipient
A3: publishes E1 on branch B1, with save_commit=unconfirmed
A4: next context includes E1 with provenance and no speech requirement
```

Case C — canceled stale menu:
```text
O1 offered, then Guy closes menu; prompt replaced by unrelated dialogue
A1: stale/mismatched O1 -> zero clicks; outcome unresolved/canceled only with evidence
A2: no claim of receipt from menu disappearance
A4: no forced decline or repeated question
```

Case D — abandoned unsaved same-day reload:
```text
L1/B1: E1 observed on Day 24, game save unconfirmed
Load checkpoint C23 again, now L2/B2
A3: B1 E1 excluded from current fact projection
A1: old attempts not reissued
A4: does not recall E1 as present-branch gift or thank Guy for it
```

Case E — two identical real gifts on one day:
```text
two distinct prompt/transition identities O1 and O2
separate valid actions and separate causal transfers
two event IDs E1/E2; neither deduped by display name/day/question text
```

No fixture should imply that all these guarantees are currently implemented; test against a future pure reducer only.

## Recommended Phase 2 task order

1. **A0 cross-agent contract alignment (read-only):** Have one Codex task review this ADR and the four reports. Compare actual pilot findings against assumptions, propose a small shared schema **without implementing**; list exceptions requiring A1–A4 owner approval. The repository currently lacks the ZIP, so this task must cite the published sanitized pilot audit and mark actual ZIP uninspected. Outcome: one `CONTRACT_REVIEW.md` draft PR to the architecture branch.
2. **First game-free implementation PR** after review: pure attempt/effect/branch/event/companion-context fixtures in a **minimal shared language-neutral JSON schema or documented dataclasses**, no runtime binding. Pick one owner (A1/A3 pairing) and avoid four separate incompatible schema modules.
3. **Observation spike** after agreement: add read-only, opt-in per-seat prompt and typed inventory observation capabilities; make safe P1/P2 eligibility explicit. Operator captures synthetic/redacted Test_ fixtures.
4. **Dispatch + proof:** implement C# game-thread prompt guards, then A2 verified item transfer, then A3 branch-aware evidence handling and A4 grounded next-decision consumption in separate PRs.
5. **Live integration:** backed-up `Test_` save; Guy→Sunny Daffodil; accept/decline/cancel, optional silence, reload; expand to Sunny→Guy and chest cooperation only after validating actual game affordances.

## Merge discipline

- PR #5 remains the draft architecture base against `main`.
- PRs #6–#9 remain individual draft research reports against the architecture branch; they are **not runtime changes**.
- PR #10 is the Orchestrator review draft against the same architecture branch.
- Do not merge any of these automatically just to make the reports visible to future tasks; read GitHub PRs directly or consolidate deliberately after discussion.
- Only operator-approved, tested, independently scoped changes may merge to `main`.
