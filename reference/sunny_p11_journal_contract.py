"""G0-only, fail-closed *proposed* journal-event contract for Sunny P11.

No filesystem, JSONL reader, HTTP, MCP, model, SMAPI or game access.
This schema is deliberately more demanding than the partially inspected
extracted v0.3.10 sunny_loop.py (243-304); it is NOT a parser of its live log.
All expected identities and journal rows here are synthetic, caller-supplied,
not authenticated. A positive outcome never proves a real game effect.
"""
from dataclasses import dataclass


INTENTS = frozenset(("stay", "move", "chair", "tv_weather", "tv_fortune", "speak"))
BASE_KEYS = frozenset(("phase", "policy", "save", "day", "epoch", "owner",
                       "attempt_id", "operation_id", "intent"))
PHASE_EXTRA = {
    "reserved": frozenset(),
    "choice": frozenset(("selected_intent",)),
    "dispatch": frozenset(("purpose",)),
    "result": frozenset(("ok", "reason")),
}


@dataclass(frozen=True)
class ProposedScope:
    policy: str
    save: str
    day: int
    epoch: str
    owner: str
    attempt_id: str
    operation_id: str
    intent: str


@dataclass(frozen=True)
class G0JournalAssessment:
    status: str
    detail: str
    # Shape validation alone cannot release a choice or resolve pending effects.
    blocks_next_choice: bool = True
    # Never real action authorization or actual gameplay completion.
    new_mutation_authorized: bool = False
    selected_activity_completed: bool = False
    real_effect_verified: bool = False


def _stop(detail: str) -> G0JournalAssessment:
    return G0JournalAssessment("STOP_UNRESOLVED", detail)


def _scope_valid(scope: ProposedScope) -> bool:
    if type(scope) is not ProposedScope or type(scope.day) is not int or scope.day < 1:
        return False
    if type(scope.intent) is not str or scope.intent not in INTENTS:
        return False
    return all(type(value) is str and 1 <= len(value) <= 128 and value == value.strip()
               for value in (scope.policy, scope.save, scope.epoch, scope.owner,
                             scope.attempt_id, scope.operation_id))


def audit_synthetic_journal(rows, scope: ProposedScope, *, stop_requested=False):
    """One strict proposed event segment, with a separately expected scope.

    This deliberately cannot interpret an arbitrary historic JSONL segment:
    the old last-reservation extractor did not require epoch/owner/operation_id
    or a dispatch purpose. Requiring them is a *proposed future* contract.
    No verdict here lets a caller send an effectful game operation.
    """
    if type(stop_requested) is not bool or not _scope_valid(scope):
        return _stop("invalid_expected_scope_or_stop_signal")
    if stop_requested:
        return G0JournalAssessment("STOP_REQUESTED", "caller_reported_stop")
    if type(rows) not in (list, tuple) or not 1 <= len(rows) <= 64:
        return _stop("missing_or_unbounded_segment")

    values = {"policy": scope.policy, "save": scope.save, "day": scope.day,
              "epoch": scope.epoch, "owner": scope.owner,
              "attempt_id": scope.attempt_id,
              "operation_id": scope.operation_id, "intent": scope.intent}
    phases = []
    for row in rows:
        if type(row) is not dict:
            return _stop("malformed_row")
        phase = row.get("phase")
        if type(phase) is not str or phase not in PHASE_EXTRA:
            return _stop("unknown_phase")
        if set(row) != BASE_KEYS | PHASE_EXTRA[phase]:
            return _stop("malformed_or_unexpected_fields")
        for name, expected in values.items():
            if type(row[name]) is not type(expected) or row[name] != expected:
                return _stop("mismatched_attempt_scope")
        phases.append(phase)
    if phases.count("reserved") != 1 or phases.count("result") != 1:
        return _stop("ambiguous_reservation_or_result")
    if phases.count("choice") > 1 or phases.count("dispatch") > 1:
        return _stop("duplicate_choice_or_dispatch")
    if phases[0] != "reserved" or phases[-1] != "result":
        return _stop("out_of_order_events")
    if phases != [p for p in ("reserved", "choice", "dispatch", "result") if p in phases]:
        return _stop("out_of_order_events")

    result = rows[-1]
    if type(result["ok"]) is not bool or type(result["reason"]) is not str:
        return _stop("malformed_result")
    choice = next((r for r in rows if r["phase"] == "choice"), None)
    dispatch = next((r for r in rows if r["phase"] == "dispatch"), None)
    if choice is not None and (type(choice["selected_intent"]) is not str or
                               choice["selected_intent"] != scope.intent):
        return _stop("choice_not_bound_to_intent")
    if dispatch is not None and (type(dispatch["purpose"]) is not str or
                                 dispatch["purpose"] not in ("selected_action", "stand_prerequisite")):
        return _stop("unknown_dispatch_purpose")

    if result["ok"] is False:
        if dispatch is None and result["reason"] == "pre_dispatch_aborted":
            # A fake no-dispatch journal is not proof no hidden send occurred.
            return G0JournalAssessment("DEFER_REOBSERVE", "reported_pre_dispatch_abort")
        return _stop("reported_failure_or_unknown")

    if choice is None:
        return _stop("success_without_choice")
    if scope.intent == "stay" and dispatch is None and result["reason"] == "stay":
        return G0JournalAssessment("STAY_AWAIT_CHANGE", "reported_no_dispatch_choice")
    if (scope.intent in ("move", "tv_weather", "tv_fortune")
            and dispatch is not None and dispatch["purpose"] == "stand_prerequisite"
            and result["reason"] == "stood_only"):
        return G0JournalAssessment("PREREQUISITE_ACK_REOBSERVE",
                                   "stand_prerequisite_report_only")
    if (scope.intent != "stay" and dispatch is not None
            and dispatch["purpose"] == "selected_action" and result["reason"] == "ok"):
        return G0JournalAssessment("ACK_REOBSERVE", "tool_report_only")
    return _stop("contradictory_success_record")
