"""Sunny Phase 2K: G0-only source-backed Windows transport comparison.

No network, sockets, processes, native Windows APIs, actual test timings,
installed Sunny, API keys or game. Passing cannot select a transport.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "reference" / "sunny_g1_transport_feasibility"
MATRIX = json.loads((REF / "matrix.json").read_text(encoding="utf-8"))
STOP = json.loads((REF / "independent_stop_sketch.json").read_text(encoding="utf-8"))
READINESS = json.loads((ROOT / "reference/sunny_g1_readiness/gates.json").read_text(encoding="utf-8"))
PLAN = json.loads((ROOT / "reference/sunny_g1_resolution/plan.json").read_text(encoding="utf-8"))
CASES = json.loads((ROOT / "reference/sunny_windows_http_acceptance/cases.json").read_text(encoding="utf-8"))
LIMITS = json.loads((ROOT / "reference/sunny_http_resource_limits/proposed_limits.json").read_text(encoding="utf-8"))
DOC = ROOT / "docs/sunny-agentic/G1_TRANSPORT_FEASIBILITY_MATRIX.md"

TRANSPORTS = {"HttpListener", "ASPNET-HttpSys", "Kestrel", "TcpListener-custom-HTTP"}
GATES = {"G1E-03", "G1E-04", "G1E-02", "G1E-05", "G1E-06"}
ASSESSMENTS = {"not_established", "documented_partial", "custom_design_burden"}
SOURCES = {
    "MS-GETCONTEXT", "MS-RAWURL", "MS-LISTENER-ABORT",
    "MS-RESPONSE-ABORT", "MS-HTTPSYS-SERVER", "MS-HTTPSYS-HEADER",
    "MS-HTTPSYS-TIME", "MS-KESTREL-LIMITS", "MS-KESTREL-SECURITY",
    "MS-RAW-TARGET", "MS-CONNECTION", "MS-CONTEXT-ABORT", "MS-TCP-STOP",
}
ABORT_STATES = (
    "RUNNING", "STOP_LATCHED", "TRAFFIC_STOPPED", "ABORT_REQUESTED",
    "DRAIN_OBSERVING", "INDEPENDENT_ESCALATION", "QUIESCENT_EVIDENCED",
    "UNRESOLVED_QUARANTINED", "MANUAL_ROLLBACK_REVIEW", "CLOSED_NO_RESTART",
)


def check_matrix(m: dict) -> None:
    assert m["schema_version"] == 1
    assert m["phase"] == "2K"
    assert m["name"] == "sunny-g1-transport-feasibility-g0"
    assert m["baseline"] == "a2c23e272a3da3ed3d6b6c613aecfdf8d723efa5"
    assert m["decision"] == "NO_GO_G1_START"
    assert m["transport_choice"] == "none_selected"
    assert m["operator_approval"] is False
    assert m["g1_executed"] is False
    assert m["g2_accepted"] is False
    assert m["numeric_limits_ratified"] is False
    assert m["source_review_only"] is True
    assert m["review_status"] == "initial_source_analysis_pending_independent_review"
    assert m["mandatory_gate_ids"] == ["G1E-03", "G1E-04", "G1E-02", "G1E-05", "G1E-06"]
    assert m["transport_ids"] == ["HttpListener", "ASPNET-HttpSys", "Kestrel", "TcpListener-custom-HTTP"]
    assert m["assessment_values"] == ["not_established", "documented_partial", "custom_design_burden"]
    assert m["entry_blockers_still_open"] == 11
    assert m["g1_case_count_not_run"] == 37
    assert m["g2_case_count_not_run"] == 13
    assert m["code_changes_forbidden"] is True
    assert m["live_experiments_forbidden"] is True
    assert m["no_automatic_go"] is True
    assert len(m["rules"]) >= 7
    assert "first-request" in " ".join(m["rules"])
    assert "BLOCK" in " ".join(m["rules"])
    assert "EntityBody" in " ".join(m["rules"])

    src = m["sources"]
    assert len(src) == len(SOURCES) == len({s["id"] for s in src})
    assert {s["id"] for s in src} == SOURCES
    for s in src:
        assert s["url"].startswith("https://learn.microsoft.com/")
        assert len(s["claim"]) > 55
        assert len(s["title"]) > 9

    rows = m["rows"]
    assert len(rows) == len(TRANSPORTS) * len(GATES) == 20
    assert len({(r["transport"], r["gate_id"]) for r in rows}) == 20
    assert {(r["transport"], r["gate_id"]) for r in rows} == {
        (t, g) for t in TRANSPORTS for g in GATES
    }
    for r in rows:
        assert r["transport"] in TRANSPORTS
        assert r["gate_id"] in GATES
        assert r["assessment"] in ASSESSMENTS
        assert r["windows_observed"] is False
        assert r["approved"] is False
        assert isinstance(r["source_ids"], list) and len(r["source_ids"]) >= 1
        assert all(s in SOURCES for s in r["source_ids"])
        assert len(r["evidence"]) >= 85
        assert len(r["blocking_condition"]) >= 47
    for t in TRANSPORTS:
        for g in GATES:
            assert [r for r in rows if r["transport"] == t and r["gate_id"] == g]
    assert next(r for r in rows if r["transport"] == "ASPNET-HttpSys" and
                r["gate_id"] == "G1E-03")["assessment"] == "documented_partial"
    assert "only after first request" in next(s for s in src if s["id"] == "MS-HTTPSYS-HEADER")["claim"]
    assert next(r for r in rows if r["transport"] == "Kestrel" and
                r["gate_id"] == "G1E-03")["assessment"] == "documented_partial"


def check_stop(s: dict) -> None:
    assert s["schema_version"] == 1
    assert s["phase"] == "2K"
    assert s["name"] == "sunny-g1-independent-stop-cleanup-g0-sketch"
    assert s["status"] == "offline_source_interface_only"
    assert s["decision"] == "NO_GO_G1_START"
    for field in ("external_stop_implemented", "stop_operator_approved",
                  "windows_abort_tested", "cleanup_verified"):
        assert s[field] is False
    for key in ("selected_abort_method", "selected_process", "selected_port",
                "stop_owner", "stop_build_sha"):
        assert s[key] is None
    assert s["source_contract"] == "reference/sunny_g1_resolution/plan.json"
    assert s["gates"] == ["G1E-05", "G1E-06"]
    assert "not depend on listener" in s["separation_policy"]
    assert len(s["states"]) == 10
    assert tuple(x["id"] for x in s["states"]) == ABORT_STATES
    assert all(x["resource_release"] is False for x in s["states"])
    assert s["states"][-1]["allowed_next"] == []
    destinations = set(ABORT_STATES)
    assert all(set(x["allowed_next"]) <= destinations for x in s["states"])
    assert all(x["id"] not in x["allowed_next"] for x in s["states"])
    assert all("RUNNING" not in x["allowed_next"] for x in s["states"])
    assert set(s["states"][0]["allowed_next"]) == {"STOP_LATCHED"}
    assert set(s["states"][-2]["allowed_next"]) == {"CLOSED_NO_RESTART"}
    assert s["no_automatic_restart"] is True
    assert s["safety_unknown_behavior"] == "BLOCK_NO_GO"

    params = s["reviewed_future_parameters"]
    assert len(params) == 12
    assert len({p["name"] for p in params}) == 12
    assert all(p["required_before_G1"] is True for p in params)
    assert all(p["status"] in {"unassigned", "undecided", "unratified",
                               "not_implemented", "unapproved", "not_granted"}
               for p in params)
    assert len(s["mechanism_notes"]) == 4
    assert {m["transport"] for m in s["mechanism_notes"]} == TRANSPORTS
    assert all(set(m["source_ids"]) <= SOURCES and m["source_ids"] for m in s["mechanism_notes"])
    order = s["required_independent_stop_order"]
    assert len(order) >= 8
    assert "independent" in " ".join(order).lower()
    assert "quarantined" in " ".join(order).lower()
    assert "manual" in " ".join(order).lower()
    assert "explicit" in " ".join(order).lower()


def test_source_plan_is_still_no_go_and_unratified() -> None:
    check_matrix(MATRIX)
    check_stop(STOP)
    assert READINESS["decision"] == PLAN["decision"] == "NO_GO_G1_START"
    assert READINESS["approved_to_open_listener"] is False
    assert len(READINESS["gates"]) == 11
    assert all(g["entry_status"] == "open" for g in READINESS["gates"])
    assert all(e["status"] == "open" for e in PLAN["entries"])
    assert LIMITS["approval_state"] == "proposed_not_ratified"
    assert LIMITS["g1_approval"] is False
    assert len(CASES["cases"]) == 50
    assert sum(c["stage"] == "future_isolated_windows_only" for c in CASES["cases"]) == 37
    assert sum(c["stage"] == "future_runtime_acceptance_only" for c in CASES["cases"]) == 13
    assert all(c["status"] == "not_run" for c in CASES["cases"])


@pytest.mark.parametrize("transport", sorted(TRANSPORTS))
@pytest.mark.parametrize("gate", sorted(GATES))
def test_each_transport_property_stays_evidenced_but_not_windows_proven(transport, gate):
    check_matrix(MATRIX)
    r = next(row for row in MATRIX["rows"] if row["transport"] == transport and row["gate_id"] == gate)
    assert r["windows_observed"] is False and r["approved"] is False


@pytest.mark.parametrize("change", [
    "fake_go", "select_transport", "approve_operator", "fake_g1", "fake_g2",
    "ratify_limits", "fake_source_review", "remove_source", "invent_source",
    "alter_source_url", "drop_row", "duplicate_row", "cross_transport",
    "wrong_gate", "fake_approval", "fake_windows", "fake_full_support",
    "remove_evidence", "remove_block_condition", "remove_rules",
    "change_headerwait_status", "change_kestrel_status",
])
def test_matrix_rejects_forged_approvals_or_missing_provenance(change):
    m = copy.deepcopy(MATRIX)
    first = m["rows"][0]
    if change == "fake_go":
        m["decision"] = "GO"
    elif change == "select_transport":
        m["transport_choice"] = "Kestrel"
    elif change == "approve_operator":
        m["operator_approval"] = True
    elif change == "fake_g1":
        m["g1_executed"] = True
    elif change == "fake_g2":
        m["g2_accepted"] = True
    elif change == "ratify_limits":
        m["numeric_limits_ratified"] = True
    elif change == "fake_source_review":
        m["source_review_only"] = False
    elif change == "remove_source":
        m["sources"].pop()
    elif change == "invent_source":
        m["sources"][0]["id"] = "NOT-A-MICROSOFT-SOURCE"
    elif change == "alter_source_url":
        m["sources"][0]["url"] = "https://example.org/untrusted"
    elif change == "drop_row":
        m["rows"].pop()
    elif change == "duplicate_row":
        m["rows"][0] = copy.deepcopy(m["rows"][1])
    elif change == "cross_transport":
        first["transport"] = "Kestrel"
    elif change == "wrong_gate":
        first["gate_id"] = "G1E-09"
    elif change == "fake_approval":
        first["approved"] = True
    elif change == "fake_windows":
        first["windows_observed"] = True
    elif change == "fake_full_support":
        first["assessment"] = "proved_safe"
    elif change == "remove_evidence":
        first["source_ids"] = []
    elif change == "remove_block_condition":
        first["blocking_condition"] = "safe"
    elif change == "remove_rules":
        m["rules"] = []
    elif change == "change_headerwait_status":
        next(r for r in m["rows"] if r["transport"] == "ASPNET-HttpSys" and
             r["gate_id"] == "G1E-03")["assessment"] = "not_established"
    else:
        next(r for r in m["rows"] if r["transport"] == "Kestrel" and
             r["gate_id"] == "G1E-03")["assessment"] = "not_established"
    with pytest.raises((AssertionError, KeyError, ValueError)):
        check_matrix(m)


@pytest.mark.parametrize("change", [
    "fake_implementation", "approve_stop", "fake_windows_abort", "fake_cleanup",
    "select_listener", "assign_operator", "skip_gate", "remove_state",
    "rearm_running", "release_slot", "skip_latch", "invent_state",
    "duplicate_parameter", "forged_ready_parameter", "remove_stop_path",
    "remove_quarantine", "enable_restart", "change_unknown_policy",
])
def test_stop_schema_rejects_unapproved_realworld_effects(change):
    s = copy.deepcopy(STOP)
    if change == "fake_implementation":
        s["external_stop_implemented"] = True
    elif change == "approve_stop":
        s["stop_operator_approved"] = True
    elif change == "fake_windows_abort":
        s["windows_abort_tested"] = True
    elif change == "fake_cleanup":
        s["cleanup_verified"] = True
    elif change == "select_listener":
        s["selected_port"] = 24822
    elif change == "assign_operator":
        s["stop_owner"] = "unreviewed"
    elif change == "skip_gate":
        s["gates"] = ["G1E-05"]
    elif change == "remove_state":
        s["states"].pop()
    elif change == "rearm_running":
        s["states"][6]["allowed_next"].append("RUNNING")
    elif change == "release_slot":
        s["states"][4]["resource_release"] = True
    elif change == "skip_latch":
        s["states"][0]["allowed_next"] = ["ABORT_REQUESTED"]
    elif change == "invent_state":
        s["states"][0]["id"] = "RUNNING_PROVEN"
    elif change == "duplicate_parameter":
        s["reviewed_future_parameters"][0] = copy.deepcopy(s["reviewed_future_parameters"][1])
    elif change == "forged_ready_parameter":
        s["reviewed_future_parameters"][0]["status"] = "ready"
    elif change == "remove_stop_path":
        s["separation_policy"] = "needs listener"
    elif change == "remove_quarantine":
        s["required_independent_stop_order"] = ["foo"] * 8
    elif change == "enable_restart":
        s["no_automatic_restart"] = False
    else:
        s["safety_unknown_behavior"] = "assume_safe"
    with pytest.raises((AssertionError, KeyError, ValueError)):
        check_stop(s)


def test_readme_clearly_separates_public_api_claims_from_unrun_windows_acceptance():
    doc = DOC.read_text(encoding="utf-8").lower()
    for term in (
        "no-go", "phase 2k", "httplistener", "kestrel", "http.sys",
        "tcplistener", "getcontextasync", "headerwait", "first request",
        "rawtarget", "original", "unobservable", "quarantine",
        "independent", "no automatic restart", "11", "37", "13", "50",
        "not_run", "g1e-05", "g1e-03", "unratified", "main",
    ):
        assert term in doc, term
    for source in MATRIX["sources"]:
        assert source["url"].lower() in doc, source["id"]
