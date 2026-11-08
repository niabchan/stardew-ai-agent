"""G0-only model tests for an UNAPPROVED future Windows HTTP transport.

No socket, HttpListener, game, background task, real timer, or credential.
All times are synthetic millisecond values supplied by the test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "reference" / "sunny_http_resource_limits"
sys.path.insert(0, str(REF))
from offline_ledger import Limits, OfflineIngressLedger  # noqa: E402

PROFILE = json.loads((REF / "proposed_limits.json").read_text(encoding="utf-8"))


@pytest.fixture
def ledger() -> OfflineIngressLedger:
    return OfflineIngressLedger(Limits.from_proposal(PROFILE))


def reserve(ledger: OfflineIngressLedger, ticket: str = "t", *,
            principal: str = "luna", lane: str = "general",
            first: int | None = 0, handler: int = 1, proven: bool = True) -> str:
    return ledger.admit(ticket, principal, lane, first, handler, proven)


def test_proposed_numbers_are_unratified_and_never_authorize_G1() -> None:
    assert PROFILE["approval_state"] == "proposed_not_ratified"
    assert PROFILE["g1_approval"] is False
    assert PROFILE["windows_http_sys_tested"] is False
    assert PROFILE["g2_runtime_tested"] is False
    assert len(PROFILE["needs_operator_review"]) >= 5
    values = PROFILE["numeric_candidates"]
    assert values["max_request_body_bytes"] == 16 * 1024
    assert values["max_response_bytes"] == 256 * 1024
    assert values["body_read_budget_ms"] == 5000  # prior server-contract proposal
    assert values["max_inflight_global_including_undrained"] == 32
    assert values["max_inflight_per_authenticated_principal"] == 8
    assert values["max_inflight_general_including_undrained"] + values["reserved_recovery_inflight"] == 32
    assert 0 < values["header_first_byte_to_complete_budget_ms"] < values["total_first_byte_to_ingress_complete_ms"]


@pytest.mark.parametrize("first,handler,proven,result", [
    (None, 1, True, "no_trusted_anchor"),
    (0, 1, False, "no_trusted_anchor"),
    (0, 8000, True, "expired_before_handler"),
    (0, 2000, True, "late_headers_unenforced"),
    (0, 1999, True, "reserved"),
    (1000, 1001, True, "reserved"),
    (0, -1, True, "invalid"),
    (-1, 0, True, "invalid"),
])
def test_first_byte_prehandler_and_header_gate(first, handler, proven, result):
    l = OfflineIngressLedger(Limits.from_proposal(PROFILE))
    assert reserve(l, first=first, handler=handler, proven=proven) == result
    assert l.potential_authorization_effects == 0
    if result == "no_trusted_anchor":
        assert l.halted_reason == "unverifiable_prehandler_time"
        assert reserve(l, "another") == "halted"


@pytest.mark.parametrize("now,expected", [
    (1, "reserved"),
    (500, "reserved"),
    (7999, "reserved"),
])
def test_synthetic_first_byte_anchor_is_not_handler_time(now, expected, ledger):
    assert reserve(ledger, first=now - 1 if now > 1 else 0, handler=now) == expected
    assert ledger.tickets["t"].deadline_ms != now + ledger.limits.total_ms
    assert ledger.potential_authorization_effects == 0


def test_valid_body_still_only_eligible_for_another_policy_gate(ledger):
    assert reserve(ledger) == "reserved"
    assert not ledger.eligible_for_next_policy_check("t", 2)
    assert ledger.begin_body("t", 2)
    assert ledger.complete_body("t", 9)
    assert ledger.eligible_for_next_policy_check("t", 9)
    assert ledger.potential_authorization_effects == 0  # no credential/lease/queue


def test_body_progress_does_not_reset_a_whole_ingress_deadline(ledger):
    assert reserve(ledger) == "reserved"
    assert ledger.begin_body("t", 1000)
    assert not ledger.complete_body("t", 6000)
    assert ledger.tickets["t"].phase == "abort_pending"
    assert not ledger.eligible_for_next_policy_check("t", 6000)
    assert ledger.counts() == (1, 1, 0, 1)


def test_total_budget_wins_even_when_body_is_not_expired(ledger):
    assert reserve(ledger) == "reserved"
    assert ledger.begin_body("t", 6500)
    assert not ledger.complete_body("t", 8000)
    assert ledger.counts()[-1] == 1
    assert ledger.tickets["t"].deadline_ms == 8000


def test_timeout_no_immediate_slot_reuse(ledger):
    assert reserve(ledger) == "reserved"
    assert ledger.begin_body("t", 2)
    assert ledger.expire(8000) == ["t"]
    assert ledger.counts() == (1, 1, 0, 1)
    assert ledger.abort_requested("t", 8000, "request")
    assert ledger.counts()[0] == 1
    assert not ledger.release("t", buffers_safely_released=True)
    assert ledger.counts()[0] == 1


@pytest.mark.parametrize("read,transport,buffers,allowed", [
    (False, False, False, False),
    (True, False, True, False),
    (False, True, True, False),
    (True, True, False, False),
    (True, True, True, True),
])
def test_all_three_completion_and_buffer_proofs_required_for_release(
        ledger, read, transport, buffers, allowed):
    assert reserve(ledger) == "reserved"
    ledger.begin_body("t", 2)
    ledger.expire(8000)
    ledger.record_observed_completion("t", read_complete=read,
                                      transport_quiescent=transport)
    assert ledger.release("t", buffers_safely_released=buffers) is allowed
    assert ledger.counts()[0] == (0 if allowed else 1)


def test_premature_release_before_read_or_abort_denied(ledger):
    assert reserve(ledger) == "reserved"
    ledger.record_observed_completion("t", read_complete=True, transport_quiescent=True)
    assert not ledger.release("t", buffers_safely_released=True)
    assert ledger.counts()[0] == 1


def test_late_observed_completion_never_resurrects_candidate(ledger):
    assert reserve(ledger) == "reserved"
    assert ledger.begin_body("t", 10)
    ledger.expire(8000)
    ledger.record_observed_completion("t", read_complete=True,
                                      transport_quiescent=True)
    assert not ledger.complete_body("t", 8001)
    assert not ledger.eligible_for_next_policy_check("t", 8001)
    assert ledger.release("t", buffers_safely_released=True)
    assert not ledger.eligible_for_next_policy_check("t", 8002)
    assert ledger.potential_authorization_effects == 0


def test_per_principal_limit_prevents_unbounded_same_owner_work(ledger):
    for i in range(8):
        assert reserve(ledger, str(i), principal="luna") == "reserved"
    assert reserve(ledger, "ninth", principal="luna") == "capacity"
    assert reserve(ledger, "other", principal="other") == "reserved"
    assert ledger.counts()[0] == 9


def test_reserved_recovery_capacity_is_distinct_from_general(ledger):
    for i in range(28):
        assert reserve(ledger, f"general-{i}", principal=f"p{i//7}") == "reserved"
    assert reserve(ledger, "general-extra", principal="someone-else") == "capacity"
    for i in range(4):
        assert reserve(ledger, f"recovery-{i}", principal="operator", lane="recovery") == "reserved"
    assert reserve(ledger, "recovery-extra", principal="other-operator", lane="recovery") == "capacity"
    assert ledger.counts() == (32, 28, 4, 0)
    assert ledger.potential_authorization_effects == 0


def test_reserved_recovery_is_only_a_slot_not_a_privilege(ledger):
    assert reserve(ledger, "recovery", principal="unverified-test", lane="recovery") == "reserved"
    assert not ledger.eligible_for_next_policy_check("recovery", 10)
    assert ledger.potential_authorization_effects == 0


def test_pending_abort_capacity_triggers_admission_halt(ledger):
    for i in range(4):
        assert reserve(ledger, str(i), principal=f"p{i}") == "reserved"
        ledger.begin_body(str(i), 5)
    assert len(ledger.expire(8000)) == 4
    assert ledger.counts() == (4, 4, 0, 4)
    assert ledger.halted_reason == "unresolved_abort_cap"
    assert reserve(ledger, "fifth") == "halted"


def test_cleanup_deadline_requires_observed_completion(ledger):
    assert reserve(ledger) == "reserved"
    ledger.begin_body("t", 2)
    ledger.expire(8000)
    assert ledger.abort_requested("t", 8000, "request")
    assert ledger.enforce_cleanup_deadline(9999)
    assert not ledger.enforce_cleanup_deadline(10000)
    assert ledger.halted_reason == "cleanup_deadline_exceeded"
    assert ledger.counts()[0] == 1


def test_unknown_abort_scope_does_not_claim_safe_cleanup(ledger):
    assert reserve(ledger) == "reserved"
    ledger.begin_body("t", 1)
    ledger.expire(8000)
    assert not ledger.abort_requested("t", 8000, "unverified")
    assert ledger.tickets["t"].transport_abort_scope is None
    assert ledger.counts()[0] == 1


def test_whole_listener_abort_requires_stopping_new_work(ledger):
    assert reserve(ledger) == "reserved"
    ledger.begin_body("t", 2)
    ledger.expire(8000)
    assert ledger.abort_requested("t", 8000, "whole_listener")
    assert ledger.halted_reason == "whole_listener_abort_collateral"
    assert reserve(ledger, "next", principal="someone-else") == "halted"


def test_proposed_values_must_be_internally_consistent():
    raw = json.loads(json.dumps(PROFILE))
    raw["numeric_candidates"]["max_inflight_general_including_undrained"] = 32
    with pytest.raises(ValueError):
        Limits.from_proposal(raw)
    raw = json.loads(json.dumps(PROFILE))
    raw["g1_approval"] = True
    with pytest.raises(ValueError):
        Limits.from_proposal(raw)


def test_duplicate_request_claim_cannot_reuse_ticket_id(ledger):
    assert reserve(ledger) == "reserved"
    assert reserve(ledger) == "invalid"
    ledger.begin_body("t", 2)
    assert ledger.complete_body("t", 3)
    ledger.record_observed_completion("t", read_complete=True,
                                      transport_quiescent=True)
    assert ledger.release("t", buffers_safely_released=True)
    assert ledger.counts()[0] == 0
    assert reserve(ledger) == "invalid"


def test_existing_windows_g0_manifest_still_unexecuted():
    p = ROOT / "reference" / "sunny_windows_http_acceptance" / "cases.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    assert m["execution_status"] == "not_run"
    assert m["real_transport_tested"] is False
    assert all(x["status"] == "not_run" for x in m["cases"])
    assert sum(x["stage"] == "future_isolated_windows_only" for x in m["cases"]) == 37
    assert sum(x["stage"] == "future_runtime_acceptance_only" for x in m["cases"]) == 13
