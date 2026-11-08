"""Offline invariants for the Phase 2F *unexecuted* Windows HTTP test plan.

This file performs no networking, launches no processes, and never reads a user
save, installed mod, OS configuration or credential. Passing means only that
the manifest is well-formed and does not falsely assert live acceptance.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE = ROOT / "reference" / "sunny_windows_http_acceptance" / "cases.json"
DOC_FILE = ROOT / "docs" / "sunny-agentic" / "WINDOWS_HTTP_TRANSPORT_ACCEPTANCE.md"
MANIFEST = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))

EXPECTED_CATEGORIES = {
    "environment",
    "target",
    "authority",
    "headers",
    "framing",
    "liveness",
    "authorization",
    "privacy",
    "compatibility",
}
STAGES = {"future_isolated_windows_only", "future_runtime_acceptance_only"}
OUTCOMES = {
    "deny_before_effects",
    "isolation_and_teardown",
    "measure_platform_behavior",
    "authorized_synthetic_candidate_only",
    "separate_requests_isolated",
    "bounded_abort_and_cleanup",
    "reviewed_runtime_evidence",
}
EVIDENCE = {
    "synthetic bytes or script fixture hash",
    "HTTP.sys or adapter observation",
    "sanitized response and handler-contact result",
    "protected effects count and request cleanup outcome",
}


def test_plan_is_not_executed_or_authorized_for_network_use() -> None:
    assert MANIFEST["schema_version"] == 1
    assert MANIFEST["plan"] == "sunny-windows-http-transport-phase2f"
    assert MANIFEST["execution_status"] == "not_run"
    assert MANIFEST["real_transport_tested"] is False
    assert MANIFEST["requires_separate_operator_approval"] is True
    assert "main" in " ".join(MANIFEST["prohibited_targets"])
    assert "Sunny" in " ".join(MANIFEST["prohibited_targets"])


def test_manifest_has_unique_50_required_cases_with_explicit_stage_split() -> None:
    cases = MANIFEST["cases"]
    assert len(cases) == 50
    assert len({c["id"] for c in cases}) == 50
    assert len([c for c in cases if c["priority"] == "blocker"]) == 17
    assert sum(c["stage"] == "future_isolated_windows_only" for c in cases) == 37
    assert sum(c["stage"] == "future_runtime_acceptance_only" for c in cases) == 13
    assert {c["category"] for c in cases} == EXPECTED_CATEGORIES
    assert all(c["status"] == "not_run" for c in cases)


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda item: item["id"])
def test_each_case_has_unambiguous_nonexecuted_acceptance_evidence(case: dict) -> None:
    assert re.fullmatch(r"(ENV|RAW|HOST|HDR|FRM|TIME|AUTH|PRIV|COMP)-\d{2}", case["id"])
    assert case["category"] in EXPECTED_CATEGORIES
    assert case["priority"] in {"blocker", "required"}
    assert case["stage"] in STAGES
    assert case["outcome_class"] in OUTCOMES
    assert case["status"] == "not_run"
    assert len(case["scenario"]) > 30
    assert len(case["expected"]) > 45
    assert EVIDENCE < set(case["evidence"])
    assert len(case["evidence"]) == len(set(case["evidence"]))
    if case["category"] in {"authorization", "privacy", "compatibility"}:
        assert case["stage"] == "future_runtime_acceptance_only"
        assert case["outcome_class"] == "reviewed_runtime_evidence"
    else:
        assert case["stage"] == "future_isolated_windows_only"
        assert case["outcome_class"] != "reviewed_runtime_evidence"
    if case["category"] == "liveness":
        assert case["outcome_class"] == "bounded_abort_and_cleanup"
    # Never treat a successful synthetic test as measured Windows acceptance.
    assert "future" in case["expected"].lower()


def test_doc_preserves_the_three_distinct_noninterchangeable_gates() -> None:
    doc = DOC_FILE.read_text(encoding="utf-8")
    assert "G0" in doc and "G1" in doc and "G2" in doc
    assert "37" in doc and "13" in doc and "50" in doc
    assert "not_run" in doc
    assert "separate explicit user approval" in doc
    assert "**not** a working transport adapter" in doc.lower()
    assert "16 KiB" in doc
    assert "1200" in doc
    assert "Evidence.All" in doc
    assert "FRM-12" in doc
    assert "TIME" in doc and "cleanup" in doc
    assert "unobservable" in doc
    assert "raw" in doc.lower()
    assert "main" in doc


def test_case_manifest_names_all_critical_transport_regressions() -> None:
    ids = {case["id"] for case in MANIFEST["cases"]}
    assert {
        "ENV-01",
        "RAW-01",
        "HOST-02",
        "HDR-01",
        "FRM-03",
        "FRM-06",
        "FRM-09",
        "FRM-12",
        "TIME-01",
        "TIME-02",
        "TIME-05",
        "AUTH-03",
        "AUTH-04",
        "AUTH-06",
        "PRIV-01",
        "COMP-03",
        "COMP-04",
    }.issubset(ids)


def test_no_fake_timestamp_or_observed_windows_evidence_sneaks_into_plan() -> None:
    doc = DOC_FILE.read_text(encoding="utf-8")
    assert "NOT EXECUTED" in doc
    assert "No sockets" in doc
    assert not any(c["status"] in {"pass", "passed", "complete"} for c in MANIFEST["cases"])
    assert "TBD" in doc


def test_framing_and_liveness_require_specific_evidence() -> None:
    cases = {c["id"]: c for c in MANIFEST["cases"]}
    assert cases["FRM-09"]["outcome_class"] == "separate_requests_isolated"
    assert cases["FRM-11"]["outcome_class"] == "separate_requests_isolated"
    for case in MANIFEST["cases"]:
        evidence = " ".join(case["evidence"])
        if case["category"] == "liveness":
            assert "pre-handler" in evidence
            assert "buffer ownership/quarantine" in evidence
        if case["category"] == "framing":
            assert "per-connection ordered request/response IDs" in evidence
        if case["stage"] == "future_runtime_acceptance_only":
            assert "separate G2" in evidence
    assert all(n in cases["FRM-07"]["scenario"] for n in ("16383", "16384", "16385"))
    assert "GetContextAsync" in cases["TIME-01"]["scenario"]
    assert "explicitly approved disposable" in cases["ENV-02"]["scenario"]


def test_source_links_resolve_and_safety_gates_are_explicit() -> None:
    doc = DOC_FILE.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", doc):
        assert (DOC_FILE.parent / target).is_file(), target
    for requirement in (
        "G1 start and signoff are blocked", "monotonic first-byte/connection anchor",
        "Client bytes are comparison input", "All-route stop rule",
        "No wildcard listener prefixes", "interim `100 Continue`",
    ):
        assert requirement in doc
