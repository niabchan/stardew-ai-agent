"""Static, G0-only mapping of operator-inspected P11 v0.3.10 option IDs.

This contract consumes a caller-supplied *synthetic* options snapshot.
It DOES NOT authenticate or generate those offers, call Luna, touch games,
send JSON-RPC, inspect P1 availability, or authorize a side effect.
No entry point in the live Mod or local controller imports this module.
"""
from dataclasses import dataclass
import json
from typing import Any


FIXED_ACTIONS = {
    "F0": "stay",
    "F1": "chair",
    "F2": "tv_weather",
    "F3": "tv_fortune",
    "F4": "speak",
}
MOVE_IDS = frozenset(f"M{i}" for i in range(1, 9))
SUPPORTED_IDS = frozenset(FIXED_ACTIONS) | MOVE_IDS
COORDINATE_ACTIONS = frozenset(("chair", "move"))


@dataclass(frozen=True)
class P11Plan:
    verdict: str
    option_id: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    postcondition: str | None = None


def _safe_coordinate(value):
    # bool is an int subclass but never a valid game tile coordinate.
    return type(value) is int and 0 <= value < 200


def _valid_offers(options):
    if not isinstance(options, (tuple, list)) or not options:
        return False
    ids = set()
    for option in options:
        if not isinstance(option, dict):
            return False
        option_id = option.get("id")
        action = option.get("action")
        if type(option_id) is not str or option_id not in SUPPORTED_IDS or option_id in ids:
            return False
        if action != (("move" if option_id in MOVE_IDS else FIXED_ACTIONS[option_id])):
            return False
        if option.keys() - {"id", "action", "description", "x", "y"}:
            return False
        if "description" in option and type(option["description"]) is not str:
            return False
        has_coords = action in COORDINATE_ACTIONS
        if has_coords != ("x" in option and "y" in option):
            return False
        if has_coords and not (_safe_coordinate(option["x"]) and _safe_coordinate(option["y"])):
            return False
        if not has_coords and ("x" in option or "y" in option):
            return False
        ids.add(option_id)
    # In extracted v0.3.10 options_for() F0 is unconditional.
    return "F0" in ids


def plan_p11_choice(options, option_id, text=""):
    """Validate an offer ID and translate it into an INERT tool-shaped proposal.

    'CONTRACT_ONLY' means a dispatcher/authorization/post-effect observer is
    MISSING; callers must NOT treat this as an authorized executable action.
    """
    if not _valid_offers(options):
        return P11Plan("INVALID_OFFER_SNAPSHOT")
    if type(option_id) is not str or type(text) is not str:
        return P11Plan("INVALID_MODEL_REPLY")
    offered = {o["id"]: o for o in options}
    if option_id not in offered:
        return P11Plan("NOT_OFFERED", option_id)
    option = offered[option_id]
    action = option["action"]
    if action != "speak" and text:
        return P11Plan("INVALID_NON_SPEECH_TEXT", option_id)
    if action == "speak" and (not 1 <= len(text) <= 150 or "@" in text
                              or text != text.strip()
                              or any(ord(c) in (9, 10, 13, 60, 62, 92, 123, 125) for c in text)):
        # Extra conservative proposal-only restriction. Historical P11
        # checks 1..150 chars; the Mod's @name may interrupt human P1.
        return P11Plan("BLOCKED_SPEECH_POLICY", option_id)
    if action == "stay":
        return P11Plan("STAY_NO_DISPATCH", option_id, postcondition="no game call")
    if action == "move":
        return P11Plan("CONTRACT_ONLY", option_id, "walk_to",
                       {"x": option["x"], "y": option["y"],
                        "reason": "Sunny freeplay: chosen walk"},
                       "observe P2 position after movement; tool ACK alone is not enough")
    if action == "chair":
        return P11Plan("CONTRACT_ONLY", option_id, "interact",
                       {"x": option["x"], "y": option["y"],
                        "reason": "Sunny freeplay: chosen chair use"},
                       "observe actual P2 sit/stand state; moving near chair is not sitting")
    if action.startswith("tv_"):
        return P11Plan("CONTRACT_ONLY", option_id, "watch_tv",
                       {"channel": action.removeprefix("tv_"),
                        "reason": "Sunny freeplay: chosen TV"},
                       "observe TV-specific result; ACK alone is not enough")
    return P11Plan("CONTRACT_ONLY", option_id, "say", {"text": text},
                   "verify intended nearby P1 delivery without forced @name interrupt")


def inspect_p11_model_reply(response, options):
    """G0 contract check for the *shape* seen in extracted P11 lines 269-293.

    Only an INERT P11Plan is returned. This function does not call a provider,
    execute a tool, or decide whether the game was changed. It applies an
    additional conservative no-@ speech rule absent from the old controller.
    """
    if not isinstance(response, dict) or response.get("status") != "completed":
        return P11Plan("MODEL_INCOMPLETE_OR_UNAVAILABLE")
    output = response.get("output")
    if not isinstance(output, list):
        return P11Plan("INVALID_MODEL_REPLY")
    calls = [value for value in output if isinstance(value, dict) and value.get("type") == "function_call"]
    if len(calls) != 1 or calls[0].get("name") != "choose_sunny_freeplay":
        return P11Plan("INVALID_MODEL_REPLY")
    arguments = calls[0].get("arguments")
    if not isinstance(arguments, str):
        return P11Plan("INVALID_MODEL_REPLY")
    try:
        fields = json.loads(arguments)
    except (ValueError, TypeError):
        return P11Plan("INVALID_MODEL_REPLY")
    if not isinstance(fields, dict) or set(fields) != {"option_id", "text"}:
        return P11Plan("INVALID_MODEL_REPLY")
    if any(not isinstance(value, str) for value in fields.values()):
        return P11Plan("INVALID_MODEL_REPLY")
    return plan_p11_choice(options, fields["option_id"], fields["text"])
