"""G0-only tests of a deterministic model, NOT evidence about game STOP."""

from reference.sunny_host_stop_fake import FakeEffectEvidence, FakeHostWaterFence, FakeWaterOperation


def op(name="op-1", epoch="fake-load-1", owner="fake-host-p2", seat="P2", action="WATER", tile=(4, 5)):
    return FakeWaterOperation(name, epoch, owner, seat, action, tile)


def test_reentrant_b_callback_uses_pre_a_lineage_and_never_repeats_effect():
    host = FakeHostWaterFence()
    task = op()
    assert host.reserve(task) == "B_LINEAGE_RESERVED"
    assert host.enter_b(task) == "DENY_B_BEFORE_A"
    seen = []

    def callback(h, t):
        assert not h.a_finished  # A has not returned yet
        seen.append(h.enter_b(t))
        seen.append(h.enter_b(t))
        seen.append(h.finish_b(t))
        seen.append(h.finish_b(t))

    assert host.run_a_with_callback(task, callback) == "A_FINISHED_FAKE"
    assert seen == ["B_ENTERED", "DENY_DUPLICATE_B", "B_FINISHED_FAKE", "DENY_B_NOT_INFLIGHT"]
    assert host.events == ["RESERVE_B_LINEAGE", "ENTER_A", "ENTER_B", "FAKE_EFFECT", "FINISH_A"]
    assert host.confirm_fake_observation(task) == "FAKE_VERIFIED"
    assert host.reserve(task) == "DENY_REPLAY"
    assert host.events.count("FAKE_EFFECT") == 1


def test_stop_before_reservation_denies_any_late_operation():
    host = FakeHostWaterFence()
    assert host.latch_stop() == "STOP_LATCHED"
    assert host.reserve(op()) == "DENY_STOP"
    assert not host.events.count("FAKE_EFFECT")


def test_stop_after_lineage_reservation_before_a_denies_both_regions():
    host = FakeHostWaterFence()
    task = op()
    assert host.reserve(task) == "B_LINEAGE_RESERVED"
    host.latch_stop()
    assert host.enter_a(task) == "DENY_STOP"
    assert host.enter_b(task) == "DENY_STOP"
    assert host.pending == task  # unresolved marker is not erased


def test_stop_after_a_but_before_b_denies_callback_entry():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)
    assert host.enter_a(task) == "A_ENTERED"
    host.latch_stop()
    assert host.enter_b(task) == "DENY_STOP"
    assert host.finish_a(task) == "A_FINISHED_FAKE"  # A may have residual work
    assert host.finish_b(task) == "DENY_B_NOT_INFLIGHT"
    assert not host.fake_wet
    assert host.confirm_fake_observation(task) == "UNKNOWN_PENDING"


def test_b_entry_winning_before_stop_may_finish_after_stop():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)
    assert host.enter_a(task) == "A_ENTERED"
    assert host.enter_b(task) == "B_ENTERED"
    host.latch_stop()
    assert host.finish_b(task) == "B_FINISHED_FAKE"
    assert host.finish_a(task) == "A_FINISHED_FAKE"
    assert host.events.index("ENTER_B") < host.events.index("STOP_LATCHED") < host.events.index("FAKE_EFFECT")
    assert host.confirm_fake_observation(task) == "FAKE_VERIFIED"
    assert host.stopped
    assert host.reserve(op("op-2")) == "DENY_STOP"


def test_missing_receipt_blocks_fresh_id_even_after_fake_effect():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)
    host.enter_a(task)
    host.enter_b(task)
    host.finish_b(task)
    host.finish_a(task)
    # Simulate a lost receipt: no confirm_fake_observation call.
    assert host.reserve(op("op-2")) == "DENY_UNRESOLVED"
    assert host.pending == task


def test_new_fake_epoch_does_not_rearm_pending_old_b():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)
    host.rotate_epoch()
    assert host.enter_a(task) == "DENY_STOP"
    assert host.enter_b(task) == "DENY_STOP"
    assert host.reserve(op("op-2", epoch="fake-load-2")) == "DENY_STOP"
    assert host.pending == task


def test_stop_is_monotonic_and_does_not_clear_on_epoch_rotation():
    host = FakeHostWaterFence()
    host.latch_stop()
    host.latch_stop()
    assert host.stop_revision == 1
    host.rotate_epoch()
    assert host.stopped
    assert host.reserve(op("new", epoch="fake-load-2")) == "DENY_STOP"


def test_wrong_operation_never_consumes_b_or_completes_a():
    host = FakeHostWaterFence()
    first, wrong = op(), op("op-other")
    host.reserve(first)
    host.enter_a(first)
    assert host.enter_b(wrong) == "DENY_STALE_OR_UNRESERVED"
    assert host.finish_a(wrong) == "DENY_A_NOT_INFLIGHT"
    assert host.enter_b(first) == "B_ENTERED"
    assert host.events.count("ENTER_B") == 1


def test_invalid_seat_action_target_and_epoch_owner_are_denied():
    for candidate in (op(seat="P1"), op(action="MARRY_NPC"), op(tile=(True, 5)),
                      op(tile=(-1, 5)), op(epoch="fake-load-2"), op(owner="intruder")):
        host = FakeHostWaterFence()
        assert host.reserve(candidate).startswith("DENY_")
        assert host.pending is None


def test_reentrant_callback_exception_leaves_unresolved_and_no_retry():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)

    def crash(_h, _task):
        raise RuntimeError("fake callback failure")

    try:
        host.run_a_with_callback(task, crash)
    except RuntimeError:
        pass
    else:
        raise AssertionError("injected fake callback must fail")
    assert host.pending == task
    assert host.a_entered and not host.a_finished
    assert host.reserve(op("another")) == "DENY_UNRESOLVED"


def test_only_internal_fake_completed_flow_can_resolve():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)
    host.enter_a(task)
    host.enter_b(task)
    assert host.confirm_fake_observation(task) == "UNKNOWN_PENDING"
    host.finish_b(task)
    assert host.confirm_fake_observation(task) == "UNKNOWN_PENDING"
    host.finish_a(task)
    assert host.confirm_fake_observation(task) == "FAKE_VERIFIED"
    assert host.reserve(op("fresh")) == "B_LINEAGE_RESERVED"


def test_no_effect_or_callback_without_a_entry():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)
    assert host.finish_b(task) == "DENY_B_NOT_INFLIGHT"
    assert host.enter_b(task) == "DENY_B_BEFORE_A"
    assert not host.fake_wet


def test_epoch_change_without_pending_still_revokes_old_owner_grant():
    host = FakeHostWaterFence()
    host.rotate_epoch()
    assert host.stopped
    assert host.reserve(op("new-op", epoch="fake-load-2")) == "DENY_STOP"


def test_equal_but_unissued_clone_cannot_enter_b_or_finish():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)
    host.enter_a(task)
    clone = op()  # equal fields do not constitute a host-issued object handle
    assert clone == task and clone is not task
    assert host.enter_b(clone) == "DENY_STALE_OR_UNRESERVED"
    assert host.finish_a(clone) == "DENY_A_NOT_INFLIGHT"
    assert host.enter_b(task) == "B_ENTERED"


def test_old_epoch_b_already_inflight_may_finish_but_cannot_clear_old_pending():
    host = FakeHostWaterFence()
    task = op()
    assert host.reserve(task) == "B_LINEAGE_RESERVED"
    assert host.enter_a(task) == "A_ENTERED"
    assert host.enter_b(task) == "B_ENTERED"

    host.rotate_epoch()
    assert host.stopped and host.epoch == "fake-load-2"
    assert host.finish_b(task) == "B_FINISHED_FAKE"  # residual may occur
    assert host.finish_a(task) == "A_FINISHED_FAKE"
    assert host.last_effect_evidence == FakeEffectEvidence(
        "op-1", "fake-load-1", "fake-host-p2", (4, 5)
    )
    assert host.events.index("FAKE_EPOCH_CHANGED") < host.events.index("FAKE_EFFECT")
    assert host.confirm_fake_observation(task) == "UNKNOWN_PENDING"
    assert host.pending is task
    assert "FAKE_OBSERVED_AND_RESOLVED" not in host.events
    assert host.reserve(op("op-2", epoch="fake-load-2")) == "DENY_STOP"


def test_mutable_equality_alias_for_seat_or_action_is_rejected_before_reserve():
    class EqualAlias:
        def __init__(self, text):
            self.text = text

        def __eq__(self, other):
            return self.text == other

    seat_alias = EqualAlias("P2")
    action_alias = EqualAlias("WATER")
    assert seat_alias == "P2" and action_alias == "WATER"
    for candidate in (
        op(seat=seat_alias), op(action=action_alias),
        op(seat=seat_alias, action=action_alias),
    ):
        host = FakeHostWaterFence()
        assert host.reserve(candidate) == "DENY_INVALID"
        assert host.pending is None
        assert not host.used_ids
        assert host.events == []
    seat_alias.text = "P1"
    action_alias.text = "OTHER"  # no mutable alias was ever retained


def test_same_epoch_fake_receipt_requires_matching_operation_load_owner_and_tile():
    host = FakeHostWaterFence()
    task = op()
    host.reserve(task)
    host.enter_a(task)
    host.enter_b(task)
    host.finish_b(task)
    host.finish_a(task)

    original = host.last_effect_evidence
    assert original is not None
    for bad in (
        FakeEffectEvidence("op-other", task.epoch, task.owner, task.tile),
        FakeEffectEvidence(task.operation_id, "fake-load-2", task.owner, task.tile),
        FakeEffectEvidence(task.operation_id, task.epoch, "other-owner", task.tile),
        FakeEffectEvidence(task.operation_id, task.epoch, task.owner, (99, 99)),
    ):
        host.last_effect_evidence = bad
        assert host.confirm_fake_observation(task) == "UNKNOWN_PENDING"
        assert host.pending is task
    host.last_effect_evidence = original
    assert host.confirm_fake_observation(task) == "FAKE_VERIFIED"
