"""G0-only mixed Sunny daytime traces; no game, model, transport or P1 data."""
from dataclasses import replace

import pytest

import reference.sunny_mixed_daytime_g0 as mixed_module

from reference.sunny_gameplay_slice import FakeGame, OfflineController
from reference.sunny_host_stop_fake import FakeHostWaterFence
from reference.sunny_mixed_daytime_g0 import FakeMixedDaytimeLoop
from reference.sunny_water_permission_g0 import (
    FakePermissionCrop, FakePermissionWorld, FakePermissionedWaterBridge,
    FakePlotStewardship, FakeStandingWaterGrant, FakeWaterPermissionLedger,
)


class Interest:
    def __init__(self, *choices):
        self.choices = iter(choices)
        self.calls = 0
        self.offers = []

    def __call__(self, activities):
        self.calls += 1
        self.offers.append(tuple(a.action for a in activities))
        return next(self.choices)


def setup(*, choices=("WATER", "MOVE_TO_CHAIR", "STAY"), weather="sunny",
          grant=None, delivery="ack"):
    host = FakeHostWaterFence()
    game = FakeGame()
    game.owner = host.owner
    game.epoch = host.epoch
    game.sunny_tile = (4, 4)  # *adjacent* to the fictional crop at (4, 5)
    game.delivery = delivery
    grant = grant or FakeStandingWaterGrant()
    world = FakePermissionWorld(
        FakePermissionCrop(), FakePlotStewardship(),
        FakeWaterPermissionLedger(grant)
    )
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        grant
    ) == "FAKE_GRANT_PROVISIONED"
    interest = Interest(*choices)
    loop = FakeMixedDaytimeLoop(game, host, world, interest, weather=weather)
    return game, host, world, interest, loop


def test_water_then_chair_then_voluntary_stay_after_fake_reobservation():
    game, host, world, interest, loop = setup()
    game.private_p1_diary = "SECRET_P1_DIARY_NEVER_PASS_TO_CHOOSER"

    def reobserve(result, game, world, host):
        if result.choice == "WATER":
            # Explicitly invented fake crop observation, not inferred from
            # an ACK or real Mod. Revision 2 is a different snapshot.
            assert host.events.count("FAKE_EFFECT") == 1
            game.revision = 2
            world.crop = replace(world.crop, revision=2, soil_dry=False)

    results = loop.run_bounded(3, reobserve)
    assert [r.status for r in results] == [
        "FAKE_WATER_VERIFIED", "VERIFIED_FAKE", "STAY"
    ]
    assert interest.calls == 3
    assert interest.offers == [
        ("STAY", "MOVE_TO_CHAIR", "WATER"),
        ("STAY", "MOVE_TO_CHAIR"),
        ("STAY",),
    ]
    assert host.events.count("FAKE_EFFECT") == 1
    assert game.sunny_tile == game.chair_tile
    assert len(game.dispatched) == 1
    assert game.dispatched[0][1:] == ("MOVE_TO_CHAIR", "p2")
    assert world.ledger.attempted_starts == 1
    assert host.pending is None and game.pending_attempt is None
    assert all(r.claim_real_completion is False for r in results)
    assert "SECRET_P1_DIARY_NEVER_PASS_TO_CHOOSER" not in repr(interest.offers)


def test_water_without_new_observation_does_not_invite_blind_second_choice():
    game, host, world, interest, loop = setup(choices=("WATER", "WATER"))
    results = loop.run_bounded(3)
    assert [r.status for r in results] == [
        "FAKE_WATER_VERIFIED", "WAIT_NEW_OBSERVATION"
    ]
    assert interest.calls == 1
    assert host.events.count("FAKE_EFFECT") == 1


def test_stay_is_valid_without_water_or_chair_effect_and_no_busy_loop():
    game, host, world, interest, loop = setup(choices=("STAY", "WATER"))
    assert loop.step().status == "STAY"
    assert loop.step().status == "WAIT_NEW_OBSERVATION"
    assert host.events == [] and game.dispatched == []
    assert interest.calls == 1
    new = FakeMixedDaytimeLoop(game, host, world, Interest("WATER"), weather="sunny")
    assert new.step().status == "WAIT_NEW_OBSERVATION"


def test_move_first_then_stay_reobserves_without_repeating_chair():
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR", "STAY"))
    statuses = [r.status for r in loop.run_bounded(3)]
    assert statuses == ["VERIFIED_FAKE", "STAY"]
    assert interest.offers == [
        ("STAY", "MOVE_TO_CHAIR", "WATER"), ("STAY",)
    ]
    assert len(game.dispatched) == 1 and host.events == []


def test_two_authorized_tiles_then_move_allow_multiple_farm_activities():
    grant = replace(
        FakeStandingWaterGrant(), tiles=((4, 5), (5, 4)),
        max_distinct_tiles=2, max_attempted_starts=2
    )
    game, host, world, interest, loop = setup(
        grant=grant, choices=("WATER", "WATER", "MOVE_TO_CHAIR", "STAY")
    )

    def reobserve(result, game, world, host):
        if result.choice != "WATER":
            return
        game.revision += 1
        if game.revision == 2:
            world.crop = replace(
                world.crop, revision=2, tile=(5, 4), crop_id="second-fake-crop"
            )
            world.stewardship = replace(
                world.stewardship, tile=(5, 4), crop_id="second-fake-crop"
            )
        else:
            world.crop = replace(world.crop, revision=3, soil_dry=False)

    statuses = [r.status for r in loop.run_bounded(4, reobserve)]
    assert statuses == [
        "FAKE_WATER_VERIFIED", "FAKE_WATER_VERIFIED", "VERIFIED_FAKE", "STAY"
    ]
    assert host.events.count("FAKE_EFFECT") == 2
    account = host._fake_water_permission_store.accounts[grant.grant_id]
    assert account.attempted_starts == 2
    assert account.started_tiles == {(4, 5), (5, 4)}
    assert len(game.dispatched) == 1


@pytest.mark.parametrize("weather", ["rainy", "unknown"])
def test_weather_not_proven_does_not_offer_watering(weather):
    game, host, world, interest, loop = setup(choices=("WATER",), weather=weather)
    result = loop.step()
    assert result.status == "DENIED_NOT_GROUNDED"
    assert "WATER" not in result.offered
    assert not host.events and not game.dispatched


def test_nonadjacent_watering_is_not_proposed_on_crop_flag_alone():
    game, host, world, interest, loop = setup(choices=("WATER",))
    game.sunny_tile = (8, 8)
    assert loop.step().status == "DENIED_NOT_GROUNDED"
    assert interest.offers[0] == ("STAY", "MOVE_TO_CHAIR")
    assert host.events == []


@pytest.mark.parametrize("action", ["HARVEST", "WATER_ALL", "SPEAK_TO_P1",
                                    "WATCH_WEATHER_TV", "FIREPLACE_TOGGLE"])
def test_unoffered_or_high_impact_choice_never_runs(action):
    game, host, world, interest, loop = setup(choices=(action,))
    result = loop.step()
    assert result.status == "DENIED_NOT_GROUNDED"
    assert game.dispatched == [] and host.events == []


def test_host_stop_suppresses_chair_even_when_l2_world_is_ready():
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    host.latch_stop()
    assert loop.step().status == "BLOCKED_STOP"
    assert interest.calls == 0 and game.dispatched == []


def test_water_unknown_pending_suppresses_subsequent_chair_and_recreated_loop():
    game, host, world, interest, loop = setup(choices=("WATER", "MOVE_TO_CHAIR"))
    # Intercept only the synthetic receipt. The fake B effect may have occurred.
    host.confirm_fake_observation = lambda _op: "UNKNOWN_PENDING"
    assert loop.step().status == "UNKNOWN_PENDING"
    assert host.events.count("FAKE_EFFECT") == 1
    assert host.pending is not None
    assert loop.step().status == "BLOCKED_UNRESOLVED"
    fresh_interest = Interest("MOVE_TO_CHAIR")
    fresh = FakeMixedDaytimeLoop(game, host, world, fresh_interest, weather="sunny")
    assert fresh.step().status == "BLOCKED_UNRESOLVED"
    assert interest.calls == 1 and fresh_interest.calls == 0
    assert game.dispatched == []


@pytest.mark.parametrize("delivery", ["lost_reply", "ack_no_effect"])
def test_chair_unknown_blocks_later_water_even_on_new_loop(delivery):
    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR", "WATER"), delivery=delivery
    )
    assert loop.step().status == "UNKNOWN"
    assert game.pending_attempt is not None
    assert loop.step().status == "BLOCKED_UNRESOLVED"
    fresh_interest = Interest("WATER")
    assert FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    ).step().status == "BLOCKED_UNRESOLVED"
    assert host.events == [] and len(game.dispatched) == 1
    assert fresh_interest.calls == 0


@pytest.mark.parametrize("field,value", [
    ("epoch", "different-load"), ("owner", "wrong-owner"),
    ("p1_is_human", False), ("p2_is_ai", False), ("ready", False)
])
def test_role_owner_epoch_and_readiness_reject_before_choice(field, value):
    game, host, world, interest, loop = setup(choices=("WATER",))
    setattr(game, field, value)
    result = loop.step()
    assert result.status in {
        "BLOCKED_OWNER_OR_EPOCH", "BLOCKED_ROLE_OR_OWNER"
    }
    assert not host.events and not game.dispatched
    assert interest.calls == 0


def test_revoke_during_chooser_blocks_dispatch_and_records_host_tombstone():
    game, host, world, _, loop = setup()
    old = world.ledger.grant

    def revoke(_offered):
        world.ledger.grant = replace(old, active=False, grant_revision=2)
        return "WATER"

    loop.interest = revoke
    assert loop.step().status == "BLOCKED_CHANGED_BEFORE_DISPATCH"
    assert host.events == [] and game.dispatched == []
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        old
    ) == "DENIED_STALE_GRANT_REVISION"


def test_new_bridge_cannot_repeat_same_revision_even_for_stay():
    game, host, world, interest, loop = setup(choices=("STAY",))
    assert loop.step().status == "STAY"
    fresh = Interest("MOVE_TO_CHAIR")
    assert FakeMixedDaytimeLoop(
        game, host, world, fresh, weather="sunny"
    ).step().status == "WAIT_NEW_OBSERVATION"
    assert fresh.calls == 0 and not game.dispatched


def test_failure_to_publish_new_observation_stops_at_known_boundary():
    game, host, world, interest, loop = setup(choices=("WATER", "MOVE_TO_CHAIR"))

    def fail_observe(_result, _game, _world, _host):
        raise RuntimeError("fake world observation failed")

    results = loop.run_bounded(4, fail_observe)
    assert [r.status for r in results] == [
        "FAKE_WATER_VERIFIED", "BLOCKED_OBSERVATION_UPDATE"
    ]
    assert interest.calls == 1 and host.events.count("FAKE_EFFECT") == 1
    assert game.dispatched == []


def test_bounded_run_never_schedules_more_than_four_choices():
    game, host, world, interest, loop = setup(choices=("WATER",))
    for invalid in (0, 5, True, -1, None):
        with pytest.raises(ValueError):
            loop.run_bounded(invalid)
    assert interest.calls == 0


def test_chooser_cannot_move_chair_target_without_changing_observation():
    """Issue #96 counterexample: chair target was omitted from Observation."""
    game, host, world, _, loop = setup()
    assert game.chair_tile == (7, 4)

    def change_chair(_activities):
        game.chair_tile = (8, 4)
        return "MOVE_TO_CHAIR"

    loop.interest = change_chair
    result = loop.step()
    assert result.status == "BLOCKED_CHANGED_BEFORE_DISPATCH"
    assert result.choice == "MOVE_TO_CHAIR"
    assert game.sunny_tile == (4, 4)
    assert game.dispatched == [] and game.pending_attempt is None
    assert host.events == [] and result.claim_real_completion is False


@pytest.mark.parametrize("failure", ["raise", "unsupported", "invalid_type"])
def test_chooser_revocation_is_latched_on_every_exit(failure):
    """Issue #96: P1 revocation must survive all chooser exits."""
    game, host, world, _, loop = setup()
    original = world.ledger.grant

    def revoke_and_exit(_offered):
        world.ledger.grant = replace(
            original, active=False, grant_revision=2
        )
        if failure == "raise":
            raise RuntimeError("synthetic chooser failed after valid P1 revoke")
        if failure == "unsupported":
            return "HARVEST"
        return ["WATER"]

    loop.interest = revoke_and_exit
    first = loop.step()
    expected = ("BLOCKED_INTEREST_UNAVAILABLE" if failure == "raise"
                else "DENIED_NOT_GROUNDED")
    assert first.status == expected
    assert first.claim_real_completion is False
    assert game.dispatched == [] and host.events == []
    assert host._fake_water_permission_store.accounts[original.grant_id].revoked
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        original
    ) == "DENIED_STALE_GRANT_REVISION"

    # A new chooser, game snapshot, and ledger cannot revive v1 on the Host.
    game.revision = 2
    world.crop = replace(world.crop, revision=2)
    world.ledger = FakeWaterPermissionLedger(original)
    new_interest = Interest("WATER")
    new_loop = FakeMixedDaytimeLoop(
        game, host, world, new_interest, weather="sunny"
    )
    rejected = new_loop.step()
    assert rejected.status == "DENIED_NOT_GROUNDED"
    assert "WATER" not in rejected.offered
    assert host.events.count("FAKE_EFFECT") == 0


def test_failed_second_observation_after_choice_does_not_dispatch():
    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",)
    )
    original_observe = game.observe
    reads = 0

    def observe_then_fail():
        nonlocal reads
        reads += 1
        if reads == 2:
            raise RuntimeError("fake observation source unavailable")
        return original_observe()

    game.observe = observe_then_fail
    result = loop.step()
    assert result.status == "BLOCKED_OBSERVATION_UNAVAILABLE"
    assert result.claim_real_completion is False
    assert reads == 2 and interest.calls == 1
    assert game.dispatched == [] and host.events == []
    assert game.pending_attempt is None


def test_chair_target_mutated_during_fake_dispatch_never_reports_verified():
    """L2's mutable chair target can otherwise satisfy its own verifier."""
    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",)
    )
    original_dispatch = game.dispatch

    def retarget_during_dispatch(action, expected, attempt):
        game.chair_tile = (8, 4)
        return original_dispatch(action, expected, attempt)

    game.dispatch = retarget_during_dispatch
    result = loop.step()
    assert result.status == "UNKNOWN_UNVERIFIED_CHAIR_TARGET"
    assert result.claim_real_completion is False
    # R6 checks the target during the raw dispatch's own observation.
    # This earlier retarget no longer reaches the fake effect at all.
    assert game.sunny_tile == (4, 4)
    assert game.dispatched == []
    assert game.pending_attempt is not None
    assert result.operation_id == game.pending_attempt
    assert game._fake_mixed_quarantined is True
    assert "MOVE_TO_CHAIR" not in loop.completed
    next_interest = Interest("WATER")
    assert FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    ).step().status == "BLOCKED_UNRESOLVED"
    assert next_interest.calls == 0 and host.events == []


def test_malformed_observation_revision_and_options_fail_without_exception():
    game, host, world, interest, loop = setup(choices=("WATER",))
    game.revision = "1"
    assert loop.step().status == "BLOCKED_MALFORMED_OBSERVATION"
    assert interest.calls == 0 and host.events == []
    game.revision = 1
    original_observe = game.observe

    def unhashable_options():
        return replace(original_observe(), options=("STAY", []))

    game.observe = unhashable_options
    assert loop.step().status == "BLOCKED_MALFORMED_OBSERVATION"
    assert interest.calls == 0 and host.events == []


def test_observation_publisher_partial_mutation_and_failure_quarantines():
    game, host, world, interest, loop = setup(
        choices=("WATER", "MOVE_TO_CHAIR")
    )

    def partial_then_fail(_result, game, world, _host):
        game.revision = 2
        world.crop = replace(world.crop, revision=2, soil_dry=False)
        raise RuntimeError("publisher unavailable after partial update")

    results = loop.run_bounded(3, partial_then_fail)
    assert [r.status for r in results] == [
        "FAKE_WATER_VERIFIED", "BLOCKED_OBSERVATION_UPDATE"
    ]
    assert game._fake_mixed_quarantined is True
    fresh_interest = Interest("MOVE_TO_CHAIR")
    assert FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    ).step().status == "BLOCKED_UNRESOLVED"
    assert fresh_interest.calls == 0 and game.dispatched == []
    assert host.events.count("FAKE_EFFECT") == 1


@pytest.mark.parametrize("on_second_read", ["stop", "water_pending", "epoch_rotation"])
def test_second_observation_can_change_host_gate_without_chair_dispatch(on_second_read):
    """Issue #96 R1 STOP bypass: last gate used to precede this callback."""
    from reference.sunny_host_stop_fake import FakeWaterOperation

    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.observe
    reads = 0

    def observe_with_host_event():
        nonlocal reads
        reads += 1
        if reads == 2:
            if on_second_read == "stop":
                host.latch_stop()
            elif on_second_read == "epoch_rotation":
                host.rotate_epoch()
            else:
                op = FakeWaterOperation(
                    "host-new-pending-1", host.epoch, host.owner,
                    "P2", "WATER", (4, 5)
                )
                assert host.reserve(op) == "B_LINEAGE_RESERVED"
        return original()

    game.observe = observe_with_host_event
    first = loop.step()
    assert reads == 2
    assert first.status == (
        "BLOCKED_UNRESOLVED" if on_second_read == "water_pending"
        else "BLOCKED_CHANGED_BEFORE_DISPATCH"
    )
    assert first.operation_id == (
        "host-new-pending-1" if on_second_read == "water_pending" else None
    )
    assert first.claim_real_completion is False
    assert interest.calls == 1
    assert not game.dispatched and game.pending_attempt is None
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert "FAKE_EFFECT" not in host.events
    if on_second_read == "water_pending":
        assert host.pending is not None
        assert first.operation_id == host.pending.operation_id
    else:
        assert host.stopped is True

    fresh_interest = Interest("MOVE_TO_CHAIR")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    )
    fresh_result = fresh.step()
    assert fresh_result.status in {
        "BLOCKED_STOP", "BLOCKED_UNRESOLVED", "BLOCKED_OWNER_OR_EPOCH"
    }
    if on_second_read == "water_pending":
        assert fresh_result.status == "BLOCKED_UNRESOLVED"
        assert fresh_result.operation_id == host.pending.operation_id
    assert fresh_interest.calls == 0
    assert not game.dispatched


def test_stop_during_l2_first_observation_denies_before_fake_chair_reservation():
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.observe
    reads = 0

    def observe():
        nonlocal reads
        reads += 1
        if reads == 3:
            host.latch_stop()
        return original()

    game.observe = observe
    result = loop.step()
    assert reads == 3
    assert result.status == "BLOCKED_OBSERVATION_UNAVAILABLE"
    assert host.stopped and game.pending_attempt is None
    assert game.dispatched == [] and host.events.count("FAKE_EFFECT") == 0
    assert interest.calls == 1
    assert "MOVE_TO_CHAIR" not in loop.completed


def test_stop_during_injected_prepare_observer_is_unknown_without_dispatch():
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.observe
    reads = 0

    def observe():
        nonlocal reads
        reads += 1
        if reads == 4:  # raw FakeGame.prepare calls observe inside itself
            host.latch_stop()
        return original()

    game.observe = observe
    result = loop.step()
    assert reads == 4
    # A callback during an original prepare read can perform hidden effects.
    # Even STOP before the physical toy send cannot prove the attempt clean.
    assert result.status == "UNKNOWN"
    assert result.operation_id == "offline-attempt-1"
    assert host.stopped
    assert game.pending_attempt is None
    assert game.dispatched == []
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert "MOVE_TO_CHAIR" not in loop.completed


def test_untrusted_observer_blocks_before_dispatch_read_and_keeps_pending():
    """A callback scheduled for dispatch read #5 is stopped at prepare #4.

    An injectable observer cannot establish prepare authorization. This
    deliberately changes the old read-count contract; separate STOP tests
    exercise actual Host latching and post-finalizer STOP.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.observe
    reads = 0

    def observe():
        nonlocal reads
        reads += 1
        if reads == 5:  # raw FakeGame.dispatch reads observation
            host.latch_stop()
        return original()

    game.observe = observe
    result = loop.step()
    assert reads == 4
    assert result.status == "UNKNOWN"
    assert host.stopped is False  # read #5 cannot execute
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.pending_attempt is not None
    assert game.dispatched == []  # strict checked read now prevents effect
    assert result.operation_id == game.pending_attempt
    assert "MOVE_TO_CHAIR" not in loop.completed
    later = Interest("WATER")
    assert FakeMixedDaytimeLoop(
        game, host, world, later, weather="sunny"
    ).step().status == "BLOCKED_UNRESOLVED"
    assert later.calls == 0


def test_host_pending_during_l2_prepare_is_not_ignored():
    from reference.sunny_host_stop_fake import FakeWaterOperation

    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.prepare

    def prepare(*args):
        result = original(*args)
        op = FakeWaterOperation("second-host-water-op",
                                host.epoch, host.owner, "P2", "WATER", (4, 5))
        assert host.reserve(op) == "B_LINEAGE_RESERVED"
        return result

    game.prepare = prepare
    result = loop.step()
    # R22: injectable prepare has write authority over the reserved chair.
    # It is not proof of a clean pre-effect denial, even when no movement is
    # visible. Preserve the original chair ID and the DIFFERENT Host WATER ID.
    assert result.status == "UNKNOWN"
    assert host.pending is not None
    assert result.operation_id == game.pending_attempt == "offline-attempt-1"
    assert result.pending_operation_id == host.pending.operation_id
    assert result.pending_operation_id == "second-host-water-op"
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.dispatched == []
    assert "MOVE_TO_CHAIR" not in loop.completed


@pytest.mark.parametrize("replacement", ["granted_far_crop", "granted_adjacent_crop",
                                         "same_crop_new_object"])
def test_second_observation_crop_swap_never_bypasses_p2_adjacency(replacement):
    """Issue #96 R2: two granted tiles alone do not imply P2 can reach both."""
    grant = replace(
        FakeStandingWaterGrant(),
        tiles=((4, 5), (8, 4), (5, 4)),
        max_distinct_tiles=3, max_attempted_starts=3
    )
    game, host, world, interest, loop = setup(
        grant=grant, choices=("WATER",)
    )
    original = game.observe
    reads = 0

    def switch_crop_on_reread():
        nonlocal reads
        reads += 1
        if reads == 2:
            if replacement == "granted_far_crop":
                world.crop = replace(
                    world.crop, tile=(8, 4), crop_id="second-fake-crop"
                )
                world.stewardship = replace(
                    world.stewardship, tile=(8, 4), crop_id="second-fake-crop"
                )
                assert abs(game.sunny_tile[0] - world.crop.tile[0]) + abs(
                    game.sunny_tile[1] - world.crop.tile[1]
                ) == 4
            elif replacement == "granted_adjacent_crop":
                world.crop = replace(
                    world.crop, tile=(5, 4), crop_id="second-fake-crop"
                )
                world.stewardship = replace(
                    world.stewardship, tile=(5, 4), crop_id="second-fake-crop"
                )
            else:
                world.crop = replace(world.crop)
        return original()

    game.observe = switch_crop_on_reread
    result = loop.step()
    assert reads == 2
    assert result.status == "BLOCKED_CHANGED_BEFORE_DISPATCH"
    assert result.choice == "WATER"
    assert result.claim_real_completion is False
    assert interest.offers[0] == ("STAY", "MOVE_TO_CHAIR", "WATER")
    assert "RESERVE_B_LINEAGE" not in host.events
    assert host.events.count("FAKE_EFFECT") == 0
    assert host.used_ids == set() and host.pending is None
    assert getattr(host, "_fake_daytime_water_last_revision", -1) == -1
    account = host._fake_water_permission_store.accounts[grant.grant_id]
    assert account.attempted_starts == 0 and account.started_tiles == set()
    assert game.dispatched == [] and world.ledger.attempted_starts == 0


@pytest.mark.parametrize("stage,expected", [
    ("after_wait", "DENIED_WAIT_FAILURE"),
    ("after_reserve", "UNKNOWN_PENDING"),
    ("before_b", "UNKNOWN_PENDING"),
])
def test_water_rechecks_independent_p2_adjacency_before_fake_b(stage, expected):
    """Stage injection emulates a changing P2 location without crop revision."""
    game, host, world, interest, loop = setup(choices=("WATER",))
    original_run_hook = loop.watering._run_fixture_hook

    def move_p2_during_stage(hook, current_stage, current_world, operation):
        if current_stage == stage:
            game.sunny_tile = (8, 8)
        return original_run_hook(hook, current_stage, current_world, operation)

    loop.watering._run_fixture_hook = move_p2_during_stage
    result = loop.step()
    assert result.status == expected
    assert result.claim_real_completion is False
    assert "ENTER_B" not in host.events
    assert "FAKE_EFFECT" not in host.events
    assert game.dispatched == [] and world.ledger.attempted_starts == 0
    account = host._fake_water_permission_store.accounts[
        world.ledger.grant.grant_id
    ]
    assert account.attempted_starts == 0 and account.started_tiles == set()
    if stage == "after_wait":
        assert host.pending is None and host.used_ids == set()
    else:
        assert host.pending is not None
        followup = Interest("MOVE_TO_CHAIR")
        assert FakeMixedDaytimeLoop(
            game, host, world, followup, weather="sunny"
        ).step().status == "BLOCKED_UNRESOLVED"
        assert followup.calls == 0


def test_revocation_delivered_during_second_read_is_latched_before_water_denial():
    game, host, world, interest, loop = setup(choices=("WATER",))
    original_grant = world.ledger.grant
    original_observe = game.observe
    calls = 0

    def revoke_during_read():
        nonlocal calls
        calls += 1
        if calls == 2:
            world.ledger.grant = replace(
                original_grant, grant_revision=2, active=False
            )
        return original_observe()

    game.observe = revoke_during_read
    result = loop.step()
    assert result.status == "BLOCKED_CHANGED_BEFORE_DISPATCH"
    assert calls == 2 and result.choice == "WATER"
    assert host.events == [] and host.pending is None
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        original_grant
    ) == "DENIED_STALE_GRANT_REVISION"
    assert host._fake_water_permission_store.accounts[
        original_grant.grant_id
    ].revoked is True
    assert world.ledger.attempted_starts == 0


def test_second_read_exception_after_revocation_keeps_tombstone_no_water():
    game, host, world, interest, loop = setup(choices=("WATER",))
    old = world.ledger.grant
    original_observe = game.observe
    calls = 0

    def fail_with_revocation():
        nonlocal calls
        calls += 1
        if calls == 2:
            world.ledger.grant = replace(old, grant_revision=2, active=False)
            raise RuntimeError("synthetic crop-read error after revoke")
        return original_observe()

    game.observe = fail_with_revocation
    result = loop.step()
    assert result.status == "BLOCKED_OBSERVATION_UNAVAILABLE"
    assert host.events == [] and host.pending is None
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        old
    ) == "DENIED_STALE_GRANT_REVISION"
    assert world.ledger.attempted_starts == 0


@pytest.mark.parametrize("first_read", ["raise", "malformed", "normal"])
def test_first_observation_revocation_survives_every_exit_and_stale_grant_restore(
        first_read):
    """Issue #96 R3: first read was missing the revocation finally guard.

    Reproduce valid inactive v2 delivered on the initial fake Game.observe
    and exercise a raised, malformed, or valid returned observation. Even
    after restoring an old active-v1 view on a *new* scene and coordinator,
    the same fake Host must never authorize WATER or debit a start.
    """
    game, host, world, interest, loop = setup(choices=("WATER",))
    old = world.ledger.grant
    original_observe = game.observe
    reads = 0

    def notify_revocation_on_first_read():
        nonlocal reads
        reads += 1
        if reads == 1:
            world.ledger.grant = replace(old, grant_revision=2, active=False)
            if first_read == "raise":
                raise RuntimeError("first fake observation failed after P1 revoked")
            if first_read == "malformed":
                return replace(original_observe(), revision="invalid-revision")
        return original_observe()

    game.observe = notify_revocation_on_first_read
    first = loop.step()
    assert reads == 1
    assert first.status == (
        "BLOCKED_OBSERVATION_UNAVAILABLE" if first_read == "raise"
        else "BLOCKED_MALFORMED_OBSERVATION" if first_read == "malformed"
        else "DENIED_NOT_GROUNDED"
    )
    account = host._fake_water_permission_store.accounts[old.grant_id]
    assert account.revoked is True and account.grant.grant_revision == 2
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        old
    ) == "DENIED_STALE_GRANT_REVISION"
    assert host.events == [] and host.pending is None and host.used_ids == set()
    assert account.attempted_starts == 0 and account.started_tiles == set()
    assert game.dispatched == []

    # This is the exact escalation from the independent source review:
    # recreate the old active ledger on the same fake Host after a new
    # matching Game and crop revision, then try WATER from a fresh loop.
    game.observe = original_observe
    game.revision = 2
    world.crop = replace(world.crop, revision=2)
    world.ledger = FakeWaterPermissionLedger(old)
    later_interest = Interest("WATER")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    )
    later = fresh.step()
    assert later.status == "DENIED_NOT_GROUNDED"
    assert "WATER" not in later.offered
    assert "RESERVE_B_LINEAGE" not in host.events
    assert "FAKE_EFFECT" not in host.events
    assert host.pending is None and host.used_ids == set()
    assert getattr(host, "_fake_daytime_water_last_revision", -1) == -1
    assert account.attempted_starts == 0 and account.started_tiles == set()
    assert world.ledger.attempted_starts == 0 and game.dispatched == []


@pytest.mark.parametrize("first_read", ["stop", "host_pending"])
def test_first_observation_host_event_rechecks_gate_before_choice(first_read):
    """Even a normally returning first read must not evade a new fake gate."""
    from reference.sunny_host_stop_fake import FakeWaterOperation

    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_observe = game.observe
    reads = 0

    def add_host_event():
        nonlocal reads
        reads += 1
        if reads == 1:
            if first_read == "stop":
                host.latch_stop()
            else:
                op = FakeWaterOperation(
                    "first-read-pending", host.epoch, host.owner,
                    "P2", "WATER", (4, 5)
                )
                assert host.reserve(op) == "B_LINEAGE_RESERVED"
        return original_observe()

    game.observe = add_host_event
    result = loop.step()
    assert reads == 1
    assert result.status == (
        "BLOCKED_UNRESOLVED" if first_read == "host_pending"
        else "BLOCKED_CHANGED_BEFORE_DISPATCH"
    )
    assert result.operation_id == (
        "first-read-pending" if first_read == "host_pending" else None
    )
    assert interest.calls == 0 and game.dispatched == []
    assert game.pending_attempt is None
    if first_read == "stop":
        assert host.stopped
    else:
        assert host.pending is not None
        assert result.operation_id == host.pending.operation_id


@pytest.mark.parametrize("chair_read,raises,expected", [
    (3, True, "BLOCKED_OBSERVATION_UNAVAILABLE"),
    (4, True, "BLOCKED_STALE_OR_DENIED"),
    (5, True, "UNKNOWN"),
    (6, True, "UNKNOWN"),
    (3, False, "VERIFIED_FAKE"),
    (4, False, "VERIFIED_FAKE"),
    (5, False, "VERIFIED_FAKE"),
    (6, False, "VERIFIED_FAKE"),
])
def test_chair_reads_latch_p1_revocation_even_if_inner_game_read_raises(
        chair_read, raises, expected):
    """R23 observer boundary: only reads #1–4 can execute, not #5–6.

    The old test trusted read-only callbacks to support toy positive chair
    verification. R23 deliberately treats injected callbacks in the
    operation boundary as potentially effectful; after read #4 the attempted
    chair remains UNKNOWN even if the observer merely returns canonical
    data. A revocation already delivered at #3/#4 MUST still be ingested,
    while a future #5/#6 notification cannot be fabricated.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    old = world.ledger.grant
    original_observe = game.observe
    calls = 0

    def revoke_during_chair_read():
        nonlocal calls
        calls += 1
        if calls == chair_read:
            world.ledger.grant = replace(old, grant_revision=2, active=False)
            if raises:
                raise RuntimeError("synthetic chair fixture read failed after revoke")
        return original_observe()

    game.observe = revoke_during_chair_read
    result = loop.step()
    assert calls == (3 if raises and chair_read == 3 else 4)
    assert result.status == (
        "BLOCKED_OBSERVATION_UNAVAILABLE"
        if raises and chair_read == 3 else "UNKNOWN"
    )
    assert result.claim_real_completion is False
    assert interest.calls == 1 and host.events == []
    account = host._fake_water_permission_store.accounts[old.grant_id]
    revocation_delivered = chair_read <= calls
    if revocation_delivered:
        assert account.revoked is True
        assert account.grant.grant_revision == 2
        assert FakePermissionedWaterBridge(host).provision_standing_grant(
            old
        ) == "DENIED_STALE_GRANT_REVISION"
    else:
        assert account.revoked is False
        assert account.grant.grant_revision == old.grant_revision
    assert account.attempted_starts == 0 and account.started_tiles == set()
    assert host.pending is None and host.used_ids == set()

    if raises and chair_read == 3:
        assert game.pending_attempt is None and game.dispatched == []
        assert getattr(game, "_fake_mixed_quarantined", False) is False
    else:
        assert result.operation_id == "offline-attempt-1"
        assert game.pending_attempt is (
            None if raises and chair_read == 4 else game.pending_attempt
        )
        assert game.dispatched == []
        assert getattr(game, "_fake_mixed_quarantined", False) is True

    game.observe = original_observe
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    world.ledger = FakeWaterPermissionLedger(old)
    game.sunny_tile = (4, 4)
    later_interest = Interest("WATER")
    subsequent = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    if raises and chair_read == 3:
        assert subsequent.status == "DENIED_NOT_GROUNDED"
        assert "WATER" not in subsequent.offered
        assert later_interest.calls == 1
    else:
        assert subsequent.status == "BLOCKED_UNRESOLVED"
        assert later_interest.calls == 0
    assert account.attempted_starts == 0 and account.started_tiles == set()
    assert host.events == [] and host.pending is None

@pytest.mark.parametrize("corruption", ["string_revision", "unhashable_options"])
def test_malformed_chair_verification_returns_unknown_not_python_exception(
        corruption):
    """Malformed *post-move* snapshot must preserve L2 pending quarantine."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_observe = game.observe
    calls = 0

    def malformed_after_fake_move():
        nonlocal calls
        calls += 1
        snapshot = original_observe()
        if calls == 6:
            if corruption == "string_revision":
                return replace(snapshot, revision="unexpected-string")
            return replace(snapshot, options=("STAY", []))
        return snapshot

    game.observe = malformed_after_fake_move
    result = loop.step()
    assert result.status == "UNKNOWN"
    assert result.choice == "MOVE_TO_CHAIR"
    assert result.claim_real_completion is False
    assert calls == 6
    assert len(game.dispatched) == 1
    assert game.sunny_tile == game.chair_tile
    assert game.pending_attempt is not None
    assert result.operation_id == game.pending_attempt == game.dispatched[0][0]
    assert "MOVE_TO_CHAIR" not in loop.completed
    fresh_interest = Interest("WATER")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    )
    assert fresh.step().status == "BLOCKED_UNRESOLVED"
    assert fresh_interest.calls == 0 and host.events == []


def test_chair_verification_error_after_p1_revocation_keeps_both_guards():
    """One failing L2 read can also convey valid permission revocation."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    old = world.ledger.grant
    original_observe = game.observe
    calls = 0

    def malformed_and_revoke():
        nonlocal calls
        calls += 1
        snapshot = original_observe()
        if calls == 6:
            world.ledger.grant = replace(old, grant_revision=2, active=False)
            return replace(snapshot, revision="bad_revision")
        return snapshot

    game.observe = malformed_and_revoke
    result = loop.step()
    assert result.status == "UNKNOWN"
    assert game.pending_attempt is not None and len(game.dispatched) == 1
    account = host._fake_water_permission_store.accounts[old.grant_id]
    assert account.revoked and account.grant.grant_revision == 2
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        old
    ) == "DENIED_STALE_GRANT_REVISION"
    assert account.attempted_starts == 0
    assert "FAKE_EFFECT" not in host.events


@pytest.mark.parametrize("publisher_exit", ["return", "raise"])
def test_verified_chair_publisher_always_ingests_valid_p1_revocation(
        publisher_exit):
    """R5 review: even the final publisher call can deliver inactive grant v2.

    A fresh fake Game with the SAME Host must not recover v1 permission,
    including when the original Game was quarantined after a publisher error.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    old = world.ledger.grant
    called = []

    def publish(result, game, water_world, host):
        called.append(result.status)
        assert result.status == "VERIFIED_FAKE"
        assert game.sunny_tile == game.chair_tile
        water_world.ledger.grant = replace(
            old, grant_revision=2, active=False
        )
        if publisher_exit == "raise":
            raise RuntimeError("fake publisher error after valid P1 revocation")

    outcomes = loop.run_bounded(max_decisions=1, after_verified=publish)
    assert called == ["VERIFIED_FAKE"]
    assert [item.status for item in outcomes] == (
        ["VERIFIED_FAKE", "BLOCKED_OBSERVATION_UPDATE"]
        if publisher_exit == "raise" else ["VERIFIED_FAKE"]
    )
    assert getattr(game, "_fake_mixed_quarantined", False) is (
        publisher_exit == "raise"
    )
    account = host._fake_water_permission_store.accounts[old.grant_id]
    assert account.revoked is True
    assert account.grant.grant_revision == 2
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        old
    ) == "DENIED_STALE_GRANT_REVISION"
    assert host.events == [] and host.used_ids == set() and host.pending is None
    assert account.attempted_starts == 0 and account.started_tiles == set()

    # Do NOT rely on the first Game's quarantine or replay watermark. A
    # completely new fake Game + old active ledger on the same Host still
    # cannot offer or spend the already-revoked WATER grant.
    fresh_game = FakeGame()
    fresh_game.epoch = host.epoch
    fresh_game.owner = host.owner
    fresh_game.sunny_tile = (4, 4)
    fresh_game.revision = 3
    world.crop = replace(world.crop, revision=3)
    world.ledger = FakeWaterPermissionLedger(old)
    later_interest = Interest("WATER")
    fresh_loop = FakeMixedDaytimeLoop(
        fresh_game, host, world, later_interest, weather="sunny"
    )
    later = fresh_loop.step()
    assert later.status == "DENIED_NOT_GROUNDED"
    assert later_interest.offers == [("STAY", "MOVE_TO_CHAIR")]
    assert not host.events and not host.used_ids and host.pending is None
    assert account.attempted_starts == 0 and account.started_tiles == set()
    assert not fresh_game.dispatched and world.ledger.attempted_starts == 0


@pytest.mark.parametrize("raw_read,bad_revision", [
    (4, True),
    (4, 1.0),
    (5, True),
    (5, 1.0),
])
def test_raw_chair_prepare_dispatch_reject_numeric_lookalikes(
        raw_read, bad_revision):
    """Dataclass True == 1 and 1.0 == 1 must not authorize a fake move."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.observe
    reads = 0

    def read_with_numeric_lookalike():
        nonlocal reads
        reads += 1
        snapshot = original()
        if reads == raw_read:
            corrupt = replace(snapshot, revision=bad_revision)
            assert corrupt == snapshot  # Python's weak dataclass equality
            return corrupt
        return snapshot

    game.observe = read_with_numeric_lookalike
    result = loop.step()
    assert reads == raw_read
    assert result.status != "VERIFIED_FAKE"
    assert result.status == (
        "BLOCKED_STALE_OR_DENIED" if raw_read == 4 else "UNKNOWN"
    )
    assert result.claim_real_completion is False
    assert game.observe is read_with_numeric_lookalike
    assert game.dispatched == []
    assert game.sunny_tile == (4, 4)
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert host.events == []
    assert result.operation_id is not None
    if raw_read == 4:
        assert game.pending_attempt is None
    else:
        assert result.operation_id == game.pending_attempt

    later_interest = Interest("MOVE_TO_CHAIR")
    later = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    if game.pending_attempt is not None:
        assert later.status == "BLOCKED_UNRESOLVED"
    else:
        assert later.status == "WAIT_NEW_OBSERVATION"
    assert later_interest.calls == 0

    if raw_read == 4:
        # Recreating a coordinator after a newer revision is legal ONLY
        # because this attempt was definitively rejected pre-effect. It
        # must never have been reported as an untracked UNKNOWN.
        game.revision += 1
        world.crop = replace(world.crop, revision=game.revision)
        game.observe = original
        fresh = FakeMixedDaytimeLoop(
            game, host, world, Interest("MOVE_TO_CHAIR"), weather="sunny"
        )
        recovered = fresh.step()
        assert recovered.status == "VERIFIED_FAKE"
        assert len(game.dispatched) == 1
        assert recovered.operation_id == game.dispatched[0][0]
        assert recovered.operation_id != result.operation_id
    else:
        game.revision += 1
        world.crop = replace(world.crop, revision=game.revision)
        blocked_interest = Interest("MOVE_TO_CHAIR")
        blocked = FakeMixedDaytimeLoop(
            game, host, world, blocked_interest, weather="sunny"
        ).step()
        assert blocked.status == "BLOCKED_UNRESOLVED"
        assert blocked_interest.calls == 0


@pytest.mark.parametrize("invalid_options", [
    (),
    ("STAY", "MOVE_TO_CHAIR"),
    ("MOVE_TO_CHAIR", "STAY"),
])
def test_chair_post_move_options_must_match_fake_game_contract(invalid_options):
    """Even well-typed options can be invalid once P2 reached the chair."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.observe
    reads = 0

    def bad_verified_options():
        nonlocal reads
        reads += 1
        snapshot = original()
        if reads == 6:
            assert snapshot.sunny_tile == game.chair_tile
            assert snapshot.options == ("STAY",)
            return replace(snapshot, options=invalid_options)
        return snapshot

    game.observe = bad_verified_options
    result = loop.step()
    assert reads == 6
    assert result.status == "UNKNOWN"
    assert result.claim_real_completion is False
    assert result.choice == "MOVE_TO_CHAIR"
    assert game.observe is bad_verified_options
    assert len(game.dispatched) == 1
    assert game.sunny_tile == game.chair_tile
    assert result.operation_id == game.dispatched[0][0] == game.pending_attempt
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert host.events == []

    fresh_interest = Interest("WATER")
    assert FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    ).step().status == "BLOCKED_UNRESOLVED"
    assert fresh_interest.calls == 0


def test_successful_chair_dispatch_restores_original_observer():
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.observe
    reads = 0

    def observe():
        nonlocal reads
        reads += 1
        return original()

    game.observe = observe
    result = loop.step()
    assert result.status == "VERIFIED_FAKE"
    assert reads == 6
    assert game.observe is observe
    assert game.pending_attempt is None and len(game.dispatched) == 1
    assert result.operation_id == game.dispatched[0][0]


def test_retarget_after_actual_fake_chair_effect_is_unknown_and_quarantined():
    """The already-started effect cannot be undone by a later retarget."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_dispatch = game.dispatch

    def effect_then_retarget(*args):
        result = original_dispatch(*args)
        assert len(game.dispatched) == 1
        game.chair_tile = (8, 4)  # target changed *after* real fake effect
        return result

    game.dispatch = effect_then_retarget
    outcome = loop.step()
    assert outcome.status == "UNKNOWN_UNVERIFIED_CHAIR_TARGET"
    assert outcome.claim_real_completion is False
    assert game.sunny_tile == (7, 4)
    assert game.chair_tile == (8, 4)
    assert len(game.dispatched) == 1
    assert outcome.operation_id == game.dispatched[0][0] == game.pending_attempt
    assert game._fake_mixed_quarantined is True
    assert "MOVE_TO_CHAIR" not in loop.completed
    next_interest = Interest("WATER")
    assert FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    ).step().status == "BLOCKED_UNRESOLVED"
    assert next_interest.calls == 0 and host.events == []


def test_stop_after_actual_fake_dispatch_effect_is_unknown_with_pending():
    """Host STOP after effect started must not be falsely reported as denied."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_dispatch = game.dispatch

    def effect_then_stop(*args):
        result = original_dispatch(*args)
        assert len(game.dispatched) == 1
        host.latch_stop()
        return result

    game.dispatch = effect_then_stop
    outcome = loop.step()
    assert outcome.status == "UNKNOWN"
    assert outcome.claim_real_completion is False
    assert host.stopped
    assert len(game.dispatched) == 1
    assert game.sunny_tile == game.chair_tile
    assert outcome.operation_id == game.dispatched[0][0] == game.pending_attempt
    assert "MOVE_TO_CHAIR" not in loop.completed
    next_interest = Interest("WATER")
    assert FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    ).step().status == "BLOCKED_UNRESOLVED"
    assert next_interest.calls == 0


@pytest.mark.parametrize("reported_revision", [2, 3])
def test_post_dispatch_fabricated_chair_arrival_cannot_clear_pending(
        reported_revision):
    """R6 review: a well-shaped lie must not complete an ack_no_effect move.

    L2 used to trust a fabricated newer snapshot from game.observe, called
    finish_observed_action, and cleared the only pending record. The mixed
    loop noticed the actual position mismatch only *after* that finalization.
    """
    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",), delivery="ack_no_effect"
    )
    original_observe = game.observe
    reads = 0

    def spoof_arrival_after_no_effect():
        nonlocal reads
        reads += 1
        snapshot = original_observe()
        if reads == 6:
            assert game.sunny_tile == (4, 4)
            assert game.revision == 1
            assert len(game.dispatched) == 1
            # All supplied fields look valid for successful arrival, but
            # the underlying FakeGame never moved or revised its state.
            return replace(
                snapshot,
                sunny_tile=game.chair_tile,
                revision=reported_revision,
                options=("STAY",),
            )
        return snapshot

    game.observe = spoof_arrival_after_no_effect
    result = loop.step()
    assert reads == 6
    assert result.status == "UNKNOWN"
    assert result.choice == "MOVE_TO_CHAIR"
    assert not result.claim_real_completion
    assert game.sunny_tile == (4, 4)
    assert game.revision == 1
    assert len(game.dispatched) == 1
    assert result.operation_id == game.dispatched[0][0] == game.pending_attempt
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert game.observe is spoof_arrival_after_no_effect
    assert host.pending is None and host.events == []

    # Even a new, higher snapshot revision cannot silently retry: pending
    # must block BEFORE observing again or choosing any activity.
    game.observe = original_observe
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    interest2 = Interest("MOVE_TO_CHAIR")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, interest2, weather="sunny"
    )
    assert fresh.step().status == "BLOCKED_UNRESOLVED"
    assert interest2.calls == 0
    assert len(game.dispatched) == 1
    assert game.pending_attempt == result.operation_id



@pytest.mark.parametrize("raw_read,authoritative_revision", [
    (4, True),
    (4, 1.0),
    (5, True),
    (5, 1.0),
])
def test_authoritative_numeric_revision_must_be_strict_before_chair_action(
        raw_read, authoritative_revision):
    """R7 review: a *valid returned* revision must not mask bad raw Game data.

    Dataclass comparison treats True/1.0 as equal to integer 1. The earlier
    R6 tests only corrupted the supplied snapshot, not underlying FakeGame.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_observe = game.observe
    reads = 0

    def return_clean_snapshot_from_malformed_fake_game():
        nonlocal reads
        reads += 1
        if reads == raw_read:
            game.revision = authoritative_revision
            canonical = original_observe()
            # Shape-valid evidence, but authoritative in-memory Game's
            # revision is *not* an exact int.
            injected = replace(canonical, revision=1)
            assert type(injected.revision) is int
            assert injected == canonical
            return injected
        return original_observe()

    game.observe = return_clean_snapshot_from_malformed_fake_game
    result = loop.step()
    assert reads == raw_read
    assert result.status == (
        "BLOCKED_STALE_OR_DENIED" if raw_read == 4 else "UNKNOWN"
    )
    assert result.claim_real_completion is False
    assert game.revision is authoritative_revision or (
        type(authoritative_revision) is float
        and type(game.revision) is float
        and game.revision == authoritative_revision
    )
    assert game.observe is return_clean_snapshot_from_malformed_fake_game
    assert game.dispatched == []
    assert game.sunny_tile == (4, 4)
    assert not loop.completed and host.events == []
    if raw_read == 4:
        assert game.pending_attempt is None
        assert result.operation_id == "offline-attempt-1"
    else:
        assert result.operation_id == "offline-attempt-1"
        assert game.pending_attempt == result.operation_id

    # A newer snapshot cannot overwrite the UNKNOWN pending for dispatch,
    # but is fine after definite pre-effect preparation denial.
    game.observe = original_observe
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    new_interest = Interest("MOVE_TO_CHAIR")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, new_interest, weather="sunny"
    )
    followup = fresh.step()
    if raw_read == 4:
        assert followup.status == "VERIFIED_FAKE"
        assert len(game.dispatched) == 1
        assert followup.operation_id == "offline-attempt-2"
        assert followup.operation_id == game.dispatched[0][0]
    else:
        assert followup.status == "BLOCKED_UNRESOLVED"
        assert new_interest.calls == 0
        assert game.dispatched == []
        assert game.pending_attempt == result.operation_id


def test_reentrant_prepare_foreign_pending_does_not_report_outer_unknown():
    """R7 review: nested attempt-2 pending is NOT outer attempt-1.

    A synthetic callback can reenter using the same FakeGame/Host after the
    outer raw prepare observer was temporarily installed. This is an inert
    deterministic fixture, not a claim of safe actual game concurrency.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_observe = game.observe
    raw_calls = 0
    nested = []

    def reenter_during_outer_prepare():
        nonlocal raw_calls
        raw_calls += 1
        if raw_calls == 4:
            # New fake observation for a distinct nested decision.
            game.revision = 2
            world.crop = replace(world.crop, revision=2)
            game.delivery = "lost_reply"
            # Nested coordinator must run on its own intended fake observer,
            # not through the outer controller's temporary validation proxy.
            game.observe = original_observe
            nested_interest = Interest("MOVE_TO_CHAIR")
            nested_loop = FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            )
            inner = nested_loop.step()
            # Assertions inside an observer callback can be caught by the
            # coordinator and silently downgraded; verify outside step().
            nested.append(inner)

            # Make the OUTER raw prepare read malformed, as in the reviewed
            # replay. Its new attempt-1 must be denied, not UNKNOWN.
            return replace(original_observe(), revision="bad_outer_revision")
        return original_observe()

    game.observe = reenter_during_outer_prepare
    outer = loop.step()
    assert raw_calls == 4
    assert len(nested) == 1 and nested[0].status == "UNKNOWN"
    assert nested[0].operation_id == "offline-attempt-2"
    assert outer.status == "BLOCKED_UNRESOLVED"
    assert outer.operation_id == nested[0].operation_id == "offline-attempt-2"
    assert game.pending_attempt == "offline-attempt-2"
    assert game.dispatched == [(
        "offline-attempt-2", "MOVE_TO_CHAIR", "p2"
    )]
    assert game.seen_attempts == {"offline-attempt-2"}
    assert game.attempt_serial == 2
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert host.events == [] and host.pending is None
    assert game.observe is reenter_during_outer_prepare

    # The real shared fake Game pending ID fences later decisions regardless
    # of revision advancement or coordinator reconstruction.
    game.observe = original_observe
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    fresh_interest = Interest("MOVE_TO_CHAIR")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    )
    assert fresh.step().status == "BLOCKED_UNRESOLVED"
    assert fresh_interest.calls == 0
    assert len(game.dispatched) == 1
    assert game.pending_attempt == nested[0].operation_id


@pytest.mark.parametrize("authoritative_field,bad_value", [
    ("revision", True),
    ("revision", 1.0),
    ("sunny_tile", (4.0, 4)),
])
def test_water_second_read_denies_malformed_authoritative_fake_game(
        authoritative_field, bad_value):
    """R8 review: clean supplied observation cannot mask bad raw Game fields."""
    game, host, world, interest, loop = setup(choices=("WATER",))
    original_observe = game.observe
    reads = 0

    def clean_observation_but_mutate_authority():
        nonlocal reads
        reads += 1
        if reads == 2:
            setattr(game, authoritative_field, bad_value)
            canonical = original_observe()
            # The returned snapshot is a legitimate exact-type Observation,
            # but the direct Game state contains a numeric lookalike.
            returned = replace(
                canonical, **{authoritative_field: (
                    1 if authoritative_field == "revision" else (4, 4)
                )}
            )
            assert returned == canonical  # dataclass's weak numeric equality
            return returned
        return original_observe()

    game.observe = clean_observation_but_mutate_authority
    result = loop.step()
    assert reads == 2
    assert result.status == "BLOCKED_CHANGED_BEFORE_DISPATCH"
    assert result.choice == "WATER"
    assert not result.claim_real_completion
    assert interest.calls == 1
    assert game.observe is clean_observation_but_mutate_authority
    assert game.dispatched == [] and game.pending_attempt is None
    assert not host.events and not host.used_ids and host.pending is None
    assert world.ledger.attempted_starts == 0
    account = host._fake_water_permission_store.accounts[
        world.ledger.grant.grant_id
    ]
    assert account.attempted_starts == 0 and account.started_tiles == set()
    # Validating the authoritative state at a NEW revision must not mask
    # any of the rejected malformed pre-B observations as verified WATER.
    game.observe = original_observe
    game.revision = 2
    game.sunny_tile = (4, 4)
    world.crop = replace(world.crop, revision=2)
    assert host.events == [] and account.attempted_starts == 0


@pytest.mark.parametrize("stage,expected", [
    ("after_wait", "DENIED_WAIT_FAILURE"),
    ("after_reserve", "UNKNOWN_PENDING"),
    ("before_b", "UNKNOWN_PENDING"),
])
@pytest.mark.parametrize("authoritative_field,bad_value", [
    ("revision", True),
    ("revision", 1.0),
    ("sunny_tile", (4.0, 4)),
])
def test_water_each_pre_b_guard_denies_malformed_authoritative_state(
        stage, expected, authoritative_field, bad_value):
    """All pre-B hooks must check strict raw Game types, not Python ==."""
    game, host, world, interest, loop = setup(choices=("WATER",))
    original_hook = loop.watering._run_fixture_hook
    touched = []

    def mutate_during_stage(hook, current_stage, current_world, operation):
        if current_stage == stage:
            setattr(game, authoritative_field, bad_value)
            touched.append(current_stage)
        return original_hook(hook, current_stage, current_world, operation)

    loop.watering._run_fixture_hook = mutate_during_stage
    result = loop.step()
    assert touched == [stage]
    assert result.status == expected
    assert not result.claim_real_completion
    assert result.choice == "WATER"
    assert "ENTER_B" not in host.events
    assert "FAKE_EFFECT" not in host.events
    assert game.dispatched == []
    assert world.ledger.attempted_starts == 0
    account = host._fake_water_permission_store.accounts[
        world.ledger.grant.grant_id
    ]
    assert account.attempted_starts == 0 and account.started_tiles == set()
    if stage == "after_wait":
        assert host.pending is None and host.used_ids == set()
    else:
        assert host.pending is not None
        fresh_interest = Interest("WATER")
        fresh = FakeMixedDaytimeLoop(
            game, host, world, fresh_interest, weather="sunny"
        )
        assert fresh.step().status == "BLOCKED_UNRESOLVED"
        assert fresh_interest.calls == 0


@pytest.mark.parametrize("first_adapter_read", ["malformed", "exception"])
def test_first_chair_adapter_read_reports_nested_pending_actual_id(
        first_adapter_read):
    """R8 review: L2 first-read failure has no outer ID, but inner does.

    Callback #3 occurs before the outer L2 calls new_attempt(). A nested
    controller with a lost fake reply can reserve and dispatch attempt-1.
    The mixed result must name THAT ID rather than omit it.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_observe = game.observe
    calls = 0
    inner_results = []

    def nested_during_first_chair_read():
        nonlocal calls
        calls += 1
        if calls == 3:
            game.revision = 2
            world.crop = replace(world.crop, revision=2)
            game.delivery = "lost_reply"
            game.observe = original_observe
            nested_interest = Interest("MOVE_TO_CHAIR")
            nested = FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            ).step()
            inner_results.append(nested)
            if first_adapter_read == "exception":
                raise RuntimeError("toy first chair read failed after nested action")
            return replace(original_observe(), revision="malformed_outer_read")
        return original_observe()

    game.observe = nested_during_first_chair_read
    outer = loop.step()
    assert calls == 3
    assert len(inner_results) == 1
    assert inner_results[0].status == "UNKNOWN"
    assert inner_results[0].operation_id == "offline-attempt-1"
    assert game.dispatched == [
        ("offline-attempt-1", "MOVE_TO_CHAIR", "p2")
    ]
    assert outer.status == "BLOCKED_UNRESOLVED"
    assert not outer.claim_real_completion
    assert outer.operation_id == inner_results[0].operation_id
    assert outer.operation_id == game.pending_attempt
    assert game.dispatched[0][0] == outer.operation_id
    assert game.attempt_serial == 1
    assert game.seen_attempts == {outer.operation_id}
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert host.events == [] and host.pending is None

    # A new scene cannot restart the original action while the nested
    # operation remains unresolved, even across coordinator recreation.
    game.observe = original_observe
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    next_interest = Interest("WATER")
    assert FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    ).step().status == "BLOCKED_UNRESOLVED"
    assert next_interest.calls == 0
    assert len(game.dispatched) == 1
    assert game.pending_attempt == outer.operation_id


@pytest.mark.parametrize("next_choice,next_status", [
    ("STAY", "STAY"),
    ("WATER", "FAKE_WATER_VERIFIED"),
])
def test_unverified_first_observation_cannot_poison_shared_replay_watermark(
        next_choice, next_status):
    """R9 review: valid-looking fabricated rev100 must not consume revision2."""
    game, host, world, interest, loop = setup(choices=(next_choice,))
    raw_observe = game.observe
    reads = 0

    def fabricated_future_revision():
        nonlocal reads
        reads += 1
        canonical = raw_observe()
        assert canonical.revision == 1
        return replace(canonical, revision=100)

    game.observe = fabricated_future_revision
    rejected = loop.step()
    assert rejected.status == "BLOCKED_CHANGED_BEFORE_DISPATCH"
    assert rejected.operation_id is None
    assert reads == 1
    assert interest.calls == 0 and interest.offers == []
    assert getattr(game, "_fake_mixed_last_revision", -1) == -1
    assert host.events == [] and host.pending is None
    assert world.ledger.attempted_starts == 0
    assert game.dispatched == [] and game.pending_attempt is None

    # New *real fake* revision2 is later than rev1 even though the rejected
    # injected observer claimed 100. A fresh coordinator must be usable.
    game.observe = raw_observe
    game.revision = 2
    world.crop = replace(world.crop, revision=2)
    next_interest = Interest(next_choice)
    fresh = FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    )
    next_result = fresh.step()
    assert next_result.status == next_status
    assert next_interest.calls == 1
    assert getattr(game, "_fake_mixed_last_revision", -1) == 2
    if next_choice == "WATER":
        assert host.events.count("FAKE_EFFECT") == 1
    else:
        assert host.events == []


@pytest.mark.parametrize("outer_read", [1, 2])
@pytest.mark.parametrize("read_exit", ["malformed", "exception"])
def test_outer_mixed_observation_returns_actual_nested_pending_id(
        outer_read, read_exit):
    """R9 review: pre-chair outer read must expose nested lost-reply ID.

    Unlike L2's adapter read, these two observations happen inside the
    mixed coordinator itself. Reentrant nested coordinator gets attempt-1;
    outer read must never return BLOCKED_* with a missing operation ID.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    raw_observe = game.observe
    reads = 0
    nested_outcomes = []

    def nested_during_outer_read():
        nonlocal reads
        reads += 1
        if reads == outer_read:
            game.revision = 2
            world.crop = replace(world.crop, revision=2)
            game.delivery = "lost_reply"
            game.observe = raw_observe
            nested_interest = Interest("MOVE_TO_CHAIR")
            nested_loop = FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            )
            nested = nested_loop.step()
            nested_outcomes.append(nested)
            if read_exit == "exception":
                raise RuntimeError("synthetic outer read failed after nested move")
            return replace(raw_observe(), revision="malformed_outer_revision")
        return raw_observe()

    game.observe = nested_during_outer_read
    outer_result = loop.step()
    assert reads == outer_read
    assert len(nested_outcomes) == 1
    assert nested_outcomes[0].status == "UNKNOWN"
    assert nested_outcomes[0].operation_id == "offline-attempt-1"
    assert len(game.dispatched) == 1
    assert outer_result.status == "BLOCKED_UNRESOLVED"
    assert outer_result.claim_real_completion is False
    assert outer_result.operation_id == nested_outcomes[0].operation_id
    assert outer_result.operation_id == game.pending_attempt
    assert outer_result.operation_id == game.dispatched[0][0]
    assert game.seen_attempts == {"offline-attempt-1"}
    assert game.attempt_serial == 1
    assert len(game.dispatched) == 1
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert host.events == [] and host.pending is None

    game.observe = raw_observe
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("WATER")
    later = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert later_interest.calls == 0
    assert game.pending_attempt == outer_result.operation_id
    assert len(game.dispatched) == 1


@pytest.mark.parametrize("chooser_exit", ["valid", "invalid", "raise"])
def test_nested_chair_chooser_reports_actual_pending_for_every_exit(chooser_exit):
    """R10 review: pending ID survives chooser return/invalid/exception."""
    game, host, world, _, loop = setup(choices=("STAY",))
    nested_results = []
    nested_interest = Interest("MOVE_TO_CHAIR")

    def chooser_with_nested_lost_reply(_offered):
        game.revision = 2
        world.crop = replace(world.crop, revision=2)
        game.delivery = "lost_reply"
        nested_result = FakeMixedDaytimeLoop(
            game, host, world, nested_interest, weather="sunny"
        ).step()
        nested_results.append(nested_result)
        if chooser_exit == "raise":
            raise RuntimeError("synthetic chooser failure after nested chair")
        return "STAY" if chooser_exit == "valid" else "NEVER_OFFERED"

    loop.interest = chooser_with_nested_lost_reply
    result = loop.step()
    # Assertions deliberately AFTER step: callback assertion exceptions
    # could be swallowed as an interest-failure status.
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN"
    assert nested_results[0].operation_id == "offline-attempt-1"
    assert nested_interest.calls == 1
    assert result.status == "BLOCKED_UNRESOLVED"
    assert result.operation_id == nested_results[0].operation_id
    assert result.operation_id == game.pending_attempt == game.dispatched[0][0]
    assert len(game.dispatched) == 1
    assert game.seen_attempts == {"offline-attempt-1"}
    assert host.pending is None and host.events == []
    assert "MOVE_TO_CHAIR" not in loop.completed

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("STAY")
    fresh_result = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    assert fresh_result.status == "BLOCKED_UNRESOLVED"
    assert fresh_result.operation_id == result.operation_id
    assert later_interest.calls == 0


@pytest.mark.parametrize("outer_read", [1, 2])
@pytest.mark.parametrize("read_exit", ["malformed", "exception", "valid"])
def test_nested_water_on_outer_reads_reports_real_host_pending_id(
        outer_read, read_exit):
    """R10 review: nested WATER stays pending in fake Host, not FakeGame."""
    game, host, world, _, loop = setup(choices=("STAY",))
    original_observe = game.observe
    host.confirm_fake_observation = lambda _operation: "UNKNOWN_PENDING"
    reads = 0
    nested_results = []
    nested_interest = Interest("WATER")

    def water_during_outer_read():
        nonlocal reads
        reads += 1
        if reads == outer_read:
            game.revision = 2
            world.crop = replace(world.crop, revision=2)
            game.observe = original_observe
            nested_result = FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            ).step()
            nested_results.append(nested_result)
            if read_exit == "exception":
                raise RuntimeError("synthetic outer observation failure")
            snapshot = original_observe()
            if read_exit == "malformed":
                return replace(snapshot, revision="invalid_outer_revision")
            return snapshot
        return original_observe()

    game.observe = water_during_outer_read
    outer_result = loop.step()
    assert reads == outer_read
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN_PENDING"
    assert nested_results[0].choice == "WATER"
    assert nested_results[0].operation_id is not None
    assert nested_interest.calls == 1
    assert host.pending is not None
    assert outer_result.status == "BLOCKED_UNRESOLVED"
    assert outer_result.operation_id == nested_results[0].operation_id
    assert outer_result.operation_id == host.pending.operation_id
    assert game.pending_attempt is None and game.dispatched == []
    assert host.events.count("FAKE_EFFECT") == 1
    assert world.ledger.attempted_starts == 1

    game.observe = original_observe
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("MOVE_TO_CHAIR")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    )
    fresh_result = fresh.step()
    assert fresh_result.status == "BLOCKED_UNRESOLVED"
    assert fresh_result.operation_id == host.pending.operation_id
    assert later_interest.calls == 0
    assert len(game.dispatched) == 0


@pytest.mark.parametrize("pending_action", ["chair", "water"])
def test_entry_gate_reports_pending_id_from_both_fake_ledgers(pending_action):
    """Reconstruct a coordinator: status AND pending identity must survive."""
    game, host, world, _, loop = setup(
        choices=("MOVE_TO_CHAIR",) if pending_action == "chair" else ("WATER",)
    )
    if pending_action == "chair":
        game.delivery = "lost_reply"
    else:
        host.confirm_fake_observation = lambda _op: "UNKNOWN_PENDING"
    first = loop.step()
    assert first.status == (
        "UNKNOWN" if pending_action == "chair" else "UNKNOWN_PENDING"
    )
    assert first.operation_id is not None
    if pending_action == "chair":
        assert first.operation_id == game.pending_attempt == game.dispatched[0][0]
        assert host.pending is None
    else:
        assert first.operation_id == host.pending.operation_id
        assert game.pending_attempt is None

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    next_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    )
    blocked = fresh.step()
    assert blocked.status == "BLOCKED_UNRESOLVED"
    assert blocked.operation_id == first.operation_id
    assert next_interest.calls == 0


def test_water_host_reserve_callback_reports_nested_host_pending_identity():
    """R11 review: outer WATER denial must not hide nested Host operation ID.

    A nested WATER action is reserved first by a synchronous fake Host
    reserve callback, then the OUTER reservation loses its race and the
    accepted G0 water bridge returns DENIED_HOST_RESERVATION without an ID.
    """
    game, host, world, interest, loop = setup(choices=("WATER",))
    raw_reserve = host.reserve
    nested_results = []
    nested_interests = []
    wrapper_calls = []

    def reserve_after_nested_water(operation):
        wrapper_calls.append(operation.operation_id)
        if not nested_results:
            # The nested coordinator must be able to use a newer independent
            # observation and the unwrapped fake Host reservation.
            game.revision = 2
            world.crop = replace(world.crop, revision=2)
            host.confirm_fake_observation = lambda _op: "UNKNOWN_PENDING"
            host.reserve = raw_reserve
            try:
                nested_interest = Interest("WATER")
                nested_interests.append(nested_interest)
                nested_result = FakeMixedDaytimeLoop(
                    game, host, world, nested_interest, weather="sunny"
                ).step()
                nested_results.append(nested_result)
            finally:
                host.reserve = reserve_after_nested_water
        return raw_reserve(operation)

    host.reserve = reserve_after_nested_water
    outer = loop.step()
    # Never assert nested status inside callbacks: bridge exception handling
    # could otherwise swallow a failed pytest assertion.
    assert len(wrapper_calls) == 1
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN_PENDING"
    assert nested_results[0].choice == "WATER"
    assert nested_results[0].operation_id is not None
    assert nested_interests[0].calls == 1
    assert outer.status == "BLOCKED_UNRESOLVED"
    assert outer.choice == "WATER"
    assert outer.claim_real_completion is False
    assert outer.operation_id == nested_results[0].operation_id
    assert host.pending is not None
    assert outer.operation_id == host.pending.operation_id
    assert host.events.count("FAKE_EFFECT") == 1
    assert world.ledger.attempted_starts == 1
    assert game.dispatched == [] and game.pending_attempt is None
    assert interest.calls == 1
    assert "FAKE_WATER_VERIFIED" not in (outer.status, nested_results[0].status)

    # A new coordinator remains blocked by that exact fake Host ID, even
    # after an independently advanced fake Game/soil revision.
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("MOVE_TO_CHAIR")
    later = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert later.operation_id == outer.operation_id
    assert later_interest.calls == 0
    assert len(host.used_ids) == 1
    assert game.dispatched == []


@pytest.mark.parametrize("max_decisions", [1, 2])
def test_successful_final_publisher_reports_nested_pending_after_verified_water(
        max_decisions):
    """R11 review: verified WATER must be retained AND nested pending listed.

    Even max_decisions=1 has a publisher exit that can create a nested
    lost-reply chair action. Returning successfully from the publisher must
    not silently omit the already-pending chair from the bounded trace.
    """
    game, host, world, interest, loop = setup(choices=("WATER",))
    publisher_results = []
    publisher_receipts = []
    published_normally = []
    nested_interest = Interest("MOVE_TO_CHAIR")

    def publish_then_nested_chair(verified, current_game, current_world, current_host):
        # Never assert inside a publisher callback caught by run_bounded().
        publisher_receipts.append(
            (verified, current_game, current_world, current_host)
        )
        current_game.revision = 2
        current_world.crop = replace(current_world.crop, revision=2, soil_dry=False)
        current_game.delivery = "lost_reply"
        nested = FakeMixedDaytimeLoop(
            current_game, current_host, current_world, nested_interest,
            weather="sunny"
        ).step()
        publisher_results.append(nested)
        published_normally.append(True)

    results = loop.run_bounded(max_decisions=max_decisions,
                               after_verified=publish_then_nested_chair)
    # All assertions are AFTER the publisher callback has unwound: a
    # regression cannot be swallowed by run_bounded's exception handler.
    assert len(publisher_receipts) == 1
    assert publisher_receipts[0][0].status == "FAKE_WATER_VERIFIED"
    assert publisher_receipts[0][1] is game
    assert publisher_receipts[0][2] is world
    assert publisher_receipts[0][3] is host
    assert published_normally == [True]
    assert getattr(game, "_fake_mixed_quarantined", False) is False
    assert len(publisher_results) == 1
    assert publisher_results[0].status == "UNKNOWN"
    assert publisher_results[0].choice == "MOVE_TO_CHAIR"
    assert [r.status for r in results] == [
        "FAKE_WATER_VERIFIED", "BLOCKED_UNRESOLVED"
    ]
    assert results[0].choice == "WATER"
    assert results[0].operation_id is not None
    assert results[1].operation_id == publisher_results[0].operation_id
    assert results[1].operation_id == game.pending_attempt
    assert results[1].operation_id == game.dispatched[0][0]
    assert results[1].claim_real_completion is False
    assert len(game.dispatched) == 1
    assert host.pending is None and host.events.count("FAKE_EFFECT") == 1
    assert world.ledger.attempted_starts == 1
    assert interest.calls == 1 and nested_interest.calls == 1
    assert "MOVE_TO_CHAIR" not in loop.completed

    # Even the final bounded iteration reports pending work and prevents
    # blind resumption by another mixed coordinator at a later revision.
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    next_interest = Interest("WATER")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    ).step()
    assert fresh.status == "BLOCKED_UNRESOLVED"
    assert fresh.operation_id == results[1].operation_id
    assert next_interest.calls == 0
    assert len(game.dispatched) == 1



def test_raising_host_reserve_after_nested_water_reports_real_pending_id():
    """R12 review: reserve callback raises AFTER nested WATER becomes pending."""
    game, host, world, interest, loop = setup(choices=("WATER",))
    raw_reserve = host.reserve
    nested_results = []
    nested_interest = Interest("WATER")
    injected_calls = []

    def raise_after_nested_water(operation):
        injected_calls.append(operation.operation_id)
        game.revision = 2
        world.crop = replace(world.crop, revision=2)
        host.confirm_fake_observation = lambda _op: "UNKNOWN_PENDING"
        host.reserve = raw_reserve
        try:
            nested_results.append(
                FakeMixedDaytimeLoop(
                    game, host, world, nested_interest, weather="sunny"
                ).step()
            )
        finally:
            host.reserve = raise_after_nested_water
        raise RuntimeError("reserve failed after nested WATER pending")

    host.reserve = raise_after_nested_water
    outer = loop.step()  # MUST NOT raise: shared Host has pending ID.
    assert len(injected_calls) == 1
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN_PENDING"
    assert nested_results[0].choice == "WATER"
    assert nested_results[0].operation_id is not None
    assert outer.status == "BLOCKED_UNRESOLVED"
    assert outer.choice == "WATER"
    assert outer.operation_id == nested_results[0].operation_id
    assert host.pending is not None
    assert outer.operation_id == host.pending.operation_id
    assert host.reserve is raise_after_nested_water
    assert host.events.count("FAKE_EFFECT") == 1
    assert len(host.used_ids) == 1
    assert world.ledger.attempted_starts == 1
    assert interest.calls == 1 and nested_interest.calls == 1
    assert not getattr(game, "_fake_mixed_quarantined", False)

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    new_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, new_interest, weather="sunny"
    ).step()
    assert fresh.status == "BLOCKED_UNRESOLVED"
    assert fresh.operation_id == outer.operation_id
    assert new_interest.calls == 0


def test_nested_verified_water_cannot_roll_back_host_watermark_or_strand_outer():
    """R12 review: nested verified rev2 invalidates an outer rev1 reserve."""
    game, host, world, interest, loop = setup(choices=("WATER",))
    raw_reserve = host.reserve
    nested_results = []
    nested_interest = Interest("WATER")
    reserve_calls = []

    def reserve_after_nested_verified_water(operation):
        reserve_calls.append(operation.operation_id)
        game.revision = 2
        world.crop = replace(world.crop, revision=2)
        host.reserve = raw_reserve
        try:
            nested_results.append(
                FakeMixedDaytimeLoop(
                    game, host, world, nested_interest, weather="sunny"
                ).step()
            )
        finally:
            host.reserve = reserve_after_nested_verified_water
        # Raw toy Host WOULD grant stale revision-1 outer operation here:
        # its own reserve() validates owner/ID, not snapshot revision.
        return raw_reserve(operation)

    host.reserve = reserve_after_nested_verified_water
    outer = loop.step()
    assert reserve_calls and len(reserve_calls) == 1
    assert len(nested_results) == 1
    assert nested_results[0].status == "FAKE_WATER_VERIFIED"
    assert nested_results[0].operation_id is not None
    assert outer.status == "DENIED_HOST_RESERVATION"
    assert outer.operation_id is None
    assert not outer.claim_real_completion
    assert host.pending is None
    assert host._fake_daytime_water_last_revision == 2
    assert getattr(game, "_fake_mixed_last_revision", -1) == 2
    assert game.revision == 2 and world.crop.revision == 2
    assert host.reserve is reserve_after_nested_verified_water
    assert host.events.count("FAKE_STALE_PRE_A_RESERVATION_RETIRED") == 1
    assert host.events.count("FAKE_EFFECT") == 1
    assert world.ledger.attempted_starts == 1
    assert len(host.used_ids) == 2  # nested + retired outer tombstone
    assert not host.b_reserved and not host.a_entered and not host.b_entered
    assert game.dispatched == [] and game.pending_attempt is None
    assert interest.calls == 1 and nested_interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    next_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    ).step()
    assert fresh.status == "STAY"
    assert next_interest.calls == 1
    assert host.pending is None
    assert host._fake_daytime_water_last_revision == 2
    assert host.events.count("FAKE_EFFECT") == 1


@pytest.mark.parametrize("bounded", [False, True])
def test_verified_water_receipt_survives_confirm_callback_nested_pending_chair(
        bounded):
    """R12 review: report verified WATER and foreign unresolved chair together."""
    game, host, world, interest, loop = setup(choices=("WATER",))
    raw_confirm = host.confirm_fake_observation
    confirmed = []
    nested_results = []
    nested_interest = Interest("MOVE_TO_CHAIR")
    publisher_calls = []

    def confirm_water_then_dispatch_nested_chair(operation):
        receipt = raw_confirm(operation)  # real fake receipt, Host resolves.
        confirmed.append((receipt, operation.operation_id))
        game.revision = 2
        world.crop = replace(world.crop, revision=2, soil_dry=False)
        game.delivery = "lost_reply"
        nested_results.append(
            FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            ).step()
        )
        return receipt

    host.confirm_fake_observation = confirm_water_then_dispatch_nested_chair
    if bounded:
        def unexpected_publisher(*_args):
            publisher_calls.append("CALLED_AFTER_NESTED_PENDING")

        trace = loop.run_bounded(max_decisions=1,
                                 after_verified=unexpected_publisher)
        assert [r.status for r in trace] == [
            "FAKE_WATER_VERIFIED", "BLOCKED_UNRESOLVED"
        ]
        result = trace[0]
        assert trace[1].operation_id == result.pending_operation_id
        assert trace[1].claim_real_completion is False
        assert publisher_calls == []  # no next action or publisher while pending
    else:
        result = loop.step()
    assert confirmed and len(confirmed) == 1
    assert confirmed[0][0] == "FAKE_VERIFIED"
    assert result.status == "FAKE_WATER_VERIFIED"
    assert result.choice == "WATER"
    assert result.operation_id == confirmed[0][1]
    assert result.operation_id is not None
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN"
    assert nested_results[0].operation_id == "offline-attempt-1"
    assert result.pending_operation_id == nested_results[0].operation_id
    assert result.pending_operation_id == game.pending_attempt
    assert result.pending_operation_id == game.dispatched[0][0]
    assert result.pending_operation_id != result.operation_id
    assert host.events.count("FAKE_EFFECT") == 1
    assert host.events.count("FAKE_OBSERVED_AND_RESOLVED") == 1
    assert world.ledger.attempted_starts == 1
    assert host.pending is None
    assert len(game.dispatched) == 1
    assert interest.calls == 1 and nested_interest.calls == 1
    assert "MOVE_TO_CHAIR" not in loop.completed

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    next_interest = Interest("WATER")
    later = FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert later.operation_id == result.pending_operation_id
    assert next_interest.calls == 0


def test_exceptional_publisher_trace_requires_quarantine_even_with_pending_id():
    """R12 review: same statuses as success but exception MUST quarantine."""
    game, host, world, interest, loop = setup(choices=("WATER",))
    nested_results = []

    def publish_nested_then_raise(_verified, _game, _world, _host):
        game.revision = 2
        world.crop = replace(world.crop, revision=2, soil_dry=False)
        game.delivery = "lost_reply"
        nested_results.append(FakeMixedDaytimeLoop(
            game, host, world, Interest("MOVE_TO_CHAIR"), weather="sunny"
        ).step())
        raise RuntimeError("publisher exception after nesting")

    trace = loop.run_bounded(1, after_verified=publish_nested_then_raise)
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN"
    assert [r.status for r in trace] == [
        "FAKE_WATER_VERIFIED", "BLOCKED_UNRESOLVED"
    ]
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert trace[1].operation_id == nested_results[0].operation_id
    assert trace[1].operation_id == game.pending_attempt
    assert trace[1].operation_id == game.dispatched[0][0]
    assert host.events.count("FAKE_EFFECT") == 1



@pytest.mark.parametrize("bounded", [False, True])
def test_chair_finalization_retains_verified_chair_and_nested_pending_water(bounded):
    """R13 review: successful chair finalize can spawn pending Host WATER."""
    grant = replace(FakeStandingWaterGrant(), tiles=((7, 5),))
    game, host, world, interest, loop = setup(
        grant=grant, choices=("MOVE_TO_CHAIR",)
    )
    world.crop = replace(world.crop, tile=(7, 5))
    world.stewardship = replace(world.stewardship, tile=(7, 5))
    raw_finish = game.finish_observed_action
    finish_calls = []
    normal_callback_returned = []
    nested_results = []
    nested_interest = Interest("WATER")
    publisher_calls = []

    def finalize_then_nested_water(attempt):
        receipt = raw_finish(attempt)
        finish_calls.append((attempt, receipt))
        game.revision = 3  # real new fake scene after chair dispatch's rev2
        world.crop = replace(world.crop, revision=3)
        host.confirm_fake_observation = lambda _op: "UNKNOWN_PENDING"
        nested_results.append(FakeMixedDaytimeLoop(
            game, host, world, nested_interest, weather="sunny"
        ).step())
        normal_callback_returned.append(True)
        return receipt

    game.finish_observed_action = finalize_then_nested_water
    if bounded:
        def unexpected_publisher(*_args):
            publisher_calls.append(True)

        trace = loop.run_bounded(1, after_verified=unexpected_publisher)
        assert [r.status for r in trace] == [
            "VERIFIED_FAKE", "BLOCKED_UNRESOLVED"
        ]
        outer = trace[0]
        assert trace[1].operation_id == outer.pending_operation_id
        assert publisher_calls == []
    else:
        outer = loop.step()
    # All assertions outside finalization callback (L2 may catch failures).
    assert finish_calls == [("offline-attempt-1", True)]
    assert normal_callback_returned == [True]
    assert getattr(game, "_fake_mixed_quarantined", False) is False
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN_PENDING"
    assert nested_results[0].choice == "WATER"
    assert nested_results[0].operation_id is not None
    assert outer.status == "VERIFIED_FAKE"
    assert outer.choice == "MOVE_TO_CHAIR"
    assert outer.operation_id == finish_calls[0][0]
    assert outer.pending_operation_id == nested_results[0].operation_id
    assert outer.pending_operation_id == host.pending.operation_id
    assert outer.pending_operation_id != outer.operation_id
    assert "MOVE_TO_CHAIR" in loop.completed
    assert game.sunny_tile == game.chair_tile == (7, 4)
    assert game.pending_attempt is None
    assert game.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert host.events.count("FAKE_EFFECT") == 1
    assert host.events.count("FAKE_OBSERVED_AND_RESOLVED") == 0
    assert world.ledger.attempted_starts == 1
    assert interest.calls == 1 and nested_interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    next_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, next_interest, weather="sunny"
    ).step()
    assert fresh.status == "BLOCKED_UNRESOLVED"
    assert fresh.operation_id == outer.pending_operation_id
    assert next_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
def test_chair_finalization_exception_after_real_completion_quarantines(bounded):
    """R13 review: callback raises after original finalizer clears pending."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    raw_finish = game.finish_observed_action
    finalizations = []
    publishers = []

    def finalize_then_raise(attempt):
        done = raw_finish(attempt)
        finalizations.append((attempt, done))
        raise RuntimeError("synthetic chair finalization post-commit failure")

    game.finish_observed_action = finalize_then_raise
    if bounded:
        def unexpected_publisher(*_args):
            publishers.append(True)

        trace = loop.run_bounded(2, after_verified=unexpected_publisher)
        assert [r.status for r in trace] == [
            "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION"
        ]
        outer = trace[0]
        assert not publishers
    else:
        outer = loop.step()
    assert finalizations == [("offline-attempt-1", True)]
    # The raw fake finalizer DID run, but the adapter cannot independently
    # certify operation-bound finalization after a throwing callback. Safe
    # G0 behavior is UNKNOWN + quarantine, NEVER invented VERIFIED_FAKE.
    assert outer.status == "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION"
    assert outer.operation_id == finalizations[0][0]
    assert outer.pending_operation_id is None
    assert outer.post_verification_block_status is None
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert game.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert game.sunny_tile == (7, 4) and game.pending_attempt is None
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert host.events == [] and host.pending is None
    assert interest.calls == 1
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    fresh_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    ).step()
    assert fresh.status == "BLOCKED_UNRESOLVED"
    assert fresh_interest.calls == 0


@pytest.mark.parametrize("nested_chair", [False, True])
@pytest.mark.parametrize("bounded", [False, True])
def test_confirmed_water_then_callback_raises_keeps_operation_matched_receipt(
        nested_chair, bounded):
    """R13 review: Host confirmed WATER, then test callback raises.

    Bridge returns UNKNOWN_PENDING on the exception, but operation-matched
    Host evidence proves the fake receipt was already accepted/resolved.
    """
    game, host, world, interest, loop = setup(choices=("WATER",))
    raw_confirm = host.confirm_fake_observation
    confirmation = []
    nested_results = []
    nested_interest = Interest("MOVE_TO_CHAIR")
    publisher_calls = []
    observed_callback_exceptions = []

    def real_confirm_then_raise(operation):
        receipt = raw_confirm(operation)
        confirmation.append((receipt, operation.operation_id))
        if nested_chair:
            game.revision = 2
            world.crop = replace(world.crop, revision=2, soil_dry=False)
            game.delivery = "lost_reply"
            nested_results.append(FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            ).step())
        raise RuntimeError("callback raised AFTER fake Host confirmation")

    def observe_exception_from_confirm(operation):
        # A mutation that changes the intended raise into a normal return
        # MUST fail the regression even when the final trace is identical.
        try:
            return real_confirm_then_raise(operation)
        except RuntimeError as exc:
            observed_callback_exceptions.append(str(exc))
            raise

    host.confirm_fake_observation = observe_exception_from_confirm
    if bounded:
        def publisher(*_args):
            publisher_calls.append(True)
        trace = loop.run_bounded(1, after_verified=publisher)
        result = trace[0]
        if nested_chair:
            assert [r.status for r in trace] == [
                "FAKE_WATER_VERIFIED", "BLOCKED_UNRESOLVED"
            ]
            assert trace[1].operation_id == result.pending_operation_id
            assert publisher_calls == []
        else:
            assert [r.status for r in trace] == ["FAKE_WATER_VERIFIED"]
            assert publisher_calls == [True]
    else:
        result = loop.step()

    assert observed_callback_exceptions == [
        "callback raised AFTER fake Host confirmation"
    ]
    assert confirmation and len(confirmation) == 1
    assert confirmation[0][0] == "FAKE_VERIFIED"
    assert result.status == "FAKE_WATER_VERIFIED"
    assert result.operation_id == confirmation[0][1]
    assert result.choice == "WATER"
    assert result.claim_real_completion is False
    assert host.events.count("FAKE_EFFECT") == 1
    assert host.events.count("FAKE_OBSERVED_AND_RESOLVED") == 1
    assert host.last_effect_evidence.operation_id == result.operation_id
    assert result.operation_id in host.used_ids
    assert host.pending is None
    assert world.ledger.attempted_starts == 1
    assert interest.calls == 1
    assert not getattr(game, "_fake_mixed_quarantined", False)
    if nested_chair:
        assert len(nested_results) == 1
        assert nested_results[0].status == "UNKNOWN"
        assert nested_results[0].operation_id == "offline-attempt-1"
        assert result.pending_operation_id == nested_results[0].operation_id
        assert result.pending_operation_id == game.pending_attempt
        assert result.pending_operation_id == game.dispatched[0][0]
        assert len(game.dispatched) == 1
        assert nested_interest.calls == 1
    else:
        assert nested_results == []
        assert result.pending_operation_id is None
        assert game.pending_attempt is None and game.dispatched == []

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    if nested_chair:
        assert fresh.status == "BLOCKED_UNRESOLVED"
        assert fresh.operation_id == result.pending_operation_id
        assert later_interest.calls == 0
    else:
        assert fresh.status == "STAY"
        assert later_interest.calls == 1



@pytest.mark.parametrize("bounded", [False, True])
def test_forged_water_verified_callback_cannot_confirm_host_pending(bounded):
    """R14 review: callback string is not an operation-matched Host receipt."""
    game, host, world, interest, loop = setup(choices=("WATER",))
    callback_calls = []

    def lie_about_host_confirmation(op):
        callback_calls.append(op.operation_id)
        # Deliberately do NOT call the genuine fake Host finalizer.
        return "FAKE_VERIFIED"

    host.confirm_fake_observation = lie_about_host_confirmation
    if bounded:
        trace = loop.run_bounded(1)
        assert len(trace) == 1
        result = trace[0]
    else:
        result = loop.step()
    assert len(callback_calls) == 1
    assert result.status == "UNKNOWN_PENDING"
    assert result.choice == "WATER"
    assert result.operation_id == callback_calls[0]
    assert host.pending is not None
    assert result.operation_id == host.pending.operation_id
    assert result.pending_operation_id is None
    assert result.claim_real_completion is False
    assert host.events.count("FAKE_EFFECT") == 1
    assert host.events.count("FAKE_OBSERVED_AND_RESOLVED") == 0
    assert world.ledger.attempted_starts == 1
    assert not getattr(game, "_fake_mixed_quarantined", False)
    assert interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    fresh_interest = Interest("STAY")
    fresh_result = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    ).step()
    assert fresh_result.status == "BLOCKED_UNRESOLVED"
    assert fresh_result.operation_id == result.operation_id
    assert fresh_interest.calls == 0


@pytest.mark.parametrize("finalizer_mode", [
    "clear_without_finalizer", "finalize_then_rotate_load"
])
@pytest.mark.parametrize("bounded", [False, True])
def test_exceptional_chair_finalizer_without_independent_receipt_never_verifies(
        finalizer_mode, bounded):
    """R14 review: cleared pending/tile is not operation-bound finalization."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_finish = game.finish_observed_action
    callback_records = []
    publisher_called = []

    def finish_then_raise(attempt):
        if finalizer_mode == "clear_without_finalizer":
            # Bypass original finalizer and erase the only pending record.
            game.pending_attempt = None
            callback_records.append((attempt, "manually-cleared"))
        else:
            done = original_finish(attempt)
            callback_records.append((attempt, done))
            host.rotate_epoch()
            game.epoch = "fake-load-2"
            game.owner = "different-fake-owner"
        raise RuntimeError("injected finalizer exception")

    game.finish_observed_action = finish_then_raise
    if bounded:
        def unexpected_publisher(*_args):
            publisher_called.append(True)

        trace = loop.run_bounded(2, after_verified=unexpected_publisher)
        assert [r.status for r in trace] == [
            "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION"
        ]
        result = trace[0]
        assert publisher_called == []
    else:
        result = loop.step()
    assert callback_records == [(
        "offline-attempt-1",
        "manually-cleared" if finalizer_mode == "clear_without_finalizer" else True
    )]
    assert result.status == "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION"
    assert result.operation_id == "offline-attempt-1"
    assert result.pending_operation_id is None
    assert result.claim_real_completion is False
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.pending_attempt is None
    assert game.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert game.sunny_tile == game.chair_tile
    assert interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    fresh_interest = Interest("STAY")
    later = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert fresh_interest.calls == 0


@pytest.mark.parametrize("finalizer_exit", ["return", "raise"])
def test_chair_finalizer_latches_p1_revocation_on_both_exits(finalizer_exit):
    """Higher inactive fake grant must survive restoring old fixture v1."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    initial = world.ledger.grant
    original_finish = game.finish_observed_action
    callback_outcomes = []

    def finalize_with_revocation(attempt):
        done = original_finish(attempt)
        callback_outcomes.append((attempt, done))
        world.ledger.grant = replace(
            initial, active=False, grant_revision=2
        )
        if finalizer_exit == "raise":
            raise RuntimeError("finalizer delivered revocation then raised")
        return done

    game.finish_observed_action = finalize_with_revocation
    result = loop.step()
    assert callback_outcomes == [("offline-attempt-1", True)]
    assert result.status == (
        "VERIFIED_FAKE" if finalizer_exit == "return"
        else "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION"
    )
    assert getattr(game, "_fake_mixed_quarantined", False) is (
        finalizer_exit == "raise"
    )
    assert ("MOVE_TO_CHAIR" in loop.completed) is (
        finalizer_exit == "return"
    )
    assert result.operation_id == "offline-attempt-1"
    assert host._fake_water_permission_store.accounts[initial.grant_id].revoked
    assert host._fake_water_permission_store.accounts[
        initial.grant_id
    ].grant.grant_revision == 2
    # The inactive notification is gone from the fixture, but Host's
    # revocation tombstone cannot be undone by the old active revision.
    world.ledger.grant = initial
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        initial
    ) == "DENIED_STALE_GRANT_REVISION"
    assert host.events.count("FAKE_EFFECT") == 0


@pytest.mark.parametrize("untrusted_exit", ["return", "raise"])
def test_chair_rejection_cleanup_latches_p1_revocation(untrusted_exit):
    """R20: P1 grant is a separate fixture; untrusted cleanup is never run.

    Previously this G0 test delivered the revocation *from* an injected
    Game.finish_rejected callback. That is no longer allowed to run with a
    reserved chair operation: it can dispatch using a saved callable.
    Deliver the higher inactive revision via the independent ledger instead.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = world.ledger.grant
    # A revocation is a Host-side event, independent of a Game cleanup.
    world.ledger.grant = replace(
        original, active=False, grant_revision=2
    )
    intercepted = []

    def rejected_without_effect(_action, _expected, _attempt):
        return "rejected_before_effect"

    def untrusted_reject(attempt):
        intercepted.append(attempt)
        if untrusted_exit == "raise":
            raise RuntimeError("unauthorized injected cleanup attempted")
        return True

    game.dispatch = rejected_without_effect
    game.finish_rejected = untrusted_reject
    result = loop.step()
    assert intercepted == []  # adapter invokes pinned baseline ONLY
    assert result.status == "UNKNOWN"
    assert result.operation_id == "offline-attempt-1"
    assert result.claim_real_completion is False
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.pending_attempt == "offline-attempt-1"
    assert game.dispatched == []
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert host.events == [] and host.pending is None
    account = host._fake_water_permission_store.accounts[original.grant_id]
    assert account.revoked is True
    assert account.grant.grant_revision == 2
    world.ledger.grant = original
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        original
    ) == "DENIED_STALE_GRANT_REVISION"


def test_outer_water_wrapper_never_retires_valid_nested_second_tile():
    """R14 review: each installed Host.reserve wrapper owns ONLY its op ID."""
    grant = replace(
        FakeStandingWaterGrant(),
        tiles=((4, 5), (5, 4)),
        max_distinct_tiles=2,
        max_attempted_starts=2,
    )
    game, host, world, interest, loop = setup(
        grant=grant, choices=("WATER",)
    )
    original_confirm = host.confirm_fake_observation
    nested_results = []
    nested_interest = Interest("WATER")
    outer_confirm = []
    host_pending_after_nested = []

    def confirm_first_then_nested_second_crop(op):
        first_receipt = original_confirm(op)
        outer_confirm.append((first_receipt, op.operation_id))
        game.revision = 2
        world.crop = replace(
            world.crop, revision=2, tile=(5, 4),
            crop_id="second-fake-crop"
        )
        world.stewardship = replace(
            world.stewardship, tile=(5, 4),
            crop_id="second-fake-crop"
        )
        # The outer mixed coordinator's pinned reserve wrapper remains on
        # host.reserve here. This nested revision-2 WATER must be handled by
        # its OWN wrapper, never retired by revision-1 outer evidence.
        host.confirm_fake_observation = original_confirm
        try:
            nested_results.append(FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            ).step())
        finally:
            host.confirm_fake_observation = confirm_first_then_nested_second_crop
        host_pending_after_nested.append(host.pending)
        return first_receipt

    host.confirm_fake_observation = confirm_first_then_nested_second_crop
    outer = loop.step()
    assert outer_confirm and outer_confirm[0][0] == "FAKE_VERIFIED"
    assert len(nested_results) == 1
    assert nested_results[0].status == "FAKE_WATER_VERIFIED"
    assert nested_results[0].operation_id is not None
    assert nested_results[0].operation_id != outer_confirm[0][1]
    assert host_pending_after_nested == [None]
    assert host.pending is None
    assert host.events.count("FAKE_EFFECT") == 2
    assert host.events.count("FAKE_OBSERVED_AND_RESOLVED") == 2
    assert host.events.count("FAKE_STALE_PRE_A_RESERVATION_RETIRED") == 0
    assert host._fake_daytime_water_last_revision == 2
    assert world.ledger.attempted_starts == 2
    assert host._fake_water_permission_store.accounts[
        grant.grant_id
    ].attempted_starts == 2
    assert len(host.used_ids) == 2
    assert outer.operation_id == outer_confirm[0][1]
    # The toy Host exposes only the LATEST operation's last_effect_evidence.
    # Without the original operation's retained receipt, R15 cannot safely
    # claim the outer one is verified merely from a callback string. Its
    # conservative quarantine does not invalidate nested WATER success.
    assert outer.status == "UNKNOWN_UNVERIFIED_WATER_RECEIPT"
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert interest.calls == 1 and nested_interest.calls == 1



@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("malformed_receipt", ["fake-success", 1, object()])
def test_chair_truthy_non_true_finalizer_never_verifies_or_publishes(
        bounded, malformed_receipt, monkeypatch):
    """R15 finding 1: L2 MUST return UNKNOWN, not just mixed override."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    finalizer_calls = []
    publisher_calls = []
    l2_verdicts = []
    raw_l2_step = OfflineController.step

    def capture_l2_verdict(controller):
        decision = raw_l2_step(controller)
        l2_verdicts.append(decision.verdict)
        return decision

    monkeypatch.setattr(OfflineController, "step", capture_l2_verdict)

    def fake_finalizer(attempt):
        finalizer_calls.append(attempt)
        # Deliberately release WITHOUT the real FakeGame finalizer.
        game.pending_attempt = None
        return malformed_receipt

    game.finish_observed_action = fake_finalizer
    if bounded:
        def publisher(*_args):
            publisher_calls.append(True)

        trace = loop.run_bounded(max_decisions=2, after_verified=publisher)
        assert [r.status for r in trace] == [
            "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION"
        ]
        result = trace[0]
        assert publisher_calls == []
    else:
        result = loop.step()
    assert finalizer_calls == ["offline-attempt-1"]
    assert l2_verdicts == ["UNKNOWN"]
    assert result.status == "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION"
    assert result.choice == "MOVE_TO_CHAIR"
    assert result.operation_id == "offline-attempt-1"
    assert result.pending_operation_id is None
    assert result.claim_real_completion is False
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.pending_attempt is None
    assert game.dispatched == [
        ("offline-attempt-1", "MOVE_TO_CHAIR", "p2")
    ]
    assert game.sunny_tile == game.chair_tile
    assert interest.calls == 1
    assert host.events == [] and host.pending is None

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    new_interest = Interest("STAY")
    later = FakeMixedDaytimeLoop(
        game, host, world, new_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert new_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
def test_chair_dispatch_exception_cleared_attempt_still_quarantines(
        bounded, monkeypatch):
    """R15 finding 2: require real exception AND L2 UNKNOWN branch."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    raw_dispatch = game.dispatch
    dispatch_receipts = []
    dispatch_exceptions = []
    l2_verdicts = []
    publisher_calls = []
    raw_l2_step = OfflineController.step

    def capture_l2_verdict(controller):
        decision = raw_l2_step(controller)
        l2_verdicts.append(decision.verdict)
        return decision

    monkeypatch.setattr(OfflineController, "step", capture_l2_verdict)

    def dispatch_then_lose_attempt_and_raise(action, expected, attempt):
        receipt = raw_dispatch(action, expected, attempt)
        dispatch_receipts.append((attempt, receipt))
        # The effect and dispatch row are real in the toy, but a callback
        # unlawfully erases the only attempt reservation before failing.
        game.pending_attempt = None
        raise RuntimeError("dispatch raised after fake chair movement")

    def observe_dispatch_exception(action, expected, attempt):
        try:
            return dispatch_then_lose_attempt_and_raise(
                action, expected, attempt
            )
        except RuntimeError as exc:
            dispatch_exceptions.append(str(exc))
            raise

    game.dispatch = observe_dispatch_exception
    if bounded:
        def unexpected_publisher(*_args):
            publisher_calls.append(True)

        trace = loop.run_bounded(max_decisions=2,
                                 after_verified=unexpected_publisher)
        assert [r.status for r in trace] == ["UNKNOWN"]
        result = trace[0]
        assert publisher_calls == []
    else:
        result = loop.step()
    assert dispatch_receipts == [("offline-attempt-1", "ack")]
    assert dispatch_exceptions == [
        "dispatch raised after fake chair movement"
    ]
    assert l2_verdicts == ["UNKNOWN"]
    assert result.status == "UNKNOWN"
    assert result.choice == "MOVE_TO_CHAIR"
    assert result.operation_id == "offline-attempt-1"
    assert result.pending_operation_id is None
    assert result.claim_real_completion is False
    assert not loop.completed
    assert game.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert game.sunny_tile == game.chair_tile
    assert game.pending_attempt is None
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert host.pending is None and host.events == []
    assert interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    new_interest = Interest("STAY")
    later = FakeMixedDaytimeLoop(
        game, host, world, new_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert new_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
def test_chair_exception_finalizer_also_reports_nested_pending_water(bounded):
    """R15 finding 3: keep both unverified chair ID and foreign Host WATER ID."""
    grant = replace(FakeStandingWaterGrant(), tiles=((7, 5),))
    game, host, world, interest, loop = setup(
        grant=grant, choices=("MOVE_TO_CHAIR",)
    )
    world.crop = replace(world.crop, tile=(7, 5))
    world.stewardship = replace(world.stewardship, tile=(7, 5))
    raw_finish = game.finish_observed_action
    raw_confirm = host.confirm_fake_observation
    finalized = []
    nested_results = []
    nested_interest = Interest("WATER")
    publisher_calls = []
    exception_observed = []

    def pending_confirmation(_operation):
        return "UNKNOWN_PENDING"

    def finalize_nested_water_then_raise(attempt):
        finalized.append((attempt, raw_finish(attempt)))
        game.revision = 3
        world.crop = replace(world.crop, revision=3)
        host.confirm_fake_observation = pending_confirmation
        nested_results.append(
            FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            ).step()
        )
        raise RuntimeError("chair finalizer raised after nested WATER")

    def observe_finalizer_exception(attempt):
        try:
            return finalize_nested_water_then_raise(attempt)
        except RuntimeError as exc:
            exception_observed.append(str(exc))
            raise

    game.finish_observed_action = observe_finalizer_exception
    if bounded:
        def unwanted_publisher(*_args):
            publisher_calls.append(True)

        trace = loop.run_bounded(1, after_verified=unwanted_publisher)
        assert [r.status for r in trace] == [
            "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION",
            "BLOCKED_UNRESOLVED",
        ]
        result = trace[0]
        assert trace[1].operation_id == result.pending_operation_id
        assert trace[1].claim_real_completion is False
        assert publisher_calls == []
    else:
        result = loop.step()
    assert finalized == [("offline-attempt-1", True)]
    assert exception_observed == [
        "chair finalizer raised after nested WATER"
    ]
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN_PENDING"
    assert nested_results[0].choice == "WATER"
    assert result.status == "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION"
    assert result.choice == "MOVE_TO_CHAIR"
    assert result.operation_id == "offline-attempt-1"
    assert result.pending_operation_id == nested_results[0].operation_id
    assert host.pending is not None
    assert result.pending_operation_id == host.pending.operation_id
    assert result.pending_operation_id != result.operation_id
    assert not loop.completed
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.pending_attempt is None
    assert game.sunny_tile == game.chair_tile
    assert game.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert host.events.count("FAKE_EFFECT") == 1
    assert host.events.count("FAKE_OBSERVED_AND_RESOLVED") == 0
    assert world.ledger.attempted_starts == 1
    assert interest.calls == 1 and nested_interest.calls == 1
    assert host.confirm_fake_observation is pending_confirmation

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    fresh_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    ).step()
    assert fresh.status == "BLOCKED_UNRESOLVED"
    assert fresh.operation_id == result.pending_operation_id
    assert fresh_interest.calls == 0



@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("clear_attempt", [False, True])
def test_chair_dispatch_denial_after_real_move_is_unknown_not_pre_effect(
        bounded, clear_attempt, monkeypatch):
    """R16 review: a post-effect rejection token must NEVER retire the attempt."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    raw_dispatch = game.dispatch
    dispatch_receipts = []
    l2_verdicts = []
    publisher_calls = []
    raw_l2_step = OfflineController.step

    def capture_l2_verdict(controller):
        outcome = raw_l2_step(controller)
        l2_verdicts.append(outcome.verdict)
        return outcome

    monkeypatch.setattr(OfflineController, "step", capture_l2_verdict)

    def effect_then_lie_rejected(action, expected, attempt):
        receipt = raw_dispatch(action, expected, attempt)
        dispatch_receipts.append((attempt, receipt))
        if clear_attempt:
            game.pending_attempt = None
        return "rejected_before_effect"

    game.dispatch = effect_then_lie_rejected
    if bounded:
        def unexpected_publisher(*_args):
            publisher_calls.append(True)

        trace = loop.run_bounded(2, after_verified=unexpected_publisher)
        assert [r.status for r in trace] == ["UNKNOWN"]
        result = trace[0]
        assert publisher_calls == []
    else:
        result = loop.step()
    assert dispatch_receipts == [("offline-attempt-1", "ack")]
    assert l2_verdicts == ["UNKNOWN"]
    assert result.status == "UNKNOWN"
    assert result.choice == "MOVE_TO_CHAIR"
    assert result.operation_id == "offline-attempt-1"
    assert result.claim_real_completion is False
    assert result.pending_operation_id is None
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert game.sunny_tile == game.chair_tile
    assert game.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert game.pending_attempt == (
        None if clear_attempt else "offline-attempt-1"
    )
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert host.pending is None and host.events == []
    assert interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    assert fresh.status == "BLOCKED_UNRESOLVED"
    assert fresh.operation_id == (
        "offline-attempt-1" if not clear_attempt else None
    )
    assert later_interest.calls == 0


@pytest.mark.parametrize("token_kind", ["ack_subclass", "rejection_subclass"])
@pytest.mark.parametrize("bounded", [False, True])
def test_chair_dispatch_str_subclass_is_not_a_trusted_literal(
        token_kind, bounded, monkeypatch):
    """R16 review: str subclasses mimicking ACK/rejection must not pass L2."""
    class FakeStr(str):
        pass

    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    raw_dispatch = game.dispatch
    raw_l2_step = OfflineController.step
    l2_verdicts = []
    publisher_calls = []
    raw_receipts = []

    def capture_l2_verdict(controller):
        outcome = raw_l2_step(controller)
        l2_verdicts.append(outcome.verdict)
        return outcome

    monkeypatch.setattr(OfflineController, "step", capture_l2_verdict)

    def dispatch_return_subclass(action, expected, attempt):
        if token_kind == "ack_subclass":
            raw_receipts.append(raw_dispatch(action, expected, attempt))
            return FakeStr("ack")
        return FakeStr("rejected_before_effect")

    game.dispatch = dispatch_return_subclass
    if bounded:
        def publisher(*_args):
            publisher_calls.append(True)

        trace = loop.run_bounded(1, after_verified=publisher)
        assert [r.status for r in trace] == ["UNKNOWN"]
        result = trace[0]
        assert publisher_calls == []
    else:
        result = loop.step()
    assert l2_verdicts == ["UNKNOWN"]
    assert result.status == "UNKNOWN"
    assert result.operation_id == "offline-attempt-1"
    assert result.claim_real_completion is False
    assert not loop.completed
    assert game.pending_attempt == result.operation_id
    assert len(game.dispatched) == (1 if token_kind == "ack_subclass" else 0)
    if token_kind == "ack_subclass":
        assert raw_receipts == ["ack"]
        assert game.sunny_tile == game.chair_tile
    else:
        assert raw_receipts == []
        assert game.sunny_tile != game.chair_tile
    assert host.pending is None and host.events == []

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    future_interest = Interest("STAY")
    future = FakeMixedDaytimeLoop(
        game, host, world, future_interest, weather="sunny"
    ).step()
    assert future.status == "BLOCKED_UNRESOLVED"
    assert future.operation_id == result.operation_id
    assert future_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
def test_dispatch_exception_with_nested_water_preserves_both_operation_ids(
        bounded, monkeypatch):
    """R16 review: UNKNOWN chair and pending WATER are separate evidence."""
    grant = replace(FakeStandingWaterGrant(), tiles=((7, 5),))
    game, host, world, interest, loop = setup(
        grant=grant, choices=("MOVE_TO_CHAIR",)
    )
    world.crop = replace(world.crop, tile=(7, 5))
    world.stewardship = replace(world.stewardship, tile=(7, 5))
    raw_dispatch = game.dispatch
    raw_l2_step = OfflineController.step
    dispatch_receipts = []
    dispatch_exceptions = []
    l2_verdicts = []
    nested_results = []
    publisher_calls = []
    nested_interest = Interest("WATER")

    def capture_l2_verdict(controller):
        outcome = raw_l2_step(controller)
        l2_verdicts.append(outcome.verdict)
        return outcome

    monkeypatch.setattr(OfflineController, "step", capture_l2_verdict)

    def move_clear_pending_then_water_then_raise(action, expected, attempt):
        receipt = raw_dispatch(action, expected, attempt)
        dispatch_receipts.append((attempt, receipt))
        game.pending_attempt = None
        game.revision = 3
        world.crop = replace(world.crop, revision=3)
        host.confirm_fake_observation = lambda _op: "UNKNOWN_PENDING"
        nested_results.append(
            FakeMixedDaytimeLoop(
                game, host, world, nested_interest, weather="sunny"
            ).step()
        )
        raise RuntimeError("dispatch failed after nested pending WATER")

    def observe_dispatch_exception(action, expected, attempt):
        try:
            return move_clear_pending_then_water_then_raise(
                action, expected, attempt
            )
        except RuntimeError as exc:
            dispatch_exceptions.append(str(exc))
            raise

    game.dispatch = observe_dispatch_exception
    if bounded:
        def publisher(*_args):
            publisher_calls.append(True)

        trace = loop.run_bounded(1, after_verified=publisher)
        assert [r.status for r in trace] == [
            "UNKNOWN", "BLOCKED_UNRESOLVED"
        ]
        outcome = trace[0]
        assert trace[1].operation_id == outcome.pending_operation_id
        assert publisher_calls == []
    else:
        outcome = loop.step()
    assert dispatch_receipts == [("offline-attempt-1", "ack")]
    assert dispatch_exceptions == [
        "dispatch failed after nested pending WATER"
    ]
    assert l2_verdicts == ["UNKNOWN"]
    assert len(nested_results) == 1
    assert nested_results[0].status == "UNKNOWN_PENDING"
    assert nested_results[0].operation_id is not None
    assert outcome.status == "UNKNOWN"
    assert outcome.choice == "MOVE_TO_CHAIR"
    assert outcome.operation_id == "offline-attempt-1"
    assert outcome.pending_operation_id == nested_results[0].operation_id
    assert outcome.pending_operation_id == host.pending.operation_id
    assert outcome.pending_operation_id != outcome.operation_id
    assert outcome.claim_real_completion is False
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.pending_attempt is None
    assert game.dispatched == [
        ("offline-attempt-1", "MOVE_TO_CHAIR", "p2")
    ]
    assert game.sunny_tile == game.chair_tile
    assert not loop.completed
    assert host.events.count("FAKE_EFFECT") == 1
    assert host.events.count("FAKE_OBSERVED_AND_RESOLVED") == 0
    assert world.ledger.attempted_starts == 1
    assert interest.calls == 1 and nested_interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    future_interest = Interest("STAY")
    later = FakeMixedDaytimeLoop(
        game, host, world, future_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert later.operation_id == outcome.pending_operation_id
    assert future_interest.calls == 0


def test_host_stop_after_fake_chair_finalization_skips_publisher():
    """R16 adjacent STOP probe: preserve receipt but do not publish post-STOP."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_finish = game.finish_observed_action
    finished = []
    publishers = []

    def finalize_then_stop(attempt):
        result = original_finish(attempt)
        finished.append((attempt, result))
        host.latch_stop()
        return result

    def publisher(*_args):
        publishers.append(True)

    game.finish_observed_action = finalize_then_stop
    results = loop.run_bounded(1, after_verified=publisher)
    assert finished == [("offline-attempt-1", True)]
    assert [r.status for r in results] == [
        "VERIFIED_FAKE", "BLOCKED_STOP"
    ]
    assert results[0].operation_id == "offline-attempt-1"
    assert publishers == []
    assert "MOVE_TO_CHAIR" in loop.completed
    assert host.stopped is True
    assert host.events.count("STOP_LATCHED") == 1
    assert game.pending_attempt is None
    assert game.sunny_tile == game.chair_tile
    assert len(game.dispatched) == 1
    assert interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("STAY")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    assert fresh.status == "BLOCKED_STOP"
    assert later_interest.calls == 0



@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("saved_kind", ["bound", "unbound"])
@pytest.mark.parametrize("delivery", ["ack", "ack_no_effect"])
def test_chair_rejection_cleanup_saved_dispatch_callback_never_runs(
        bounded, saved_kind, delivery, monkeypatch):
    """R19 finding: saved FakeGame.dispatch bypasses monkeypatch witnesses.

    The safe boundary is to NEVER invoke game.finish_rejected while an
    attempt is reserved; the pinned base FakeGame method alone releases it.
    Both saved-bound and saved-unbound callables would execute a real move
    and erase its row if the malicious cleanup were ever called.
    """
    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",), delivery=delivery
    )
    saved = game.dispatch if saved_kind == "bound" else FakeGame.dispatch
    raw_reject = game.finish_rejected
    malicious_calls = []
    l2_verdicts = []
    published = []
    original_step = OfflineController.step

    def capture_l2(controller):
        result = original_step(controller)
        l2_verdicts.append(result.verdict)
        return result

    monkeypatch.setattr(OfflineController, "step", capture_l2)

    def genuine_pre_effect_denial(action, expected, attempt):
        assert game.pending_attempt == attempt
        assert game.dispatched == []
        return "rejected_before_effect"

    def malicious_cleanup(attempt):
        malicious_calls.append(attempt)
        snapshot = FakeGame.observe(game)
        if saved_kind == "bound":
            result = saved("MOVE_TO_CHAIR", snapshot, attempt)
        else:
            result = saved(game, "MOVE_TO_CHAIR", snapshot, attempt)
        assert result == "ack"
        assert game.dispatched.pop() == (
            attempt, "MOVE_TO_CHAIR", "p2"
        )
        return raw_reject(attempt)

    game.dispatch = genuine_pre_effect_denial
    game.finish_rejected = malicious_cleanup
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: published.append(True)
        )
        assert [result.status for result in trace] == [
            "UNKNOWN"
        ]
        outcome = trace[0]
    else:
        outcome = loop.step()
    assert l2_verdicts == ["UNKNOWN"]
    assert malicious_calls == []
    assert published == []
    assert outcome.status == "UNKNOWN"
    assert outcome.operation_id == "offline-attempt-1"
    assert outcome.claim_real_completion is False
    assert not loop.completed
    assert game.dispatched == []
    assert game.sunny_tile == (4, 4)
    assert game.revision == 1
    assert game.pending_attempt == "offline-attempt-1"
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert host.events == [] and host.pending is None
    assert interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    fresh_interest = Interest("STAY")
    subsequent = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    ).step()
    assert subsequent.status == "BLOCKED_UNRESOLVED"
    assert fresh_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
def test_chair_cleanup_saved_dispatch_cannot_mutate_log_or_hide_revocation(
        bounded, monkeypatch):
    """R20: untrusted callback cannot dispatch, malformed-log, or revoke.

    Revocation remains independently accepted when supplied in the
    permission fixture before the cleanup executes; no unsafe Game cleanup
    callback must run just to publish such permission changes.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = world.ledger.grant
    saved_dispatch = FakeGame.dispatch
    unsafe_called = []
    published = []
    real_l2 = OfflineController.step
    l2_verdicts = []
    world.ledger.grant = replace(
        original, active=False, grant_revision=2
    )

    def capture_l2(controller):
        result = real_l2(controller)
        l2_verdicts.append(result.verdict)
        return result

    monkeypatch.setattr(OfflineController, "step", capture_l2)
    game.dispatch = lambda *_args: "rejected_before_effect"

    def bad_cleanup(attempt):
        unsafe_called.append(attempt)
        snapshot = FakeGame.observe(game)
        saved_dispatch(game, "MOVE_TO_CHAIR", snapshot, attempt)
        game.dispatched = None
        game.pending_attempt = None
        raise RuntimeError("malformed fake log after dispatch")

    game.finish_rejected = bad_cleanup
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: published.append(True)
        )
        assert [x.status for x in trace] == [
            "UNKNOWN"
        ]
        result = trace[0]
    else:
        result = loop.step()

    assert l2_verdicts == ["UNKNOWN"]
    assert unsafe_called == [] and published == []
    assert result.status == "UNKNOWN"
    assert result.operation_id == "offline-attempt-1"
    assert result.claim_real_completion is False
    assert game.dispatched == []
    assert game.pending_attempt == "offline-attempt-1"
    assert game.sunny_tile == (4, 4)
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    account = host._fake_water_permission_store.accounts[original.grant_id]
    assert account.revoked is True
    assert account.grant.grant_revision == 2
    world.ledger.grant = original
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        original
    ) == "DENIED_STALE_GRANT_REVISION"


@pytest.mark.parametrize("bad_return", [None, True, "fake-success"])
@pytest.mark.parametrize("bounded", [False, True])
def test_untrusted_cleanup_receipt_cannot_override_adapter_owned_release(
        bad_return, bounded, monkeypatch):
    """An injected cleanup's return value is not allowed as L2 evidence."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    calls = []
    original_l2 = OfflineController.step
    verdicts = []

    def watch_l2(controller):
        result = original_l2(controller)
        verdicts.append(result.verdict)
        return result

    monkeypatch.setattr(OfflineController, "step", watch_l2)
    game.dispatch = lambda *_args: "rejected_before_effect"

    def bad_reject(attempt):
        calls.append(attempt)
        return bad_return

    game.finish_rejected = bad_reject
    if bounded:
        result = loop.run_bounded(1)[0]
    else:
        result = loop.step()
    assert calls == []
    assert verdicts == ["UNKNOWN"]
    assert result.status == "UNKNOWN"
    assert result.operation_id == "offline-attempt-1"
    assert result.claim_real_completion is False
    assert game.pending_attempt == "offline-attempt-1"
    assert game.dispatched == []
    assert not loop.completed
    assert getattr(game, "_fake_mixed_quarantined", False) is True


def test_clean_rejection_without_injected_cleanup_is_replay_safe():
    """Valid fake rejection remains optional; foreign callbacks are ignored."""
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    game.dispatch = lambda *_args: "rejected_before_effect"
    game.finish_rejected = lambda *_args: (_ for _ in ()).throw(
        AssertionError("must never execute untrusted cleanup")
    )
    outcome = loop.step()
    assert outcome.status == "UNKNOWN"
    assert outcome.operation_id == "offline-attempt-1"
    assert game.pending_attempt == "offline-attempt-1"
    assert game.dispatched == []
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    new_interest = Interest("STAY")
    again = FakeMixedDaytimeLoop(
        game, host, world, new_interest, weather="sunny"
    ).step()
    assert again.status == "BLOCKED_UNRESOLVED"
    assert new_interest.calls == 0




@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("saved_kind", ["bound", "unbound"])
def test_injected_chair_dispatch_saved_callable_erases_ack_no_effect_row(
        bounded, saved_kind, monkeypatch):
    """R20 review finding 1: dispatch callback may erase its own real row.

    A saved bound/unbound original FakeGame.dispatch is invoked under the
    original reservation, in ack_no_effect mode. The callback deletes its
    row and lies about a pre-effect denial. This CANNOT prove a clean
    rejection; L2 must see UNKNOWN and adapter must not release the ID.
    """
    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",), delivery="ack_no_effect"
    )
    saved = game.dispatch if saved_kind == "bound" else FakeGame.dispatch
    dispatch_calls = []
    l2_verdicts = []
    publisher_calls = []
    raw_l2 = OfflineController.step

    def capture_l2(controller):
        result = raw_l2(controller)
        l2_verdicts.append(result.verdict)
        return result

    monkeypatch.setattr(OfflineController, "step", capture_l2)

    def dispatch_conceal_effect(action, expected, attempt):
        assert game.pending_attempt == attempt
        if saved_kind == "bound":
            receipt = saved(action, expected, attempt)
        else:
            receipt = saved(game, action, expected, attempt)
        assert receipt == "ack"
        removed = game.dispatched.pop()
        assert removed == (attempt, "MOVE_TO_CHAIR", "p2")
        dispatch_calls.append((attempt, receipt, removed))
        return "rejected_before_effect"

    game.dispatch = dispatch_conceal_effect
    if bounded:
        trace = loop.run_bounded(
            max_decisions=2,
            after_verified=lambda *_args: publisher_calls.append(True)
        )
        assert [r.status for r in trace] == ["UNKNOWN"]
        result = trace[0]
        assert publisher_calls == []
    else:
        result = loop.step()

    assert dispatch_calls == [
        ("offline-attempt-1", "ack",
         ("offline-attempt-1", "MOVE_TO_CHAIR", "p2"))
    ]
    assert l2_verdicts == ["UNKNOWN"]
    assert result.status == "UNKNOWN"
    assert result.choice == "MOVE_TO_CHAIR"
    assert result.operation_id == "offline-attempt-1"
    assert result.pending_operation_id is None
    assert result.claim_real_completion is False
    assert game.pending_attempt == "offline-attempt-1"
    assert game.dispatched == []
    assert game.sunny_tile == (4, 4)
    assert game.revision == 1
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert host.pending is None and host.events == []
    assert interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("STAY")
    later = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert later.operation_id == "offline-attempt-1"
    assert later_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("saved_kind", ["bound", "unbound"])
def test_injected_chair_dispatch_malformed_log_and_cleared_attempt_keeps_id(
        bounded, saved_kind, monkeypatch):
    """R20 review finding 2: malformed Game rows cannot escape L2 UNKNOWN."""
    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",), delivery="ack_no_effect"
    )
    saved = game.dispatch if saved_kind == "bound" else FakeGame.dispatch
    old_grant = world.ledger.grant
    raw_l2 = OfflineController.step
    l2_verdicts = []
    callback_events = []
    publisher_calls = []

    def capture_l2(controller):
        outcome = raw_l2(controller)
        l2_verdicts.append(outcome.verdict)
        return outcome

    monkeypatch.setattr(OfflineController, "step", capture_l2)

    def malicious_dispatch(action, expected, attempt):
        if saved_kind == "bound":
            receipt = saved(action, expected, attempt)
        else:
            receipt = saved(game, action, expected, attempt)
        assert receipt == "ack"
        removed = game.dispatched.pop()
        assert removed == (attempt, "MOVE_TO_CHAIR", "p2")
        game.pending_attempt = None
        world.ledger.grant = replace(
            old_grant, grant_revision=2, active=False
        )
        game.dispatched = None
        callback_events.append((attempt, receipt))
        return "rejected_before_effect"

    game.dispatch = malicious_dispatch
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: publisher_calls.append(True)
        )
        assert [r.status for r in trace] == ["UNKNOWN"]
        outcome = trace[0]
        assert publisher_calls == []
    else:
        outcome = loop.step()
    assert callback_events == [("offline-attempt-1", "ack")]
    assert l2_verdicts == ["UNKNOWN"]
    assert outcome.status == "UNKNOWN"
    assert outcome.choice == "MOVE_TO_CHAIR"
    assert outcome.operation_id == "offline-attempt-1"
    assert outcome.pending_operation_id is None
    assert outcome.claim_real_completion is False
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.pending_attempt is None
    assert game.dispatched is None
    assert game.sunny_tile == (4, 4) and game.revision == 1
    assert "MOVE_TO_CHAIR" not in loop.completed
    account = host._fake_water_permission_store.accounts[old_grant.grant_id]
    assert account.revoked is True
    assert account.grant.grant_revision == 2
    world.ledger.grant = old_grant
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        old_grant
    ) == "DENIED_STALE_GRANT_REVISION"

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    subsequent_interest = Interest("STAY")
    later = FakeMixedDaytimeLoop(
        game, host, world, subsequent_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert subsequent_interest.calls == 0


@pytest.mark.parametrize("release_case", [
    "no_receipt", "retained_pending", "changed_target",
    "float_revision", "malformed_rows", "throws"
])
def test_adapter_owned_rejection_release_failure_is_quarantined_and_ingests_p1(
        release_case, monkeypatch):
    """R20 review gap: exercise the *actual* guarded release failure branch.

    These test-local mutations target the pinned adapter-owned release and
    inspect its postconditions; they do not grant an untrusted Game callback
    authority during an ordinary mixed-loop step.
    """
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original_grant = world.ledger.grant
    original_finish = mixed_module._ORIGINAL_FAKE_REJECT
    expected = FakeGame.observe(game)
    attempt = "offline-attempt-1"
    assert game.prepare("MOVE_TO_CHAIR", expected, attempt) is True
    target = game.chair_tile
    adapter = mixed_module._HostGatedChairWorld(
        game,
        lambda _attempt: True,
        expected,
        lambda observed: loop._valid_chair_observation(observed, target),
        lambda: loop.watering._ingest_fixture_revocation(world),
        target,
    )

    def fake_pinned_release(game_obj, operation):
        assert game_obj is game
        assert operation == attempt
        # Deliver a valid P1 revocation DURING release, not before step.
        world.ledger.grant = replace(
            original_grant, grant_revision=2, active=False
        )
        if release_case == "retained_pending":
            return True
        released = original_finish(game_obj, operation)
        assert released is True
        if release_case == "no_receipt":
            return None
        if release_case == "changed_target":
            game_obj.chair_tile = (8, 4)
        elif release_case == "float_revision":
            game_obj.revision = 1.0
        elif release_case == "malformed_rows":
            game_obj.dispatched = None
        elif release_case == "throws":
            raise RuntimeError("bad pinned fake release")
        return released

    monkeypatch.setattr(mixed_module, "_ORIGINAL_FAKE_REJECT",
                        fake_pinned_release)
    if release_case in ("throws", "malformed_rows"):
        with pytest.raises((RuntimeError, TypeError)):
            adapter.finish_rejected(attempt)
    else:
        assert adapter.finish_rejected(attempt) is False

    assert adapter._rejection_cleanup_attempt == attempt
    assert adapter._rejection_cleanup_contradicted is True
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert game.pending_attempt == (
        attempt if release_case == "retained_pending" else None
    )
    assert "MOVE_TO_CHAIR" not in loop.completed
    account = host._fake_water_permission_store.accounts[original_grant.grant_id]
    assert account.revoked is True
    assert account.grant.grant_revision == 2
    world.ledger.grant = original_grant
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        original_grant
    ) == "DENIED_STALE_GRANT_REVISION"


@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("corrupt", ["none_log", "none_revision", "fake_count"])
def test_r22_finalizer_true_with_malformed_effect_evidence_fails_closed(
        bounded, corrupt, monkeypatch):
    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    original = game.finish_observed_action
    l2_original = OfflineController.step
    l2_outcomes, executed, publisher = [], [], []

    class ForgedLog:
        def count(self, row):
            return 1

    def watch_l2(controller):
        outcome = l2_original(controller)
        l2_outcomes.append(outcome.verdict)
        return outcome

    monkeypatch.setattr(OfflineController, "step", watch_l2)

    def finalize_and_corrupt(attempt):
        value = original(attempt)
        executed.append((attempt, value))
        if corrupt == "none_log":
            game.dispatched = None
        elif corrupt == "none_revision":
            game.revision = None
        else:
            game.dispatched = ForgedLog()
        return True

    game.finish_observed_action = finalize_and_corrupt
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: publisher.append(True)
        )
        assert [x.status for x in trace] == [
            "UNKNOWN_UNVERIFIED_CHAIR_TARGET"
        ]
        result = trace[0]
        assert publisher == []
    else:
        result = loop.step()
    assert executed == [("offline-attempt-1", True)]
    assert l2_outcomes == ["VERIFIED_FAKE"]
    assert result.status == "UNKNOWN_UNVERIFIED_CHAIR_TARGET"
    assert result.operation_id == "offline-attempt-1"
    assert result.claim_real_completion is False
    assert game.pending_attempt is None
    assert game.sunny_tile == game.chair_tile
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert "MOVE_TO_CHAIR" not in loop.completed
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("STAY")
    later = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    assert later.status == "BLOCKED_UNRESOLVED"
    assert later_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("prepare_return", [True, False])
def test_r22_prepare_saved_dispatch_hidden_row_keeps_two_ids(
        bounded, prepare_return, monkeypatch):
    from reference.sunny_host_stop_fake import FakeWaterOperation

    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",), delivery="ack_no_effect"
    )
    saved_prepare = game.prepare
    saved_dispatch = FakeGame.dispatch
    saved_observe = game.observe
    l2_original = OfflineController.step
    l2_outcomes, callback_receipts, publisher = [], [], []
    host_id = "water-nested-during-injected-prepare"

    def watch_l2(controller):
        result = l2_original(controller)
        l2_outcomes.append(result.verdict)
        return result

    monkeypatch.setattr(OfflineController, "step", watch_l2)

    def hidden_prepare(action, expected, attempt):
        assert saved_prepare(action, expected, attempt) is True
        # Raw prepare temporarily routes the Game's observer through the
        # strict adapter. A malicious callback can restore its saved raw
        # observer before invoking an independently saved dispatcher.
        game.observe = saved_observe
        receipt = saved_dispatch(game, action, expected, attempt)
        assert receipt == "ack"
        erased = game.dispatched.pop()
        assert erased == (attempt, "MOVE_TO_CHAIR", "p2")
        water = FakeWaterOperation(
            host_id, host.epoch, host.owner, "P2", "WATER", (4, 5)
        )
        assert host.reserve(water) == "B_LINEAGE_RESERVED"
        callback_receipts.append((attempt, receipt, erased))
        return prepare_return

    game.prepare = hidden_prepare
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: publisher.append(True)
        )
        assert [x.status for x in trace] == [
            "UNKNOWN", "BLOCKED_UNRESOLVED"
        ]
        assert trace[1].operation_id == host_id
        result = trace[0]
        assert publisher == []
    else:
        result = loop.step()
    assert callback_receipts == [
        ("offline-attempt-1", "ack",
         ("offline-attempt-1", "MOVE_TO_CHAIR", "p2"))
    ]
    assert l2_outcomes == ["UNKNOWN"]
    assert result.status == "UNKNOWN"
    assert result.operation_id == "offline-attempt-1"
    assert result.pending_operation_id == host_id
    assert host.pending.operation_id == host_id
    assert game.pending_attempt == "offline-attempt-1"
    assert game.dispatched == []
    assert game.sunny_tile == (4, 4)
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert result.claim_real_completion is False
    assert not loop.completed
    future_interest = Interest("STAY")
    future = FakeMixedDaytimeLoop(
        game, host, world, future_interest, weather="sunny"
    ).step()
    assert future.status == "BLOCKED_UNRESOLVED"
    assert future_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
def test_r22_dispatch_retained_chair_and_nested_water_both_reported(
        bounded, monkeypatch):
    from reference.sunny_host_stop_fake import FakeWaterOperation

    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",), delivery="ack_no_effect"
    )
    saved_dispatch = game.dispatch
    l2_original = OfflineController.step
    l2_outcomes, publisher = [], []
    host_id = "water-nested-after-chair-dispatch"

    def watch_l2(controller):
        outcome = l2_original(controller)
        l2_outcomes.append(outcome.verdict)
        return outcome

    monkeypatch.setattr(OfflineController, "step", watch_l2)

    def mixed_dispatch(action, expected, attempt):
        assert saved_dispatch(action, expected, attempt) == "ack"
        op = FakeWaterOperation(host_id, host.epoch, host.owner,
                                "P2", "WATER", (4, 5))
        assert host.reserve(op) == "B_LINEAGE_RESERVED"
        return "ack"

    game.dispatch = mixed_dispatch
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: publisher.append(True)
        )
        assert [r.status for r in trace] == [
            "UNKNOWN", "BLOCKED_UNRESOLVED"
        ]
        assert trace[1].operation_id == host_id
        outcome = trace[0]
        assert publisher == []
    else:
        outcome = loop.step()
    assert l2_outcomes == ["UNKNOWN"]
    assert outcome.status == "UNKNOWN"
    assert outcome.operation_id == game.pending_attempt == "offline-attempt-1"
    assert outcome.pending_operation_id == host.pending.operation_id == host_id
    assert outcome.claim_real_completion is False
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert "MOVE_TO_CHAIR" not in loop.completed


@pytest.mark.parametrize("bounded", [False, True])
def test_r22_failed_owned_release_retains_chair_and_foreign_water_ids(
        bounded, monkeypatch):
    from reference.sunny_host_stop_fake import FakeWaterOperation

    game, host, world, interest, loop = setup(choices=("MOVE_TO_CHAIR",))
    l2_original = OfflineController.step
    l2_outcomes, release_calls, publisher = [], [], []
    host_id = "water-from-failed-chair-release"

    def watch_l2(controller):
        outcome = l2_original(controller)
        l2_outcomes.append(outcome.verdict)
        return outcome

    def pinned_pre_effect_rejection(world_obj, action, expected, attempt):
        assert world_obj is game and game.pending_attempt == attempt
        return "rejected_before_effect"

    def faulty_owned_release(world_obj, attempt):
        assert world_obj is game and game.pending_attempt == attempt
        release_calls.append(attempt)
        op = FakeWaterOperation(host_id, host.epoch, host.owner,
                                "P2", "WATER", (4, 5))
        assert host.reserve(op) == "B_LINEAGE_RESERVED"
        return True  # reservation is intentionally NOT cleared

    monkeypatch.setattr(OfflineController, "step", watch_l2)
    monkeypatch.setattr(mixed_module, "_ORIGINAL_FAKE_DISPATCH",
                        pinned_pre_effect_rejection)
    monkeypatch.setattr(mixed_module, "_ORIGINAL_FAKE_REJECT",
                        faulty_owned_release)
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: publisher.append(True)
        )
        assert [r.status for r in trace] == [
            "UNKNOWN", "BLOCKED_UNRESOLVED"
        ]
        assert trace[1].operation_id == host_id
        outcome = trace[0]
        assert publisher == []
    else:
        outcome = loop.step()
    assert release_calls == ["offline-attempt-1"]
    assert l2_outcomes == ["BLOCKED_STALE_OR_DENIED"]
    assert outcome.status == "UNKNOWN"
    assert outcome.operation_id == game.pending_attempt == "offline-attempt-1"
    assert outcome.pending_operation_id == host.pending.operation_id == host_id
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert outcome.claim_real_completion is False
    assert "MOVE_TO_CHAIR" not in loop.completed



@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("nested_water", [False, True])
def test_r23_prepare_observer_can_hide_dispatched_attempt_and_release_then_raise(
        bounded, nested_water, monkeypatch):
    """R22 independent finding 1: a read is an effect-capable callback.

    FakeGame.prepare itself is original and unmodified. Its injected
    observation #4 calls previously saved original FakeGame methods to
    reserve and dispatch the OUTER chair operation, erases the ack_no_effect
    row, releases the reservation, creates optional independent Host WATER
    and raises. A missing row/pending MUST NOT become known pre-effect denial.
    """
    from reference.sunny_host_stop_fake import FakeWaterOperation

    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",), delivery="ack_no_effect"
    )
    raw_observe = game.observe
    saved_prepare = FakeGame.prepare
    saved_dispatch = FakeGame.dispatch
    saved_release = FakeGame.finish_rejected
    original_l2 = OfflineController.step
    l2_verdicts, evidence, publisher = [], [], []
    read_count = [0]
    water_id = "water-from-malicious-prepare-observer"

    def capture_l2(controller):
        result = original_l2(controller)
        l2_verdicts.append(result.verdict)
        return result

    monkeypatch.setattr(OfflineController, "step", capture_l2)

    def observer_with_hidden_dispatch():
        read_count[0] += 1
        if read_count[0] == 4:
            game.observe = raw_observe  # bypass the scoped adapter observer
            snapshot = raw_observe()
            attempt = "offline-attempt-1"
            assert saved_prepare(game, "MOVE_TO_CHAIR", snapshot, attempt) is True
            receipt = saved_dispatch(
                game, "MOVE_TO_CHAIR", snapshot, attempt
            )
            assert receipt == "ack"
            row = game.dispatched.pop()
            assert row == (attempt, "MOVE_TO_CHAIR", "p2")
            released = saved_release(game, attempt)
            assert released is True
            if nested_water:
                op = FakeWaterOperation(
                    water_id, host.epoch, host.owner, "P2", "WATER", (4, 5)
                )
                assert host.reserve(op) == "B_LINEAGE_RESERVED"
            evidence.append((attempt, receipt, row, released))
            raise RuntimeError("fake observer hidden dispatch and erased row")
        return raw_observe()

    game.observe = observer_with_hidden_dispatch
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: publisher.append(True)
        )
        statuses = (
            ["UNKNOWN", "BLOCKED_UNRESOLVED"]
            if nested_water else ["UNKNOWN"]
        )
        assert [r.status for r in trace] == statuses
        result = trace[0]
        if nested_water:
            assert trace[1].operation_id == water_id
        assert publisher == []
    else:
        result = loop.step()
    assert read_count == [4]
    assert evidence == [
        ("offline-attempt-1", "ack",
         ("offline-attempt-1", "MOVE_TO_CHAIR", "p2"), True)
    ]
    assert l2_verdicts == ["UNKNOWN"]
    assert result.status == "UNKNOWN"
    assert result.choice == "MOVE_TO_CHAIR"
    assert result.operation_id == "offline-attempt-1"
    assert result.pending_operation_id == (
        water_id if nested_water else None
    )
    assert game.pending_attempt is None and game.dispatched == []
    assert game.sunny_tile == (4, 4) and game.revision == 1
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert result.claim_real_completion is False
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert host.events.count("FAKE_EFFECT") == 0
    assert interest.calls == 1

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    later_interest = Interest("STAY")
    blocked = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    ).step()
    assert blocked.status == "BLOCKED_UNRESOLVED"
    assert later_interest.calls == 0


@pytest.mark.parametrize("bounded", [False, True])
def test_r23_dispatch_observer_duplicate_raw_sends_never_verify_or_publish(
        bounded, monkeypatch):
    """R22 independent finding 2: two sends can leave one genuine-looking row.

    Test-local injection *between* accepted original prepare and dispatch
    exercises the dispatch boundary independently of the earlier prepare
    observer guard. The injected observer invokes a saved original dispatcher
    (ack_no_effect), deletes its row, switches to ack and supplies a canonical
    snapshot so the outer original dispatcher sends again for the same ID.
    Neither final row count nor literal ACK proves one-and-only-one send.
    """
    game, host, world, interest, loop = setup(
        choices=("MOVE_TO_CHAIR",), delivery="ack_no_effect"
    )
    real_adapter_dispatch = mixed_module._HostGatedChairWorld.dispatch
    saved_game_observe = game.observe
    original_dispatch = FakeGame.dispatch
    original_l2 = OfflineController.step
    nested_receipts, l2_verdicts, publisher = [], [], []

    def witness_l2(controller):
        result = original_l2(controller)
        l2_verdicts.append(result.verdict)
        return result

    monkeypatch.setattr(OfflineController, "step", witness_l2)

    def injection_before_dispatch(adapter, action, expected, attempt):
        assert game.pending_attempt == attempt
        assert game.dispatched == []
        def observer_reentrant_dispatch():
            # Temporarily restore saved original observer to make the nested
            # raw FakeGame.dispatch distinct from the adapter's raw read.
            game.observe = saved_game_observe
            game.delivery = "ack_no_effect"
            receipt = original_dispatch(game, action, expected, attempt)
            assert receipt == "ack"
            row = game.dispatched.pop()
            assert row == (attempt, "MOVE_TO_CHAIR", "p2")
            nested_receipts.append((attempt, receipt, row))
            game.delivery = "ack"
            return saved_game_observe()

        adapter._raw_observe = observer_reentrant_dispatch
        return real_adapter_dispatch(adapter, action, expected, attempt)

    monkeypatch.setattr(
        mixed_module._HostGatedChairWorld,
        "dispatch", injection_before_dispatch
    )
    if bounded:
        trace = loop.run_bounded(
            1, after_verified=lambda *_args: publisher.append(True)
        )
        assert [r.status for r in trace] == ["UNKNOWN"]
        result = trace[0]
        assert publisher == []
    else:
        result = loop.step()
    assert nested_receipts == [
        ("offline-attempt-1", "ack",
         ("offline-attempt-1", "MOVE_TO_CHAIR", "p2"))
    ]
    assert l2_verdicts == ["UNKNOWN"]
    assert result.status == "UNKNOWN"
    assert result.operation_id == "offline-attempt-1"
    assert result.pending_operation_id is None
    assert result.claim_real_completion is False
    assert game.pending_attempt == "offline-attempt-1"
    assert game.dispatched == [
        ("offline-attempt-1", "MOVE_TO_CHAIR", "p2")
    ]
    assert game.sunny_tile == game.chair_tile
    assert game.revision == 2
    assert getattr(game, "_fake_mixed_quarantined", False) is True
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert host.events.count("FAKE_EFFECT") == 0

    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    future_interest = Interest("STAY")
    blocked = FakeMixedDaytimeLoop(
        game, host, world, future_interest, weather="sunny"
    ).step()
    assert blocked.status == "BLOCKED_UNRESOLVED"
    assert future_interest.calls == 0
