"""Phase 2J: offline regression checks for the G1 blocker resolution plan.

G0-only document consistency checks. No network sockets, Windows APIs,
threads, timers, game files, API credentials, or live runtime operations.
Tests NEVER return approval or establish Windows evidence.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "reference/sunny_g1_resolution/plan.json"
DOC_PATH = ROOT / "docs/sunny-agentic/G1_BLOCKER_RESOLUTION_PLAN.md"
PLAN = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
GATES = json.loads((ROOT / "reference/sunny_g1_readiness/gates.json").read_text(encoding="utf-8"))
CASES = json.loads((ROOT / "reference/sunny_windows_http_acceptance/cases.json").read_text(encoding="utf-8"))
LIMITS = json.loads((ROOT / "reference/sunny_http_resource_limits/proposed_limits.json").read_text(encoding="utf-8"))
EXPERIMENT = json.loads((ROOT / "reference/sunny_g1_experiment/experiment_plan.json").read_text(encoding="utf-8"))


EXPECTED_ORDER = (
    "G1E-03", "G1E-04", "G1E-02", "G1E-05", "G1E-06", "G1E-01",
    "G1E-10", "G1E-07", "G1E-08", "G1E-11", "G1E-09",
)
PACKETS = (
    "P1_TRANSPORT_FEASIBILITY", "P2_STOP_AND_ISOLATE",
    "P3_FINITE_EXPERIMENT_REVIEW", "P4_EXPLICIT_OPERATOR_DECISION",
)
ALLOWED_MODES = {
    "platform_method_selection", "offline_source_design",
    "numeric_signoff_required", "fixture_source_review",
    "explicit_user_operator_approval",
}
EXPECTED_DEPENDENCIES = {
    "G1E-03": [], "G1E-04": [], "G1E-02": [],
    "G1E-05": [], "G1E-06": ["G1E-05"],
    "G1E-01": ["G1E-03", "G1E-04", "G1E-02", "G1E-05", "G1E-06"],
    "G1E-10": ["G1E-02"],
    "G1E-07": ["G1E-03", "G1E-04", "G1E-05", "G1E-06"],
    "G1E-08": ["G1E-01", "G1E-02", "G1E-07", "G1E-10"],
    "G1E-11": ["G1E-02", "G1E-05", "G1E-06", "G1E-08", "G1E-10"],
    "G1E-09": [
        "G1E-01", "G1E-02", "G1E-03", "G1E-04", "G1E-05",
        "G1E-06", "G1E-07", "G1E-08", "G1E-10", "G1E-11",
    ],
}


EXPECTED_GATE_REVIEW = {
    "G1E-03": ("platform_method_selection", "independent_windows_transport_reviewer"),
    "G1E-04": ("platform_method_selection", "independent_windows_transport_reviewer"),
    "G1E-02": ("platform_method_selection", "independent_windows_transport_reviewer"),
    "G1E-05": ("offline_source_design", "independent_safety_reviewer"),
    "G1E-06": ("offline_source_design", "independent_safety_reviewer"),
    "G1E-01": ("offline_source_design", "independent_isolation_reviewer"),
    "G1E-10": ("offline_source_design", "independent_privacy_reviewer"),
    "G1E-07": ("numeric_signoff_required", "independent_limits_reviewer"),
    "G1E-08": ("fixture_source_review", "independent_fixture_reviewer"),
    "G1E-11": ("offline_source_design", "independent_acceptance_reviewer"),
    "G1E-09": ("explicit_user_operator_approval", "user_operator"),
}
EXPECTED_PACKET_GATES = (
    ["G1E-03", "G1E-04", "G1E-02"],
    ["G1E-05", "G1E-06", "G1E-01"],
    ["G1E-10", "G1E-07", "G1E-08", "G1E-11"],
    ["G1E-09"],
)


def check_plan(plan: dict, experiment: dict = EXPERIMENT) -> str:
    """Only validates the current unapproved baseline: no GO return path."""
    assert plan["schema_version"] == 1
    assert plan["name"] == "sunny-g1-blocker-resolution-phase2j"
    assert plan["phase"] == "2J"
    assert plan["base_commit"] == "e0710b4d87f14ae411b7d4067896ba5ca3648b3c"
    assert plan["authority"] == "G0 offline planning ONLY"
    assert plan["decision"] == "NO_GO_G1_START"
    for key in ("permission_to_bind_port", "disposable_test_approved",
                "windows_g1_tested", "g2_implemented", "limits_ratified"):
        assert plan[key] is False, key
    assert plan["selected_transport"] is None
    assert plan["operator_approval_reference"] is None
    for field, filename in (
        ("source_readiness", "reference/sunny_g1_readiness/gates.json"),
        ("source_cases", "reference/sunny_windows_http_acceptance/cases.json"),
        ("source_limits", "reference/sunny_http_resource_limits/proposed_limits.json"),
        ("source_experiment", "reference/sunny_g1_experiment/experiment_plan.json"),
    ):
        assert plan[field] == filename
        assert (ROOT / filename).is_file()

    source_gates = {g["id"]: g for g in GATES["gates"]}
    assert len(source_gates) == len(GATES["gates"]) == 11
    assert all(g["entry_status"] == "open" and g["entry_blocker"] is True and
               g["evidence_at_entry"] == "none" for g in source_gates.values())
    assert GATES["decision"] == "NO_GO_G1_START"
    assert GATES["approved_to_open_listener"] is False

    source_cases = {c["id"]: c for c in CASES["cases"]}
    assert len(CASES["cases"]) == len(source_cases) == 50
    assert sum(c["stage"] == "future_isolated_windows_only" for c in CASES["cases"]) == 37
    assert sum(c["stage"] == "future_runtime_acceptance_only" for c in CASES["cases"]) == 13
    assert sum(c["priority"] == "blocker" for c in CASES["cases"]) == 17
    assert all(c["status"] == "not_run" for c in CASES["cases"])
    assert CASES["execution_status"] == "not_run"
    assert CASES["real_transport_tested"] is False

    assert LIMITS["approval_state"] == "proposed_not_ratified"
    assert LIMITS["g1_approval"] is False
    assert LIMITS["windows_http_sys_tested"] is False
    assert experiment["g1_decision"] == "NO_GO_G1_START"
    assert experiment["operator_authorized"] is False
    assert len(experiment["case_plans"]) == 37
    assert all(x["status"] == "not_run" for x in experiment["case_plans"])

    g1_ids = {c["id"] for c in CASES["cases"]
              if c["stage"] == "future_isolated_windows_only"}
    probes = experiment["case_plans"]
    assert {x["case_id"] for x in probes} == g1_ids
    assert all(x["stage"] == "future_isolated_windows_only" and
               x["post_run_verdict"] == "unobserved" and
               x["evidence_reference"] is None for x in probes)
    for key in ("g1_executed", "g2_executed", "tests_run_on_windows", "numeric_ratified"):
        assert experiment[key] is False
    for key in ("selected_transport", "disposable_port", "second_disposable_port",
                "executable_build_sha", "approved_process_inventory",
                "independent_stop_owner", "approval_reference"):
        assert experiment[key] is None
    assert plan["safety_review_scheduling"] == {
        "start_with": "P1_TRANSPORT_FEASIBILITY",
        "parallel_gate_ids": ["G1E-05", "G1E-06"],
        "transport_choice_finalization_requires": [
            "G1E-02", "G1E-03", "G1E-04", "G1E-05", "G1E-06"],
        "unknown_required_safety_property": "BLOCK_NO_GO",
        "review_iteration": "P1 and P2 may revise proposals together offline; no mutual gate-closure dependency and no listener",
    }

    assert plan["expected_counts"] == {
        "entry_open": 11, "phase2f_total": 50, "g1_not_run": 37,
        "g2_not_run": 13, "priority_blockers": 17,
    }
    entries = plan["entries"]
    assert len(entries) == 11
    assert tuple(x["id"] for x in entries) == EXPECTED_ORDER
    assert [x["rank"] for x in entries] == list(range(1, 12))
    assert set(x["id"] for x in entries) == set(source_gates)
    seen = set()
    for entry in entries:
        gate_id = entry["id"]
        src = source_gates[gate_id]
        assert entry["status"] == "open"
        assert entry["g0_work_state"] == "not_started"
        assert entry["entry_prerequisite"] is True
        assert entry["gate_approved"] is False
        assert entry["platform_measurement_claimed"] is False
        assert entry["approval_reference"] is None
        assert entry["evidence_reference"] is None
        assert (entry["mode"], entry["review_owner_role"]) == EXPECTED_GATE_REVIEW[gate_id]
        assert entry["mode"] in ALLOWED_MODES
        assert entry["packet"] in PACKETS
        assert entry["source_case_ids"] == src["g1_case_ids"]
        assert entry["source_required_artifact"] == src["required_reviewed_artifact"]
        assert len(entry["deliverable"]) >= 50
        assert len(entry["entry_closure_evidence"]) >= 60
        assert len(entry["explicit_fallback"]) >= 50
        assert entry["review_owner_role"].startswith(("independent_", "user_"))
        assert entry["depends_on"] == EXPECTED_DEPENDENCIES[gate_id]
        assert all(dep in seen for dep in entry["depends_on"]), gate_id
        assert all(source_cases[cid]["stage"] == "future_isolated_windows_only"
                   for cid in entry["source_case_ids"])
        seen.add(gate_id)

    packets = plan["packets"]
    assert len(packets) == 4
    assert tuple(p["id"] for p in packets) == PACKETS
    assert tuple(p["gate_ids"] for p in packets) == EXPECTED_PACKET_GATES
    assert [p["sequence"] for p in packets] == [1, 2, 3, 4]
    assert all(p["status"] == "not_started" for p in packets)
    assert [p["can_progress_offline"] for p in packets] == [True, True, True, False]
    assert {x for p in packets for x in p["gate_ids"]} == set(source_gates)
    assert sum(len(p["gate_ids"]) for p in packets) == 11
    assert all(x["packet"] == p["id"] for p in packets
               for x in entries if x["id"] in p["gate_ids"])
    assert packets[-1]["gate_ids"] == ["G1E-09"]
    assert entries[-1]["mode"] == "explicit_user_operator_approval"
    assert len(plan["resolution_principles"]) >= 6
    assert len(plan["prohibited_actions"]) >= 6
    assert "37" in plan["g1_exit_requirements"]
    assert "13" in plan["g2_exit_requirements"]
    return "NO_GO_G1_START"


def test_current_plan_is_consistent_and_no_go() -> None:
    assert check_plan(PLAN) == "NO_GO_G1_START"
    assert DOC_PATH.is_file()
    doc = DOC_PATH.read_text(encoding="utf-8")
    for part in ("Phase 2J", "NO-GO", "11", "37", "13", "50",
                 "G1E-09", "G1E-03", "HttpListener", "GetContextAsync",
                 "before", "unratified", "first-byte", "independent",
                 "no automatic", "quarantine", "explicit", "main"):
        # Wording remains a human-reviewed documentation obligation.
        assert part.lower() in doc.lower(), part


@pytest.mark.parametrize("entry_id", EXPECTED_ORDER)
def test_each_entry_has_source_grounded_work_and_closure_not_windows_results(entry_id):
    entry = next(e for e in PLAN["entries"] if e["id"] == entry_id)
    assert entry["status"] == "open"
    assert entry["approval_reference"] is None
    assert entry["evidence_reference"] is None
    assert entry["gate_approved"] is False
    assert "review" in entry["entry_closure_evidence"].lower() or "explicit" in entry["entry_closure_evidence"].lower()


@pytest.mark.parametrize("change", [
    "pretend_go", "fake_approval", "fake_transport", "ratify_limits",
    "fake_windows", "change_g0_authority", "shorten_packet_plan",
    "drop_gate", "duplicate_gate", "reorder_entry", "bad_dependency",
    "fabricate_gate_result", "fake_gate_evidence", "reassign_gate_to_packet",
    "delete_case_link", "inject_g2_case_link", "delete_source_artifact",
    "skip_operator_gate", "allow_offline_operator_approval",
])
def test_unsafe_plan_mutations_cannot_validate(change):
    p = copy.deepcopy(PLAN)
    if change == "pretend_go":
        p["decision"] = "GO"
    elif change == "fake_approval":
        p["operator_approval_reference"] = "unverified"
    elif change == "fake_transport":
        p["selected_transport"] = "HttpListener"
    elif change == "ratify_limits":
        p["limits_ratified"] = True
    elif change == "fake_windows":
        p["windows_g1_tested"] = True
    elif change == "change_g0_authority":
        p["authority"] = "run live tests"
    elif change == "shorten_packet_plan":
        p["packets"].pop()
    elif change == "drop_gate":
        p["entries"].pop()
    elif change == "duplicate_gate":
        p["entries"][0]["id"] = p["entries"][1]["id"]
    elif change == "reorder_entry":
        p["entries"][0], p["entries"][1] = p["entries"][1], p["entries"][0]
    elif change == "bad_dependency":
        p["entries"][0]["depends_on"] = ["G1E-09"]
    elif change == "fabricate_gate_result":
        p["entries"][0]["gate_approved"] = True
    elif change == "fake_gate_evidence":
        p["entries"][0]["evidence_reference"] = "fabricated"
    elif change == "reassign_gate_to_packet":
        p["entries"][0]["packet"] = "P4_EXPLICIT_OPERATOR_DECISION"
    elif change == "delete_case_link":
        p["entries"][0]["source_case_ids"].pop()
    elif change == "inject_g2_case_link":
        p["entries"][0]["source_case_ids"].append("AUTH-03")
    elif change == "delete_source_artifact":
        p["entries"][0]["source_required_artifact"] = ""
    elif change == "skip_operator_gate":
        p["packets"][-1]["gate_ids"] = []
    else:
        p["packets"][-1]["can_progress_offline"] = True
    with pytest.raises((AssertionError, KeyError, TypeError, ValueError)):
        check_plan(p)


def test_progress_does_not_require_37_windows_tests_before_g1_entry() -> None:
    assert len([c for c in CASES["cases"] if
                c["stage"] == "future_isolated_windows_only" and
                c["status"] == "not_run"]) == 37
    assert PLAN["entries"][-1]["id"] == "G1E-09"
    assert PLAN["permission_to_bind_port"] is False
    # Future G1 approval is separate from running its exit measurements.
    assert "After separately authorized G1" in PLAN["g1_exit_requirements"]


def test_operator_consent_is_only_last_step_after_all_other_ten_gates() -> None:
    operator = PLAN["entries"][-1]
    assert operator["id"] == "G1E-09"
    assert operator["review_owner_role"] == "user_operator"
    assert set(operator["depends_on"]) == set(EXPECTED_ORDER[:-1])
    assert operator["approval_reference"] is None


@pytest.mark.parametrize("change", [
    "coordinated_packet_move", "wrong_mode", "wrong_owner", "remove_transport_barrier",
    "stop_delayed", "unknown_safety_deferred", "self_cycle", "mutual_cycle", "skip_privacy_review",
])
def test_review_and_safety_contract_mutations(change):
    p = copy.deepcopy(PLAN)
    entries = {e["id"]: e for e in p["entries"]}
    if change == "coordinated_packet_move":
        p["packets"][0]["gate_ids"].remove("G1E-02")
        p["packets"][1]["gate_ids"].append("G1E-02")
        entries["G1E-02"]["packet"] = PACKETS[1]
    elif change == "wrong_mode":
        entries["G1E-07"]["mode"] = "offline_source_design"
    elif change == "wrong_owner":
        entries["G1E-07"]["review_owner_role"] = "independent_fixture_reviewer"
    elif change == "remove_transport_barrier":
        entries["G1E-01"]["depends_on"] = ["G1E-05", "G1E-06"]
    elif change == "skip_privacy_review":
        entries["G1E-08"]["depends_on"].remove("G1E-10")
    elif change == "stop_delayed":
        p["safety_review_scheduling"]["parallel_gate_ids"] = []
    elif change == "unknown_safety_deferred":
        p["safety_review_scheduling"]["unknown_required_safety_property"] = "measure_during_G1"
    elif change == "self_cycle":
        entries["G1E-03"]["depends_on"] = ["G1E-03"]
    else:
        entries["G1E-05"]["depends_on"] = ["G1E-06"]
    with pytest.raises(AssertionError):
        check_plan(p)


@pytest.mark.parametrize("change", ["duplicate_id", "g2_substitution", "fake_verdict", "fake_evidence"])
def test_experiment_identity_and_unobserved_evidence_mutations(change):
    experiment = copy.deepcopy(EXPERIMENT)
    probes = experiment["case_plans"]
    if change == "duplicate_id":
        probes[0]["case_id"] = probes[1]["case_id"]
    elif change == "g2_substitution":
        probes[0]["case_id"] = next(c["id"] for c in CASES["cases"]
                                    if c["stage"] == "future_runtime_acceptance_only")
    elif change == "fake_verdict":
        probes[0]["post_run_verdict"] = "GO"
    else:
        probes[0]["evidence_reference"] = "CI-is-not-Windows-proof"
    with pytest.raises(AssertionError):
        check_plan(PLAN, experiment)
