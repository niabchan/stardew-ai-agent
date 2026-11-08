"""Offline NO-GO G1 entry readiness regression tests.

The files represent a planning decision, not observed Windows test results.
Never launch a listener, inspect OS settings, or touch Sunny/SMAPI in CI.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "reference" / "sunny_g1_readiness"
sys.path.insert(0, str(REF))
from evaluate import ReadinessError, evaluate_g0_entry  # noqa: E402

READINESS = json.loads((REF / "gates.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "reference" / "sunny_windows_http_acceptance" /
                      "cases.json").read_text(encoding="utf-8"))
PROFILE = json.loads((ROOT / "reference" / "sunny_http_resource_limits" /
                      "proposed_limits.json").read_text(encoding="utf-8"))
DOC = ROOT / "docs" / "sunny-agentic" / "G1_READINESS_REVIEW.md"


def audit(r=None, c=None, p=None):
    return evaluate_g0_entry(
        copy.deepcopy(READINESS if r is None else r),
        copy.deepcopy(CATALOG if c is None else c),
        copy.deepcopy(PROFILE if p is None else p),
    )


def test_real_state_remains_no_go_without_windows_or_operator_approval():
    result = audit()
    assert result["decision"] == "NO_GO_G1_START"
    assert result["open_entry_blockers"] == 11
    assert result["g1_cases_not_run"] == 37
    assert result["g2_cases_not_run"] == 13
    assert result["source_cases"] == 50
    assert result["g1_source_cases_linked"] >= 20
    assert result["numeric_profile_ratified"] is False
    assert result["windows_transport_tested"] is False
    assert result["permission_to_open_listener"] is False


@pytest.mark.parametrize("key", [
    "approved_to_open_listener", "g1_executed", "g2_executed",
    "transport_abort_scope_verified", "prehandler_first_byte_source_verified",
    "windows_provenance_verified", "all_route_live_authorization_proven",
])
def test_fake_live_evidence_or_approval_is_rejected(key):
    r = copy.deepcopy(READINESS)
    r[key] = True
    with pytest.raises(ReadinessError):
        audit(r=r)


@pytest.mark.parametrize("key,value", [
    ("decision", "GO_G1"), ("decision_type", "real_windows_approval"),
    ("operator_approval_record", "approved"), ("numeric_ratification_record", "approved"),
    ("source_plan", "unknown.json"), ("source_candidate_profile", "unsafe.json"),
])
def test_no_fake_go_approval_or_source_override(key, value):
    r = copy.deepcopy(READINESS)
    r[key] = value
    with pytest.raises(ReadinessError):
        audit(r=r)


@pytest.mark.parametrize("entry_key,value", [
    ("entry_status", "ready"), ("entry_status", "passed"),
    ("entry_blocker", False), ("evidence_at_entry", "verified_windows"),
    ("proposed_test_only", False),
])
def test_unresolved_entry_prerequisites_cannot_be_promoted_by_json(entry_key, value):
    r = copy.deepcopy(READINESS)
    r["gates"][0][entry_key] = value
    with pytest.raises(ReadinessError):
        audit(r=r)


def test_missing_duplicate_and_wrong_stage_links_cannot_fake_complete_coverage():
    for mutation in ("remove", "duplicate", "g2_ref", "unknown_ref"):
        r = copy.deepcopy(READINESS)
        if mutation == "remove":
            r["gates"].pop()
        elif mutation == "duplicate":
            r["gates"][0]["id"] = r["gates"][1]["id"]
        elif mutation == "g2_ref":
            r["gates"][0]["g1_case_ids"].append("AUTH-03")
        else:
            r["gates"][0]["g1_case_ids"].append("NOT-A-CASE")
        with pytest.raises(ReadinessError):
            audit(r=r)


@pytest.mark.parametrize("mutation", ["pass_one", "shift_case_stage",
                                       "remove_case", "change_catalog_count",
                                       "fake_windows_evidence"])
def test_phase2f_catalog_cannot_claim_G1_or_G2_acceptance(mutation):
    c = copy.deepcopy(CATALOG)
    if mutation == "pass_one":
        c["cases"][0]["status"] = "passed"
    elif mutation == "shift_case_stage":
        c["cases"][0]["stage"] = "future_runtime_acceptance_only"
    elif mutation == "remove_case":
        c["cases"].pop()
    elif mutation == "change_catalog_count":
        c["cases"][0]["priority"] = "required"
    elif mutation == "fake_windows_evidence":
        c["real_transport_tested"] = True
    with pytest.raises(ReadinessError):
        audit(c=c)


@pytest.mark.parametrize("key,value", [
    ("g1_approval", True), ("windows_http_sys_tested", True),
    ("g2_runtime_tested", True), ("approval_state", "ratified"),
])
def test_phase2g_budget_profile_cannot_be_auto_ratified(key, value):
    p = copy.deepcopy(PROFILE)
    p[key] = value
    with pytest.raises(ReadinessError):
        audit(p=p)


@pytest.mark.parametrize("key,value", [
    ("max_inflight_global_including_undrained", True),
    ("max_inflight_general_including_undrained", 33),
    ("max_request_body_bytes", 0),
    ("body_read_budget_ms", 1.5),
])
def test_invalid_candidate_profile_never_reaches_go(key, value):
    p = copy.deepcopy(PROFILE)
    p["numeric_candidates"][key] = value
    with pytest.raises(ReadinessError):
        audit(p=p)


def test_future_g1_cases_do_not_need_to_be_run_before_G1_can_be_authorized():
    # This is a preflight: all 37 G1 cases being 'not_run' is normal at entry.
    # The reason for NO_GO is 11 open approval/design prerequisites, not
    # circularly demanding results from an experiment that has not begun.
    result = audit()
    assert result["open_entry_blockers"] == 11
    assert all(c["status"] == "not_run" for c in CATALOG["cases"])
    assert READINESS["approved_to_open_listener"] is False


def test_no_G2_case_can_be_mislabeled_as_G1_entry_evidence():
    g1_refs = {ref for g in READINESS["gates"] for ref in g["g1_case_ids"]}
    stage_by_id = {c["id"]: c["stage"] for c in CATALOG["cases"]}
    assert all(stage_by_id[cid] == "future_isolated_windows_only"
               for cid in g1_refs)


def test_docs_explain_no_go_scope_approval_and_exit_separation():
    doc = DOC.read_text(encoding="utf-8")
    for phrase in (
        "NO-GO", "11", "37", "13", "50", "17", "not_run",
        "pre-handler", "HTTP.sys", "G0", "G1", "G2", "8", "2", "5",
        "separate explicit", "main", "Sunny", "rollback", "abort",
        "approval", "first byte", "unobservable",
    ):
        assert phrase in doc, phrase
    assert "not a Windows acceptance" in doc
    assert "not yet approved to begin G1" in doc


def test_source_paths_exist_and_no_live_execution_is_enabled():
    assert DOC.is_file()
    for source in (READINESS["source_plan"], READINESS["source_candidate_profile"]):
        assert (ROOT / source).is_file()
    assert READINESS["approved_to_open_listener"] is False
    assert PROFILE["g1_approval"] is False
