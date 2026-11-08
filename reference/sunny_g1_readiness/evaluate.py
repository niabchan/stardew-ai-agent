"""G0-only G1 entry readiness checker for Sunny.

Pure in-memory policy audit: no networking, subprocess, time, OS queries,
Game1/SMAPI, dynamic credentials or live evidence. A green check proves
consistency of unexecuted planning documents, NEVER permission to run G1.

This validator deliberately has NO GO-producing execution path. An operator
approval, true Windows transport observations and eventual G2 acceptance
require separate authorized processes outside this fixture.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any


class ReadinessError(ValueError):
    pass


REQUIRED_GATES = frozenset({
    "G1E-01", "G1E-02", "G1E-03", "G1E-04", "G1E-05", "G1E-06",
    "G1E-07", "G1E-08", "G1E-09", "G1E-10", "G1E-11",
})
CRITICAL_G1_IDS = frozenset({
    "ENV-01", "RAW-01", "HOST-02", "HDR-01", "FRM-03", "FRM-06",
    "FRM-09", "FRM-12", "TIME-01", "TIME-02", "TIME-05",
})


# Pins are baseline consistency checks, not signatures or approval evidence.
# Changing sources requires a new independent G0 review, never auto-ratification.
SOURCE_DIGESTS = (
    "ae192787a75bbc8ccec6e362720adfd540ebb88a1d7bda3b9b2f40d88dc24f82",
    "61ac96429122658058c18e903f69d934fdaafafa9cd991e41d7d2b0f16da9605",
)
READINESS_FIELDS = frozenset({
    "all_route_live_authorization_proven", "approved_to_open_listener",
    "baseline_commit", "decision", "decision_rule", "decision_type",
    "expected_case_counts", "g1_executed", "g2_executed", "gates", "name",
    "non_entry_separate_future_work", "numeric_ratification_record",
    "operator_approval_record", "prehandler_first_byte_source_verified",
    "schema_version", "source_candidate_profile", "source_plan",
    "transport_abort_scope_verified", "windows_provenance_verified",
})
GATE_FIELDS = frozenset({
    "category", "entry_blocker", "entry_status", "evidence_at_entry", "g1_case_ids",
    "id", "proposed_test_only", "reason_open", "required_reviewed_artifact",
})
GATE_CASE_IDS = {
    'G1E-01': ('ENV-01', 'ENV-02', 'ENV-03'),
    'G1E-02': ('RAW-01', 'HOST-02', 'HDR-02', 'FRM-12'),
    'G1E-03': ('TIME-01', 'TIME-04', 'TIME-05'),
    'G1E-04': ('HDR-03', 'TIME-01', 'TIME-05'),
    'G1E-05': ('TIME-02', 'TIME-03', 'TIME-06'),
    'G1E-06': ('TIME-02', 'TIME-04', 'TIME-06', 'ENV-03'),
    'G1E-07': ('FRM-06', 'FRM-07', 'TIME-01', 'TIME-05'),
    'G1E-08': ('FRM-03', 'FRM-07', 'FRM-09', 'FRM-11'),
    'G1E-09': ('ENV-01', 'ENV-02', 'ENV-03'),
    'G1E-10': ('HOST-04', 'HDR-01', 'HDR-05', 'ENV-01', 'ENV-03'),
    'G1E-11': ('RAW-01', 'FRM-12', 'TIME-02', 'TIME-05'),
}


def _source_digest(value: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ReadinessError("source is not finite JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ReadinessError(reason)


def evaluate_g0_entry(readiness: dict[str, Any], catalog: dict[str, Any],
                      profile: dict[str, Any]) -> dict[str, Any]:
    """Validate a *not-yet-approved* G0 baseline; always returns NO_GO.

    Do NOT reinterpret the output as Windows acceptance. Refuse changes
    that try to smuggle execution flags, forged proof or completed cases.
    """
    _require(isinstance(readiness, dict) and isinstance(catalog, dict) and
             isinstance(profile, dict), "nonobject inputs")
    _require(set(readiness) == READINESS_FIELDS, "missing/unknown readiness fields")
    _require(type(readiness.get("schema_version")) is int and
             readiness["schema_version"] == 1, "readiness schema")
    _require(readiness.get("baseline_commit") ==
             "752db4a7d5fda301947287862f480cc221aafffc", "wrong PR #22 baseline")
    _require((_source_digest(catalog), _source_digest(profile)) == SOURCE_DIGESTS,
             "Phase 2F/2G source snapshot changed; independent G0 review required")
    _require(readiness.get("name") == "sunny-g1-entry-readiness-g0", "readiness name")
    _require(readiness.get("decision") == "NO_GO_G1_START", "decision must be NO_GO")
    _require(readiness.get("decision_type") == "offline_document_review_only",
             "unapproved decision type")
    for field in ("approved_to_open_listener", "g1_executed", "g2_executed",
                  "transport_abort_scope_verified", "prehandler_first_byte_source_verified",
                  "windows_provenance_verified", "all_route_live_authorization_proven"):
        _require(readiness.get(field) is False, f"unverified evidence flag {field}")
    _require(readiness.get("operator_approval_record") is None,
             "unexpected operator approval record")
    _require(readiness.get("numeric_ratification_record") is None,
             "unexpected numeric approval record")
    _require(readiness.get("source_plan") ==
             "reference/sunny_windows_http_acceptance/cases.json", "wrong plan source")
    _require(readiness.get("source_candidate_profile") ==
             "reference/sunny_http_resource_limits/proposed_limits.json", "wrong profile source")

    _require(catalog.get("schema_version") == 1 and
             catalog.get("execution_status") == "not_run" and
             catalog.get("real_transport_tested") is False and
             catalog.get("requires_separate_operator_approval") is True,
             "original transport catalog cannot be counted as executed")
    cases = catalog.get("cases")
    _require(isinstance(cases, list) and len(cases) == 50, "catalog total must remain 50")
    by_id = {c.get("id"): c for c in cases if isinstance(c, dict)}
    _require(len(by_id) == 50, "duplicate/invalid catalog id")
    counts = Counter(c.get("stage") for c in cases)
    _require(counts == {"future_isolated_windows_only": 37,
                        "future_runtime_acceptance_only": 13}, "G1/G2 catalog stage split")
    _require(sum(c.get("priority") == "blocker" for c in cases) == 17,
             "changed priority blocker count")
    _require(all(c.get("status") == "not_run" for c in cases), "fabricated G1/G2 execution")
    _require(all(c.get("id") and c.get("outcome_class") for c in cases),
             "incomplete case description")

    _require(profile.get("approval_state") == "proposed_not_ratified" and
             profile.get("g1_approval") is False and
             profile.get("windows_http_sys_tested") is False and
             profile.get("g2_runtime_tested") is False, "unapproved numeric profile")
    values = profile.get("numeric_candidates")
    _require(isinstance(values, dict) and len(values) == 12,
             "numeric candidate set changed")
    _require(all(type(v) is int and v > 0 for v in values.values()),
             "invalid numeric candidate type or value")
    _require(values["max_request_body_bytes"] == 16384 and
             values["body_read_budget_ms"] == 5000 and
             values["max_inflight_global_including_undrained"] == 32 and
             values["max_inflight_general_including_undrained"] +
             values["reserved_recovery_inflight"] == 32, "candidate arithmetic changed")

    expected = readiness.get("expected_case_counts")
    _require(expected == {"total": 50, "g1": 37, "g2": 13,
                          "highlighted_blockers": 17}, "readiness count snapshot")
    gates = readiness.get("gates")
    _require(isinstance(gates, list) and len(gates) == len(REQUIRED_GATES),
             "entry prerequisite matrix incomplete")
    _require(all(isinstance(g, dict) and set(g) == GATE_FIELDS and
                 isinstance(g.get("id"), str) for g in gates),
             "missing/unknown gate fields or invalid gate id")
    gate_ids = [g["id"] for g in gates]
    _require(len(gate_ids) == len(gates) and set(gate_ids) == REQUIRED_GATES,
             "missing or duplicate entry prerequisite")
    covered: set[str] = set()
    for gate in gates:
        _require(gate.get("entry_status") == "open" and
                 gate.get("entry_blocker") is True and
                 gate.get("evidence_at_entry") == "none" and
                 gate.get("proposed_test_only") is True,
                 f"unauthorized readiness promotion {gate.get('id')}")
        for key in ("category", "required_reviewed_artifact", "reason_open"):
            _require(isinstance(gate.get(key), str) and len(gate[key]) >= 12,
                     f"missing {key} for {gate.get('id')}")
        refs = gate.get("g1_case_ids")
        _require(isinstance(refs, list) and len(refs) > 0 and
                 all(isinstance(cid, str) for cid in refs) and
                 len(set(refs)) == len(refs), "empty/repeated/invalid G1 case links")
        _require(set(refs) == set(GATE_CASE_IDS[gate["id"]]),
                 "changed gate-specific G1 case links")
        for cid in refs:
            _require(cid in by_id, f"missing source case {cid}")
            _require(by_id[cid]["stage"] == "future_isolated_windows_only",
                     f"G2 case {cid} cannot be treated as G1-entry evidence")
            covered.add(cid)
    _require(CRITICAL_G1_IDS.issubset(covered), "unmapped critical G1 families")
    _require(len(covered) >= 20, "G1 entry audit too narrow")
    separate = readiness.get("non_entry_separate_future_work")
    _require(isinstance(separate, list) and len(separate) >= 3 and
             all(isinstance(x, str) and len(x) > 35 for x in separate),
             "G1 and G2 downstream proof confused")
    # ALL G1 cases are not_run at entry; completing them is G1's purpose,
    # not a circular requirement before G1 may be authorized later.
    return {
        "decision": "NO_GO_G1_START",
        "open_entry_blockers": len(gates),
        "g1_cases_not_run": 37,
        "g2_cases_not_run": 13,
        "source_cases": 50,
        "g1_source_cases_linked": len(covered),
        "numeric_profile_ratified": False,
        "windows_transport_tested": False,
        "permission_to_open_listener": False,
    }
