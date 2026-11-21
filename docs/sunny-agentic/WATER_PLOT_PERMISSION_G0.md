# Sunny G0: observed crop ≠ P1 permission to WATER

**INERT TEST-ONLY / no actual WATER capability.** This additive slice is attached to [Issue #92](https://github.com/niabchan/stardew-ai-agent/issues/92) and stacked as a separate Draft PR on [PR #91](https://github.com/niabchan/stardew-ai-agent/pull/91) at its independently G0-reviewed head `8bc4b6b03a678d0041d07c685ffa7bc702cb8824`. The established `reference/sunny_water_daytime_g0.py`, `reference/sunny_host_stop_fake.py`, earlier tests and live Mod are unchanged. It runs only in isolated Python fixtures and game-free CI.

## Why this policy exists

The operator welcomes Sunny watering P1-managed crops as helpful companionship. The objective is **information to choose when and how**, not a forced per-tile dialog or blanket ban on human crops. A **pre-established, bounded help-watering grant** lets Sunny decide to help without asking again for every crop. STAY and synthetic INSPECT (decision-only, not a real tool claim) remain valid. A grant to WATER is **not** a grant to harvest, plant, fertilize, clear a scythe arc, use bulk watering, own crops, or disclose P1 private data.

The design follows [Issue #89 R2 paper acceptance](https://github.com/niabchan/stardew-ai-agent/issues/89#issuecomment-6978250509), with stronger limits than the existing game's raw owner tag. For the actual Mod, crop symbols/owner tags are insufficient; native `look` can hide soil, `water_all` can broaden scope on invalid `whose`, and even after source-described pre-walk checks a genuine callback is not proven safe. None of these real tools is called here.

## Three independent fictional records

| Test record | Meaning / what it cannot prove |
| --- | --- |
| `FakePermissionCrop` | Invented reading for exact load, save, day, map, revision, tile and crop identity, plus soil/tool/position. Its untrusted `owner_tag` **never grants rights**, even if it says P2. |
| `FakePlotStewardship` | Separate, test-fixture supplied P1 manager assignment bound to the exact crop/tile/save/map/epoch. Not deduced from `owner_tag` or public crop observation; **not Host attestation**. |
| `FakeStandingWaterGrant` | Separately test-fixture supplied standing P1→P2 **WATER-only** permission, with issuer/manager, save/epoch/map/day/owner, explicit tile list, revision, distinct-tile count and attempted-start budget. The **fake Host-object-attached permission store** tracks budget use and revocation across new bridges and ledgers. `FakeWaterPermissionLedger` is only a replaceable per-world view. Each grant is explicitly seeded by a test fixture through `FakePermissionedWaterBridge.provision_standing_grant`; **no real P1 identity, UI consent, cryptographic proof, durable permission, or session identity** is implemented. |

The toy example is deliberately restricted to **P1-managed help watering**. It does not make `owner_tag="P2"` a self-grant, and it does not claim a real default authorization for the user's farm. Future P2-owned plots, mixed stewardship, revocation UI and cross-day refresh require separate evidence and design. A new Python ledger/world instance can be fabricated; it cannot provide authenticated grants or reset spent budgets or revoked grant IDs **on the same unmodified fake Host object**. Different fake Hosts and direct Python mutation remain outside this toy boundary.

## Single-threaded fake flow

1. Explicitly fixture-provision a grant into a fake Host-attached store. The same ID binds to immutable scope, tile list, budgets and a monotone revision. An inactive newer revision permanently revokes that ID; using an old active record cannot revive it. Reapproval needs a distinct explicitly fixture-provisioned grant ID, not a new ledger.
2. Validate exact primitive field shapes (no bool-as-int, mutable aliases, duplicate tiles, empty scope or invalid budgets), fake Host pending/STOP and epoch/owner; the already-reviewed `FakeDaytimePlanner` must offer STAY and pass its role/revision checks. An unsupported choice or STAY never reserves anything.
3. WATER only if **separate fictional** stewardship and standing permission match a dry, equipped, adjacent, menu-closed crop and explicit offered WATER in sunny synthetic weather. All observations and grants are still invented fixtures.
4. A test hook (`after_wait`) can change the crop, cause sprinklers to water it, revoke the grant, stop the Host or rotate load. Re-check all scope/identity/tool/dryness conditions **after** this synthetic movement/wait boundary, before reservation. A changed crop, now-wet soil, stale grant or STOP cannot reserve or produce an effect.
5. Derive the same deterministic synthetic snapshot operation ID as PR #91 and use the **same fake Host** replay `used_ids` and monotone `_fake_daytime_water_last_revision` checks. Reserve B lineage before A and advance the shared watermark **only after successful reservation**. No replay across bridge objects sharing this Host (but no crash persistence or different-Host synchronization).
6. A reentrant B callback has another test hook (`before_b`) for STOP, revocation or changed observations. Re-check and consume a **single-use fake Host-attached attempted-start budget** at a toy T3 immediately before `enter_b` (the per-world ledger displays diagnostic counters only). If denied after reservation, the existing Host's unresolved marker remains quarantined; there is no invented safe release/retirement protocol. If B entered before STOP, the original fake Host can still produce a *synthetic residual effect after STOP*. Never claim physical preemption.
7. A matched same-load synthetic `FakeHostWaterFence.confirm_fake_observation` yields `CONFIRMED_FAKE_EFFECT` and `FAKE_RESOLVED` labels **only inside the toy model**. A late/unknown receipt, old epoch, callback exception or STOP-before-entry yields `PENDING_UNKNOWN` / `QUARANTINED`; no auto retry. `reply_status=NOT_MODELED`, and `claim_real_completion=False` on every result. Observing a wet tile, a tool ACK, a diary sentence or a harvested crop does not prove Sunny caused it.

**Important linearization limit:** Calling `claim_start` and then `enter_b` sequentially is *not* an atomic Host/STOP gate. A test hook is allowed before that pair and after B entry, but this is not the independent physical STOP-before-effect ordering or durable start protocol required by Issue #89. The production handoff still requires security review of all producers, nested callbacks, footprint and P1 privacy.

## Adversarial regression matrix (G0 fake-only acceptance targets)

| Area | Cases / invariant | Runtime proof? |
| --- | --- | --- |
| A — Observation vs authority | No grant, invalid stewardship, fake P2 owner tag, wrong crop/owner/load/region | **No** |
| B — Standing permission | Permitted P1-help WATER, voluntary STAY, synthetic INSPECT, unauthorized harvesting/planting/scythe/bulk, patch and per-day budgets | **No** |
| C — Revalidation & STOP | Sprinkler during wait, changed crop, P1 revoke, epoch/STOP during wait, revoke/STOP immediately before B, residual B after STOP, old load still pending | **No** |
| D — Results / replay | Same fake Host different bridge/ledger replay across newer revisions, spent budgets persist in Host state, revoked grants cannot reappear from old records, lost fake receipt, no retry, unrelated wet observation not causally attributed | **No** |
| E — Hostile inputs & disclosure | Bool-as-int, list/equality aliases, duplicate tile grants, bad budgets, owner mismatches; result contains only synthetic labels and IDs, no P1 dialogue/diary | **No** |
| F — Existing G0 behavior | Existing PR #91 tests must remain green; no changes to accepted implementation or parent tests | **No** |

Check real final-head CI before stating PASS for any of the above. Python game-free suite success, even if complete, is not proof of Windows/SMAPI/runtime behavior or independent review. The independent reviewer should challenge unauthorized lookalike permission objects, ledger replacement, STOP ordering and same-load fake-effect claims.

## Immutable stage boundaries

The only intended changed paths are this document, `reference/sunny_water_permission_g0.py`, and `mod/tests/test_sunny_water_permission_g0.py`. This slice does **not** modify the running Mod or controller, access a game/save, launch SMAPI, call a model/provider, open a listener, deploy a Windows DLL, authenticate a Host or create a durable journal. It does not prove native watering, exact game callback footprints, P1 disclosure/consent or physical STOP/quiescence.

**Keep Issue #76 OPEN; PR #90/#91 and this new PR Draft/unmerged; Native WATER `BLOCK/DENY`, actual Host A/B `PROPOSED_UNWIRED`; all 11 G1E gates OPEN; all 50 canonical G1/G2 cases `not_run`; `NO_GO_G1_START / NO_GO_LIVE_G2`.** Require a separate independent exact-head source review; green CI cannot confer acceptance.

## R1 response to independent Issue #94 FIX_REQUIRED

The independent [source-cited review](https://github.com/niabchan/stardew-ai-agent/issues/94#issuecomment-7060769880) found two sequential counterexamples: **fresh ledger replacement** could restore the same standing grant budgets on a newer scene revision, and **old active grant restoration** could undo an inactive higher-revision grant. Prior green CI did not cover either case.

The R1 fake-only correction keeps a typed grant-ID record and immutable scope, latest revision, terminal revocation, attempted-start count and distinct started tiles **on the same fake Host object**, rather than in a replaceable ledger. A separate test-fixture provisioning action seeds the Host grant. Even when the current action aborts after a wait or before B, observing a valid higher-revision inactive fixture latches revocation. Restoring the old grant, silently raising active revision, or widening the same grant's area/budget is rejected. New ledgers may still help another permitted tile if the shared Host budget allows it.

Added negative test traces for cross-bridge budget reset, revoked-grant restoration on the same or new ledger, revocation during wait/at B and changed scope/budgets; positive cross-ledger two-tile WATER assistance; and exception boundaries before reservation, before B, and after B entry. A callback already entered remains a potential effect with unknown completion after an exception.

**This is not a real P1 permission authority.** A Python caller can still fabricate fixtures or mutate fake Host attributes; there is no durable storage, authenticated signature, cross-process synchronization, independent STOP or atomic real callback boundary. The existing fake Host is unchanged; no production controller/Mod/game is used.

Check exact final-head CI before claiming test PASS, and request independent source re-review of these R1 fixes. Neither successful CI nor this author document is independent G0 acceptance.