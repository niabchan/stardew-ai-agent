"""G0-only mixed Sunny daytime traces; no game, model, transport or P1 data."""
from dataclasses import replace

import pytest

from reference.sunny_gameplay_slice import FakeGame
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
    assert game.sunny_tile == (8, 4)  # synthetic changed destination
    assert len(game.dispatched) == 1
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
    assert first.status == "BLOCKED_CHANGED_BEFORE_DISPATCH"
    assert first.claim_real_completion is False
    assert interest.calls == 1
    assert not game.dispatched and game.pending_attempt is None
    assert "MOVE_TO_CHAIR" not in loop.completed
    assert "FAKE_EFFECT" not in host.events
    if on_second_read == "water_pending":
        assert host.pending is not None
    else:
        assert host.stopped is True

    fresh_interest = Interest("MOVE_TO_CHAIR")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, fresh_interest, weather="sunny"
    )
    assert fresh.step().status in {
        "BLOCKED_STOP", "BLOCKED_UNRESOLVED", "BLOCKED_OWNER_OR_EPOCH"
    }
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


def test_stop_during_l2_prepare_observation_retires_reservation_without_dispatch():
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
    assert result.status == "BLOCKED_STALE_OR_DENIED"
    assert host.stopped
    assert game.pending_attempt is None
    assert game.dispatched == []
    assert "MOVE_TO_CHAIR" not in loop.completed


def test_stop_inside_started_fake_dispatch_quarantines_unknown_not_success():
    """STOP during raw L2 dispatch cannot prove a *pre-effect* rejection."""
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
    assert reads == 5
    assert result.status == "UNKNOWN"
    assert host.stopped
    assert game.pending_attempt is not None
    assert len(game.dispatched) == 1  # residual fake effect is possible
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
    assert result.status == "BLOCKED_STALE_OR_DENIED"
    assert host.pending is not None
    assert game.pending_attempt is None
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
    assert reads == 1 and result.status == "BLOCKED_CHANGED_BEFORE_DISPATCH"
    assert interest.calls == 0 and game.dispatched == []
    assert game.pending_attempt is None
    if first_read == "stop":
        assert host.stopped
    else:
        assert host.pending is not None


@pytest.mark.parametrize("chair_read,raises,expected", [
    (3, True, "BLOCKED_OBSERVATION_UNAVAILABLE"),
    (4, True, "UNKNOWN"),
    (5, True, "UNKNOWN"),
    (6, True, "UNKNOWN"),
    (3, False, "VERIFIED_FAKE"),
    (4, False, "VERIFIED_FAKE"),
    (5, False, "VERIFIED_FAKE"),
    (6, False, "VERIFIED_FAKE"),
])
def test_chair_reads_latch_p1_revocation_even_if_inner_game_read_raises(
        chair_read, raises, expected):
    """R4 review: chair adapter and raw prepare/dispatch bypassed ingestion.

    Read 3 is adapter.observe, 4 is FakeGame.prepare's own observe,
    5 is FakeGame.dispatch's own observe, and 6 is adapter verification.
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
    assert calls == (chair_read if raises else 6)
    assert result.status == expected
    assert result.claim_real_completion is False
    assert interest.calls == 1 and host.events == []
    account = host._fake_water_permission_store.accounts[old.grant_id]
    assert account.revoked is True
    assert account.grant.grant_revision == 2
    assert FakePermissionedWaterBridge(host).provision_standing_grant(
        old
    ) == "DENIED_STALE_GRANT_REVISION"
    assert account.attempted_starts == 0 and account.started_tiles == set()
    assert host.pending is None and host.used_ids == set()

    if raises and chair_read in (3, 4):
        assert game.pending_attempt is None and game.dispatched == []
    elif raises:
        assert game.pending_attempt is not None
        assert len(game.dispatched) == (1 if chair_read == 6 else 0)
    else:
        assert game.pending_attempt is None and len(game.dispatched) == 1

    # On known pre-effect failure or verified chair completion, a new fake
    # observation and ledger must NEVER revive the old grant for WATER.
    game.observe = original_observe
    game.revision = 9
    world.crop = replace(world.crop, revision=9)
    world.ledger = FakeWaterPermissionLedger(old)
    game.sunny_tile = (4, 4)
    later_interest = Interest("WATER")
    fresh = FakeMixedDaytimeLoop(
        game, host, world, later_interest, weather="sunny"
    )
    subsequent = fresh.step()
    if game.pending_attempt is None:
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
    assert result.status == "UNKNOWN"
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
