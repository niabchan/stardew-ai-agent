"""Phase 2I OFFLINE-only Windows experiment *specification* checks.

No socket, process, OS configuration, network library, HTTP request,
real credential, game, user file or G1 execution. A green pytest run
validates a G0 planning artifact; it never authorizes Windows tests.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "reference" / "sunny_g1_experiment"
PLAN = json.loads((REF / "experiment_plan.json").read_text(encoding="utf-8"))
TEMPLATE = json.loads((REF / "evidence_template.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "reference" / "sunny_windows_http_acceptance" /
                      "cases.json").read_text(encoding="utf-8"))
READINESS = json.loads((ROOT / "reference" / "sunny_g1_readiness" /
                        "gates.json").read_text(encoding="utf-8"))
LIMITS = json.loads((ROOT / "reference" / "sunny_http_resource_limits" /
                     "proposed_limits.json").read_text(encoding="utf-8"))
DOC = ROOT / "docs" / "sunny-agentic" / "G1_EXPERIMENT_SPECIFICATION.md"

G1 = {c["id"]: c for c in CATALOG["cases"]
      if c["stage"] == "future_isolated_windows_only"}
G2 = {c["id"]: c for c in CATALOG["cases"]
      if c["stage"] == "future_runtime_acceptance_only"}
MEASUREMENT_IDS = {"CLIENT_SENT", "HTTP_SYS", "LISTENER", "CANDIDATE", "CLEANUP"}
PLATFORM_IDS = {"PLATFORM-01", "PLATFORM-02", "PLATFORM-03", "PLATFORM-04"}
LAYER_KEYS = {"client_transmitted", "http_sys_pre_handler", "listener_exposed"}


def validate_plan(plan: dict, template: dict) -> None:
    """Deliberately NO 'GO' outcome; rejects forged G1 execution evidence."""
    assert plan["schema_version"] == 1
    assert plan["phase"] == "2I"
    assert plan["name"] == "sunny-g1-disposable-experiment-g0-spec"
    assert plan["source_parent_sha"] == "83609912c36f20e8e7d4b325e749c0a4399d9b02"
    assert plan["g0_status"] == "offline_design_only"
    assert plan["g1_decision"] == "NO_GO_G1_START"
    for flag in ("operator_authorized", "g1_executed", "g2_executed",
                 "tests_run_on_windows", "numeric_ratified"):
        assert plan[flag] is False
    for key in ("selected_transport", "disposable_port", "second_disposable_port",
                "executable_build_sha", "approved_process_inventory",
                "independent_stop_owner", "approval_reference"):
        assert plan[key] is None
    assert plan["current_experiment_stage"] == "source_review_only"
    assert len(plan["no_live_targets"]) >= 7
    assert "Sunny" in " ".join(plan["no_live_targets"])
    assert "main" in " ".join(plan["no_live_targets"])

    layers = plan["measurement_interfaces"]
    assert isinstance(layers, list) and len(layers) == 5
    assert {x["id"] for x in layers} == MEASUREMENT_IDS
    for layer in layers:
        assert len(layer["fields"]) >= 4
        assert len(layer["not_trusted_for"]) >= 1
        assert len(layer["origin"]) > 18
    assert next(x for x in layers if x["id"] == "HTTP_SYS")["trusted_for"] == []
    assert next(x for x in layers if x["id"] == "CLEANUP")["trusted_for"] == []

    unresolved = plan["unresolved_platform_choices"]
    assert len(unresolved) == 4
    assert {x["id"] for x in unresolved} == PLATFORM_IDS
    assert all(x["status"] == "not_established" and
               x["fallback"].startswith("BLOCK") for x in unresolved)
    assert "NO_GO" in plan["go_no_go_policy"]["entry"]
    assert "37" in plan["go_no_go_policy"]["exit"]
    assert "13 G2" in plan["go_no_go_policy"]["exit"]
    assert "BLOCK" in plan["go_no_go_policy"]["unknown"]
    assert plan["go_no_go_policy"]["no_automatic_restart"] is True
    assert "quarantine" in plan["go_no_go_policy"]["unsafe"]

    cases = plan["case_plans"]
    assert len(cases) == 37
    assert len(G1) == 37 and len(G2) == 13
    assert len({x["case_id"] for x in cases}) == 37
    assert {x["case_id"] for x in cases} == set(G1)
    assert all(x["case_id"] not in G2 for x in cases)
    for case in cases:
        src = G1[case["case_id"]]
        assert case["source_scenario"] == src["scenario"]
        assert case["priority"] == src["priority"]
        assert case["required_outcome_class"] == src["outcome_class"]
        assert case["stage"] == "future_isolated_windows_only"
        assert case["status"] == "not_run"
        assert case["post_run_verdict"] == "unobserved"
        assert case["evidence_reference"] is None
        assert case["fixture_id"] == f"FX-{case['case_id']}"
        assert case["fixture_kind"] == "described_only_no_raw_payload"
        assert len(case["recipe"]) >= 35
        assert isinstance(case["capture_fields"], list) and len(case["capture_fields"]) >= 3
        assert case["test_environment"] == "future_disposable_loopback_only"
        if case["case_id"] == "ENV-02":
            assert case["secondary_port_policy"] == (
                "offline_mismatch_by_default_or_separately_approved_disposable_only")
        else:
            assert case["secondary_port_policy"] == "never_discover_existing_services"

    assert template["schema_version"] == 1
    assert template["phase"] == "2I"
    assert template["template_only"] is True
    assert template["evidence_status"] == "not_run"
    assert template["real_windows_evidence"] is False
    assert template["g1_approval"] is False
    assert template["case_id"] is None
    assert template["fixture_id"] is None
    assert template["source_plan_sha"] is None
    assert template["review"]["verdict"] == "not_run"
    assert template["review"]["unknowns_blocked"] is True
    assert template["review"]["stop_triggered"] is False
    assert template["review"]["new_restart_approval"] is None
    assert set(template["three_layer_observations"]) == LAYER_KEYS
    assert template["three_layer_observations"]["http_sys_pre_handler"]["observability"] == "unobserved"
    assert template["three_layer_observations"]["http_sys_pre_handler"]["direct_observation"] is None
    assert template["three_layer_observations"]["listener_exposed"]["raw_field_provenance_confirmed"] is None
    for section in ("three_layer_observations", "effects_and_responses",
                    "lifecycle", "approved_testbed"):
        assert section in template
    assert template["approved_testbed"]["bound_endpoints"] == []
    assert template["effects_and_responses"]["protected_effect_count"] is None
    assert template["lifecycle"]["read_completion_observed"] is None
    assert template["lifecycle"]["transport_quiescence_proven"] is None
    assert template["lifecycle"]["buffer_ownership_proven"] is None
    assert "ambiguous_transform" in template["allowed_future_verdicts"]
    assert "timeout_unaborted" in template["allowed_future_verdicts"]
    assert len(template["forbidden_evidence"]) >= 5
    # Explicitly reject any fabricated measurements or authorization in G0.
    for section in ("approved_testbed", "three_layer_observations",
                    "effects_and_responses", "lifecycle"):
        def check_unrun(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, dict):
                        check_unrun(value)
                    elif isinstance(value, list):
                        assert value == []
                    elif key == "observability":
                        assert value == "unobserved"
                    else:
                        assert value is None
        check_unrun(template[section])


def test_g0_plan_is_intact_and_not_authorization() -> None:
    validate_plan(PLAN, TEMPLATE)
    assert READINESS["decision"] == "NO_GO_G1_START"
    assert READINESS["approved_to_open_listener"] is False
    assert all(g["entry_status"] == "open" for g in READINESS["gates"])
    assert len(READINESS["gates"]) == 11
    assert all(c["status"] == "not_run" for c in CATALOG["cases"])
    assert len(CATALOG["cases"]) == 50
    assert sum(c["priority"] == "blocker" for c in CATALOG["cases"]) == 17
    assert LIMITS["g1_approval"] is False
    assert LIMITS["approval_state"] == "proposed_not_ratified"


@pytest.mark.parametrize("case_id", sorted(G1))
def test_each_future_G1_probe_matches_original_unexecuted_case(case_id: str) -> None:
    validate_plan(PLAN, TEMPLATE)
    matches = [x for x in PLAN["case_plans"] if x["case_id"] == case_id]
    assert len(matches) == 1
    assert matches[0]["required_outcome_class"] == G1[case_id]["outcome_class"]


@pytest.mark.parametrize("mutation", [
    "fake_approval", "fake_run", "fake_windows", "ratify_limits",
    "choose_port", "choose_server", "operator_id", "select_transport",
    "change_source", "fake_go", "auto_restart", "missing_platform",
    "platform_proven", "unknown_not_blocked", "drop_case",
    "duplicate_case", "add_g2", "mark_case_passed", "fake_case_evidence",
    "grant_existing_endpoint", "allow_second_port", "switch_outcome",
    "swap_scenario", "short_recipe", "fake_fixture_payload",
])
def test_malformed_or_premature_experiment_plans_never_validate(mutation: str) -> None:
    p = copy.deepcopy(PLAN)
    first = p["case_plans"][0]
    if mutation == "fake_approval":
        p["operator_authorized"] = True
    elif mutation == "fake_run":
        p["g1_executed"] = True
    elif mutation == "fake_windows":
        p["tests_run_on_windows"] = True
    elif mutation == "ratify_limits":
        p["numeric_ratified"] = True
    elif mutation == "choose_port":
        p["disposable_port"] = 18770
    elif mutation == "choose_server":
        p["executable_build_sha"] = "pretend"
    elif mutation == "operator_id":
        p["independent_stop_owner"] = "someone"
    elif mutation == "select_transport":
        p["selected_transport"] = "HttpListener"
    elif mutation == "change_source":
        p["source_parent_sha"] = "main"
    elif mutation == "fake_go":
        p["g1_decision"] = "GO"
    elif mutation == "auto_restart":
        p["go_no_go_policy"]["no_automatic_restart"] = False
    elif mutation == "missing_platform":
        p["unresolved_platform_choices"].pop()
    elif mutation == "platform_proven":
        p["unresolved_platform_choices"][0]["status"] = "verified"
    elif mutation == "unknown_not_blocked":
        p["go_no_go_policy"]["unknown"] = "ALLOW"
    elif mutation == "drop_case":
        p["case_plans"].pop()
    elif mutation == "duplicate_case":
        p["case_plans"][1]["case_id"] = first["case_id"]
    elif mutation == "add_g2":
        first["case_id"] = "AUTH-03"
    elif mutation == "mark_case_passed":
        first["status"] = "passed"
    elif mutation == "fake_case_evidence":
        first["evidence_reference"] = "real_wins"
    elif mutation == "grant_existing_endpoint":
        p["no_live_targets"] = []
    elif mutation == "allow_second_port":
        p["case_plans"][1]["secondary_port_policy"] = "free_choice"
    elif mutation == "switch_outcome":
        first["required_outcome_class"] = "authorized_synthetic_candidate_only"
    elif mutation == "swap_scenario":
        first["source_scenario"] = "different source"
    elif mutation == "short_recipe":
        first["recipe"] = "test"
    else:
        first["fixture_kind"] = "sendable_bytes"
    with pytest.raises((AssertionError, KeyError, TypeError, ValueError)):
        validate_plan(p, TEMPLATE)


@pytest.mark.parametrize("mutation", [
    "fake_evidence", "fake_case_id", "fake_approval", "fake_verdict",
    "fake_kernel_observation", "fake_raw_header_provenance", "fake_response",
    "fake_cleanup", "fake_time", "fake_stop", "secret_endpoint", "missing_layer",
])
def test_evidence_template_does_not_look_like_collected_windows_evidence(mutation: str) -> None:
    t = copy.deepcopy(TEMPLATE)
    if mutation == "fake_evidence":
        t["real_windows_evidence"] = True
    elif mutation == "fake_case_id":
        t["case_id"] = "TIME-01"
    elif mutation == "fake_approval":
        t["g1_approval"] = True
    elif mutation == "fake_verdict":
        t["review"]["verdict"] = "passed"
    elif mutation == "fake_kernel_observation":
        t["three_layer_observations"]["http_sys_pre_handler"]["direct_observation"] = "observed"
    elif mutation == "fake_raw_header_provenance":
        t["three_layer_observations"]["listener_exposed"]["raw_field_provenance_confirmed"] = True
    elif mutation == "fake_response":
        t["effects_and_responses"]["client_http_status"] = 200
    elif mutation == "fake_cleanup":
        t["lifecycle"]["read_completion_observed"] = True
    elif mutation == "fake_time":
        t["lifecycle"]["first_byte_ms"] = 1
    elif mutation == "fake_stop":
        t["review"]["stop_triggered"] = True
    elif mutation == "secret_endpoint":
        t["approved_testbed"]["bound_endpoints"] = ["http://example.com"]
    else:
        del t["three_layer_observations"]["listener_exposed"]
    with pytest.raises((AssertionError, KeyError, TypeError, ValueError)):
        validate_plan(PLAN, t)


@pytest.mark.parametrize("gate_id", [f"G1E-{i:02d}" for i in range(1, 12)])
def test_all_entry_gate_ids_stay_open_and_unapproved(gate_id: str) -> None:
    gates = [x for x in READINESS["gates"] if x["id"] == gate_id]
    assert len(gates) == 1
    assert gates[0]["entry_blocker"] is True
    assert gates[0]["entry_status"] == "open"
    assert gates[0]["evidence_at_entry"] == "none"


def test_document_retains_no_go_stop_and_separate_g1_g2() -> None:
    doc = DOC.read_text(encoding="utf-8")
    for part in (
        "NO-GO", "G0", "G1", "G2", "37", "13", "50", "11",
        "HTTP.sys", "GetContextAsync", "RawUrl", "unobservable",
        "no automatic", "first byte", "abort", "quarantine",
        "explicit approval", "synthetic", "evidence template",
        "independent", "not a runnable server", "main",
    ):
        assert part.lower() in doc.lower(), part
    assert PLAN["g1_decision"] == "NO_GO_G1_START"
