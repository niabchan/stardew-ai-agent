# Sunny P11 Journal and STOP handoff — G0-only proposed contract

**Offline and synthetic only.** This small continuation of the reconciled Draft PR #58 → #60 → #61 stack adds a pure reference classifier and negative tests. It is **NOT** a replacement for the extracted v0.3.10 Controller, an actual JSONL reader, an authenticated P2 host, a live game integration, or evidence of a safe installed DLL. There is no filesystem access, model, game, HTTP, MCP or action dispatch in the proposed module.

## What was actually observed in source

The operator privately supplied read-only extracted v0.3.10 **scripts/sunny_loop.py lines 243–304**. Neither the full historical writer nor the actually executed Windows Controller was independently established.

- The old **new_attempt_results** takes new JSONL rows after a row-count cursor, selects the last reserved event matching the FreePlay policy, then selects the last result with the same attempt ID. It does not explicitly reject duplicate reservations/results, out-of-order results, or mismatched result policy/save/day/owner/epoch. These limitations were reconstructed synthetically in the independent PR #61 audit. They are **not proven runtime exploitation or corruption**.
- The old **run_once** checks the journal result, and normally returns stop on a missing, failed or unknown outcome, with constrained pre-dispatch exceptions. Therefore the fact that FreePlay may itself return integer 0 after recording unknown does **not** establish an outer-loop blind retry.
- A stand prerequisite can produce a result labeled **stood_only** without sending the originally chosen move or TV action. Intent, prerequisite and completed effect must stay distinct.
- A Python per-save process lock and stop-file checks at decision/action boundaries do **not** prove a server-side lease, independently effective STOP, queued/running action retirement, crash-durable operation reconciliation or authoritative load epoch.

## The new, stricter proposal is intentionally NOT the old schema

The reference module accepts a **caller-supplied fake expected scope**, comprising policy, save, farm day, load epoch, P2 owner, attempt ID, operation ID and selected intent. Each simulated event must match every field; one reserved event, at most one choice and one dispatch, and exactly one result must be ordered as reserved → choice → dispatch → result (with optional middle events). A successful activity requires an explicit matching choice; a dispatch purpose identifies either the selected action or the stand prerequisite.

**Important difference:** the historical v0.3.10 writer is NOT known to emit authoritative epoch, owner, operation ID or dispatch purpose on every row; its extractor does not enforce this proposal. Existing log data must not be interpreted as approved, silently migrated, or accepted because a string happens to match. The proposed statuses also use strictly narrowed example reason codes; they do not claim to represent all historical PRE_DISPATCH_ABORTS or actual Mod response reasons.

| Pure G0 result | Conservative interpretation | Not established |
| --- | --- | --- |
| **ACK_REOBSERVE** | One coherent selected dispatch plus reported success | The actor reached a tile, sat, watched TV or delivered speech |
| **PREREQUISITE_ACK_REOBSERVE** | Stand prerequisite reportedly dispatched; original move or TV not executed | P2's real seated state or chosen activity completion |
| **STAY_AWAIT_CHANGE** | STAY chosen with no dispatch | Forced next choice or daily action quota |
| **DEFER_REOBSERVE** | Fake pre-dispatch abort and no dispatch event in the supplied segment | No unlogged action happened; automatic retry is safe |
| **STOP_UNRESOLVED** | Missing, duplicate, foreign, conflicting, malformed or out-of-order event | Diagnosis of an actual live mutation |
| **STOP_REQUESTED** | Test caller set a stop Boolean | Host-independent cancellation and resource retirement |

Every output explicitly has **new_mutation_authorized=False**, **selected_activity_completed=False**, and **real_effect_verified=False**. An ACK cannot by itself allow another game mutation; the future system needs separate, authenticated new observation and reconciliation. The caller can fabricate even a syntactically perfect fake journal, so the reference is **shape validation only, not provenance**. A row count is not an authenticated cursor and a JSON-RPC request ID is not an idempotency/operation ID.

## Required real implementation before any G1 pilot

1. **Actual version evidence, private and read-only.** Establish the exact loaded Mod and actual executed Controller and their current hashes, rather than relying on an extracted ZIP or a source-audited different archive. Do not upload secrets, raw P1 messages, full saves, logs or the pilot ZIP.
2. **Host-issued P2 owner, epoch and operation authority.** Validate a server-side exclusive P2 lease and current save/load epoch; bind tool, intended actor, arguments, expected revision and operation ID *before* side effect; guard queue and active task paths. Neither local UUIDs nor client supplied strings establish authenticity.
3. **Durable write-ahead pending and unknown quarantine.** Before effectful dispatch, persist an operation record; after timeouts, reload, controller restart, reply loss, conflicts or contradictory journal rows retain unknown pending state. Never blindly replay walk, chair/stand, respond, sleep or speech due to missing result or a new farm day. A future recovery must reconcile server-owned operation state and observed effect.
4. **Independent authorized STOP.** Fence all new dispatch at the host, account for queued and running work plus task/buffer cleanup, and verify retirement or leave the operation quarantined. The existing Python stop-file polling is not proof of independent STOP.
5. **Specific game evidence and P1 privacy.** Walk requires a trusted P2 target observation; chair requires actual sit/stand state; TV requires playback/channel proof; speech requires a privacy/consent-aware receipt policy, not raw P1 dialogue; sleep has a separately gated long-running lifecycle. Tool ACK does not establish any of these.
6. **Explicit exact-run approval later.** After relevant independent review and all G1 gates, require a distinct user-approved Test_ save, rollback and G2 gameplay plan. This G0 PR grants no such approval.

## Tests and limits

Focused command: **python -m pytest -q mod/tests/test_sunny_p11_journal_contract.py**.

Sixteen game-free tests cover normal ACK, STAY and stand-only, no-replay deferral, unknown/missing result, duplicates, concurrent/foreign reservations, contradictory/out-of-order results, foreign policy/save/day/epoch/owner/attempt/operation, stray dispatch, malformed/nonboolean fields, untrusted reply text, stop flag, incomplete legacy rows and bounds. This is **not** test coverage of the actual local Controller code, host cleanup or real crash recovery.

**Final gate status remains unchanged:** all eleven G1 gates OPEN; fifty historical live cases not_run; Phase 2G limits unratified; **NO_GO_G1_START / NO_GO_LIVE_G2**. Keep every PR Draft/unmerged. Independently review this G0 classifier before any further design integration.
