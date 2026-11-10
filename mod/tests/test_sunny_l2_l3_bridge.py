"""G0-only tests connecting the fake L3 proposal to the fake L2 executor."""
from reference.sunny_gameplay_slice import FakeGame
from reference.sunny_l2_l3_bridge import OfflineIntentToAction


class ToyInterest:
    def __init__(self, *desired):
        self.desired = iter(desired)
        self.calls = 0
        self.offers = []

    def __call__(self, candidates):
        self.calls += 1
        self.offers.append(tuple(candidate.action for candidate in candidates))
        return next(self.desired)


def test_integrated_move_verify_then_fresh_stay_without_extra_dispatch():
    world = FakeGame()
    interest = ToyInterest("MOVE_TO_CHAIR", "STAY")
    bridge = OfflineIntentToAction(world, interest)
    first = bridge.step()
    second = bridge.step()
    assert (first.status, second.status) == ("VERIFIED_FAKE", "STAY")
    assert first.attempt == "offline-attempt-1"
    assert world.sunny_tile == world.chair_tile
    assert world.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert interest.offers == [
        ("STAY", "MOVE_TO_CHAIR"),
        ("STAY",),
    ]


def test_stay_is_not_retried_on_the_identical_snapshot():
    world = FakeGame()
    interest = ToyInterest("STAY", "MOVE_TO_CHAIR")
    bridge = OfflineIntentToAction(world, interest)
    assert bridge.step().status == "STAY"
    assert bridge.step().status == "WAIT_NEW_OBSERVATION"
    assert interest.calls == 1
    assert world.dispatched == []


def test_model_like_interest_cannot_invent_tv_without_l2_action_support():
    world = FakeGame()
    interest = ToyInterest("WATCH_WEATHER_TV")
    result = OfflineIntentToAction(world, interest).step()
    assert result.status == "DENIED_NOT_GROUNDED"
    assert "WATCH_WEATHER_TV" not in result.offered
    assert world.dispatched == []


def test_p1_social_approach_is_not_offered_or_executed():
    world = FakeGame()
    interest = ToyInterest("APPROACH_P1")
    result = OfflineIntentToAction(world, interest).step()
    assert result.status == "DENIED_NOT_GROUNDED"
    assert "APPROACH_P1" not in result.offered
    assert "SPEAK_TO_P1" not in result.offered
    assert world.dispatched == []


def test_lost_reply_remains_unknown_and_never_calls_interest_again():
    world = FakeGame()
    world.delivery = "lost_reply"
    interest = ToyInterest("MOVE_TO_CHAIR", "STAY")
    bridge = OfflineIntentToAction(world, interest)
    assert bridge.step().status == "UNKNOWN"
    assert world.pending_attempt == "offline-attempt-1"
    assert bridge.step().status == "BLOCKED_UNRESOLVED"
    assert interest.calls == 1
    assert len(world.dispatched) == 1


def test_new_bridge_same_fake_world_cannot_erase_pending_attempt():
    world = FakeGame()
    world.delivery = "ack_no_effect"
    first = OfflineIntentToAction(world, ToyInterest("MOVE_TO_CHAIR"))
    assert first.step().status == "UNKNOWN"
    fresh_interest = ToyInterest("MOVE_TO_CHAIR")
    assert OfflineIntentToAction(world, fresh_interest).step().status == "BLOCKED_UNRESOLVED"
    assert fresh_interest.calls == 0
    assert len(world.dispatched) == 1


def test_owner_or_epoch_mismatch_never_calls_interest():
    for field, bad in (("owner", "other-owner"), ("epoch", "other-load")):
        world = FakeGame()
        setattr(world, field, bad)
        interest = ToyInterest("MOVE_TO_CHAIR")
        result = OfflineIntentToAction(world, interest).step()
        assert result.status in ("BLOCKED_EPOCH", "BLOCKED_ROLE_OR_OWNER")
        assert interest.calls == 0
        assert world.dispatched == []


def test_p1_or_p2_role_mismatch_never_calls_interest():
    for field in ("p1_is_human", "p2_is_ai", "ready"):
        world = FakeGame()
        setattr(world, field, False)
        interest = ToyInterest("STAY")
        assert OfflineIntentToAction(world, interest).step().status == "BLOCKED_ROLE_OR_OWNER"
        assert interest.calls == 0
        assert world.dispatched == []


def test_mutation_during_interest_selection_invalidates_pinned_choice():
    world = FakeGame()

    def mutating_interest(_):
        world.revision += 1
        return "MOVE_TO_CHAIR"

    bridge = OfflineIntentToAction(world, mutating_interest)
    assert bridge.step().status == "BLOCKED_CHOICE_UNAVAILABLE"
    assert world.dispatched == []
    assert world.pending_attempt is None


def test_no_fabricated_weather_p1_availability_or_private_diary():
    world = FakeGame()
    world.private_p1_diary = "SECRET-P1-CONTENT"
    observations = []

    def capturing_interest(candidates):
        observations.extend(candidates)
        return "STAY"

    bridge = OfflineIntentToAction(world, capturing_interest)
    assert bridge.step().status == "STAY"
    scene = bridge._make_scene(world.observe())
    assert scene.weather == "unknown"
    assert scene.p1_awake is False
    assert scene.p1_distance_tiles is None
    assert scene.tv_reachable is False
    assert "SECRET-P1-CONTENT" not in repr(scene)
    assert "SECRET-P1-CONTENT" not in repr(observations)


def test_chooser_error_does_not_dispatch_or_expose_p1_info():
    world = FakeGame()

    def raise_interest(_):
        raise RuntimeError("fake chooser error")

    bridge = OfflineIntentToAction(world, raise_interest)
    assert bridge.step().status == "BLOCKED_INTEREST_UNAVAILABLE"
    assert world.dispatched == []
    assert world.pending_attempt is None
