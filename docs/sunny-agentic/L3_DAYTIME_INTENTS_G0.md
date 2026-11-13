# Sunny L3 — contextual daytime choices (G0 proposal experiment)

**Game-free only.** This file accompanies `reference/sunny_daytime_intents.py` and its tests. No PowerShell, Luna/API, Stardew/SMAPI, HTTP listener, save, installed DLL, or live Mod code is invoked. This proposal experiment is **not** an L3 live implementation.

## Exact local reference boundaries (operator-reported, not independently verified at runtime)

- Installed candidate: `Mods/StardewMCP/StardewMCP.dll`, SHA-256 `51718B9620BF32BCEFB7F586F6BE3518187313874AAED1A5556AD38986495213`; .NET AssemblyVersion `0.4.0.0`, neighboring manifest `0.3.0`. Runtime-loaded DLL and source commit **unknown**.
- Extracted controller reference candidate: `Sunny_P10_P11_P12_P13_Gift_Offers_v0.3.10` under a local Downloads folder; `scripts/sunny_freeplay.py` SHA-256 `F049A9502E073A487C473B962D8FD0A53968FD4C15E80B25F9547A23A5E6F156`. It has **not** been proved to be the last executed controller. `FIREPLACE` keyword absent; `TOGGLE` only in two chair safety comments (operator-provided lines 136 and 493). Literal keyword search does not establish chooser schema.
- v0.3.11 is a source-audited ZIP which the operator reports **not extracting**, not evidence of a live run. Detailed provenance and other package hashes reside in Issue #56.

## Smallest useful new behavior

Instead of another hardcoded 09:00 / one-action-per-day routine, provide **synthetic grounded candidate activities** from a minimal observation. The test selects a fake interest and filters it against offered capabilities, readiness, privacy, and recent activity. A new *observed revision* allows another choice on the same fake day. `STAY` is always an explicit permitted candidate when the scene is otherwise valid.

| Fake candidate | Minimum observation | Purpose / actual bridge status |
| --- | --- | --- |
| `STAY` | owner/epoch/roles/ready valid, STAY offered | Rest without forced conversation; **no dispatch** |
| `MOVE_TO_CHAIR` | offered, chair reachable, Sunny not seated, not just completed | Avoid blind chair toggles. Only a toy proposal; no chair action executed |
| `WATCH_WEATHER_TV` | offered, TV reachable, not just completed | Contextual curiosity; operator-inspected extracted v0.3.10 source reports a weather TV watch tool; installed/runtime mapping remains unknown |
| `SPEAK_TO_P1` | offered, P1 awake and at most five tiles away, social cooldown inactive, not just completed | Avoid intrusive repeated talk; no P1 private chat/diary exposed, and no speech dispatched |

Unknown/high-impact requests (`MARRY_NPC`, `FIREPLACE_TOGGLE`) are denied even if a fake external offer happens to list them. The test policy has an **explicit tiny allowlist**. It is not a statement that furniture/TV/speech are all safe on the real installed Mod or that P1 proximity info can be trusted from a client-provided observation. External world claims are fake inputs here, not authenticated evidence.

The `weather` fact and scripted `simulated_interest` illustrate how perceptual facts and autonomy preferences could be separated from allowed capabilities; **the fake policy itself does not infer curiosity from weather or call Luna**. It makes proposals only, not effects or verified outcomes. If an attempt is unresolved, the toy planner blocks new choice rounds. Same/stale observation revision also pauses until changed evidence, instead of busy-looping.

## Acceptance (local, test-only)

`python -m pytest -q mod/tests/test_sunny_daytime_intents.py`

Fifteen fake tests cover TV interest → chair interest → STAY across three synthetic observations; no one-action quota; repeated observation pause; sleepy/far-away P1 talk suppression; chair repeat suppression; denied high-impact/unoffered choices; fake P1 private-data field exclusion; owner/role/epoch/unknown preconditions; missing STAY. **No real interaction is executed; tests do not validate real security enforcement, loaded assembly, pathfinding, post-action observation or model decisions.**

## Actual follow-up required before integration

Review the *extracted v0.3.10* `sunny_freeplay.py` chooser action grammar and dispatcher targets **read-only**, alongside any other P10/P12 invoking source; do not infer executable choices from substring matches. Map `WATCH_WEATHER_TV` to any actual exposed `watch_tv` form and verify safety/feedback semantics, or mark the candidate unsupported. Only after independent review of PR #58 and the separate G1 security gates could a separately authorized real Windows experiment be considered. Keep `NO_GO_G1_START`, `NO_GO_LIVE_G2`, no merges/deployments.

## Independent Issue #63 source-only correction record

Evidence labels: **SOURCE_PROVEN** applies to this repository's pinned toy code;
**REFERENCE_ONLY** applies to synthetic fixtures and operator-reported external
source; **UNVERIFIED_REAL_RUNTIME** applies to the installed controller, Mod,
observations, authorization, effects and persistence. No runtime clearance follows.

Severity-ranked findings at original head `052355baffb13f63520d5cc824c6d4e628ebcf70`:

1. **High / SOURCE_PROVEN — malformed inputs crash or pass truthiness gates.**
   `FakeScene(offered_actions=None)` or `recently_completed=([],)` raises
   `TypeError`; `revision=True`, `p2_is_ai="false"`, or
   `p1_distance_tiles=True` can select speech. Strict built-in types now reject
   malformed scenes before revision consumption; hostile non-string interests
   return `DENIED_NOT_GROUNDED` without hashing/comparing them. Distant nonnegative
   integer P1 distances remain valid observations but suppress speech beyond five.
2. **Medium / SOURCE_PROVEN — unresolved flag could be cleared by a refresh.**
   On one planner, choose with `unresolved_attempt=True`, then choose revision 2
   with that flag false: formerly `BLOCKED_UNRESOLVED` then `SELECTED_FAKE`.
   Now unresolved input permanently latches this toy instance closed. There is
   deliberately no resolution/reset API; this is not an effect-verification design.
3. **Medium / REFERENCE_ONLY — chair/completion and source wording.** Candidate
   text previously requested location *or seating* evidence for chair movement.
   L2 `MOVE_TO_CHAIR` moves a fake tile; it is not P11 F1 `interact`, which is a
   sit/stand toggle. `recently_completed` is entirely a caller-supplied synthetic
   suppression flag, never verified gameplay. A `stood_only` prerequisite result
   is not completion of a chosen move/TV action. Tool ACK, coordinate or revision
   establishes neither real sit/stand nor the intended effect. Candidate wording
   now makes the fake movement and speech limitations explicit.

Per Issue #63's later operator inspection, extracted v0.3.10 contains F0–F4,
M1–M8 and the weather TV watch tool (**REFERENCE_ONLY** in this review: that
external source is not supplied here). This supersedes the earlier mapping-unknown
statement only at the extracted-source level; installed real controller/Mod
runtime remains **UNVERIFIED_REAL_RUNTIME**.

All owner/epoch/revision/role/readiness, reachability, seating, completion and P1
availability claims remain caller-supplied. A coherent forged scene is accepted
by this toy; monotonic forged revisions and replacement/stale planner objects
cannot establish freshness or authority. Resetting the Python object bypasses
its local history. No authenticated observation or real safety clearance is
claimed. P1 proximity/awake flags establish neither human availability, consent,
nor speech receipt. P1 is human and never automated here; no direct `@name`
speech, private chat/diary, raw P1 text, or real dispatch exists. STAY remains a
no-dispatch choice without a daily quota or optimizer.

Validation: original ten test functions passed, while the new malformed-input,
hostile-interest and unresolved-refresh regressions fail on the original code.
All fifteen pass after correction. Boundary speech tests require successful
`PROPOSED_FAKE`/selection on valid input, so an unrelated blocking branch cannot
make them pass. Mutation checks separately remove role/epoch/readiness gates,
revision waiting, malformed checks and the unresolved latch; focused tests must
reject those representative faults. Local execution invokes test functions
with Python because pytest is absent; no software is installed. Actual associated
GitHub final-head Python/C# CI is separate evidence reported with the review.

Stack boundary: reviewed PR #58 head
`901646a52e3587a8c7b9d018099412338d491183` contains one regression absent here;
original #60 is three commits ahead and one behind it. No reconciliation,
cherry-pick, rebase or merge is included. PR #61 is untouched. All PRs
#22/#58/#60/#61 stay Draft/unmerged. All eleven G1 gates remain open;
`NO_GO_G1_START` / `NO_GO_LIVE_G2`. Phase 2G limits are unratified and the old
50 live cases remain `not_run`. No live game/controller/API calls or deployment.
