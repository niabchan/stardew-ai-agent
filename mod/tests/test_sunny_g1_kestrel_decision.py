"""Phase 2L G0-only Kestrel candidate and independent-stop OFFLINE checks.

These are planning-artifact guards, NOT Windows, HTTP, credential, gameplay,
or abort effectiveness tests. No sockets, processes, .NET APIs, timers or
actual ownership/authorization is involved.
"""
from __future__ import annotations

import copy
import json
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "reference" / "sunny_g1_kestrel_decision"


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(raw):
    return json.loads(raw, object_pairs_hook=reject_duplicate_keys)


def semantic_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


FIELD = load_json((REF / "field_provenance.json").read_text(encoding="utf-8"))
STOP = load_json((REF / "stop_ownership.json").read_text(encoding="utf-8"))
READINESS = load_json((ROOT / "reference/sunny_g1_readiness/gates.json").read_text(encoding="utf-8"))
CASES = load_json((ROOT / "reference/sunny_windows_http_acceptance/cases.json").read_text(encoding="utf-8"))
LIMITS = load_json((ROOT / "reference/sunny_http_resource_limits/proposed_limits.json").read_text(encoding="utf-8"))
BASE = load_json((ROOT / "reference/sunny_g1_transport_feasibility/matrix.json").read_text(encoding="utf-8"))
DOC = ROOT / "docs/sunny-agentic/G1_KESTREL_DECISION_DESIGN.md"

# Reviewed semantic pins detect fixture drift, not authenticity or changes to this test.
# Never derive expected pins from the loaded artifacts at test runtime.
REVIEWED_SHA256 = {'FIELD': '3d9423814c0016b0f96ae4b06e32315e8f5521c1e9b2852b03c8aa46f2b2062b',
 'STOP': 'c818503f6c63580180eeeaaa11f5671586e9e5cdaf3db4ed05c2b5358db69884',
 'READINESS': '6a3b30fe50316a6d015b64673ece437849598ef69f08520a623255cb8db4beba',
 'CASES': 'ae192787a75bbc8ccec6e362720adfd540ebb88a1d7bda3b9b2f40d88dc24f82',
 'LIMITS': '61ac96429122658058c18e903f69d934fdaafafa9cd991e41d7d2b0f16da9605',
 'BASE': '85d89efb5b51348cef587b47ab4980b08092760375ad7cc0a6f39500877b5ef0'}


FIELD_IDS = tuple(f"FIELD-{i:02d}" for i in range(1, 19))
GATE_BY_FIELD = {
    **{f"FIELD-{i:02d}": "G1E-03" for i in range(1, 4)},
    **{f"FIELD-{i:02d}": "G1E-04" for i in range(4, 8)},
    **{f"FIELD-{i:02d}": "G1E-02" for i in range(8, 14)},
    **{f"FIELD-{i:02d}": "G1E-05" for i in range(14, 16)},
    **{f"FIELD-{i:02d}": "G1E-06" for i in range(16, 19)},
}
EXPECTED_ASSESSMENTS = {
    "FIELD-01": "documented_partial", "FIELD-02": "not_established",
    "FIELD-03": "method_design_required", "FIELD-04": "documented_partial",
    "FIELD-05": "documented_partial", "FIELD-06": "documented_partial",
    "FIELD-07": "not_established", "FIELD-08": "documented_partial",
    "FIELD-09": "documented_partial", "FIELD-10": "not_established",
    "FIELD-11": "documented_partial", "FIELD-12": "method_design_required",
    "FIELD-13": "method_design_required", "FIELD-14": "documented_partial",
    "FIELD-15": "not_established", "FIELD-16": "not_established",
    "FIELD-17": "not_established", "FIELD-18": "method_design_required",
}
SOURCES = {
    "KESTREL-OPTIONS", "KESTREL-ENDPOINTS", "KESTREL-SECURITY",
    "RAW-FEATURE", "CONNECTION-FEATURE", "HTTP-CONTEXT",
    "HTTP-CONTEXT-GUIDE", "PREVIOUS-2K",
}
STOP_ROLES = (
    "external_operator", "fixture_sender", "transport_process",
    "request_read_task", "response_write_task", "pooled_buffers_and_leases",
    "evidence_observer", "manual_rollback_and_restart",
)
STOP_PARAMS = {
    "stop_owner_name", "external_control_channel",
    "abort_scope_and_collateral", "first_byte_clock_provenance",
    "abort_grace_limit_ms", "external_stop_deadline_ms",
    "total_teardown_deadline_ms", "buffer_owner_ledger_implementation",
    "test_process_binary_sha", "approved_disposable_endpoint",
}
EXACT_FLAGS = ("g1_variant_authorized", "operator_approval", "numeric_limits_ratified",
               "live_windows_observations", "g2_runtime_acceptance")
ROW_KEYS = {
    "id", "gate_id", "field", "origin_layer",
    "documented_interface_or_control", "source_ids", "design_assessment",
    "entry_review_needed", "mandatory_unknown_fallback", "evidence_owner_role",
    "phase2f_case_ids", "actual_windows_observation", "validated_for_net6",
    "approved", "current_verdict",
}
OWNERSHIP_KEYS = {
    "id", "role", "assigned_identity", "review_owner_role",
    "required_obligation", "required_terminal_evidence", "on_unresolved",
    "implemented", "approved",
}
G1_CASES = {
    c["id"] for c in CASES["cases"]
    if c["stage"] == "future_isolated_windows_only"
}


def validate_field_contract(m: dict) -> None:
    """Require the current, entirely unapproved G0 proposal (no GO path)."""
    assert semantic_digest(m) == REVIEWED_SHA256["FIELD"]
    assert m["schema_version"] == 1
    assert m["phase"] == "2L"
    assert m["name"] == "sunny-kestrel-provisional-transport-decision-g0"
    assert m["parent_sha"] == "36d90ae0e814f94cb7266ff789f90a3ef3477bff"
    assert m["authority"] == "G0_OFFLINE_DESIGN_ONLY"
    assert m["decision"] == "NO_GO_G1_START"
    assert m["candidate"] == "Kestrel"
    assert m["candidate_state"] == "prospective_disposable_variant_only_not_selected"
    assert m["selected_transport"] is None
    assert all(m[key] is False for key in EXACT_FLAGS)
    assert m["no_real_data"] is True
    assert m["no_port_selected"] is True
    assert m["no_listener_created"] is True
    assert m["no_auto_go"] is True
    assert "net6" in m["source_version"] and "10.x" in m["source_version"]

    links = m["doc_sources"]
    assert len(links) == len(SOURCES) == len({s["id"] for s in links})
    assert {s["id"] for s in links} == SOURCES
    for source in links:
        assert set(source) == {"id", "url", "scope"}
        assert source["url"].startswith(("https://learn.microsoft.com/",
                                         "https://raw.githubusercontent.com/dotnet/aspnetcore/v10.0.0/",
                                         "docs/sunny-agentic/"))
        assert "http" in source["url"] or source["id"] == "PREVIOUS-2K"
        assert len(source["scope"]) >= 65

    assert m["open_entry_gate_ids"] == [f"G1E-{i:02d}" for i in range(1, 12)]
    rows = m["field_rows"]
    assert len(rows) == len(FIELD_IDS)
    assert [r["id"] for r in rows] == list(FIELD_IDS)
    for r in rows:
        assert set(r) == ROW_KEYS
        assert r["gate_id"] == GATE_BY_FIELD[r["id"]]
        assert r["design_assessment"] == EXPECTED_ASSESSMENTS[r["id"]]
        assert r["current_verdict"] == "BLOCK_PENDING_REVIEW"
        assert r["actual_windows_observation"] is False
        assert r["validated_for_net6"] is False
        assert r["approved"] is False
        assert isinstance(r["field"], str) and len(r["field"]) >= 12
        assert isinstance(r["origin_layer"], str) and len(r["origin_layer"]) >= 12
        assert len(r["documented_interface_or_control"]) >= 60
        assert len(r["entry_review_needed"]) >= 60
        assert len(r["mandatory_unknown_fallback"]) >= 30
        assert r["evidence_owner_role"].startswith("independent_")
        assert len(set(r["source_ids"])) == len(r["source_ids"]) >= 1
        assert set(r["source_ids"]) <= SOURCES
        assert len(set(r["phase2f_case_ids"])) == len(r["phase2f_case_ids"]) >= 1
        assert set(r["phase2f_case_ids"]) <= G1_CASES
    assert m["known_blockers"] == [
        "FIELD-02", "FIELD-07", "FIELD-10",
        "FIELD-15", "FIELD-16", "FIELD-17",
    ]
    assert set(m["requirements"]) == {
        "provenance", "admission", "prehandler", "abort", "version",
        "g1_mapping", "stop", "decision_boundary",
    }
    for key, value in m["requirements"].items():
        assert isinstance(value, str) and len(value) >= 75, key
    assert "BLOCK" in m["requirements"]["provenance"]
    assert "37" in m["requirements"]["g1_mapping"]
    assert "independent" in m["requirements"]["stop"].lower()
    assert "No G1 entry gate closes automatically" in m["requirements"]["decision_boundary"]
    assert isinstance(m["next_design_review"], str) and len(m["next_design_review"]) > 90


def validate_stop_contract(s: dict) -> None:
    assert semantic_digest(s) == REVIEWED_SHA256["STOP"]
    assert s["schema_version"] == 1
    assert s["phase"] == "2L"
    assert s["name"] == "sunny-kestrel-independent-stop-ownership-g0"
    assert s["authority"] == "G0_OFFLINE_DESIGN_ONLY"
    assert s["decision"] == "NO_GO_G1_START"
    assert s["candidate"] == "Kestrel"
    for key in ("selected_abort_primitive", "operator_identity", "selected_port",
                "selected_executable"):
        assert s[key] is None
    for key in ("independent_stop_implemented", "read_completion_proven",
                "buffer_ownership_proven", "numeric_deadline_ratified",
                "g1_authorized", "no_real_observations", "no_windows_listener",
                "no_network_probe", "g2_game_authorization_not_established"):
        assert s[key] is (key in ("no_real_observations", "no_windows_listener",
                                    "no_network_probe", "g2_game_authorization_not_established"))
    assert s["no_automatic_restart"] is True
    assert s["stop_channel"] == "external_operator_owned_only_not_selected"
    assert set(s["stop_policy"]) == {
        "latch", "clock", "external", "cleanup",
        "unresolved", "escalation", "restart",
    }
    pol = s["stop_policy"]
    assert "Irreversible" in pol["latch"]
    assert "not reset" in pol["clock"]
    assert "saturated" in pol["external"]
    assert "Observe" in pol["cleanup"]
    assert "UNRESOLVED_QUARANTINED" in pol["unresolved"]
    assert "future explicit approval" in pol["escalation"]
    assert "new explicit operator approval" in pol["restart"]

    roles = s["owned_resources"]
    assert len(roles) == len(STOP_ROLES)
    assert tuple(r["role"] for r in roles) == STOP_ROLES
    assert [r["id"] for r in roles] == [f"OWN-{i:02d}" for i in range(1, 9)]
    for r in roles:
        assert set(r) == OWNERSHIP_KEYS
        assert r["assigned_identity"] is None
        assert r["implemented"] is False
        assert r["approved"] is False
        assert r["review_owner_role"].startswith(("independent_", "user_"))
        assert len(r["required_obligation"]) >= 60
        assert len(r["required_terminal_evidence"]) >= 60
        assert "BLOCK" in r["on_unresolved"]
    assert roles[0]["role"] == "external_operator"
    assert roles[-1]["review_owner_role"] == "user_operator"
    assert "process exit alone not per-request cleanup" in roles[2]["on_unresolved"]

    flow = s["proposed_state_flow"]
    assert flow == [
        "RUNNING_UNAPPROVED_MODEL", "STOP_LATCHED", "TRAFFIC_STOPPED",
        "ABORT_REQUESTED", "OBSERVE_READ_WRITE_AND_COLLATERAL",
        "QUIESCENT_EVIDENCED_OR_UNRESOLVED_QUARANTINED",
        "MANUAL_ROLLBACK", "CLOSED_NO_RESTART",
    ]
    assert s["terminal_statuses"] == [
        "QUIESCENT_EVIDENCED_OR_UNRESOLVED_QUARANTINED",
        "CLOSED_NO_RESTART",
    ]
    params = s["unselected_parameters"]
    assert len(params) == len(STOP_PARAMS)
    assert {p["id"] for p in params} == STOP_PARAMS
    for p in params:
        assert set(p) == {"id", "value", "approval_required"}
        assert p["value"] is None and p["approval_required"] is True
    assert "Design only" in s["contract_warning"]


def test_no_live_actions_or_approval_and_source_count() -> None:
    validate_field_contract(FIELD)
    validate_stop_contract(STOP)
    assert BASE["decision"] == FIELD["decision"] == STOP["decision"] == "NO_GO_G1_START"
    assert BASE["transport_choice"] == "none_selected"
    assert READINESS["decision"] == "NO_GO_G1_START"
    assert READINESS["approved_to_open_listener"] is False
    assert len(READINESS["gates"]) == 11
    assert all(g["entry_status"] == "open" for g in READINESS["gates"])
    assert LIMITS["approval_state"] == "proposed_not_ratified"
    assert LIMITS["g1_approval"] is False
    assert len(CASES["cases"]) == 50
    assert len(G1_CASES) == 37
    assert all(c["status"] == "not_run" for c in CASES["cases"])
    assert sum(c["stage"] == "future_runtime_acceptance_only" for c in CASES["cases"]) == 13


@pytest.mark.parametrize("id", FIELD_IDS)
def test_every_field_has_source_link_and_stays_blocked(id: str) -> None:
    row = next(r for r in FIELD["field_rows"] if r["id"] == id)
    assert row["gate_id"] == GATE_BY_FIELD[id]
    assert row["current_verdict"] == "BLOCK_PENDING_REVIEW"
    assert row["source_ids"] and row["phase2f_case_ids"]
    assert not row["actual_windows_observation"]
    assert not row["validated_for_net6"]


@pytest.mark.parametrize("role", STOP_ROLES)
def test_every_ownership_group_is_unimplemented(role: str) -> None:
    r = next(r for r in STOP["owned_resources"] if r["role"] == role)
    assert r["assigned_identity"] is None
    assert r["implemented"] is False
    assert r["approved"] is False


@pytest.mark.parametrize("change", [
    "approve_variant", "choose_transport", "operator_approved",
    "numeric_ratified", "fake_windows", "fake_g2", "claim_net6",
    "reassign_gate", "mark_field_passed", "delete_field", "duplicate_id",
    "wrong_source", "remove_provenance", "drop_case", "inject_g2",
    "change_assessment", "remove_blocker", "remove_requirements",
    "remove_source", "foreign_source", "choose_port", "open_listener",
    "enable_auto_go", "invent_field", "shorten_review",
])
def test_field_contract_rejects_adversarial_changes(change):
    m = copy.deepcopy(FIELD)
    r = m["field_rows"][0]
    if change == "approve_variant":
        m["g1_variant_authorized"] = True
    elif change == "choose_transport":
        m["selected_transport"] = "Kestrel"
    elif change == "operator_approved":
        m["operator_approval"] = True
    elif change == "numeric_ratified":
        m["numeric_limits_ratified"] = True
    elif change == "fake_windows":
        r["actual_windows_observation"] = True
    elif change == "fake_g2":
        m["g2_runtime_acceptance"] = True
    elif change == "claim_net6":
        r["validated_for_net6"] = True
    elif change == "reassign_gate":
        r["gate_id"] = "G1E-02"
    elif change == "mark_field_passed":
        r["current_verdict"] = "PASS"
    elif change == "delete_field":
        m["field_rows"].pop()
    elif change == "duplicate_id":
        m["field_rows"][0]["id"] = m["field_rows"][1]["id"]
    elif change == "wrong_source":
        r["source_ids"] = ["FAKE-SOURCE"]
    elif change == "remove_provenance":
        r["source_ids"] = []
    elif change == "drop_case":
        r["phase2f_case_ids"] = []
    elif change == "inject_g2":
        r["phase2f_case_ids"].append("AUTH-03")
    elif change == "change_assessment":
        r["design_assessment"] = "fully_verified"
    elif change == "remove_blocker":
        m["known_blockers"].pop()
    elif change == "remove_requirements":
        del m["requirements"]["stop"]
    elif change == "remove_source":
        m["doc_sources"].pop()
    elif change == "foreign_source":
        m["doc_sources"][0]["url"] = "https://example.com"
    elif change == "choose_port":
        m["no_port_selected"] = False
    elif change == "open_listener":
        m["no_listener_created"] = False
    elif change == "enable_auto_go":
        m["no_auto_go"] = False
    elif change == "invent_field":
        r["windows_verified"] = True
    else:
        r["entry_review_needed"] = "review"
    with pytest.raises((AssertionError, KeyError, TypeError, ValueError)):
        validate_field_contract(m)


@pytest.mark.parametrize("change", [
    "approve_real_stop", "fake_read_completion", "fake_buffer_proof",
    "approve_g1", "assign_operator", "select_port", "auto_restart",
    "delete_owner", "duplicate_owner", "finish_task_unowned",
    "remove_rollback", "remove_latch", "wrong_quarantine",
    "skip_review_parameter", "authorize_parameter", "record_experiment",
    "choose_abort", "remove_stop_policy", "invent_owner_field",
])
def test_stop_contract_rejects_unsafe_state_changes(change):
    s = copy.deepcopy(STOP)
    r = s["owned_resources"][0]
    if change == "approve_real_stop":
        s["independent_stop_implemented"] = True
    elif change == "fake_read_completion":
        s["read_completion_proven"] = True
    elif change == "fake_buffer_proof":
        s["buffer_ownership_proven"] = True
    elif change == "approve_g1":
        s["g1_authorized"] = True
    elif change == "assign_operator":
        s["operator_identity"] = "operator"
    elif change == "select_port":
        s["selected_port"] = 20000
    elif change == "auto_restart":
        s["no_automatic_restart"] = False
    elif change == "delete_owner":
        s["owned_resources"].pop()
    elif change == "duplicate_owner":
        s["owned_resources"][0]["id"] = s["owned_resources"][1]["id"]
    elif change == "finish_task_unowned":
        r["approved"] = True
    elif change == "remove_rollback":
        s["proposed_state_flow"].remove("MANUAL_ROLLBACK")
    elif change == "remove_latch":
        s["proposed_state_flow"].remove("STOP_LATCHED")
    elif change == "wrong_quarantine":
        s["terminal_statuses"] = ["CLOSED_NO_RESTART"]
    elif change == "skip_review_parameter":
        s["unselected_parameters"].pop()
    elif change == "authorize_parameter":
        s["unselected_parameters"][0]["value"] = "approved"
    elif change == "record_experiment":
        s["no_real_observations"] = False
    elif change == "choose_abort":
        s["selected_abort_primitive"] = "HttpContext.Abort"
    elif change == "remove_stop_policy":
        del s["stop_policy"]["external"]
    else:
        r["windows_stop_evidence"] = True
    with pytest.raises((AssertionError, KeyError, TypeError, ValueError)):
        validate_stop_contract(s)


def test_doc_is_consistent_with_unapproved_kestrel_candidate() -> None:
    doc = DOC.read_text(encoding="utf-8").lower()
    for phrase in (
        "phase 2l", "no-go", "candidate", "not selected", "kestrel",
        "httplistener", "http.sys", "rawtarget", "original-wire",
        "first-byte", "unobservable", "quarantine", "independent",
        "abort", "11", "37", "13", "50", "not_run", "unratified",
        "main", "operator", "manual", "net 6",
    ):
        assert phrase in doc, phrase
    assert "no requirement to choose kestrel" in doc


def test_inherited_g0_artifacts_have_no_coordinated_status_or_case_drift():
    for name, value in (("READINESS", READINESS), ("CASES", CASES),
                        ("LIMITS", LIMITS), ("BASE", BASE)):
        assert semantic_digest(value) == REVIEWED_SHA256[name]


def nested_mutations(value):
    """Mutate every leaf, inject every object, and drop/duplicate every list item."""
    if isinstance(value, dict):
        yield {**value, "forged_approval_or_ci": "passed"}
        for key, child in value.items():
            for changed in nested_mutations(child):
                yield {**value, key: changed}
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield value[:i] + value[i + 1:]
            yield value[:i] + [child, child] + value[i + 1:]
            for changed in nested_mutations(child):
                yield value[:i] + [changed] + value[i + 1:]
    else:
        yield not value if isinstance(value, bool) else "forged_observed_and_approved"


@pytest.mark.parametrize("name,validate", [
    ("FIELD", validate_field_contract), ("STOP", validate_stop_contract),
])
def test_every_nested_claim_and_schema_mutation_is_rejected(name, validate):
    for changed in nested_mutations(globals()[name]):
        with pytest.raises((AssertionError, KeyError, TypeError, ValueError)):
            validate(changed)


@pytest.mark.parametrize("raw", [
    '{"operator_approval":true,"operator_approval":false}',
    '{"row":{"approved":true,"approved":false}}',
    '{"rows":[{"implemented":true,"implemented":false}]}',
])
def test_duplicate_keys_are_rejected_before_validation(raw):
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_json(raw)


@pytest.mark.parametrize("change", ["valid_wrong_case", "valid_wrong_source",
                                      "unsafe_cleanup", "fake_ci"])
def test_previously_accepted_plausible_forgeries_are_rejected(change):
    m, s = copy.deepcopy(FIELD), copy.deepcopy(STOP)
    if change == "valid_wrong_case":
        m["field_rows"][0]["phase2f_case_ids"] = ["ENV-02"]
    elif change == "valid_wrong_source":
        m["field_rows"][0]["source_ids"] = ["RAW-FEATURE"]
    elif change == "fake_ci":
        m.update(ci_status="passed", operator_approved=True)
    else:
        s["stop_policy"]["cleanup"] = "Observe cancellation then immediately return all pooled buffers without task completion."
    with pytest.raises(AssertionError):
        if change == "unsafe_cleanup":
            validate_stop_contract(s)
        else:
            validate_field_contract(m)
