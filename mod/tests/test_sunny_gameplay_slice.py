"""G0-only: inert fake-world L2 outcomes. Not real Luna/HTTP/game safety."""
from dataclasses import fields

from reference.sunny_gameplay_slice import FakeGame, OfflineController, ScriptedChooser


def test_two_choices_move_then_stay_and_complete_fake_pending_attempt():
    world = FakeGame()
    choose = ScriptedChooser("MOVE_TO_CHAIR", "STAY")
    loop = OfflineController(world, choose)

    first = loop.step()
    second = loop.step()

    assert (first.verdict, second.verdict) == ("VERIFIED_FAKE", "STAY")
    assert choose.calls == 2
    assert world.sunny_tile == (7, 4)
    assert world.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]
    assert world.pending_attempt is None
    assert not loop.halted


def test_lost_reply_is_unknown_even_if_effect_happened_and_never_retried():
    world = FakeGame()
    world.delivery = "lost_reply"
    choose = ScriptedChooser("MOVE_TO_CHAIR", "MOVE_TO_CHAIR")
    loop = OfflineController(world, choose)

    assert loop.step().verdict == "UNKNOWN"
    assert world.sunny_tile == (7, 4)  # fake effect may have happened
    assert world.pending_attempt == "offline-attempt-1"
    assert loop.step().verdict == "BLOCKED_UNRESOLVED"
    assert choose.calls == 1
    assert len(world.dispatched) == 1


def test_controller_recreation_cannot_erase_shared_fake_pending_marker():
    world = FakeGame()
    world.delivery = "ack_no_effect"
    first = OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR"))
    assert first.step().verdict == "UNKNOWN"
    assert world.pending_attempt == "offline-attempt-1"

    # New controller object, SAME in-memory fake world; no new choice or action.
    new_chooser = ScriptedChooser("MOVE_TO_CHAIR")
    second = OfflineController(world, new_chooser)
    assert second.step().verdict == "BLOCKED_UNRESOLVED"
    assert new_chooser.calls == 0
    assert world.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]


def test_ack_without_observed_change_is_not_success():
    world = FakeGame()
    world.delivery = "ack_no_effect"
    loop = OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR"))
    assert loop.step().verdict == "UNKNOWN"
    assert loop.halted
    assert len(world.dispatched) == 1
    assert world.pending_attempt is not None


def test_stay_has_no_dispatch_or_forced_activity():
    world = FakeGame()
    loop = OfflineController(world, ScriptedChooser("STAY"))
    assert loop.step().verdict == "STAY"
    assert world.dispatched == []
    assert world.pending_attempt is None


def test_high_impact_action_not_offered_or_dispatched():
    world = FakeGame()
    assert OfflineController(world, ScriptedChooser("MARRY_NPC")).step().verdict == "BLOCKED_NOT_OFFERED"
    assert world.dispatched == []


def test_fireplace_is_future_capability_not_smuggled_into_l2():
    world = FakeGame()
    assert "FIREPLACE_TOGGLE" not in world.observe().options
    assert OfflineController(world, ScriptedChooser("FIREPLACE_TOGGLE")).step().verdict == "BLOCKED_NOT_OFFERED"
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
            self.epoch = "load-2"  # same save/day but new host load epoch
            return super().dispatch(action, expected, attempt)

    world = ReloadBeforeDispatch()
    loop = OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR"))
    assert loop.step().verdict == "BLOCKED_STALE_OR_DENIED"
    assert loop.halted
    assert world.dispatched == []
    assert world.pending_attempt is None


def test_epoch_change_between_choices_blocks_second_without_rebind():
    world = FakeGame()
    chooser = ScriptedChooser("MOVE_TO_CHAIR", "STAY")
    loop = OfflineController(world, chooser)
    assert loop.step().verdict == "VERIFIED_FAKE"
    world.epoch = "load-2"  # same save/day reload, no explicit new approval
    assert loop.step().verdict == "BLOCKED_STALE_EPOCH"
    assert chooser.calls == 1
    assert world.dispatched == [("offline-attempt-1", "MOVE_TO_CHAIR", "p2")]


def test_new_controller_does_not_automatically_accept_stale_epoch():
    world = FakeGame()
    world.epoch = "load-2"
    chooser = ScriptedChooser("MOVE_TO_CHAIR")
    assert OfflineController(world, chooser, expected_epoch="load-1").step().verdict == "BLOCKED_STALE_EPOCH"
    assert chooser.calls == 0
    assert world.dispatched == []


def test_changed_world_revision_rejected_before_side_effect():
    class MutateBeforeDispatch(FakeGame):
        def dispatch(self, action, expected, attempt):
            self.revision += 1
            return super().dispatch(action, expected, attempt)

    world = MutateBeforeDispatch()
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "BLOCKED_STALE_OR_DENIED"
    assert world.dispatched == []
    assert world.pending_attempt is None


def test_duplicate_attempt_rejected_without_second_effect():
    world = FakeGame()
    before = world.observe()
    assert world.prepare("MOVE_TO_CHAIR", before, "attempt-a")
    assert world.dispatch("MOVE_TO_CHAIR", before, "attempt-a") == "ack"
    assert not world.prepare("MOVE_TO_CHAIR", before, "attempt-a")
    assert len(world.dispatched) == 1
    assert world.pending_attempt == "attempt-a"


def test_different_attempt_id_does_not_override_unresolved_fake_action():
    world = FakeGame()
    before = world.observe()
    world.delivery = "ack_no_effect"
    assert world.prepare("MOVE_TO_CHAIR", before, "attempt-a")
    assert world.dispatch("MOVE_TO_CHAIR", before, "attempt-a") == "ack"
    assert not world.prepare("MOVE_TO_CHAIR", before, "attempt-b")
    assert len(world.dispatched) == 1


def test_reload_after_dispatch_yields_unknown_and_keeps_pending_marker():
    class ReloadAfterDispatch(FakeGame):
        def dispatch(self, action, expected, attempt):
            response = super().dispatch(action, expected, attempt)
            if response == "ack":
                self.epoch = "load-2"  # after the fake effect, before verification
            return response

    world = ReloadAfterDispatch()
    loop = OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR"))
    assert loop.step().verdict == "UNKNOWN"
    assert world.pending_attempt == "offline-attempt-1"
    assert OfflineController(world, ScriptedChooser("STAY")).step().verdict == "BLOCKED_UNRESOLVED"


def test_dispatch_exception_after_fake_effect_is_unknown_not_retried():
    class RaiseAfterMutation(FakeGame):
        def dispatch(self, action, expected, attempt):
            super().dispatch(action, expected, attempt)
            raise RuntimeError("simulated reply failure")

    world = RaiseAfterMutation()
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "UNKNOWN"
    assert world.sunny_tile == world.chair_tile
    assert world.pending_attempt is not None
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "BLOCKED_UNRESOLVED"
    assert len(world.dispatched) == 1


def test_observation_failure_after_effect_is_unknown():
    class ReadFailsAfterDispatch(FakeGame):
        def dispatch(self, action, expected, attempt):
            response = super().dispatch(action, expected, attempt)
            self.post_read_fails = True
            return response

        def observe(self):
            if getattr(self, "post_read_fails", False):
                raise IOError("simulated post-action state read failure")
            return super().observe()

    world = ReadFailsAfterDispatch()
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "UNKNOWN"
    assert world.pending_attempt is not None
    assert len(world.dispatched) == 1


def test_chooser_exception_never_dispatches():
    def bad_chooser(_):
        raise RuntimeError("simulated model failure")

    world = FakeGame()
    assert OfflineController(world, bad_chooser).step().verdict == "BLOCKED_CHOICE_UNAVAILABLE"
    assert world.pending_attempt is None
    assert world.dispatched == []


def test_initial_observation_exception_never_calls_chooser_or_dispatches():
    class ObserveUnavailable(FakeGame):
        def observe(self):
            raise IOError("simulated source unavailable")

    world = ObserveUnavailable()
    chooser = ScriptedChooser("MOVE_TO_CHAIR")
    assert OfflineController(world, chooser).step().verdict == "BLOCKED_OBSERVATION_UNAVAILABLE"
    assert chooser.calls == 0
    assert world.dispatched == []


def test_observation_never_contains_raw_p1_diary_or_chat():
    world = FakeGame()
    obs = world.observe()
    assert "private_p1_diary" not in {f.name for f in fields(obs)}
    assert "NEVER EXPOSE" not in repr(obs)
    assert not any("feed" in f.name or "chat" in f.name for f in fields(obs))



def test_prepare_marker_survives_exception_before_effect_for_new_controller():
    class CrashBeforeMutation(FakeGame):
        def dispatch(self, action, expected, attempt):
            raise IOError("simulated failure before knowing if write was sent")

    world = CrashBeforeMutation()
    assert OfflineController(world, ScriptedChooser("MOVE_TO_CHAIR")).step().verdict == "UNKNOWN"
    assert world.dispatched == []
    assert world.pending_attempt == "offline-attempt-1"
    chooser = ScriptedChooser("MOVE_TO_CHAIR")
    assert OfflineController(world, chooser).step().verdict == "BLOCKED_UNRESOLVED"
    assert chooser.calls == 0


def test_unprepared_action_is_never_executed():
    world = FakeGame()
    before = world.observe()
    assert world.dispatch("MOVE_TO_CHAIR", before, "not-prepared") == "rejected_before_effect"
    assert world.dispatched == []
    assert world.pending_attempt is None
