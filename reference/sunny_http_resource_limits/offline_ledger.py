"""Phase 2G OFFLINE synthetic resource/abort ledger.

NO network, no sockets, no Windows API, no game and no real cancellation.
Caller-supplied time/transport acknowledgements are MODEL EVENTS ONLY.
A successful model check is *never* authority to accept an HTTP request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Lane = Literal["general", "recovery"]


@dataclass(frozen=True)
class Limits:
    total_ms: int
    header_ms: int
    body_ms: int
    cleanup_ms: int
    global_slots: int
    general_slots: int
    recovery_slots: int
    per_principal_slots: int
    unresolved_slots: int

    @classmethod
    def from_proposal(cls, raw: dict) -> "Limits":
        if raw.get("approval_state") != "proposed_not_ratified" or raw.get("g1_approval") is not False:
            raise ValueError("G0 fixture must not consume an approved/runtime profile")
        v = raw["numeric_candidates"]
        out = cls(
            v["total_first_byte_to_ingress_complete_ms"],
            v["header_first_byte_to_complete_budget_ms"],
            v["body_read_budget_ms"],
            v["abort_and_cleanup_grace_ms"],
            v["max_inflight_global_including_undrained"],
            v["max_inflight_general_including_undrained"],
            v["reserved_recovery_inflight"],
            v["max_inflight_per_authenticated_principal"],
            v["max_pending_unresolved_aborts"],
        )
        if not (0 < out.header_ms < out.total_ms and
                0 < out.body_ms < out.total_ms and
                0 < out.cleanup_ms and
                0 < out.recovery_slots < out.global_slots and
                out.general_slots + out.recovery_slots == out.global_slots and
                0 < out.per_principal_slots <= out.general_slots and
                0 < out.unresolved_slots <= out.global_slots):
            raise ValueError("contradictory numerical candidates")
        return out


@dataclass
class Ticket:
    request_id: str
    principal: str
    lane: Lane
    first_byte_ms: int
    handler_ms: int
    deadline_ms: int
    body_started_ms: int | None = None
    body_finished: bool = False
    phase: str = "active"  # active | abort_pending | released
    abort_requested_ms: int | None = None
    transport_abort_scope: str | None = None
    read_completion_observed: bool = False
    transport_quiescence_proven: bool = False
    buffers_safely_released: bool = False


class OfflineIngressLedger:
    """Synthetic *post-handler* admission/resource bookkeeping.

    Does NOT enforce pre-handler HTTP.sys queue or header occupancy. Gate G1
    requires independently trusted platform observability/enforcement first.
    """

    def __init__(self, limits: Limits):
        self.limits = limits
        self.tickets: dict[str, Ticket] = {}
        self.halted_reason: str | None = None
        self.potential_authorization_effects = 0  # must remain zero

    def _held(self) -> list[Ticket]:
        return [t for t in self.tickets.values() if t.phase != "released"]

    def _pending(self) -> list[Ticket]:
        return [t for t in self._held() if t.phase == "abort_pending"]

    def counts(self) -> tuple[int, int, int, int]:
        held = self._held()
        return (
            len(held),
            sum(t.lane == "general" for t in held),
            sum(t.lane == "recovery" for t in held),
            len(self._pending()),
        )

    def admit(self, request_id: str, principal: str, lane: Lane,
              first_byte_ms: int | None, handler_ms: int,
              provenance_verified: bool) -> str:
        if self.halted_reason:
            return "halted"
        if not provenance_verified or first_byte_ms is None:
            self.halted_reason = "unverifiable_prehandler_time"
            return "no_trusted_anchor"
        if (first_byte_ms < 0 or handler_ms < first_byte_ms or
                lane not in ("general", "recovery") or
                not request_id or not principal or request_id in self.tickets):
            return "invalid"
        if handler_ms >= first_byte_ms + self.limits.total_ms:
            return "expired_before_handler"
        held, general, recovery, _ = self.counts()
        if (held >= self.limits.global_slots or
                (lane == "general" and general >= self.limits.general_slots) or
                (lane == "recovery" and recovery >= self.limits.recovery_slots) or
                sum(t.principal == principal for t in self._held()) >=
                self.limits.per_principal_slots):
            return "capacity"
        # This gate only models an application-visible reservation; no OS
        # header/queue capacity can be established from this state machine.
        self.tickets[request_id] = Ticket(
            request_id, principal, lane, first_byte_ms, handler_ms,
            first_byte_ms + self.limits.total_ms)
        return "reserved"

    def begin_body(self, request_id: str, now_ms: int) -> bool:
        t = self.tickets[request_id]
        if t.phase != "active" or t.body_started_ms is not None:
            return False
        if now_ms < t.handler_ms:
            return False
        if now_ms >= t.deadline_ms:
            self.expire(now_ms)
            return False
        t.body_started_ms = now_ms
        return True

    def expire(self, now_ms: int) -> list[str]:
        changed = []
        for t in self._held():
            if t.phase != "active":
                continue
            deadline = t.deadline_ms
            if t.body_started_ms is not None and not t.body_finished:
                deadline = min(deadline, t.body_started_ms + self.limits.body_ms)
            if now_ms >= deadline:
                t.phase = "abort_pending"
                t.abort_requested_ms = now_ms
                changed.append(t.request_id)
        if len(self._pending()) >= self.limits.unresolved_slots:
            self.halted_reason = "unresolved_abort_cap"
        return changed

    def complete_body(self, request_id: str, now_ms: int) -> bool:
        t = self.tickets[request_id]
        if t.phase != "active" or t.body_started_ms is None or t.body_finished:
            return False
        if now_ms < t.body_started_ms:
            return False
        self.expire(now_ms)
        if t.phase != "active":
            return False
        t.body_finished = True
        return True

    def eligible_for_next_policy_check(self, request_id: str, now_ms: int) -> bool:
        self.expire(now_ms)
        t = self.tickets[request_id]
        return (t.phase == "active" and t.body_finished and
                not self.halted_reason and now_ms < t.deadline_ms)
        # Even True is NOT a credential, lease or authorization decision.

    def abort_requested(self, request_id: str, now_ms: int, scope: str) -> bool:
        t = self.tickets[request_id]
        if t.phase != "abort_pending" or t.abort_requested_ms is None:
            return False
        if scope not in ("request", "whole_listener"):
            return False
        t.transport_abort_scope = scope
        if scope == "whole_listener":
            self.halted_reason = "whole_listener_abort_collateral"
        if now_ms > t.abort_requested_ms + self.limits.cleanup_ms:
            self.halted_reason = "cleanup_deadline_exceeded"
        return True

    def record_observed_completion(self, request_id: str, *, read_complete: bool,
                                   transport_quiescent: bool) -> None:
        t = self.tickets[request_id]
        if t.phase == "released":
            return
        t.read_completion_observed = read_complete
        t.transport_quiescence_proven = transport_quiescent
        # These Booleans are SYNTHETIC CLAIMS, not HttpListener evidence.

    def release(self, request_id: str, *, buffers_safely_released: bool) -> bool:
        t = self.tickets[request_id]
        if t.phase == "released":
            return False
        if not (t.read_completion_observed and t.transport_quiescence_proven and
                buffers_safely_released):
            return False
        t.buffers_safely_released = True
        t.phase = "released"
        return True

    def enforce_cleanup_deadline(self, now_ms: int) -> bool:
        for t in self._pending():
            assert t.abort_requested_ms is not None
            if now_ms >= t.abort_requested_ms + self.limits.cleanup_ms:
                self.halted_reason = "cleanup_deadline_exceeded"
                return False
        return not bool(self.halted_reason)
