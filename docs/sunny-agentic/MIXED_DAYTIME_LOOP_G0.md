# Sunny G0: mixed voluntary daytime choices after reviewed P1-help WATER

**TEST-ONLY / INERT / G0.** This additive behavior slice belongs to [Issue #56](https://github.com/niabchan/stardew-ai-agent/issues/56). It **stacks on independently G0-accepted [Draft PR #93](https://github.com/niabchan/stardew-ai-agent/pull/93)** at pinned `ac87aac4c896377b44db161f23aae26ceb115bb4`; this new branch changes **only** `reference/sunny_mixed_daytime_g0.py`, `mod/tests/test_sunny_mixed_daytime_g0.py`, and this document. No existing live Mod, accepted Host, WATER policy, controller or L2/L3 planner is changed or merged.

## What existed and what was missing

- Existing [Draft PR #58](https://github.com/niabchan/stardew-ai-agent/pull/58) has `FakeGame` + `OfflineController` for synthetic P2 `MOVE_TO_CHAIR` or `STAY`, with pending unknown outcome quarantined.
- Existing [Draft PR #60](https://github.com/niabchan/stardew-ai-agent/pull/60) has `FakeDaytimePlanner` contextual proposal filtering; it alone does not execute effects.
- Existing [Draft PR #61](https://github.com/niabchan/stardew-ai-agent/pull/61), **a separate parallel branch**, already joins L2 fake chair action with L3 contextual choice. It does **not** exist in this PR #93 stack, and is deliberately **not copied** into this branch.
- Independently source-accepted [Issue #94 G0 R2](https://github.com/niabchan/stardew-ai-agent/issues/94#issuecomment-7062109098) covers `FakePermissionedWaterBridge`: P1-managed crop, a separately fixture-provisioned standing P1→P2 `WATER` grant, fake Host budgets, STOP, revocation and unknown pending. That alone does not implement a **mixed-interest** activity chooser.

The **new difference** is a very small optional mixed daytime composition: at each new *synthetic* revision propose `STAY` / `MOVE_TO_CHAIR` / **permitted** `WATER`, let a bounded *scripted test interest* select any offered activity, pass the selected action to the appropriate existing G0 fake executor, check its exact fake result, and only consider a next interest after the source supplies a newer observation. Unlike PR #61's chair-only flow, this tests mixing P1-help WATER with another P2 daytime choice.

## Explicit fake scenario

1. A deterministic fixture places Sunny P2 at `(4,4)`, next to the fictional P1-managed dry crop `(4,5)`, and independently provisions a one-tile WATER grant into the SAME fake Host. The fake L2 game and fake Host must share exact epoch and owner. Synthetic weather `sunny` is **explicitly provided** by the test; the L2 world alone cannot prove weather. No P1 diary/private chat or P1 direct controls are available to the interest callback.
2. On revision 1, the candidates are `STAY`, `MOVE_TO_CHAIR`, `WATER`. A synthetic interest chooses `WATER`. The accepted G0 policy verifies fake A/B effect and operation-matched fake receipt. The mixed coordinator **does not itself declare the soil wet or advance the revision from an ACK**.
3. The test-owned *fake observation publisher* explicitly supplies revision 2 and a newly wet soil reading. On this newer scene, WATER is no longer eligible, but `MOVE_TO_CHAIR` remains a voluntary choice. Its existing L2 fake controller observes P2 tile change from `(4,4)` to `(7,4)`; this is **movement to a chair tile**, **not proof of sitting down**.
4. The fake world provides revision 3 after successful movement. Sunny can now independently choose `STAY`, with no new dispatch. No rigid 09:00 start, fixed daily schedule, single action/day cap or forced speech. A separate test verifies two distinct P1-approved crop tiles can be watered under a two-start/two-tile fake Host grant, then Sunny chooses movement and STAY.

## Safety and limits

- This code runs **only** in the in-memory Python fake models. The real Mod, Windows DLL, SMAPI, HTTP/IPC adapter, production Host, external model chooser, actual game state, P1 consent UI and native WATER remain entirely **unimplemented/unproven**.
- The P1 crop owner tag is never permission. The fake Host grant must already have been independently test-provisioned. The synthetic planner additionally cross-checks P2 fake tile is actually one Manhattan step from the crop rather than trusting `adjacent=True` alone.
- `WATER` is not inserted into the plain L3 planner's authorized candidate set: it is added only after the accepted fake Host grant/soil/epoch/owner/day/tile checks. No HARVEST, PLANT, bulk water, SPEAK_TO_P1, arbitrary TV or FIREPLACE action is offered. STAY is always available on a valid new scene.
- Any unresolved attempt in **either** `FakeGame` or `FakeHostWaterFence` blocks all further actions. A newly constructed coordinator referencing the same objects cannot drop pending or revive a consumed snapshot. STOP blocks even chair movement. Chooser-side world/ledger/grant changes are rejected before fake dispatch; a valid revocation fixture notice is still latched.
- The toy coordinator's `run_bounded` makes at most four deterministic sequential attempts and stops on STAY, denial, error or unknown outcome. The supplied `after_verified` callback is a **test-controlled source of invented observations**. No fabricated soil change, new revision or automatic retry happens without it. An exception in that callback ends the bounded run.
- The two existing fake dispatchers **do not** share one real atomic cross-action Host A/B gate, credential, durable journal or cross-process STOP. Fake chair movement is not posture evidence. These limitations matter even though their unit tests pass. No external provider is called; simulated interests are not a trained model's independent agency. This is a gameplay contract demonstration, **not** actual Sunny choosing activities in a running farm.
- In-memory counters and revisions can be modified by arbitrary Python callers. The fixture cannot authenticate P1 approvals, provide privacy/isolation against a compromised process, or establish real physical STOP/quiescence, actual tool footprints, effect evidence or full action-route coverage.

## Target acceptance cases

| G0 fake trace | Expected contract |
| --- | --- |
| WATER → explicit new wet observation → chair tile move → STAY | Three independent decisions, one fake Host WATER effect, one L2 move and no STAY dispatch |
| Two distinct authorized WATER tiles → move → STAY | Permit multiple bounded acts in a single fake day |
| WATER verified, but no new observation | WAIT; no second decision/side effect |
| STAY on unchanged scene, including a new coordinator | WAIT; no busy-loop |
| Unknown WATER receipt or unknown chair effect | Shared pending quarantine blocks every action even after coordinator recreation |
| P1 revoke during scripted interest | Tombstone recorded, no effect |
| Rain/unknown weather, nonadjacent crop, unsupported activities | Do not offer unauthorized WATER or any unsupported activity |
| STOP, wrong Host/owner/epoch/role | Reject before test interest or fake dispatch |
| Fake observation publisher fails | Stop immediately; no retry or invented success |

**Exact-head CI and independent source review are separate acceptance requirements.** Do not call the new slice G0-accepted from a green CI alone. Keep parent PR #93 at its independently reviewed SHA without rebasing/modification.

**Frozen runtime safety:** Issue #76 OPEN; Native WATER `BLOCK/DENY`, real Host A/B `PROPOSED_UNWIRED`, all 11 G1E gates OPEN, all 50 G1/G2 cases `not_run`, `NO_GO_G1_START / NO_GO_LIVE_G2`. All affected PRs remain Draft/unmerged; no game launch/deployment/provider calls, no real save or credential exposure.
