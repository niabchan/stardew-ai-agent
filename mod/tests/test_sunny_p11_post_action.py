"""Pure G0 toy evidence checks: no Luna, game, HTTP or real authorization."""
from dataclasses import replace

from reference.sunny_p11_option_contract import plan_p11_choice
from reference.sunny_p11_post_action import FakeP2Snapshot, assess_after_action
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
