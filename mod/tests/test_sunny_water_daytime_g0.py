"""G0-only regression tests: synthetic daytime WATER choice -> fake A/B STOP.

No game, network, local DLL, provider or production authority.
"""

from dataclasses import replace

import pytest

from reference.sunny_daytime_intents import FakeScene
from reference.sunny_host_stop_fake import FakeHostWaterFence
from reference.sunny_water_daytime_g0 import (
    FakeCropObservation,
    FakeDaytimeWaterBridge,
)


def scene(revision=1, **changes):
    initial = FakeScene(
        epoch="fake-load-1", owner="fake-host-p2", revision=revision,
        offered_actions=("STAY", "WATER"), weather="sunny",
    )
    return replace(initial, **changes)


def crop(revision=1, **changes):
    return replace(FakeCropObservation(revision=revision), **changes)


def test_dry_p2_owned_allowlisted_tile_uses_one_fake_host_operation():
    host = FakeHostWaterFence()
    bridge = FakeDaytimeWaterBridge(host)
    result = bridge.step(scene(), crop(), "WATER")
    assert (result.verdict, result.selected, result.offered) == (
        "FAKE_WATER_VERIFIED", "WATER", ("STAY", "WATER")
    )
    assert host.last_effect_evidence.operation_id == result.operation_id
    assert host.last_effect_evidence.tile == (4, 5)
    assert host.events == [
        "RESERVE_B_LINEAGE", "ENTER_A", "ENTER_B",
        "FAKE_EFFECT", "FINISH_A", "FAKE_OBSERVED_AND_RESOLVED",
    ]
    assert host.pending is None
    assert host.used_ids == {result.operation_id}


def test_stay_is_voluntary_even_when_water_is_grounded():
    host = FakeHostWaterFence()
    result = FakeDaytimeWaterBridge(host).step(scene(), crop(), "STAY")
    assert (result.verdict, result.selected, result.offered) == (
        "STAY", "STAY", ("STAY", "WATER")
    )
    assert host.events == []
    assert host.pending is None


@pytest.mark.parametrize("change", [
    {"soil_dry": False},
    {"plot_owner": "P1"},
    {"watering_can_equipped": False},
    {"water_left": 0},
    {"adjacent": False},
    {"menu_closed": False},
    {"tile": (6, 7)},
    {"revision": 2},
    {"epoch": "fake-old-load"},
])
def test_missing_grounding_declines_water_without_any_host_reservation(change):
    host = FakeHostWaterFence()
    result = FakeDaytimeWaterBridge(host).step(scene(), crop(**change), "WATER")
    assert (result.verdict, result.selected, result.offered) == (
        "STAY_NOT_GROUNDED", "STAY", ("STAY",)
    )
    assert host.pending is None and host.events == []


@pytest.mark.parametrize("change", [
    {"weather": "rainy"},
    {"weather": "unknown"},
    {"offered_actions": ("STAY",)},
    {"recently_completed": ("WATER",)},
])
def test_weather_offer_and_recent_activity_prevent_fake_water(change):
    host = FakeHostWaterFence()
    assert FakeDaytimeWaterBridge(host).step(
        scene(**change), crop(), "WATER"
    ).verdict == "STAY_NOT_GROUNDED"
    assert host.events == []


def test_stay_missing_is_hard_block_not_an_implicit_water_grant():
    host = FakeHostWaterFence()
    result = FakeDaytimeWaterBridge(host).step(
        scene(offered_actions=("WATER",)), crop(), "WATER"
    )
    assert result.verdict == "BLOCKED_NO_STAY"
    assert host.events == []


@pytest.mark.parametrize("change", [
    {"p1_is_human": False},
    {"p2_is_ai": False},
    {"p2_ready": False},
    {"owner": "fake-foreign-owner"},
    {"epoch": "fake-load-other"},
])
def test_roles_owner_and_epoch_fail_closed(change):
    host = FakeHostWaterFence()
    result = FakeDaytimeWaterBridge(host).step(scene(**change), crop(), "WATER")
    assert result.verdict in {"BLOCKED_ROLE_OR_OWNER", "BLOCKED_EPOCH"}
    assert host.events == []


def test_host_owner_change_denies_even_if_scene_looks_right():
    host = FakeHostWaterFence()
    host.owner = "fake-other-host"
    assert FakeDaytimeWaterBridge(host).step(
        scene(), crop(), "WATER"
    ).verdict == "BLOCKED_HOST_EPOCH_OR_OWNER"
    assert host.events == []


@pytest.mark.parametrize("attempted", ["MARRY_NPC", "MOVE_TO_CHAIR", "", None, True])
def test_unoffered_choice_is_not_silently_routed_to_water(attempted):
    host = FakeHostWaterFence()
    result = FakeDaytimeWaterBridge(host).step(scene(), crop(), attempted)
    assert result.verdict == "DENIED_UNSUPPORTED_CHOICE"
    assert host.events == []


@pytest.mark.parametrize("bad_crop", [
    {"water_left": True}, {"soil_dry": 1}, {"tile": (True, 5)},
    {"tile": [4, 5]}, {"plot_owner": object()},
    {"adjacent": "true"}, {"water_left": 101},
])
def test_malformed_crop_is_blocked_before_planning_or_reservation(bad_crop):
    host = FakeHostWaterFence()
    assert FakeDaytimeWaterBridge(host).step(
        scene(), crop(**bad_crop), "WATER"
    ).verdict == "BLOCKED_MALFORMED_CROP"
    assert host.events == []


@pytest.mark.parametrize("offered", [
    ("STAY", "WATER", "WATER"),
    ("STAY", ["WATER"]),
    ["STAY", "WATER"],
])
def test_malformed_or_duplicate_offer_shape_is_blocked(offered):
    host = FakeHostWaterFence()
    assert FakeDaytimeWaterBridge(host).step(
        scene(offered_actions=offered), crop(), "WATER"
    ).verdict == "BLOCKED_MALFORMED_SCENE"
    assert host.events == []


def test_unresolved_scene_flag_blocks_before_any_host_operation():
    host = FakeHostWaterFence()
    assert FakeDaytimeWaterBridge(host).step(
        scene(unresolved_attempt=True), crop(), "WATER"
    ).verdict == "BLOCKED_UNRESOLVED"
    assert host.events == []


def test_no_reproposal_without_new_revision_and_multiple_fake_rounds_allowed():
    host = FakeHostWaterFence()
    bridge = FakeDaytimeWaterBridge(host)
    assert bridge.step(scene(), crop(), "STAY").verdict == "STAY"
    assert bridge.step(scene(), crop(), "WATER").verdict == "WAIT_NEW_OBSERVATION"
    assert bridge.step(scene(revision=2), crop(revision=2), "WATER").verdict == "FAKE_WATER_VERIFIED"
    assert bridge.step(scene(revision=3), crop(revision=3), "STAY").verdict == "STAY"
    assert host.events.count("FAKE_EFFECT") == 1


def test_existing_unknown_pending_blocks_fresh_daytime_water_choice():
    host = FakeHostWaterFence()
    host.pending = object()  # synthetic stale unresolved marker
    result = FakeDaytimeWaterBridge(host).step(scene(), crop(), "WATER")
    assert result.verdict == "BLOCKED_UNRESOLVED"
    assert host.events == []


def test_stop_before_choice_blocks_watering_and_stay_dispatch():
    host = FakeHostWaterFence()
    host.latch_stop()
    result = FakeDaytimeWaterBridge(host).step(scene(), crop(), "WATER")
    assert result.verdict == "BLOCKED_STOP"
    assert host.events == ["STOP_LATCHED"]


def test_stop_just_after_reservation_blocks_a_and_preserves_pending():
    host = FakeHostWaterFence()
    bridge = FakeDaytimeWaterBridge(host)

    def stop(stage, h, _op):
        if stage == "after_reserve":
            h.latch_stop()

    result = bridge.step(scene(), crop(), "WATER", stop)
    assert result.verdict == "UNKNOWN_PENDING"
    assert host.pending is not None
    assert "ENTER_A" not in host.events and "FAKE_EFFECT" not in host.events
    assert bridge.step(scene(revision=2), crop(revision=2), "WATER").verdict == "BLOCKED_UNRESOLVED"


def test_stop_after_a_entry_prevents_b_entry_and_keeps_pending():
    host = FakeHostWaterFence()

    def stop(stage, h, _op):
        if stage == "in_a_before_b":
            h.latch_stop()

    result = FakeDaytimeWaterBridge(host).step(scene(), crop(), "WATER", stop)
    assert result.verdict == "UNKNOWN_PENDING"
    assert "ENTER_A" in host.events and "ENTER_B" not in host.events
    assert host.pending is not None and not host.fake_wet


def test_b_that_entered_before_stop_may_finish_after_stop_same_load():
    host = FakeHostWaterFence()

    def stop(stage, h, _op):
        if stage == "b_entered":
            h.latch_stop()

    result = FakeDaytimeWaterBridge(host).step(scene(), crop(), "WATER", stop)
    assert result.verdict == "FAKE_WATER_VERIFIED"
    assert host.events.index("ENTER_B") < host.events.index("STOP_LATCHED") < host.events.index("FAKE_EFFECT")
    assert host.stopped and host.pending is None
    assert host.used_ids == {result.operation_id}
    assert FakeDaytimeWaterBridge(host).step(scene(revision=2), crop(revision=2), "WATER").verdict == "BLOCKED_STOP"


def test_b_that_entered_before_epoch_change_cannot_resolve_old_pending():
    host = FakeHostWaterFence()

    def reload(stage, h, _op):
        if stage == "b_entered":
            h.rotate_epoch()

    result = FakeDaytimeWaterBridge(host).step(scene(), crop(), "WATER", reload)
    assert result.verdict == "UNKNOWN_PENDING"
    assert host.fake_wet and host.pending is not None
    assert host.last_effect_evidence.epoch == "fake-load-1"
    assert host.epoch == "fake-load-2"
    assert "FAKE_OBSERVED_AND_RESOLVED" not in host.events


def test_receipt_loss_after_effect_leaves_unknown_and_no_retry():
    host = FakeHostWaterFence()
    bridge = FakeDaytimeWaterBridge(host)

    def fail(stage, _h, _op):
        if stage == "before_fake_receipt":
            raise RuntimeError("injected synthetic lost receipt")

    result = bridge.step(scene(), crop(), "WATER", fail)
    assert result.verdict == "UNKNOWN_PENDING"
    assert host.fake_wet and host.pending is not None
    assert host.events.count("FAKE_EFFECT") == 1
    assert bridge.step(scene(revision=2), crop(revision=2), "WATER").verdict == "BLOCKED_UNRESOLVED"
    assert FakeDaytimeWaterBridge(host).step(scene(), crop(), "WATER").verdict == "BLOCKED_UNRESOLVED"


def test_callback_exception_never_falsely_confirms_effect():
    host = FakeHostWaterFence()

    def fail(stage, _h, _op):
        if stage == "in_a_before_b":
            raise RuntimeError("injected callback error")

    result = FakeDaytimeWaterBridge(host).step(scene(), crop(), "WATER", fail)
    assert result.verdict == "UNKNOWN_PENDING"
    assert host.pending is not None
    assert host.a_entered and not host.a_finished
    assert host.events.count("FAKE_EFFECT") == 0


def test_new_host_epoch_blocks_new_bridge_even_when_no_pending():
    host = FakeHostWaterFence()
    host.rotate_epoch()
    fresh = FakeDaytimeWaterBridge(host)
    result = fresh.step(
        scene(epoch="fake-load-2"), crop(epoch="fake-load-2"), "WATER"
    )
    assert result.verdict == "BLOCKED_STOP"
    assert host.events.count("RESERVE_B_LINEAGE") == 0


def test_only_explicit_synthetic_allowed_tiles_are_candidates():
    host = FakeHostWaterFence()
    bridge = FakeDaytimeWaterBridge(host, allowed_tiles=((1, 2),))
    assert bridge.step(scene(), crop(), "WATER").verdict == "STAY_NOT_GROUNDED"
    assert host.events == []


def test_no_host_forced_deduction_from_base_planner_cannot_water_without_offer():
    host = FakeHostWaterFence()
    result = FakeDaytimeWaterBridge(host).step(
        scene(offered_actions=("STAY", "MOVE_TO_CHAIR")), crop(), "WATER"
    )
    assert result.verdict == "STAY_NOT_GROUNDED"
    assert host.events == []


def test_two_bridges_cannot_replay_completed_water_after_revision_collision():
    """Exact prior reviewer counterexample: bridge B must never issue effect 2."""
    host = FakeHostWaterFence()
    bridge_a = FakeDaytimeWaterBridge(host)
    assert bridge_a.step(scene(revision=1), crop(revision=1), "STAY").verdict == "STAY"
    first = bridge_a.step(scene(revision=2), crop(revision=2), "WATER")
    assert first.verdict == "FAKE_WATER_VERIFIED"
    assert host.pending is None
    assert host._fake_daytime_water_last_revision == 2

    # Fresh bridge has forgotten A's planner history and starts its own
    # counter in the rejected predecessor. The shared Host must deny BOTH
    # stale rev 1 and replayed rev 2, without emitting another fake effect.
    bridge_b = FakeDaytimeWaterBridge(host)
    assert bridge_b.step(scene(revision=1), crop(revision=1), "WATER").verdict == (
        "DENIED_HOST_STALE_SNAPSHOT"
    )
    again = bridge_b.step(scene(revision=2), crop(revision=2), "WATER")
    assert again.verdict == "DENIED_HOST_STALE_SNAPSHOT"
    assert host.events.count("FAKE_EFFECT") == 1
    assert host.used_ids == {first.operation_id}
    assert host._fake_daytime_water_last_revision == 2
    assert FakeDaytimeWaterBridge(host).step(
        scene(revision=2), crop(revision=2), "WATER"
    ).verdict == "DENIED_HOST_STALE_SNAPSHOT"
    assert host.events.count("FAKE_EFFECT") == 1


@pytest.mark.parametrize("completed", [
    ("MOVE_TO_CHAIR", "MOVE_TO_CHAIR"),
    ("WATER", "WATER"),
    ("SPEAK_TO_P1", "SPEAK_TO_P1", "WATCH_WEATHER_TV"),
])
def test_duplicate_recently_completed_is_malformed_before_any_host_event(completed):
    host = FakeHostWaterFence()
    result = FakeDaytimeWaterBridge(host).step(
        scene(recently_completed=completed), crop(), "WATER"
    )
    assert result.verdict == "BLOCKED_MALFORMED_SCENE"
    assert host.events == []
    assert host.pending is None
    assert host.used_ids == set()


def test_failed_reservation_does_not_consume_host_revision_watermark():
    host = FakeHostWaterFence()
    # Same snapshot ID was already spent in this synthetic host, so the
    # reservation fails without any A/B effect and without moving the
    # watermark. A genuinely new scene revision can still be submitted.
    first_id = FakeDaytimeWaterBridge._snapshot_operation_id(scene(), crop())
    host.used_ids.add(first_id)
    bridge = FakeDaytimeWaterBridge(host)
    assert bridge.step(scene(), crop(), "WATER").verdict == "DENIED_HOST_RESERVATION"
    assert not hasattr(host, "_fake_daytime_water_last_revision")
    assert host.events == []
    fresh = bridge.step(scene(revision=2), crop(revision=2), "WATER")
    assert fresh.verdict == "FAKE_WATER_VERIFIED"
    assert fresh.operation_id != first_id
    assert host._fake_daytime_water_last_revision == 2
    assert host.events.count("FAKE_EFFECT") == 1


def test_corrupted_host_watermark_fails_closed_before_reservation():
    host = FakeHostWaterFence()
    host._fake_daytime_water_last_revision = "2"
    assert FakeDaytimeWaterBridge(host).step(
        scene(revision=3), crop(revision=3), "WATER"
    ).verdict == "DENIED_HOST_SNAPSHOT_STATE"
    assert host.events == []
