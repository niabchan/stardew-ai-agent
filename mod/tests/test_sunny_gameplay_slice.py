"""G0-only tests: synthetic gameplay loop, never a real Sunny/Luna/HTTP test."""
from dataclasses import fields

from reference.sunny_gameplay_slice import FakeGame, OfflineController, ScriptedChooser


def test_two_independent_choices_move_then_stay():
    world = FakeGame()
    choose = ScriptedChooser("MOVE_TO_CHAIR", "STAY")
    loop = OfflineController(world, choose)

    first = loop.step()
    second = loop.step()

    assert (first.verdict, second.verdict) == ("VERIFIED_FAKE", "STAY")
    assert choose.calls == 2
    assert world.sunny_tile == (7, 4)
    assert world.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert not loop.halted


def test_lost_reply_is_unknown_even_if_effect_happened_and_never_retried():
    world = FakeGame()
    world.delivery = "lost_reply"
    choose = ScriptedChooser("MOVE_TO_CHAIR", "MOVE_TO_CHAIR")
    loop = OfflineController(world, choose)

    assert loop.step().verdict == "UNKNOWN"
    assert world.sunny_tile == (7, 4)  # effect could have happened
    assert loop.step().verdict == "BLOCKED_UNRESOLVED"
    assert choose.calls == 1
    assert len(world.dispatched) == 1


def test_ack_without_observed_change_is_not_success():
    world = FakeGame()
    world.delivery = "ack_no_effect"
    loop = OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR"))
    assert loop.step().verdict == "UNKNOWN"
    assert loop.halted
    assert len(world.dispatched) == 1


def test_stay_has_no_dispatch_or_forced_activity():
    world = FakeGame()
    loop = OfflineController(world, ScriptedChooser("STAY"))
    assert loop.step().verdict == "STAY"
    assert world.dispatched == []


def test_high_impact_action_not_offered_or_dispatched():
    world = FakeGame()
    loop = OfflineController(world, ScriptedChooser("MARRY_NPC"))
    assert loop.step().verdict == "BLOCKED_NOT_OFFERED"
    assert world.dispatched == []


def test_fireplace_is_future_capability_not_smuggled_into_l2():
    world = FakeGame()
    assert "FIREPLACE_TOGGLE" not in world.observe().options
    loop = OfflineController(world, ScriptedChooser("FIREPLACE_TOGGLE"))
    assert loop.step().verdict == "BLOCKED_NOT_OFFERED"
    assert world.dispatched == []


def test_p1_human_is_required_but_never_command_target():
    world = FakeGame()
    world.p1_is_human = False
    chooser = ScriptedChooser("MOVE_TO_CHAIR")
    assert OfflineController(world, chooser).step().verdict == "BLOCKED_PRECONDITION"
    assert chooser.calls == 0
    assert world.dispatched == []


def test_p2_must_be_ai_and_ready():
    world = FakeGame()
    world.p2_is_ai = False
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "BLOCKED_PRECONDITION"
    world.p2_is_ai = True
    world.ready = False
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "BLOCKED_PRECONDITION"
    assert world.dispatched == []


def test_foreign_owner_cannot_start():
    world = FakeGame()
    world.owner = "other-fake-owner"
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "BLOCKED_PRECONDITION"
    assert world.dispatched == []


def test_same_save_new_load_epoch_rejected_before_side_effect():
    class ReloadBeforeDispatch(FakeGame):
        def dispatch(self, action, expected, attempt):
            self.epoch = "load-2"  # same save/day, new load epoch
            return super().dispatch(action, expected, attempt)

    world = ReloadBeforeDispatch()
    loop = OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR"))
    assert loop.step().verdict == "BLOCKED_STALE_OR_DENIED"
    assert loop.halted
    assert world.dispatched == []


def test_changed_world_revision_rejected_before_side_effect():
    class MutateBeforeDispatch(FakeGame):
        def dispatch(self, action, expected, attempt):
            self.revision += 1
            return super().dispatch(action, expected, attempt)

    world = MutateBeforeDispatch()
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "BLOCKED_STALE_OR_DENIED"
    assert world.dispatched == []


def test_duplicate_attempt_rejected_without_second_effect():
    world = FakeGame()
    before = world.observe()
    assert world.dispatch("MOVE_TO_CHAIR", before, "attempt-a") == "ack"
    assert world.dispatch("MOVE_TO_CHAIR", before, "attempt-a") == "rejected"
    assert len(world.dispatched) == 1


def test_observation_never_contains_raw_p1_diary_or_chat():
    world = FakeGame()
    obs = world.observe()
    assert "private_p1_diary" not in {f.name for f in fields(obs)}
    assert "NEVER EXPOSE" not in repr(obs)
    assert not any("feed" in f.name or "chat" in f.name for f in fields(obs))
