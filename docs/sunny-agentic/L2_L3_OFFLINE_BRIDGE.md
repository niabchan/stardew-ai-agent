# G0: L3 daytime intentions -> L2 fake-world action and verification

**Synthetic integration ONLY.** No actual Luna, Python pilot, Mod DLL, Stardew/SMAPI, SteamLibrary file, credential, port or HTTP. These tests add no live capability. Branch is stacked **on Draft PR #60, which is stacked on Draft PR #58**, not on `main`.

## Purpose

Previously, Draft PR #58 demonstrated **L2**: a fake `MOVE_TO_CHAIR` can be prepared, dispatched to synthetic P2, and verified; a subsequent `STAY` makes no dispatch. Draft PR #60 independently proposed **L3** contextual activity candidates on fake observations (STAY, chair, TV, P1 speech). The two were **not connected**.

This small adapter, `reference/sunny_l2_l3_bridge.py`, now composes the two **without altering either underlying PR**. It reads the L2 fake observation, constructs a minimal L3 scene from **only known fake facts**, presents available proposals to an injected *scripted* interest callback, and passes a chosen, snapshot-pinned `STAY` or `MOVE_TO_CHAIR` back to the unchanged L2 fake controller. The L2 checker must independently reobserve the same fake snapshot before dispatch.

Example: one toy world revision offers `STAY` and `MOVE_TO_CHAIR`; a test interest chooses `MOVE_TO_CHAIR`. The fake action is reserved before dispatch, updates P2 toy tile and revision, and returns `VERIFIED_FAKE`. The second observation offers only `STAY`, which another scripted decision chooses without a second dispatch. Thus proposal, choice, action, fake effect, verification, and new choice are joined in one **fake** demonstration.

## Important limits and explicit non-capabilities

- `WATCH_WEATHER_TV` and `SPEAK_TO_P1` exist as **L3 proposal concepts**, not as executable L2 fake actions. This adapter **does not** offer them, because the L2 fake world did not expose those actions. There is no mapping to Mod `watch_tv` or `interact` yet.
- `APPROACH_P1` and `FIND_P1` are **not implemented**. The human P1 may be busy, sleeping or elsewhere; there is no trusted availability or P1 locator observation. The future idea in Issue #57 (Sunny can approach, change her mind, wait or cancel) requires separately specified, bounded pathing and reobservation.
- The L2 `sunny_tile` is a fake position and **does not prove chair seated status**. The adapter explicitly does not infer seating from it; `p2_seated=False` is a dummy non-evidence field, and the L2 offered-action set still suppresses repeat move when at the target tile.
- Fake weather is `unknown`, fake TV reachability is `False`, and fake P1-awake/distance are `False/None`: do not fabricate values to authorize interactions. No P1 raw diary, chat, feed or inventory is projected.
- A fake chooser callback is **not Luna**. The code does not implement curiosity, natural dialogue, memories, real environment perception or autonomous intentions.
- The executor's result `VERIFIED_FAKE` is the **same in-memory fake world effect** as the L2 tests; **not independent game evidence**.
- A missing reply, stale observation, owner/epoch mismatch or pending effect prevents blind retry. The marker persists only in the **same in-memory fake world**; **not** across process termination, new world creation, crash or Windows game reload. This is not a durable journal.
- L3 requires a new observed revision to make a new proposal; a `STAY` without changed observation pauses. There is no fixed time, action quota, or automatic timer.
- Identifying one extracted controller reference candidate (`Sunny_P10_P11_P12_P13_Gift_Offers_v0.3.10`) and on-disk Mod DLL AssemblyVersion 0.4.0.0 in Issue #56 **did not establish that they ran together**. This bridge does not pretend otherwise.

## Acceptance in the game-free test runner

`python -m pytest -q mod/tests/test_sunny_l2_l3_bridge.py`

Eleven test cases cover integration of two independent decisions, STAY pause, unsupported TV and P1 approach/speech proposals blocked, lost reply, same-world controller recreation, owner/epoch and P1/P2 role mismatch, snapshot change between proposal and execution, unknown private P1 content exclusion and chooser error. Keep the existing PR #58 and #60 tests unchanged and green.

## Real integration gates

Read-only inspect **exact extracted v0.3.10 P11 chooser action schema** and corresponding safe Mod dispatcher. Do not infer executable action support from substring searches. No live P2 test or change to SteamLibrary is allowed yet: Issue #59's independent PR #58 review is open, G1 resource/auth/privacy/independent-stop preflight gates remain open, G1/G2 verification not run. `NO_GO_G1_START`, `NO_GO_LIVE_G2`; do not merge, deploy, call Luna or launch game as part of this PR.
