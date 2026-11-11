"""Pure G0 toy evidence checks: no Luna, game, HTTP or real authorization."""
from dataclasses import replace

from reference.sunny_p11_option_contract import plan_p11_choice
from reference.sunny_p11_post_action import (FakeP2Snapshot, assess_after_action,
    interpret_run_once_report, fake_activity_memory, fake_recent_activity_context,
    FakeActivityMemory)
from reference.sunny_p11_reply_contract import inspect_mcp_reply


def options(*others):
    return [{"id": "F0", "action": "stay"}, *others]


def plan(action):
    choices = {
        "move": [{"id": "M1", "action": "move", "x": 8, "y": 9}],
        "chair": [{"id": "F1", "action": "chair", "x": 7, "y": 4}],
        "tv": [{"id": "F2", "action": "tv_weather"}],
        "speak": [{"id": "F4", "action": "speak"}],
    }
    name = {"move": "M1", "chair": "F1", "tv": "F2", "speak": "F4"}[action]
    return plan_p11_choice(options(*choices[action]), name, "Hello, Guy!" if action == "speak" else "")


def reply(*, ok=True, partial=False, reason="ok", text="Tool replied."):
    s = {"ok": ok, "reason": reason}
    if partial:
        s["partial"] = True
    return inspect_mcp_reply({
        "jsonrpc": "2.0", "id": 20013,
        "result": {"isError": not ok, "structuredContent": s,
                   "content": [{"type": "text", "text": text}]},
    })


def test_move_requires_fresh_fake_p2_tile_at_chosen_target():
    before = FakeP2Snapshot()
    after = replace(before, revision=2, p2_tile=(8, 9))
    result = assess_after_action(plan("move"), reply(), before, after)
    assert result.status == "FAKE_MOVE_OBSERVED"
    assert result.can_offer_next_fake_choice
    assert "VERIFIED" not in result.status


def test_ack_with_old_or_wrong_tile_cannot_make_new_choice_safe():
    before = FakeP2Snapshot()
    for after in (before, replace(before, revision=2),
                  replace(before, revision=2, p2_tile=(5, 8))):
        result = assess_after_action(plan("move"), reply(), before, after)
        assert result.can_offer_next_fake_choice is False


def test_tool_success_without_fresh_observation_blocks_more_actions():
    before = FakeP2Snapshot()
    result = assess_after_action(plan("move"), reply(), before, None)
    assert result.status == "STOP_NO_RELIABLE_POST_OBSERVATION"
    assert not result.can_offer_next_fake_choice


def test_partial_even_with_arrived_p2_position_remains_unresolved():
    before = FakeP2Snapshot()
    after = replace(before, revision=2, p2_tile=(8, 9))
    result = assess_after_action(plan("move"), reply(partial=True, reason="interrupted"), before, after)
    assert result.status == "STOP_UNRESOLVED_MCP_RESULT"
    assert not result.can_offer_next_fake_choice


def test_tool_failure_cannot_be_relabeled_success_by_matching_coordinates():
    before = FakeP2Snapshot()
    after = replace(before, revision=2, p2_tile=(8, 9))
    result = assess_after_action(plan("move"), reply(ok=False, reason="no_path"), before, after)
    assert result.status == "STOP_UNRESOLVED_MCP_RESULT"


def test_unknown_mcp_result_stops_without_even_post_snapshot():
    result = assess_after_action(plan("move"), None, FakeP2Snapshot(), None)
    assert result.status == "STOP_UNRESOLVED_MCP_RESULT"


def test_same_day_but_new_load_epoch_is_not_same_world():
    before = FakeP2Snapshot()
    after = replace(before, revision=2, p2_tile=(8, 9), epoch="fake-load-2")
    result = assess_after_action(plan("move"), reply(), before, after)
    assert result.status == "STOP_CHANGED_GAME_IDENTITY"


def test_other_save_day_or_owner_stops_result_promotion():
    before = FakeP2Snapshot()
    for changes in ({"save": "other-save"}, {"day": 2}, {"owner": "other-owner"}):
        after = replace(before, revision=2, p2_tile=(8, 9), **changes)
        result = assess_after_action(plan("move"), reply(), before, after)
        assert result.status == "STOP_CHANGED_GAME_IDENTITY"


def test_human_p1_and_ai_p2_required_before_and_after():
    before = FakeP2Snapshot()
    after = replace(before, revision=2, p2_tile=(8, 9))
    for field in ("p1_human", "p2_ai"):
        assert assess_after_action(plan("move"), reply(), replace(before, **{field: False}), after).status == "STOP_ROLE_CHANGED"
        assert assess_after_action(plan("move"), reply(), before, replace(after, **{field: False})).status == "STOP_ROLE_CHANGED"


def test_chair_ack_and_same_tile_do_not_prove_sitting_or_standing():
    before = FakeP2Snapshot(p2_tile=(7, 4))
    after = replace(before, revision=2)
    result = assess_after_action(plan("chair"),
        reply(text="Stood up from chair at (7,4)"), before, after)
    assert result.status == "DEFER_CHAIR_STATE_UNPROVEN"
    assert not result.can_offer_next_fake_choice


def test_tv_ack_with_movement_has_no_verified_channel_playback():
    before = FakeP2Snapshot()
    after = replace(before, revision=2, p2_tile=(8, 9))
    result = assess_after_action(plan("tv"), reply(text="Watched weather"), before, after)
    assert result.status == "DEFER_TV_OUTCOME_UNPROVEN"
    assert not result.can_offer_next_fake_choice


def test_speech_ack_cannot_prove_human_heard_or_is_free():
    before = FakeP2Snapshot()
    after = replace(before, revision=2)
    result = assess_after_action(plan("speak"),
        reply(text="Heard by Guy"), before, after)
    assert result.status == "DEFER_SPEECH_DELIVERY_UNPROVEN"
    assert not result.can_offer_next_fake_choice


def test_stay_never_needs_mcp_ack_or_immediately_replans():
    stay = plan_p11_choice(options(), "F0", "")
    result = assess_after_action(stay, None, FakeP2Snapshot(), None)
    assert result.status == "STAY_AWAIT_NEW_OBSERVATION"
    assert not result.can_offer_next_fake_choice


def test_unoffered_or_unexecutable_plan_never_acts():
    p = plan_p11_choice(options(), "F4", "hello")
    result = assess_after_action(p, reply(), FakeP2Snapshot(), replace(FakeP2Snapshot(), revision=2))
    assert result.status == "BLOCKED_UNEXECUTABLE_PLAN"
    assert not result.can_offer_next_fake_choice


def test_no_p1_private_messages_in_post_action_snapshot():
    from dataclasses import fields
    names = {f.name for f in fields(FakeP2Snapshot)}
    assert not any(term in name for name in names
                   for term in ("diary", "chat", "message", "feed", "inventory", "secret"))


def test_p11_loop_stop_for_unknown_game_effect_is_not_a_replan():
    meaning = interpret_run_once_report("stop", "unknown")
    assert meaning.status == "STOP_UNRESOLVED"
    assert not meaning.may_consider_fresh_fake_choice
    assert not meaning.selected_activity_completed


def test_p11_loop_stand_only_must_not_mark_selected_move_completed():
    meaning = interpret_run_once_report("success", "stood_only")
    assert meaning.status == "STAND_ONLY_REEVALUATE"
    assert meaning.may_consider_fresh_fake_choice
    assert not meaning.selected_activity_completed


def test_p11_loop_stand_only_must_not_mark_selected_tv_completed():
    # The same stand-only journal reason is used before TV and before MOVE.
    result = interpret_run_once_report("success", "stood_only")
    assert not result.selected_activity_completed


def test_p11_loop_stay_does_not_complete_any_activity():
    meaning = interpret_run_once_report("stay", "stay")
    assert meaning.status == "STAY_AWAIT_CHANGED_SCENE"
    assert not meaning.may_consider_fresh_fake_choice


def test_p11_loop_pre_dispatch_defer_is_not_retrying_selected_tool():
    meaning = interpret_run_once_report("deferred", "option_changed")
    assert meaning.status == "DEFER_NO_DISPATCH"
    assert not meaning.may_consider_fresh_fake_choice


def test_p11_loop_ack_success_still_does_not_prove_game_effect():
    meaning = interpret_run_once_report("success", "ok")
    assert meaning.status == "ACK_SUCCESS_REOBSERVE"
    assert meaning.may_consider_fresh_fake_choice
    assert not meaning.selected_activity_completed


def test_inconsistent_success_unknown_reason_must_not_promote_activity():
    for reason in ("unknown", "model_uncertain", "posture_uncertain",
                   "stand_unconfirmed", None):
        meaning = interpret_run_once_report("success", reason)
        assert meaning.status == "STOP_INCONSISTENT_SUCCESS"
        assert not meaning.may_consider_fresh_fake_choice


def test_unknown_scheduler_result_fails_closed():
    meaning = interpret_run_once_report("unexpected", "ok")
    assert meaning.status == "STOP_UNRECOGNIZED_OUTCOME"
    assert not meaning.may_consider_fresh_fake_choice



def test_stand_before_tv_remembers_original_tv_not_executed():
    record = fake_activity_memory(plan("tv"), "success", "stood_only")
    assert record.selected_intent == "tv_weather"
    assert record.selected_activity_status == "not_executed"
    assert record.prerequisite_status == "stand_acknowledged_not_independently_verified"
    assert not record.claim_real_completion


def test_stand_before_move_does_not_become_walked():
    record = fake_activity_memory(plan("move"), "success", "stood_only")
    assert record.selected_intent == "move"
    assert record.selected_activity_status == "not_executed"
    assert record.evidence_level == "controller_report_only"


def test_mcp_success_only_stores_unverified_selected_activity():
    for intent in ("move", "chair", "tv", "speak"):
        record = fake_activity_memory(plan(intent), "success", "ok")
        assert record.selected_activity_status == "tool_reported_not_game_verified"
        assert record.evidence_level == "mcp_ack_only"
        assert not record.claim_real_completion


def test_stay_is_an_explicit_no_action_choice():
    p = plan_p11_choice(options(), "F0", "")
    record = fake_activity_memory(p, "stay", "stay")
    assert record.selected_intent == "stay"
    assert record.selected_activity_status == "chose_no_action"
    assert not record.claim_real_completion


def test_deferred_choice_is_not_an_executed_activity():
    record = fake_activity_memory(plan("move"), "deferred", "option_changed")
    assert record.selected_activity_status == "not_executed"
    assert record.evidence_level == "pre_dispatch_controller_report"


def test_uncertain_action_is_blocked_from_next_synthetic_context():
    unresolved = fake_activity_memory(plan("chair"), "stop", "unknown")
    assert unresolved.blocks_new_choice
    assert unresolved.selected_activity_status == "outcome_unresolved"
    assert fake_recent_activity_context([unresolved]) is None


def test_inconsistent_report_stays_unresolved():
    record = fake_activity_memory(plan("speak"), "success", "unknown")
    assert record.blocks_new_choice
    assert fake_recent_activity_context([record]) is None


def test_fake_move_observation_never_becomes_real_completed_game_action():
    before = FakeP2Snapshot()
    after = replace(before, revision=2, p2_tile=(8, 9))
    fake_effect = assess_after_action(plan("move"), reply(), before, after)
    record = fake_activity_memory(plan("move"), "success", "ok", fake_effect)
    assert record.selected_activity_status == "synthetic_target_tile_observed"
    assert record.evidence_level == "fake_world_only"
    assert not record.claim_real_completion


def test_mismatched_evidence_never_claims_tv_succeeded():
    fake_effect = assess_after_action(plan("move"), reply(),
        FakeP2Snapshot(), replace(FakeP2Snapshot(), revision=2, p2_tile=(8, 9)))
    record = fake_activity_memory(plan("tv"), "success", "ok", fake_effect)
    assert record.selected_activity_status == "tool_reported_not_game_verified"
    assert not record.claim_real_completion


def test_unsupported_plan_does_not_create_activity_memory():
    p = plan_p11_choice(options(), "F4", "Hello")
    assert fake_activity_memory(p, "success", "ok") is None


def test_stand_only_not_accepted_for_chair_or_speech():
    for activity in ("chair", "speak"):
        assert fake_activity_memory(plan(activity), "success", "stood_only") is None


def test_synthetic_context_bounded_to_six_and_structured_no_raw_reply():
    records = [fake_activity_memory(plan("move"), "deferred", "option_changed")
               for _ in range(9)]
    result = fake_recent_activity_context(records)
    assert len(result) == 6
    assert all(item["selected_intent"] == "move" for item in result)
    assert all("reply" not in item and "text" not in item for item in result)
    assert all(item["claim_real_completion"] is False for item in result)


def test_prior_unresolved_record_blocks_next_context_even_if_many_new_items():
    unknown = fake_activity_memory(plan("move"), "stop", "unknown")
    records = [unknown] + [fake_activity_memory(plan("move"), "deferred", "option_changed")
                           for _ in range(7)]
    assert fake_recent_activity_context(records) is None


def test_intent_memory_record_fields_exclude_private_human_content():
    from dataclasses import fields
    names = {f.name for f in fields(FakeActivityMemory)}
    assert names == {"selected_intent", "selected_activity_status",
                     "prerequisite_status", "evidence_level",
                     "claim_real_completion", "blocks_new_choice"}
