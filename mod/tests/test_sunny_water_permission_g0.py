"""G0 synthetic consent/observation/WATER tests; never starts Stardew or HTTP."""
from dataclasses import replace

import pytest

from reference.sunny_daytime_intents import FakeScene
from reference.sunny_host_stop_fake import FakeHostWaterFence
from reference.sunny_water_permission_g0 import (
    FakePermissionCrop, FakePlotStewardship, FakeStandingWaterGrant,
    FakeWaterPermissionLedger, FakePermissionWorld, FakePermissionedWaterBridge,
)


def scene(revision=1, **kwargs):
    return replace(FakeScene(
        epoch="fake-load-1", owner="fake-host-p2", revision=revision,
        offered_actions=("STAY", "WATER"), weather="sunny"
    ), **kwargs)


def setup(grant=None, crop=None, steward=None):
    host = FakeHostWaterFence()
    gr = FakeStandingWaterGrant() if grant is None else grant
    cr = FakePermissionCrop() if crop is None else crop
    st = FakePlotStewardship() if steward is None else steward
    world = FakePermissionWorld(cr, st, FakeWaterPermissionLedger(gr))
    bridge = FakePermissionedWaterBridge(host)
    bridge.provision_standing_grant(gr)  # Explicit fake Host fixture, not P1 consent.
    return host, world, bridge


def test_explicit_standing_p1_help_grant_waters_once_with_fake_ab_evidence():
    host, world, bridge = setup()
    result = bridge.step(scene(), world, "WATER")
    assert result.verdict == "FAKE_WATER_VERIFIED"
    assert (result.effect_status, result.cleanup_status) == (
        "CONFIRMED_FAKE_EFFECT", "FAKE_RESOLVED"
    )
    assert result.claim_real_completion is False
    assert result.reply_status == "NOT_MODELED"
    assert host.events == [
        "RESERVE_B_LINEAGE", "ENTER_A", "ENTER_B", "FAKE_EFFECT",
        "FINISH_A", "FAKE_OBSERVED_AND_RESOLVED"
    ]
    assert host.pending is None
    assert world.ledger.started_tiles == {(4, 5)}
    assert world.ledger.attempted_starts == 1


@pytest.mark.parametrize("interest,verdict", [
    ("STAY", "STAY"),
    ("INSPECT", "INSPECT_ONLY"),
    ("HARVEST", "DENIED_UNSUPPORTED_CHOICE"),
    ("FERTILIZE", "DENIED_UNSUPPORTED_CHOICE"),
    ("water_all", "DENIED_UNSUPPORTED_CHOICE"),
    ("WATER_ALL", "DENIED_UNSUPPORTED_CHOICE"),
    ("REQUEST_PERMISSION", "DENIED_UNSUPPORTED_CHOICE"),
    (True, "DENIED_UNSUPPORTED_CHOICE"),
])
def test_no_effect_on_voluntary_stay_inspection_or_unoffered_action(interest, verdict):
    host, world, bridge = setup()
    result = bridge.step(scene(), world, interest)
    assert result.verdict == verdict
    assert host.events == [] and host.pending is None


@pytest.mark.parametrize("owner_tag", [None, "P2", "P1", "nobody"])
def test_observed_crop_owner_tag_cannot_authorize_without_grant(owner_tag):
    host, world, bridge = setup(crop=FakePermissionCrop(owner_tag=owner_tag))
    world.ledger = FakeWaterPermissionLedger(None)
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_NO_GRANT"
    assert host.events == [] and host.used_ids == set()


def test_no_stewardship_cannot_be_replaced_with_raw_owner_tag():
    host, world, bridge = setup(crop=FakePermissionCrop(owner_tag="P2"))
    world.stewardship = None
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_UNKNOWN_STEWARDSHIP"
    assert host.events == []


def test_standing_grant_is_p1_help_not_plant_or_harvest_or_owner_change():
    host, world, bridge = setup(crop=FakePermissionCrop(owner_tag="P2"))
    assert bridge.step(scene(), world, "WATER").verdict == "FAKE_WATER_VERIFIED"
    assert world.stewardship.manager == "P1" and world.ledger.grant.action == "WATER"
    assert world.ledger.started_tiles == {(4, 5)}
    assert host.events.count("FAKE_EFFECT") == 1


@pytest.mark.parametrize("change", [
    {"action": "HARVEST"}, {"action": "PLANT"}, {"action": "FERTILIZE"},
    {"action": "water_all"}, {"grantee": "P1"}, {"issued_by": "P2"},
    {"tiles": ((4, 5), (4, 5))}, {"tiles": ((4, 5), (True, 7))},
    {"tiles": [(4, 5)]}, {"max_distinct_tiles": True},
    {"max_attempted_starts": True}, {"max_attempted_starts": 0},
    {"max_distinct_tiles": 2}, {"grant_revision": 0},
    {"day": True}, {"active": 1},
])
def test_malformed_or_privilege_escalating_grant_is_rejected(change):
    host, world, bridge = setup(grant=replace(FakeStandingWaterGrant(), **change))
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_MALFORMED_GRANT"
    assert host.events == []


@pytest.mark.parametrize("change", [
    {"tiles": ((6, 7),)}, {"save_id": "other-save"}, {"epoch": "old-epoch"},
    {"day": 2}, {"map_id": "Town"}, {"p2_owner": "other-host"},
])
def test_out_of_scope_grant_or_tile_cannot_water(change):
    host, world, bridge = setup(grant=replace(FakeStandingWaterGrant(), **change))
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_GRANT_SCOPE"
    assert host.events == []


@pytest.mark.parametrize("change", [
    {"crop_id": "different-crop"}, {"tile": (5, 5)},
    {"manager": "P2"}, {"save_id": "different-save"},
])
def test_stewardship_does_not_follow_asserted_crop_or_role(change):
    host, world, bridge = setup(steward=replace(FakePlotStewardship(), **change))
    assert bridge.step(scene(), world, "WATER").verdict in {
        "DENIED_STEWARDSHIP_MISMATCH", "DENIED_UNKNOWN_STEWARDSHIP"
    }
    assert host.events == []


@pytest.mark.parametrize("change", [
    {"soil_dry": 1}, {"water_left": True}, {"tile": (True, 5)},
    {"tile": [4, 5]}, {"crop_id": object()}, {"owner_tag": object()},
    {"adjacent": "true"}, {"water_left": -1}, {"revision": True},
])
def test_strict_crop_evidence_shape_rejects_aliases_and_bool_as_int(change):
    host, world, bridge = setup(crop=replace(FakePermissionCrop(), **change))
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_MALFORMED_CROP"
    assert host.events == []


@pytest.mark.parametrize("change", [
    {"soil_dry": False}, {"water_left": 0}, {"can_equipped": False},
    {"adjacent": False}, {"menu_closed": False},
    {"revision": 2}, {"epoch": "other-load"},
])
def test_no_water_on_unneeded_tool_or_stale_observation(change):
    host, world, bridge = setup(crop=replace(FakePermissionCrop(), **change))
    assert bridge.step(scene(), world, "WATER").verdict in {
        "DENIED_NOW_WET", "DENIED_TOOL_OR_POSITION", "DENIED_OBSERVATION_SCOPE"
    }
    assert host.events == []


@pytest.mark.parametrize("change", [
    {"weather": "rainy"},
    {"offered_actions": ("STAY",)},
    {"recently_completed": ("WATER",)},
])
def test_scene_must_explicitly_offer_water_and_need_it(change):
    host, world, bridge = setup()
    assert bridge.step(scene(**change), world, "WATER").verdict == "DENIED_NOT_GROUNDED"
    assert host.events == []


def test_malformed_duplicates_block_before_planning_or_host():
    host, world, bridge = setup()
    result = bridge.step(
        scene(recently_completed=("MOVE_TO_CHAIR", "MOVE_TO_CHAIR")), world, "WATER"
    )
    assert result.verdict == "BLOCKED_MALFORMED_SCENE"
    assert host.events == []


def test_fake_sprinkler_wets_crop_during_wait_so_no_reservation():
    host, world, bridge = setup()

    def sprinkler(stage, _h, w, _op):
        if stage == "after_wait":
            w.crop = replace(w.crop, soil_dry=False)

    result = bridge.step(scene(), world, "WATER", sprinkler)
    assert result.verdict == "DENIED_NOW_WET"
    assert not result.claim_real_completion
    assert host.events == [] and host.pending is None


def test_changed_crop_identity_during_wait_cannot_reuse_permission():
    host, world, bridge = setup()

    def replace_crop(stage, _h, w, _op):
        if stage == "after_wait":
            w.crop = replace(w.crop, crop_id="fake-other-crop")

    assert bridge.step(scene(), world, "WATER", replace_crop).verdict == "DENIED_CHANGED_CROP"
    assert host.events == []


def test_p1_revokes_standing_help_during_wait():
    host, world, bridge = setup()

    def revoke(stage, _h, w, _op):
        if stage == "after_wait":
            w.ledger.grant = replace(w.ledger.grant, active=False, grant_revision=2)

    assert bridge.step(scene(), world, "WATER", revoke).verdict == "DENIED_GRANT_CHANGED"
    assert host.events == []


def test_stop_during_wait_has_no_reservation_or_effect():
    host, world, bridge = setup()

    def stop(stage, h, _world, _op):
        if stage == "after_wait":
            h.latch_stop()

    assert bridge.step(scene(), world, "WATER", stop).verdict == "BLOCKED_STOP"
    assert host.events == ["STOP_LATCHED"]


def test_epoch_change_during_wait_has_no_reservation():
    host, world, bridge = setup()

    def reload(stage, h, _world, _op):
        if stage == "after_wait":
            h.rotate_epoch()

    assert bridge.step(scene(), world, "WATER", reload).verdict == "BLOCKED_STOP"
    assert host.events == ["STOP_LATCHED", "FAKE_EPOCH_CHANGED"]


def test_stop_after_reservation_quarantines_and_blocks_a():
    host, world, bridge = setup()

    def stop(stage, h, _world, _op):
        if stage == "after_reserve":
            h.latch_stop()

    result = bridge.step(scene(), world, "WATER", stop)
    assert result.verdict == "UNKNOWN_PENDING" and result.cleanup_status == "QUARANTINED"
    assert "ENTER_A" not in host.events and "FAKE_EFFECT" not in host.events
    assert host.pending is not None
    assert world.ledger.attempted_starts == 0


def test_revocation_before_b_entry_is_rechecked_and_denied():
    host, world, bridge = setup()

    def revoke(stage, _h, w, _op):
        if stage == "before_b":
            w.ledger.grant = replace(w.ledger.grant, active=False, grant_revision=2)

    result = bridge.step(scene(), world, "WATER", revoke)
    assert result.verdict == "UNKNOWN_PENDING"
    assert "ENTER_A" in host.events and "ENTER_B" not in host.events
    assert world.ledger.attempted_starts == 0
    assert host.pending is not None


def test_stop_before_b_entry_has_no_effect_or_budget_claim():
    host, world, bridge = setup()

    def stop(stage, h, _world, _op):
        if stage == "before_b":
            h.latch_stop()

    assert bridge.step(scene(), world, "WATER", stop).verdict == "UNKNOWN_PENDING"
    assert host.events.count("FAKE_EFFECT") == 0
    assert world.ledger.attempted_starts == 0
    assert host.pending is not None


def test_stop_after_b_entry_can_have_residual_effect_same_load():
    host, world, bridge = setup()

    def stop(stage, h, _world, _op):
        if stage == "b_entered":
            h.latch_stop()

    result = bridge.step(scene(), world, "WATER", stop)
    assert result.verdict == "FAKE_WATER_VERIFIED"
    assert host.events.index("ENTER_B") < host.events.index("STOP_LATCHED") < host.events.index("FAKE_EFFECT")
    assert host.stopped and host.pending is None
    assert world.ledger.attempted_starts == 1


def test_old_epoch_residual_effect_does_not_clear_pending():
    host, world, bridge = setup()

    def reload(stage, h, _world, _op):
        if stage == "b_entered":
            h.rotate_epoch()

    result = bridge.step(scene(), world, "WATER", reload)
    assert result.verdict == "UNKNOWN_PENDING"
    assert host.fake_wet and host.pending is not None
    assert result.effect_status == "PENDING_UNKNOWN"


def test_lost_receipt_never_creates_success_or_blind_retry():
    host, world, bridge = setup()

    def lose(stage, _h, _world, _op):
        if stage == "before_receipt":
            raise RuntimeError("synthetic reply vanished")

    result = bridge.step(scene(), world, "WATER", lose)
    assert result.verdict == "UNKNOWN_PENDING"
    assert host.fake_wet and host.pending is not None
    assert host.events.count("FAKE_EFFECT") == 1
    assert FakePermissionedWaterBridge(host).step(scene(), world, "WATER").verdict == "BLOCKED_UNRESOLVED"


def test_cross_bridge_completed_snapshot_cannot_replay_even_with_fresh_ledger():
    host, world, bridge = setup()
    assert bridge.step(scene(), world, "WATER").verdict == "FAKE_WATER_VERIFIED"
    # A separately, explicitly provisioned *new* fictional grant avoids the
    # spent old grant's budget gate, so this isolates the Host snapshot fence.
    fresh_grant = replace(FakeStandingWaterGrant(), grant_id="fresh-p1-grant")
    fresh_world = FakePermissionWorld(
        FakePermissionCrop(), FakePlotStewardship(),
        FakeWaterPermissionLedger(fresh_grant)
    )
    fresh_bridge = FakePermissionedWaterBridge(host)
    assert fresh_bridge.provision_standing_grant(fresh_grant) == "FAKE_GRANT_PROVISIONED"
    assert fresh_bridge.step(scene(), fresh_world, "WATER").verdict == "DENIED_HOST_STALE_SNAPSHOT"
    assert host.events.count("FAKE_EFFECT") == 1


@pytest.mark.parametrize("max_tiles,max_starts", [(1, 2), (2, 1)])
def test_per_day_distinct_tile_and_attempt_budgets(max_tiles, max_starts):
    grant = replace(FakeStandingWaterGrant(),
                    tiles=((4, 5), (6, 7)),
                    max_distinct_tiles=max_tiles,
                    max_attempted_starts=max_starts)
    host, world, bridge = setup(grant=grant)
    assert bridge.step(scene(), world, "WATER").verdict == "FAKE_WATER_VERIFIED"
    world.crop = replace(world.crop, revision=2, tile=(6, 7), crop_id="second-crop")
    world.stewardship = replace(world.stewardship, tile=(6, 7), crop_id="second-crop")
    assert bridge.step(scene(revision=2), world, "WATER").verdict == "DENIED_BUDGET"
    assert host.events.count("FAKE_EFFECT") == 1


def test_two_authorized_distinct_tiles_can_be_helped_without_repeat_dialog():
    grant = replace(FakeStandingWaterGrant(),
                    tiles=((4, 5), (6, 7)),
                    max_distinct_tiles=2, max_attempted_starts=2)
    host, world, bridge = setup(grant=grant)
    assert bridge.step(scene(), world, "WATER").verdict == "FAKE_WATER_VERIFIED"
    world.crop = replace(world.crop, revision=2, tile=(6, 7), crop_id="second-crop")
    world.stewardship = replace(world.stewardship, tile=(6, 7), crop_id="second-crop")
    assert bridge.step(scene(revision=2), world, "WATER").verdict == "FAKE_WATER_VERIFIED"
    assert world.ledger.attempted_starts == 2
    assert world.ledger.started_tiles == {(4, 5), (6, 7)}
    assert host.events.count("FAKE_EFFECT") == 2


def test_forged_wet_observation_without_dispatch_is_not_causal_verification():
    host, world, bridge = setup(crop=FakePermissionCrop(soil_dry=False))
    result = bridge.step(scene(), world, "WATER")
    assert result.verdict == "DENIED_NOW_WET"
    assert result.effect_status == "NO_EFFECT_EVIDENCE"
    assert result.claim_real_completion is False
    assert host.events == []


def test_unprovisioned_grant_does_not_become_host_permission():
    host = FakeHostWaterFence()
    world = FakePermissionWorld(
        FakePermissionCrop(), FakePlotStewardship(),
        FakeWaterPermissionLedger(FakeStandingWaterGrant())
    )
    bridge = FakePermissionedWaterBridge(host)
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_HOST_PERMISSION_STATE"
    assert host.events == []


def test_new_ledger_same_grant_later_revision_cannot_reset_spent_tile():
    host, world, bridge = setup()
    grant = world.ledger.grant
    assert bridge.step(scene(), world, "WATER").verdict == "FAKE_WATER_VERIFIED"
    assert world.ledger.attempted_starts == 1
    new_world = FakePermissionWorld(
        replace(world.crop, revision=2), world.stewardship,
        FakeWaterPermissionLedger(grant)  # fresh zero counters, SAME grant
    )
    assert new_world.ledger.attempted_starts == 0
    assert FakePermissionedWaterBridge(host).step(
        scene(revision=2), new_world, "WATER"
    ).verdict == "DENIED_TILE_ALREADY_STARTED"
    assert host.events.count("FAKE_EFFECT") == 1


def test_new_ledger_same_grant_cannot_overspend_distinct_tile_or_attempt_budget():
    grant = replace(FakeStandingWaterGrant(),
                    tiles=((4, 5), (6, 7)), max_distinct_tiles=1,
                    max_attempted_starts=1)
    host, world, bridge = setup(grant=grant)
    assert bridge.step(scene(), world, "WATER").verdict == "FAKE_WATER_VERIFIED"
    new_world = FakePermissionWorld(
        replace(world.crop, revision=2, tile=(6, 7), crop_id="second-crop"),
        replace(world.stewardship, tile=(6, 7), crop_id="second-crop"),
        FakeWaterPermissionLedger(grant)
    )
    assert FakePermissionedWaterBridge(host).step(
        scene(revision=2), new_world, "WATER"
    ).verdict == "DENIED_BUDGET"
    assert host.events.count("FAKE_EFFECT") == 1


def test_revocation_then_old_grant_restore_cannot_reenable_permission():
    host, world, bridge = setup()
    original = world.ledger.grant
    revoked = replace(original, grant_revision=2, active=False)
    world.ledger.grant = revoked
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_GRANT_REVOKED"
    assert host.events == []
    world.ledger.grant = original
    world.crop = replace(world.crop, revision=2)
    assert FakePermissionedWaterBridge(host).step(
        scene(revision=2), world, "WATER"
    ).verdict == "DENIED_GRANT_REVOKED"
    assert host.events == []
    assert bridge.provision_standing_grant(original) == "DENIED_STALE_GRANT_REVISION"
    assert bridge.provision_standing_grant(
        replace(original, grant_revision=3)
    ) == "DENIED_GRANT_REVOKED"


def test_revocation_tombstone_survives_bridge_and_ledger_recreation():
    host, world, bridge = setup()
    original = world.ledger.grant
    world.ledger.grant = replace(original, grant_revision=2, active=False)
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_GRANT_REVOKED"
    new_world = FakePermissionWorld(
        replace(world.crop, revision=2), FakePlotStewardship(),
        FakeWaterPermissionLedger(original)
    )
    assert FakePermissionedWaterBridge(host).step(
        scene(revision=2), new_world, "WATER"
    ).verdict == "DENIED_GRANT_REVOKED"
    assert host.events == []


def test_revocation_during_wait_is_permanently_latched_even_after_fixture_restore():
    host, world, bridge = setup()
    original = world.ledger.grant

    def revoke(stage, _h, w, _op):
        if stage == "after_wait":
            w.ledger.grant = replace(original, active=False, grant_revision=2)

    assert bridge.step(scene(), world, "WATER", revoke).verdict == "DENIED_GRANT_CHANGED"
    world.ledger.grant = original
    world.crop = replace(world.crop, revision=2)
    assert bridge.step(scene(revision=2), world, "WATER").verdict == "DENIED_GRANT_REVOKED"
    assert host.events == []


def test_revocation_before_b_is_latched_despite_unresolved_reservation():
    host, world, bridge = setup()
    original = world.ledger.grant

    def revoke(stage, _h, w, _op):
        if stage == "before_b":
            w.ledger.grant = replace(original, grant_revision=2, active=False)

    assert bridge.step(scene(), world, "WATER", revoke).verdict == "UNKNOWN_PENDING"
    world.ledger.grant = original
    assert host.pending is not None
    assert bridge.provision_standing_grant(original) == "DENIED_STALE_GRANT_REVISION"
    assert host.events.count("FAKE_EFFECT") == 0


def test_same_grant_id_cannot_change_scope_or_limits_at_higher_revision():
    host, world, bridge = setup()
    original = world.ledger.grant
    wider = replace(original, grant_revision=2,
                    tiles=((4, 5), (6, 7)),
                    max_distinct_tiles=2, max_attempted_starts=2)
    assert bridge.provision_standing_grant(wider) == "DENIED_GRANT_SCOPE_CHANGED"
    world.ledger.grant = wider
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_GRANT_SCOPE_CHANGED"
    assert host.events == []


def test_new_ledger_can_use_second_legitimate_tile_with_remaining_host_budget():
    grant = replace(FakeStandingWaterGrant(),
                    tiles=((4, 5), (6, 7)), max_distinct_tiles=2,
                    max_attempted_starts=2)
    host, world, bridge = setup(grant=grant)
    assert bridge.step(scene(), world, "WATER").verdict == "FAKE_WATER_VERIFIED"
    second_world = FakePermissionWorld(
        replace(world.crop, revision=2, tile=(6, 7), crop_id="second-crop"),
        replace(world.stewardship, tile=(6, 7), crop_id="second-crop"),
        FakeWaterPermissionLedger(grant)
    )
    assert FakePermissionedWaterBridge(host).step(
        scene(revision=2), second_world, "WATER"
    ).verdict == "FAKE_WATER_VERIFIED"
    assert second_world.ledger.attempted_starts == 2
    assert second_world.ledger.started_tiles == {(4, 5), (6, 7)}
    assert host.events.count("FAKE_EFFECT") == 2


def test_wait_exception_never_reserves_or_debits_permission():
    host, world, bridge = setup()

    def fail(stage, _host, _world, _op):
        if stage == "after_wait":
            raise RuntimeError("wait failed")

    assert bridge.step(scene(), world, "WATER", fail).verdict == "DENIED_WAIT_FAILURE"
    assert host.events == []
    assert world.ledger.attempted_starts == 0
    # The independently reviewed planner rejects same-revision blind retries;
    # a fresh synthetic observation is required before a new attempt.
    assert bridge.step(scene(), world, "WATER").verdict == "WAIT_NEW_OBSERVATION"
    assert host.events == []
    world.crop = replace(world.crop, revision=2)
    assert bridge.step(scene(revision=2), world, "WATER").verdict == "FAKE_WATER_VERIFIED"


def test_before_b_exception_quarantines_reserved_operation_without_budget_debit():
    host, world, bridge = setup()

    def fail(stage, _host, _world, _op):
        if stage == "before_b":
            raise RuntimeError("callback failed")

    assert bridge.step(scene(), world, "WATER", fail).verdict == "UNKNOWN_PENDING"
    assert host.pending is not None
    assert "ENTER_A" in host.events
    assert "ENTER_B" not in host.events
    assert world.ledger.attempted_starts == 0
    assert FakePermissionedWaterBridge(host).step(
        scene(), world, "WATER"
    ).verdict == "BLOCKED_UNRESOLVED"


def test_after_b_entry_exception_quarantines_started_permission_and_unknown_effect():
    host, world, bridge = setup()

    def fail(stage, _host, _world, _op):
        if stage == "b_entered":
            raise RuntimeError("effect callback unobserved")

    result = bridge.step(scene(), world, "WATER", fail)
    assert result.verdict == "UNKNOWN_PENDING"
    assert result.effect_status == "PENDING_UNKNOWN"
    assert host.pending is not None and host.b_entered
    assert "ENTER_B" in host.events and "FAKE_EFFECT" not in host.events
    assert world.ledger.attempted_starts == 1
    assert world.ledger.started_tiles == {(4, 5)}
    assert FakePermissionedWaterBridge(host).step(scene(), world, "WATER").verdict == "BLOCKED_UNRESOLVED"


@pytest.mark.parametrize("replace_ledger", [False, True])
def test_combined_changed_crop_and_revocation_during_wait_stays_revoked(replace_ledger):
    """Issue #94 R1: crop identity failure must not mask inactive v2."""
    host, world, bridge = setup()
    original = world.ledger.grant
    revoked = replace(original, grant_revision=2, active=False)

    def change_both(stage, _host, w, _op):
        if stage != "after_wait":
            return
        w.crop = replace(w.crop, crop_id="replacement-crop")
        if replace_ledger:
            w.ledger = FakeWaterPermissionLedger(revoked)
        else:
            w.ledger.grant = revoked

    first = bridge.step(scene(), world, "WATER", change_both)
    assert first.verdict == "DENIED_CHANGED_CROP"
    assert host.events == [] and host.pending is None and host.used_ids == set()
    assert getattr(host, "_fake_daytime_water_last_revision", -1) == -1
    assert bridge.provision_standing_grant(original) == "DENIED_STALE_GRANT_REVISION"

    # A *fresh* ledger/bridge with the old active v1 and a proper new crop
    # observation cannot reactivate the consumed permission on this Host.
    retry_world = FakePermissionWorld(
        replace(FakePermissionCrop(), revision=2),
        FakePlotStewardship(), FakeWaterPermissionLedger(original)
    )
    retry = FakePermissionedWaterBridge(host).step(
        scene(revision=2), retry_world, "WATER"
    )
    assert retry.verdict == "DENIED_GRANT_REVOKED"
    assert retry.effect_status == "NO_EFFECT_EVIDENCE"
    assert host.events.count("FAKE_EFFECT") == 0
    assert host.pending is None


@pytest.mark.parametrize("replace_ledger", [False, True])
def test_wait_exception_after_revocation_and_crop_change_records_tombstone(replace_ledger):
    """Ingestion runs in a finally block when the injected wait hook raises."""
    host, world, bridge = setup()
    original = world.ledger.grant
    revoked = replace(original, grant_revision=2, active=False)

    def fail_after_notice(stage, _host, w, _op):
        if stage != "after_wait":
            return
        w.crop = replace(w.crop, crop_id="changed-while-failing")
        if replace_ledger:
            w.ledger = FakeWaterPermissionLedger(revoked)
        else:
            w.ledger.grant = revoked
        raise RuntimeError("synthetic wait failure after P1 notice")

    result = bridge.step(scene(), world, "WATER", fail_after_notice)
    assert result.verdict == "DENIED_WAIT_FAILURE"
    assert host.events == [] and host.pending is None
    assert bridge.provision_standing_grant(original) == "DENIED_STALE_GRANT_REVISION"
    later = FakePermissionWorld(
        replace(FakePermissionCrop(), revision=2),
        FakePlotStewardship(), FakeWaterPermissionLedger(original)
    )
    assert FakePermissionedWaterBridge(host).step(
        scene(revision=2), later, "WATER"
    ).verdict == "DENIED_GRANT_REVOKED"
    assert host.events.count("FAKE_EFFECT") == 0


@pytest.mark.parametrize("replace_ledger", [False, True])
@pytest.mark.parametrize("raise_after_notice", [False, True])
def test_before_b_combined_crop_change_and_revoke_survives_pending_quarantine(
    replace_ledger, raise_after_notice
):
    host, world, bridge = setup()
    original = world.ledger.grant
    revoked = replace(original, grant_revision=2, active=False)

    def change_both(stage, _host, w, _op):
        if stage != "before_b":
            return
        w.crop = replace(w.crop, crop_id="unrelated-crop")
        if replace_ledger:
            w.ledger = FakeWaterPermissionLedger(revoked)
        else:
            w.ledger.grant = revoked
        if raise_after_notice:
            raise RuntimeError("synthetic callback failed after P1 revoked")

    result = bridge.step(scene(), world, "WATER", change_both)
    assert result.verdict == "UNKNOWN_PENDING"
    assert result.effect_status == "PENDING_UNKNOWN"
    assert host.pending is not None
    assert "ENTER_A" in host.events and "ENTER_B" not in host.events
    assert host.events.count("FAKE_EFFECT") == 0
    assert bridge.provision_standing_grant(original) == "DENIED_STALE_GRANT_REVISION"
    assert host._fake_water_permission_store.accounts[original.grant_id].revoked is True


def test_malformed_crop_cannot_mask_valid_revocation_notice_at_step_entry():
    host, world, bridge = setup()
    original = world.ledger.grant
    world.crop = replace(world.crop, tile=[4, 5])  # deliberately invalid list
    world.ledger = FakeWaterPermissionLedger(
        replace(original, grant_revision=2, active=False)
    )
    assert bridge.step(scene(), world, "WATER").verdict == "DENIED_MALFORMED_CROP"
    assert bridge.provision_standing_grant(original) == "DENIED_STALE_GRANT_REVISION"
    assert host.events == []


def test_voluntary_stay_must_not_suppress_permission_revocation_notice():
    host, world, bridge = setup()
    original = world.ledger.grant
    world.ledger.grant = replace(original, grant_revision=2, active=False)
    assert bridge.step(scene(), world, "STAY").verdict == "STAY"
    assert bridge.provision_standing_grant(original) == "DENIED_STALE_GRANT_REVISION"
    later = FakePermissionWorld(
        replace(FakePermissionCrop(), revision=2),
        FakePlotStewardship(), FakeWaterPermissionLedger(original)
    )
    assert FakePermissionedWaterBridge(host).step(
        scene(revision=2), later, "WATER"
    ).verdict == "DENIED_GRANT_REVOKED"
    assert host.events == []
