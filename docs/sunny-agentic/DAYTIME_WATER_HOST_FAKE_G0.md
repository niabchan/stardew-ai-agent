# Sunny G0 — Daytime WATER grounding and Fake Host A/B STOP bridge

**Test-only synthetic composition.** This change adds no real water capability. There is no real game, Mod, SMAPI, Harmony, DLL reader, HTTP, IPC, provider, secret, save or P1 private state. Native WATER remains **BLOCK/DENY**.

## Scope and source anchors

- Base [Draft PR #90](https://github.com/niabchan/stardew-ai-agent/pull/90) is independently accepted **only as an inert G0 fake model**, not as real Host control. This branch stacks **on PR #90**, which stacks on [PR #60](https://github.com/niabchan/stardew-ai-agent/pull/60) (daytime fake planner) and [PR #58](https://github.com/niabchan/stardew-ai-agent/pull/58) (fake world).
- **Only three new files**: `reference/sunny_water_daytime_g0.py`, `mod/tests/test_sunny_water_daytime_g0.py`, and this document. No edit to existing planner, accepted STOP model, live C# Mod/Agent or controller.
- The upstream real Mod's `AgentTools.UseTool` contains a WateringCan path, but this new code neither invokes it nor proves any tool-authority / soil / ownership correspondence. Source-only Native WATER and Track A remain blocked by prior independent reviews.

## Synthetic flow — not real authorization

1. A caller supplies a `FakeScene` from the pre-existing `FakeDaytimePlanner` interface and an **invented** `FakeCropObservation` for one tile. Exact shape checks reject malformed/ambiguous fields. The fake bridge pins P2 owner `fake-host-p2` and load epoch `fake-load-1`; this is not identity provisioning or authenticated perception.
2. The existing daytime planner performs its fake P1-human/P2-AI, owner/epoch, ready, unresolved-flag, monotone revision and **STAY offered** checks. For this one toy example the raw scene may also explicitly offer `WATER`. **The existing planner does not implement WATER**: the new bridge adds an isolated WATER proposal *after* its base proposal passed.
3. `WATER` appears in the new toy bridge's candidate list only if every independently required synthetic predicate is satisfied:
   - `WATER` explicitly offered; `STAY` available; not marked recently completed;
   - crop epoch/revision exactly equals observed fake scene;
   - tile is in the bridge's **test-owned allowlist** of at most 16 fixed (x,y) tuples;
   - observed plot owner exactly `P2`, soil dry, watering can equipped and positive water left;
   - actor adjacent, menu closed, scene weather exactly `sunny`.
   These booleans are invented test input, **not** trusted game data. An unknown weather/state is deliberately not enough to propose WATER.
4. A scripted preference (not Luna) selects `STAY` (no dispatch), `WATER` (only if grounded) or an unsupported action (deny). If a requested WATER lacks grounding, the result is `STAY_NOT_GROUNDED` with **no Host reservation or fake effect**.
5. Only then does the bridge create an in-memory `FakeWaterOperation` with one synthetic attempt ID and request `FakeHostWaterFence.reserve`. **B callback lineage is reserved before A**. The bridge calls `run_a_with_callback` so B may enter reentrantly *before A finishes*. Optional **test-injected callbacks** choose an ordering for STOP, an epoch change or a lost response; these are not a runtime callback API.
6. If both toy regions finish, a fake receipt may close the pending operation **only in the same load** with the accepted PR #90 evidence fields. STOP before A or B leaves pending unresolved; an already-entered B can produce an effect *after* STOP, and a load change cannot use that old-load effect to clear pending. A lost response or exception after reservation returns `UNKNOWN_PENDING` and cannot auto-retry.

## Explicit claims and exclusions

- This is deterministic **sequential fake-event ordering**, not cross-thread atomic STOP/entry arbitration, ownership evidence, authenticated Host grants, an independent STOP channel, irreversible effect isolation, physical STOP latency, a working WateringCan, or durable recovery after process restart.
- The synthetic `fake_wet` flag/evidence are internal model markers, not proof any Stardew tile was watered. The fictional plot allowlist is not validation of whose crops are in the real farm. A caller-controlled `FakeScene` or `FakeCropObservation` cannot become real authoritative input by passing these checks.
- `FakeDaytimePlanner` one-proposal-per-revision prevents unobserved repeat proposals within one **in-memory** instance. A new bridge instance cannot override the *same fake host's* unresolved/used operation IDs; no process-crash persistence is provided. Different host objects are not an attested shared journal.
- No native producer coverage, Mod source ownership, complete callback quiescence, P1 consent, subscriber egress or A/B Host installation is established.
- The test `at_stage` hook intentionally executes **only injected test functions** in the Python process. It is not safe for untrusted user-supplied callbacks or network messages.

## Tests and review acceptance

The additive test file covers grounded WATER; voluntary STAY; dry/owner/allowlist/weather/adjacency/empty-can/menu/observation-revision conditions; missing STAY; malformed types/offer; unsupported preferences and human-P1/AI-P2 readiness; STOP before reserve, after reserve, during A/before B, and after B entry; old-load effect still pending; callback exception and lost receipt; repeated revision; no silent retry; multiple fake-day decisions.

**Review these specific failure modes independently:** source context/revision mixups, untrusted synthetic field types, prior committed in-memory operation collisions, fake planner side effects on denial, no-reservation paths, B reentrant entry, same-load residual-after-STOP, stale epoch receipt, accidental new Host admission, unsupported choices and doc overclaims. Do not interpret green game-free CI as real Host verification.

**Frozen:** [Issue #76](https://github.com/niabchan/stardew-ai-agent/issues/76) OPEN. PR #90 remains Draft/unmerged. Native WATER `BLOCK/DENY`, real Host A/B `PROPOSED_UNWIRED`, 11 G1E gates OPEN, all 50 G1/G2 cases `not_run`, `NO_GO_G1_START / NO_GO_LIVE_G2`. This slice cannot close any of those gates.
