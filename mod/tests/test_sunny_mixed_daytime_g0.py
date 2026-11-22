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
