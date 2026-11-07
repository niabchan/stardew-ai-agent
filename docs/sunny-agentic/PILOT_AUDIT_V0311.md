# External Sunny pilot source inspection — v0.3.11 (read-only)

> **Inspection:** Orchestrator reviewed the locally available `Sunny_P10_P11_P12_P13_Gift_Offers_v0.3.11.zip` on 2026-11-04 **without executing it**. SHA-256: `662924ad5ca981b16425ca342bcabb3945a9867d10087ab969d3ea3c5a9521fb`. Findings below are source facts for this ZIP, **not** proof this exact ZIP/DLL was installed in the historical live save.
> **Safety:** No ZIP source, user paths, private runtime logs, chat transcripts, save files or API credentials were committed. No game/API calls or behavior tests were run in this audit.

## Important correction to the four repository-only reports

A1–A4 accurately marked P10–P13 **uninspected from their own Codex repository context**. The ZIP is now available **to the Orchestrator in the working session**, and the specific read-only inspection below partially closes that gap. **The Codex agents have not yet reviewed this ZIP or these findings**; avoid treating this audit as a full integration certification.

## Verified source paths / methods (inside ZIP)

| Path / method | What the code does | Design consequence |
| --- | --- | --- |
| `scripts/sunny_loop.py:307`, `run`; `:79`, `session_lock` | Foreground loop uses a per-save local `run.lock`, selects wake/step/sleep from snapshots, invokes P13 menu inspection ahead of normal P11 eligibility. `recent_activity` is an in-memory list, cleared on new farm day; no explicit save-load branch epoch in this loop. | Local lock does not establish exclusivity against game-side `SeatBrain` or all controllers; restart/reload needs the A1/A3 contract. |
| `scripts/sunny_loop.py:190`, `snapshot_fingerprint`; `:460–468` | P11 suppresses repeat calls on an unchanged fingerprint and applies time intervals; STAY is not a one-action/day quota. Bedtime bypasses the normal prior-STAY interval. | STAY currently means waiting for a new eligible snapshot/time; not yet A4's richer model-selected reconsideration conditions. |
| `scripts/sunny_freeplay.py:237`, `choose_luna` | A P11 Luna request receives observed Cabin options, temperament, last six `recent_activity` entries, and nearby Guy status. Choices are stay/move/chair/TV/speak; speech is a separate chosen action. | No automatic post-gift utterance. A gift *can* influence a later decision only while represented in the short rolling activity list, not through durable grounded event delivery. |
| `scripts/sunny_freeplay.py:162`, `capture_guy_chat` | Parses delivered `Messages:` lines from a **P2 look** result into `recent_activity` as `heard_guy`, rather than inferring chat from proximity alone. | Actual human chat can reach a later Luna decision but source message IDs and durable cursor are absent in this path. |
| `scripts/sunny_gifts.py:59`, `extract_offer` | Requires an English vanilla gift-question regex and a Yes/No option mapping parsed from P2 MCP `status` text. P13 recognizes Guy as active human sender, not a generic item-transfer event. | UI text is a classifier, not stable item ID/prompt revision. Language/localization and changed question risk need A1 validation. |
| `scripts/sunny_gifts.py:133`, `choose` | P13 makes a **separate** Luna call containing sender name, item display name and last six activities; the schema returns **only Boolean accept/decline**, not speech, proposal or deferral. | Receiving a gift cannot itself trigger model speech in P13. A4 should react only via a later P11 choice or a new explicit social policy. |
| `scripts/sunny_gifts.py:272`, `resolve` | Reads and rechecks P2 `status` and P1 menu, rejects changed observed offers before one `respond(option=...)` dispatch. If P1 no longer has a menu it forces decline. A dispatch marker precedes the MCP call. | This external wrapper has useful safety gates, **but** there is no game-thread atomic expected-prompt token. A stale prompt could still change after last status and before C# execution; A1's proposal remains necessary. |
| `scripts/sunny_gifts.py:177`, `prior_dispatch` | Guards repeat dispatch by **save folder + farm day + identical question text**. | Blocks blind replay of same stuck prompt, but can also block a legitimate second identical offer that day; same-day reload is not a safe timeline identity. |
| `scripts/sunny_gifts.py:343–348` | After successful response, appends `{'action':'gift_accept' or 'gift_decline','outcome':'respond_answered','item':display_name}` to the in-session `recent_activity`. It explicitly does **not** verify a transfer. | **Important nuance:** P11 is not wholly unaware of gifts; it sees a *transient, unverified choice record* for up to six recent entries. This cannot be written as “verified Guy gave Sunny a Potato.” |
| `scripts/sunny_gifts.py:187–270` | Recognizes one exact English `Guy canceled the request.` text-only notice and dismisses it only after an earlier matching P13 decline with successful MCP reply and no P1 menu; records dispatch before the optionless `respond`. | Targeted cleanup exists in v0.3.11 **source**, but automatic end-to-end live success has not been established by this inspection. Human operator previously manually cleared an earlier blocked notice. |
| `scripts/sunny_bedtime.py:35`, `attempt` | Checks installed `bedtimeJournalOptional`, tests availability, refuses same-save/day duplicate bedtime dispatch and journals irreversible dispatch before MCP call. | Safety improvement already exists; still lacks branch-aware same-day reload reconciliation. |
| `scripts/sunny_memory.py` | Contains an earlier separate P04 local evidence/notes ledger and per-save helper functions reused by pilot modules. | Existing helpers are useful; importing the module does **not** mean P13 emits A3-grade verified transfer events or that those records reach Luna's prompt. |

## Corrected flow for the historical gift question

```text
Guy's current P2 gift prompt
   → P13 read-only status / English offer+option classifier
   → separate Luna accept/decline call (no speech field)
   → P13 rechecks P1+P2 observed state
   → MCP respond (dispatch recorded; no auto retry)
   → P13 appends short in-session gift_choice record, NOT receipt
   → future P11 request may see that record among last 6 recent activities
   → P11 independently chooses SPEAK or STAY/other Cabin action
```

The operator's live observation that Daffodil and Potato reached Sunny's inventory confirms those particular trials. It does not make P13's general response ledger an inventory verifier. P13 has no directly wired, verified `gift_received` event or long-term save-branch-aware receipt-memory handoff.

## Specific next research / implementation questions

1. **A1:** Preserve P13's read-only P2 prompt checks, but move exact expected-prompt validation to C# on the game thread before any mutation; audit other auto-close routes. Decouple intentional decline-on-cancel from an optional social decision.
2. **A2:** Add typed P1 and P2 before/after evidence with causal limits; P13's `item` is a parsed *display label*. A `gift_accept` short activity is not proof of receipt. Validate what can be observed without controlling human P1.
3. **A3:** Evolve the existing per-save JSONL utilities into a branch-aware event/attempt architecture only after checkpoint semantics are verified. Keep historical authoring/evidence separate; a same-question text key is insufficient for dedup and blocks legitimate repetitions.
4. **A4:** Define a bounded next-decision event projection that includes *verified* receipt when known and explicitly unresolved outcome otherwise; retain silence/STAY and no forced thanks. Avoid duplicated `gift_accept` records triggering repeated reactions.
5. **All:** Decide whether Python remains the orchestrating Luna controller and C# stays the game adapter, or whether responsibilities migrate; do not run two active brains on P2. Cross-agent review of actual pilot functions is now feasible by delivering sanitized excerpts/reports, without publishing the original ZIP.

## Test status / limitations

Static source audit only. No `pytest`, C# build or live game test run in this review. Historical A1 automated test results are independent; A2–A4 reports are research-only. Direct MCP server implementation and game/SMAPI behavior must still be validated for exactly-once boundaries, gift option ordering, cancellation UI, actual transfer, and saved checkpoint semantics.

References: [Round 1 cross-agent review](./DESIGN_REVIEW_ROUND1.md), [A1–A4 source reports](./RESEARCH_TRACKS.md).
