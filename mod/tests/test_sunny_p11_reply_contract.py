"""Offline-only P11 reply classification. No network/model/game calls."""
from copy import deepcopy

from reference.sunny_p11_reply_contract import inspect_mcp_reply, stand_reply_hint


def response(*, ok=True, partial=False, reason="ok",
             text="Walked to (8,9)"):
    sc = {"ok": ok, "reason": reason}
    if partial:
        sc["partial"] = True
    return {
        "jsonrpc": "2.0", "id": 20013,
        "result": {
            "isError": not ok,
            "structuredContent": sc,
            "content": [{"type": "text", "text": text}],
        },
    }


def test_mcp_ack_only_requests_reobservation_not_verified_game_effect():
    seen = inspect_mcp_reply(response())
    assert seen.verdict == "ACK_REOBSERVE"
    assert seen.reason == "ok"
    assert seen.unresolved is False
    assert "VERIFIED" not in seen.verdict


def test_success_and_partial_must_not_be_reported_as_complete():
    seen = inspect_mcp_reply(response(partial=True, reason="interrupted"))
    assert seen.verdict == "UNKNOWN_PARTIAL"
    assert seen.unresolved is True


def test_even_ok_without_partial_but_non_ok_reason_is_unresolved():
    seen = inspect_mcp_reply(response(reason="no_path"))
    assert seen.verdict == "UNKNOWN_REASON"
    assert seen.unresolved


def test_declared_tool_failure_is_not_permission_to_blindly_retry():
    seen = inspect_mcp_reply(response(ok=False, reason="no_path", text="[no_path] blocked"))
    assert seen.verdict == "UNKNOWN_TOOL_FAILURE"
    assert seen.unresolved


def test_disagreement_between_iserror_and_structured_ok_is_unresolved():
    changed = response()
    changed["result"]["structuredContent"]["ok"] = False
    assert inspect_mcp_reply(changed).verdict == "UNKNOWN_CONTRADICTORY"
    changed2 = response(ok=False)
    changed2["result"]["structuredContent"]["ok"] = True
    assert inspect_mcp_reply(changed2).verdict == "UNKNOWN_CONTRADICTORY"


def test_jsonrpc_error_or_lost_result_never_counts_as_tool_result():
    for bad in (
        None, [], {}, {"jsonrpc": "2.0", "id": 20013,
                       "error": {"code": -32000, "message": "unknown"}},
        {"jsonrpc": "2.0", "id": 20013},
    ):
        assert inspect_mcp_reply(bad).unresolved


def test_wrong_fixed_id_or_version_does_not_count_as_ack():
    for altered in (
        {"id": 20014}, {"id": "20013"}, {"jsonrpc": "1.0"},
    ):
        reply = response()
        reply.update(altered)
        assert inspect_mcp_reply(reply).unresolved


def test_malformed_structured_result_missing_or_non_boolean_flags_not_ack():
    examples = [
        lambda r: r["result"].pop("structuredContent"),
        lambda r: r["result"]["structuredContent"].pop("ok"),
        lambda r: r["result"]["structuredContent"].update(ok="true"),
        lambda r: r["result"]["structuredContent"].update(partial="false"),
        lambda r: r["result"]["structuredContent"].update(reason=None),
        lambda r: r["result"].update(isError=0),
        lambda r: r["result"].update(content="a string instead of text segments"),
    ]
    for mutate in examples:
        reply = response()
        mutate(reply)
        assert inspect_mcp_reply(reply).verdict == "UNKNOWN_MALFORMED"


def test_malformed_content_text_never_certifies_effect():
    reply = response()
    reply["result"]["content"] = [{"type": "image", "text": "ok"}]
    assert inspect_mcp_reply(reply).verdict == "UNKNOWN_MALFORMED"
    reply["result"]["content"] = [{"type": "text", "text": 7}]
    assert inspect_mcp_reply(reply).verdict == "UNKNOWN_MALFORMED"


def test_stand_text_is_only_a_hint_for_subsequent_independent_observation():
    reply = response(text="Stood up from chair at (7,4)")
    ack = inspect_mcp_reply(reply)
    assert stand_reply_hint(ack, 7, 4) == "STAND_REOBSERVE"
    assert stand_reply_hint(ack, 8, 4) == "STAND_UNCONFIRMED"


def test_stand_text_with_partial_or_failure_is_not_sufficient_evidence():
    for kwargs in (
        {"partial": True, "reason": "interrupted"},
        {"ok": False, "reason": "other"},
    ):
        ack = inspect_mcp_reply(response(text="Stood up from chair at (7,4)", **kwargs))
        assert stand_reply_hint(ack, 7, 4) == "STAND_UNCONFIRMED"


def test_chair_interaction_ack_is_not_a_stand_reply():
    ack = inspect_mcp_reply(response(text="Interacted with (7,4)"))
    assert stand_reply_hint(ack, 7, 4) == "STAND_UNCONFIRMED"


def test_matching_fixed_id_not_proof_of_unique_action_attempt_or_effect():
    first = inspect_mcp_reply(response(text="Walked to (8,9)"))
    duplicate = inspect_mcp_reply(response(text="Walked to (8,9)"))
    assert first == duplicate
    assert first.verdict == "ACK_REOBSERVE"  # no attempt-specific verification


def test_never_accept_malformed_result_as_stand_evidence():
    result = inspect_mcp_reply({"jsonrpc": "2.0", "id": 20013,
                                "result": {"content": []}})
    assert stand_reply_hint(result, 7, 4) == "STAND_UNCONFIRMED"
