"""G0 only: sourced option-id grammar; no game/model/network integration."""
from reference.sunny_p11_option_contract import plan_p11_choice, inspect_p11_model_reply
import json


def offers(*extra):
    return [{"id": "F0", "action": "stay", "description": "No action"}, *extra]


def test_stay_is_explicit_and_never_dispatches():
    result = plan_p11_choice(offers(), "F0", "")
    assert result.verdict == "STAY_NO_DISPATCH"
    assert result.tool is None and result.arguments is None


def test_m1_movement_is_walk_not_chair_interact():
    result = plan_p11_choice(offers({"id": "M1", "action": "move", "x": 8, "y": 9}), "M1")
    assert result.verdict == "CONTRACT_ONLY"
    assert result.tool == "walk_to"
    assert (result.arguments["x"], result.arguments["y"]) == (8, 9)
    assert "position" in result.postcondition


def test_f1_chair_is_interact_and_not_verified_sit():
    result = plan_p11_choice(offers({"id": "F1", "action": "chair", "x": 7, "y": 4}), "F1")
    assert result.verdict == "CONTRACT_ONLY"
    assert result.tool == "interact"
    assert "sit/stand" in result.postcondition


def test_f2_f3_tv_channels_match_inspected_controller():
    options = offers(
        {"id": "F2", "action": "tv_weather"},
        {"id": "F3", "action": "tv_fortune"},
    )
    weather = plan_p11_choice(options, "F2")
    fortune = plan_p11_choice(options, "F3")
    assert weather.tool == fortune.tool == "watch_tv"
    assert weather.arguments["channel"] == "weather"
    assert fortune.arguments["channel"] == "fortune"


def test_f4_nearby_speech_maps_to_say_but_does_not_execute():
    result = plan_p11_choice(offers({"id": "F4", "action": "speak"}), "F4", "Hi, Guy!")
    assert result.verdict == "CONTRACT_ONLY"
    assert result.tool == "say"
    assert result.arguments == {"text": "Hi, Guy!"}


def test_f4_rejects_interrupting_at_name_extra_policy():
    result = plan_p11_choice(offers({"id": "F4", "action": "speak"}), "F4", "@Guy follow me!")
    assert result.verdict == "BLOCKED_SPEECH_POLICY"


def test_speech_requires_valid_length_and_non_speech_empty_text():
    choices = offers({"id": "F4", "action": "speak"})
    assert plan_p11_choice(choices, "F4", "").verdict == "BLOCKED_SPEECH_POLICY"
    assert plan_p11_choice(choices, "F4", "x" * 151).verdict == "BLOCKED_SPEECH_POLICY"
    assert plan_p11_choice(choices, "F0", "something").verdict == "INVALID_NON_SPEECH_TEXT"


def test_unoffered_action_id_is_not_accepted():
    result = plan_p11_choice(offers(), "F4", "Hello!")
    assert result.verdict == "NOT_OFFERED"
    assert result.tool is None


def test_fake_option_injection_cannot_add_fireplace_or_marriage():
    for name in ("FIREPLACE_TOGGLE", "MARRY_NPC"):
        malformed = offers({"id": name, "action": "chair", "x": 7, "y": 4})
        assert plan_p11_choice(malformed, name).verdict == "INVALID_OFFER_SNAPSHOT"


def test_injected_mismatched_id_action_blocked():
    corrupted = offers({"id": "F1", "action": "move", "x": 7, "y": 4})
    assert plan_p11_choice(corrupted, "F1").verdict == "INVALID_OFFER_SNAPSHOT"


def test_duplicate_id_missing_f0_or_extra_args_rejected():
    duplicates = offers({"id": "F0", "action": "stay"})
    missing_stay = [{"id": "F1", "action": "chair", "x": 7, "y": 4}]
    extra_argument = offers({"id": "F2", "action": "tv_weather", "channel": "fortune"})
    for options in (duplicates, missing_stay, extra_argument):
        assert plan_p11_choice(options, "F0").verdict == "INVALID_OFFER_SNAPSHOT"


def test_bool_negative_and_non_integer_tiles_are_not_accepted():
    for x, y in ((True, 3), (-1, 3), (2.5, 3), (3, "4"), (4097, 1)):
        options = offers({"id": "M1", "action": "move", "x": x, "y": y})
        assert plan_p11_choice(options, "M1").verdict == "INVALID_OFFER_SNAPSHOT"


def test_p11_model_choice_does_not_supply_new_target_coordinates():
    options = offers({"id": "M1", "action": "move", "x": 4, "y": 5})
    result = plan_p11_choice(options, "M1")
    assert result.arguments["x"] == 4
    assert result.arguments["y"] == 5
    assert plan_p11_choice(options, {"option_id": "M1", "x": 99}).verdict == "INVALID_MODEL_REPLY"


def test_speaking_cannot_be_inferred_from_absence_of_f4():
    no_nearby_p1 = offers({"id": "M1", "action": "move", "x": 1, "y": 2})
    assert plan_p11_choice(no_nearby_p1, "F4", "Hi!").verdict == "NOT_OFFERED"


def test_non_string_text_rejected():
    result = plan_p11_choice(offers({"id": "F4", "action": "speak"}), "F4", None)
    assert result.verdict == "INVALID_MODEL_REPLY"


def synthetic_reply(option_id="F0", text="", *, status="completed", function_name="choose_sunny_freeplay"):
    """Synthetic model envelope, never obtained from the provider."""
    return {
        "status": status,
        "output": [{
            "type": "function_call",
            "name": function_name,
            "arguments": json.dumps({"option_id": option_id, "text": text}),
        }],
    }


def test_p11_model_envelope_maps_offered_chair_to_inert_interact_not_move():
    options = offers({"id": "F1", "action": "chair", "x": 7, "y": 4})
    plan = inspect_p11_model_reply(synthetic_reply("F1"), options)
    assert plan.verdict == "CONTRACT_ONLY"
    assert plan.tool == "interact"
    assert (plan.arguments["x"], plan.arguments["y"]) == (7, 4)


def test_p11_model_envelope_stay_has_no_game_dispatch():
    plan = inspect_p11_model_reply(synthetic_reply("F0"), offers())
    assert plan.verdict == "STAY_NO_DISPATCH"
    assert plan.tool is None and plan.arguments is None


def test_p11_model_incomplete_or_invalid_transport_envelope_is_not_executable():
    for reply in (None, [], {}, {"status": "in_progress", "output": []},
                  {"status": "failed", "output": []}):
        assert inspect_p11_model_reply(reply, offers()).verdict == "MODEL_INCOMPLETE_OR_UNAVAILABLE"


def test_p11_model_must_supply_exactly_one_named_function_call():
    bad_name = synthetic_reply(function_name="choose_other")
    multiple = synthetic_reply()
    multiple["output"].append(multiple["output"][0].copy())
    missing = {"status": "completed", "output": []}
    wrong_output = {"status": "completed", "output": "invalid"}
    for reply in (bad_name, multiple, missing, wrong_output):
        assert inspect_p11_model_reply(reply, offers()).verdict == "INVALID_MODEL_REPLY"


def test_p11_model_arguments_must_be_valid_json_exact_two_string_fields():
    for raw in ('{', 'null', '[]', '{}',
                '{"option_id":"F0"}',
                '{"option_id":"F0","text":"","x":8}',
                '{"option_id":4,"text":""}',
                '{"option_id":"F0","text":false}'):
        reply = synthetic_reply()
        reply["output"][0]["arguments"] = raw
        assert inspect_p11_model_reply(reply, offers()).verdict == "INVALID_MODEL_REPLY"


def test_p11_model_cannot_choose_unoffered_speech_or_add_coordinates():
    reply = synthetic_reply("F4", "Hello Guy")
    assert inspect_p11_model_reply(reply, offers()).verdict == "NOT_OFFERED"
    options = offers({"id": "M1", "action": "move", "x": 2, "y": 3})
    reply = synthetic_reply()
    reply["output"][0]["arguments"] = json.dumps(
        {"option_id": "M1", "text": "", "x": 99, "y": 99}
    )
    assert inspect_p11_model_reply(reply, options).verdict == "INVALID_MODEL_REPLY"


def test_p11_speech_filter_rejects_source_unsafe_controls_and_padded_text():
    opts = offers({"id": "F4", "action": "speak"})
    for speech in (" hi", "hi ", "hello\nGuy", "hello\rGuy", "hello\tGuy",
                   "<hi>", "{hi}", "hi\\Guy", "@" + "Guy", ""):
        result = inspect_p11_model_reply(synthetic_reply("F4", speech), opts)
        assert result.verdict == "BLOCKED_SPEECH_POLICY"
        assert result.tool is None
    assert inspect_p11_model_reply(synthetic_reply("F4", "Hi, Guy!"), opts).tool == "say"


def test_p11_non_speech_text_must_be_empty_and_cannot_disguise_a_second_action():
    assert inspect_p11_model_reply(synthetic_reply("F0", "speak"), offers()).verdict == "INVALID_NON_SPEECH_TEXT"
    reply = synthetic_reply()
    reply["output"].append({"type": "message", "content": "untrusted narrative"})
    # Historical P11 filters only function_call items: unrelated output
    # is not executable, and cannot override the validated selected ID.
    result = inspect_p11_model_reply(reply, offers())
    assert result.verdict == "STAY_NO_DISPATCH"
