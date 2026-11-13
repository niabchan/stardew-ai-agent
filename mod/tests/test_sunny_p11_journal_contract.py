"""Only pure proposed P11 journal events; no real log/controller/game calls."""
from dataclasses import replace

from reference.sunny_p11_journal_contract import ProposedScope, audit_synthetic_journal


SCOPE = ProposedScope("fake-policy", "synthetic-Test_save", 3, "fake-epoch-7",
                      "fake-owner", "fake-attempt-17", "fake-operation-19", "move")


def row(phase, scope=SCOPE, **extra):
    values = {"phase": phase, "policy": scope.policy, "save": scope.save,
              "day": scope.day, "epoch": scope.epoch, "owner": scope.owner,
              "attempt_id": scope.attempt_id, "operation_id": scope.operation_id,
              "intent": scope.intent}
    values.update(extra)
    return values


def good_move():
    return [row("reserved"), row("choice", selected_intent="move"),
            row("dispatch", purpose="selected_action"),
            row("result", ok=True, reason="ok")]


def test_normal_action_is_only_tool_ack_never_verified_game_effect():
    outcome = audit_synthetic_journal(good_move(), SCOPE)
    assert (outcome.status, outcome.blocks_next_choice) == ("ACK_REOBSERVE", False)
    assert outcome.real_effect_verified is False
    assert outcome.selected_activity_completed is False
    assert outcome.new_mutation_authorized is False


def test_stay_requires_choice_and_no_dispatch():
    scope = replace(SCOPE, intent="stay")
    rows = [row("reserved", scope), row("choice", scope, selected_intent="stay"),
            row("result", scope, ok=True, reason="stay")]
    outcome = audit_synthetic_journal(rows, scope)
    assert outcome.status == "STAY_AWAIT_CHANGE"
    assert outcome.new_mutation_authorized is False
    assert audit_synthetic_journal([*rows[:2], row("dispatch", scope, purpose="selected_action"), rows[2]], scope).blocks_next_choice


def test_stand_prerequisite_does_not_complete_original_tv():
    scope = replace(SCOPE, intent="tv_weather")
    rows = [row("reserved", scope), row("choice", scope, selected_intent="tv_weather"),
            row("dispatch", scope, purpose="stand_prerequisite"),
            row("result", scope, ok=True, reason="stood_only")]
    result = audit_synthetic_journal(rows, scope)
    assert result.status == "PREREQUISITE_ACK_REOBSERVE"
    assert result.selected_activity_completed is False
    assert result.real_effect_verified is False


def test_pre_dispatch_abort_is_not_permission_to_replay_mutation():
    rows = [row("reserved"), row("result", ok=False, reason="pre_dispatch_aborted")]
    result = audit_synthetic_journal(rows, SCOPE)
    assert result.status == "DEFER_REOBSERVE"
    assert not result.new_mutation_authorized
    rows.insert(1, row("dispatch", purpose="selected_action"))
    assert audit_synthetic_journal(rows, SCOPE).status == "STOP_UNRESOLVED"


def test_synthetic_unknown_or_missing_result_latches_stop():
    rows = good_move()
    for bad in ([*rows[:3]], [*rows[:3], row("result", ok=False, reason="unknown")], []):
        result = audit_synthetic_journal(bad, SCOPE)
        assert result.status == "STOP_UNRESOLVED" and result.blocks_next_choice


def test_duplicate_reservations_and_results_cannot_last_row_win():
    rows = good_move()
    for bad in ([rows[0], rows[0], *rows[1:]], [*rows, rows[-1]],
                [*rows[:-1], row("result", ok=False, reason="unknown"), rows[-1]]):
        assert audit_synthetic_journal(bad, SCOPE).status == "STOP_UNRESOLVED"


def test_late_concurrent_reservation_and_foreign_operation_cannot_disappear():
    rows = good_move()
    other = row("reserved", replace(SCOPE, attempt_id="other-attempt"))
    assert audit_synthetic_journal([*rows, other], SCOPE).blocks_next_choice
    assert audit_synthetic_journal([rows[0], other, *rows[1:]], SCOPE).blocks_next_choice


def test_result_before_reservation_or_dispatch_or_choice_fails():
    rows = good_move()
    for bad in ([rows[-1], *rows[:-1]], [rows[0], rows[2], rows[1], rows[3]],
                [rows[0], rows[1], rows[3], rows[2]]):
        assert audit_synthetic_journal(bad, SCOPE).status == "STOP_UNRESOLVED"


def test_foreign_scope_result_rejected_including_epoch_and_operation_id():
    rows = good_move()
    changes = ({"policy": "bad-policy"}, {"save": "other-save"}, {"day": 4},
               {"epoch": "different-epoch"}, {"owner": "other-owner"},
               {"attempt_id": "other-attempt"}, {"operation_id": "other-op"},
               {"intent": "speak"})
    for changed in changes:
        bad = [*rows[:-1], {**rows[-1], **changed}]
        assert audit_synthetic_journal(bad, SCOPE).blocks_next_choice


def test_stray_dispatch_unknown_phase_or_unexpected_reply_text_fails():
    rows = good_move()
    for bad in ([rows[0], row("dispatch", purpose="selected_action", attempt_id="foreign"), *rows[1:]],
                [*rows[:-1], row("noise", arbitrary="x"), rows[-1]],
                [*rows[:-1], {**rows[-1], "reply": "private-chat"}]):
        assert audit_synthetic_journal(bad, SCOPE).blocks_next_choice


def test_bool_day_or_result_ok_or_bad_records_fail_closed_without_exception():
    rows = good_move()
    for bad in ([{**rows[0], "day": True}, *rows[1:]],
                [*rows[:-1], {**rows[-1], "ok": 1}],
                [rows[0], [], *rows[1:]],
                [*rows[:-1], {**rows[-1], "reason": []}]):
        assert audit_synthetic_journal(bad, SCOPE).blocks_next_choice
    assert audit_synthetic_journal(rows, replace(SCOPE, day=True)).blocks_next_choice


def test_missing_choice_or_mismatched_choice_cannot_become_ack():
    rows = good_move()
    assert audit_synthetic_journal([rows[0], *rows[2:]], SCOPE).blocks_next_choice
    rows[1] = {**rows[1], "selected_intent": "speak"}
    assert audit_synthetic_journal(rows, SCOPE).blocks_next_choice


def test_stop_flag_blocks_even_seemingly_good_journal():
    result = audit_synthetic_journal(good_move(), SCOPE, stop_requested=True)
    assert result.status == "STOP_REQUESTED" and result.blocks_next_choice
    assert audit_synthetic_journal(good_move(), SCOPE, stop_requested="false").blocks_next_choice


def test_legacy_rows_without_host_scope_rejected_not_migrated_as_proof():
    legacy = [{"phase": "reserved", "policy": "fake-policy", "attempt_id": "a"},
              {"phase": "result", "attempt_id": "a", "ok": True, "reason": "ok"}]
    result = audit_synthetic_journal(legacy, SCOPE)
    assert result.status == "STOP_UNRESOLVED"
    assert result.real_effect_verified is False


def test_malformed_caller_scope_and_unbounded_log_segments_fail_closed():
    assert audit_synthetic_journal(good_move(), None).blocks_next_choice
    assert audit_synthetic_journal(good_move() * 17, SCOPE).blocks_next_choice
    assert audit_synthetic_journal("not-a-list", SCOPE).blocks_next_choice
    assert audit_synthetic_journal(good_move(), replace(SCOPE, owner=" ")).blocks_next_choice


def test_unhashable_expected_intent_fails_closed_not_typeerror():
    result = audit_synthetic_journal(good_move(), replace(SCOPE, intent=[]))
    assert result.status == "STOP_UNRESOLVED"
