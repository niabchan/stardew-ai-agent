"""G0 fake post-action observation gate for P11 semantics — never game I/O.

Models how a future P2-only controller could avoid treating MCP replies and
aggregate /api/state coordinates as proof of *every* game effect. This is
synthetic, in-memory reference code; it NEVER authorizes real dispatch.
"""
from dataclasses import dataclass

from reference.sunny_p11_option_contract import P11Plan
from reference.sunny_p11_reply_contract import ReplyAssessment


@dataclass(frozen=True)
class FakeP2Snapshot:
    save: str = "synthetic-save"
    day: int = 1
    epoch: str = "fake-load-1"
    owner: str = "fake-p2-owner"
    revision: int = 1
    p1_human: bool = True
    p2_ai: bool = True
    p2_tile: tuple[int, int] = (3, 11)


@dataclass(frozen=True)
class FakeEffectDecision:
    status: str
    # This is ONLY a toy policy permitting an additional synthetic observation
    # round, never dispatch or proof of success in real Stardew/SMAPI.
    can_offer_next_fake_choice: bool = False


def assess_after_action(plan: P11Plan, reply: ReplyAssessment | None,
                        before: FakeP2Snapshot | None,
                        after: FakeP2Snapshot | None) -> FakeEffectDecision:
    """Conservative *fake* decision after an intended P11 selection.

    The caller supplies trusted-looking snapshots in tests; there is no
    authenticity or independent effect evidence in this function.
    """
    if not isinstance(plan, P11Plan):
        return FakeEffectDecision("BLOCKED_BAD_PLAN")
    if plan.verdict == "STAY_NO_DISPATCH":
        # Stay does not need an MCP reply. Do not busy-loop on the same snapshot.
        return FakeEffectDecision("STAY_AWAIT_NEW_OBSERVATION")
    if plan.verdict != "CONTRACT_ONLY":
        return FakeEffectDecision("BLOCKED_UNEXECUTABLE_PLAN")
    if not isinstance(reply, ReplyAssessment) or reply.verdict != "ACK_REOBSERVE":
        return FakeEffectDecision("STOP_UNRESOLVED_MCP_RESULT")
    if not isinstance(before, FakeP2Snapshot) or not isinstance(after, FakeP2Snapshot):
        return FakeEffectDecision("STOP_NO_RELIABLE_POST_OBSERVATION")
    if (before.save != after.save or before.day != after.day or
            before.epoch != after.epoch or before.owner != after.owner):
        return FakeEffectDecision("STOP_CHANGED_GAME_IDENTITY")
    if (not before.p1_human or not before.p2_ai or
            not after.p1_human or not after.p2_ai):
        return FakeEffectDecision("STOP_ROLE_CHANGED")
    if after.revision <= before.revision:
        return FakeEffectDecision("DEFER_NO_NEW_OBSERVATION")

    if plan.tool == "walk_to":
        target = (plan.arguments.get("x"), plan.arguments.get("y")) if isinstance(plan.arguments, dict) else None
        if target is None or after.p2_tile != target or before.p2_tile == after.p2_tile:
            return FakeEffectDecision("DEFER_FAKE_MOVE_NOT_CONFIRMED")
        # Moving the fake tile matches the selected destination, but source
        # authenticity/causation and pathing remain unproved in live game.
        return FakeEffectDecision("FAKE_MOVE_OBSERVED", True)

    if plan.tool == "interact":
        # The actual P11 /api/state had no reliable isSitting field; changed
        # coordinates or positive tool text MUST NOT be treated as seated/standing.
        return FakeEffectDecision("DEFER_CHAIR_STATE_UNPROVEN")
    if plan.tool == "watch_tv":
        # Position alone gives no evidence which channel played.
        return FakeEffectDecision("DEFER_TV_OUTCOME_UNPROVEN")
    if plan.tool == "say":
        # No proof that P1 heard it, nor that they consented to being interrupted.
        return FakeEffectDecision("DEFER_SPEECH_DELIVERY_UNPROVEN")
    return FakeEffectDecision("BLOCKED_UNKNOWN_TOOL")


@dataclass(frozen=True)
class FakeLoopMeaning:
    status: str
    selected_activity_completed: bool = False
    may_consider_fresh_fake_choice: bool = False


def interpret_run_once_report(outcome: str, journal_reason: str | None) -> FakeLoopMeaning:
    """Interpret *synthetic* scheduler signals without promoting tool ACKs.

    Extracted v0.3.10 run_once() (operator lines 253-304) returns 'success'
    for every journal result with ok=True except STAY. In particular
    'stood_only' means that the chair-exit prerequisite happened, but the
    selected move/TV action was deliberately NOT dispatched.

    This is an inert design aid, NOT a replacement for run_once() or a
    security boundary. A new in-game observation and independent gates are
    still necessary before attempting another real tool call.
    """
    if outcome == "stop":
        return FakeLoopMeaning("STOP_UNRESOLVED")
    if outcome == "deferred":
        return FakeLoopMeaning("DEFER_NO_DISPATCH")
    if outcome == "stay" and journal_reason == "stay":
        return FakeLoopMeaning("STAY_AWAIT_CHANGED_SCENE")
    if outcome != "success":
        return FakeLoopMeaning("STOP_UNRECOGNIZED_OUTCOME")
    if journal_reason == "stood_only":
        return FakeLoopMeaning("STAND_ONLY_REEVALUATE", may_consider_fresh_fake_choice=True)
    if journal_reason in ("unknown", "model_uncertain", "posture_uncertain",
                          "stand_unconfirmed", None):
        return FakeLoopMeaning("STOP_INCONSISTENT_SUCCESS")
    # Even a normal success is a controller report, not independent proof of
    # the intended game effect. Avoid marking the selected action complete.
    return FakeLoopMeaning("ACK_SUCCESS_REOBSERVE", may_consider_fresh_fake_choice=True)



# A typed, *synthetic* alternative to the historical short-term record
# {"action": selected_move_or_tv, "outcome": "stood_only"}.
# No raw MCP response, P1 chat or personal game data is accepted.
_INTENTS = frozenset({
    "stay", "move", "chair", "tv_weather", "tv_fortune", "speak",
})


@dataclass(frozen=True)
class FakeActivityMemory:
    selected_intent: str
    selected_activity_status: str
    prerequisite_status: str
    evidence_level: str
    claim_real_completion: bool = False
    blocks_new_choice: bool = False

    def as_synthetic_context(self):
        """Structured fields only; NEVER a real Luna or game prompt."""
        return {
            "selected_intent": self.selected_intent,
            "selected_activity_status": self.selected_activity_status,
            "prerequisite_status": self.prerequisite_status,
            "evidence_level": self.evidence_level,
            "claim_real_completion": self.claim_real_completion,
        }


def _intent_from_plan(plan):
    if not isinstance(plan, P11Plan):
        return None
    if plan.verdict == "STAY_NO_DISPATCH" and plan.option_id == "F0" and plan.tool is None:
        return "stay"
    if plan.verdict != "CONTRACT_ONLY" or not isinstance(plan.arguments, dict):
        return None
    match = {
        "walk_to": "move",
        "interact": "chair",
        "say": "speak",
    }
    if plan.tool in match:
        return match[plan.tool]
    if plan.tool == "watch_tv":
        channel = plan.arguments.get("channel")
        if channel in ("weather", "fortune"):
            return "tv_" + channel
    return None


def fake_activity_memory(plan, outcome, journal_reason, effect=None):
    """Project only an *intent and evidence status* from fake G0 inputs.

    Intentionally no "completed real action" status exists. Real-game
    completion needs authenticated P2 evidence unavailable in this pilot.
    """
    intent = _intent_from_plan(plan)
    if intent not in _INTENTS:
        return None
    meaning = interpret_run_once_report(outcome, journal_reason)
    if meaning.status in ("STOP_UNRESOLVED", "STOP_INCONSISTENT_SUCCESS",
                          "STOP_UNRECOGNIZED_OUTCOME"):
        return FakeActivityMemory(intent, "outcome_unresolved", "unknown",
                                  "journal_uncertain", blocks_new_choice=True)
    if meaning.status == "STAY_AWAIT_CHANGED_SCENE":
        if intent != "stay":
            return None
        return FakeActivityMemory(intent, "chose_no_action", "not_applicable",
                                  "controller_choice_only")
    if intent == "stay" or meaning.status == "DEFER_NO_DISPATCH":
        return FakeActivityMemory(intent, "not_executed", "not_applicable",
                                  "pre_dispatch_controller_report")
    if meaning.status == "STAND_ONLY_REEVALUATE":
        if intent not in ("move", "tv_weather", "tv_fortune"):
            return None
        # Even a positive "Stood..." text reply does not independently prove
        # posture in this game; source lacks a reliable isSitting sensor.
        return FakeActivityMemory(intent, "not_executed",
                                  "stand_acknowledged_not_independently_verified",
                                  "controller_report_only")
    if meaning.status != "ACK_SUCCESS_REOBSERVE":
        return None
    if (isinstance(effect, FakeEffectDecision)
            and effect.status == "FAKE_MOVE_OBSERVED" and intent == "move"):
        return FakeActivityMemory(intent, "synthetic_target_tile_observed",
                                  "not_applicable", "fake_world_only")
    return FakeActivityMemory(intent, "tool_reported_not_game_verified",
                              "not_applicable", "mcp_ack_only")


def fake_recent_activity_context(records):
    """At most six evidence-labeled, no-raw-text synthetic memory items.

    A blocked/unknown record disallows this pretend next-step context, rather
    than laundering unresolved changes into new model-facing history.
    """
    if not isinstance(records, (list, tuple)):
        return None
    if any(not isinstance(r, FakeActivityMemory) or r.blocks_new_choice for r in records):
        return None
    return [r.as_synthetic_context() for r in records[-6:]]
