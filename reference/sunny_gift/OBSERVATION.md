# Sunny Phase 2 — observation and lifecycle reference

Game-free, opt-in Python extension based on [PR #12](https://github.com/niabchan/stardew-ai-agent/pull/12)
(`A1_A3_OBSERVATION_SAVE_LIFECYCLE_RESEARCH.md`, head
`29f0a030010c8b8ba033587138bc40e0fc54b83c`) and
[CONTRACT_REVIEW.md](../../docs/sunny-agentic/CONTRACT_REVIEW.md).
Base: `24f5f5caf29d466bace2dec48998b7f78b046c72`.
The explicit Phase 2 request authorizes this reference implementation beyond the
older Phase 1 research-only charter. No runtime or game behavior is implemented.

## Extension contract and compatibility

`observation.py` declares `sunny.observation/1.0.0` for its in-memory DTO contract.
This is a separate extension identifier, not a new accepted `Record.kind` or a
wire parser. The existing `sunny.gift/1.0.0` envelope, kinds, fixtures and
`Reference` API are unchanged. The extension uses frozen dataclasses; prompt
response lists are copied into tuples. It is a trusted synthetic fixture reducer,
not a complete hostile-input validator, persistent store or concurrent service.

- `Scope` binds adapter/process clock authority, save/load/branch, seat,
  incarnation, screen and farmer alias. Host-load events require new opaque load
  and branch IDs. They reset seat attachments. Join/rejoin creates a new seat
  incarnation within that host world; character readiness is capture evidence.
  Joining without known host identity rejects with a quarantine error.
- `Capture` binds scope, source-local sequence, original monotonic time, tick,
  ready/complete/coverage and optional unavailable reason. Its identity is
  `(scope, sequence)`. Exact duplicate delivery returns the original capture;
  conflicts and unseen out-of-order sequence/time/tick reject. Seat clocks are
  independent; no atomic P1/P2 snapshot is claimed. A delayed historical duplicate
  does not replace the current cache. A missing menu on a ready screen differs
  from an unready screen with an explicit unavailable reason.
- `Prompt.instance` is supplied lifecycle evidence. Same-instance unchanged
  sampling preserves the token; content, question flag, family, ordered mapping
  or classification changes increment revision. Replacement must supply a new
  instance even with identical text. Retired IDs cannot be reused within a scope.
  This reducer cannot detect an unreported replacement between samples.
  `identity_known=False` or `coverage=False` disables offer eligibility. A future
  adapter must supply honest coverage evidence; polling/text equality is not it.
- Token is an opaque canonical encoding of complete scope plus prompt instance
  and revision. Capture sequence is not a prompt revision. Only explicit semantic
  accept/decline keys produce an eligible gift mapping; labels never classify it.
- `fresh` requires the current complete, ready, covered capture for the requested
  seat, the same adapter clock, and nonnegative age within an explicit caller
  `max_age`. Cached reads never advance time. No universal safe freshness limit
  is provided. Transitioning, unclassified and non-question prompts reject offers.
- `SaveEvidence` separates operation identity from checkpoint candidates.
  `save_started` records `in_progress`; `save_completed` records only
  `completion_observed`, including an unpaired completion if start evidence was
  missed. Completion duplicates are idempotent; conflicting or regressing evidence
  rejects. Late old-load callbacks reject. Start without completion has unknown
  outcome, not failure or persistence proof. Completion does not prove that any predicate was
  serialized, that a transaction is durable, or that a checkpoint is unique.
- `host_load(..., checkpoint_candidates=...)` preserves candidates without matching
  artifacts. Multiple candidates are `ambiguous`; zero or one stays `unknown`.
  `parent_checkpoint_id` always remains null. No registry, hashing, authoritative
  detector, ancestry selection or inherited-fact activation is implemented.

## Optional gift bridge

Construct `ObservedReference(observation)` after host load and obtain an offer
through `observation.offer(identity, now=..., max_age=..., clock=...)`. Add that
immutable offer to the reference and bind decisions/attempts using the existing
exact refs, token, mapping and fence. Dispatch takes the same explicit freshness
policy. It rechecks the current capture against the original offer, so unchanged
new samples refresh eligibility without rewriting that offer.

The bridge synchronizes world/fence before context checks and inert dispatch.
Loads invalidate all old world decisions; seat join/leave/reassignment advances
fencing, invalidating old decisions and contexts even without a world change.
This conservatively fences P2 decisions when either seat changes. Prompt changes
invalidate old offer tokens. Old evidence and attempt outcomes remain historical;
known running attempts are never labeled ended or automatically replayed.
`sync()` can be called explicitly after lifecycle changes; public context/dispatch
operations also call it. Direct access to inherited storage remains a toy API,
not an enforcement boundary.

All dispatches remain inert list entries. `guarded_dispatch=False` is explicit.
Python checks are not atomic with game execution. Nothing connects to MCP,
SMAPI, C# gameplay, Luna, live menus, saves or the filesystem. No inventory truth,
receipt, cancellation, current possession or checkpoint continuity is inferred.
The existing reducer's conservative exclusion of all earlier worlds is preserved,
even for a candidate older checkpoint. No event persistence states are upgraded
by a save callback.

## Synthetic validation

`tests/fixtures/lifecycle.json` supplies equal-looking prompts, same-day labels,
load aliases and ambiguous checkpoint candidates. Tests create all evidence in
memory. Tests also exercise unknown identity/coverage, option reordering,
in-place content changes, cache stalling, wrong clocks/seats, ordering conflicts,
unready join, rejoin, seat change, late old-load evidence, unpaired/duplicate save
completion and the opt-in gift bridge. These do not certify actual SMAPI callback
ordering or prompt lifecycle coverage.

Executed with Python 3.12. Commands from the pinned reference workspace:

```text
/workspace/stardew-ai-agent/.venv/bin/python -m pytest -q reference/sunny_gift/tests/test_contract.py
43 passed in 0.07s
/workspace/stardew-ai-agent/.venv/bin/python -m pytest -q reference/sunny_gift/tests/test_observation.py
24 passed in 0.04s
/workspace/stardew-ai-agent/.venv/bin/python -m pytest -q reference/sunny_gift/tests
67 passed in 0.12s
```

The default Python lacked pytest and could not download it through the workspace
proxy; the pre-existing repository virtual environment supplied pytest. No game
build or live test was run. Git transport was unavailable; pinned files were read
and the draft change published through the GitHub connector.
