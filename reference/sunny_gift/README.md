# Sunny Gift Contract reference

This is an **unwired, game-free reference subset** of
[`sunny.gift/1.0.0`](../../docs/sunny-agentic/CONTRACT_REVIEW.md), authorized by the
Phase 2 implementation task. It does not approve or implement runtime wiring.
Python 3.11+ and pytest are sufficient; the implementation uses only the standard
library. No game, SMAPI, MCP, model API, save, controller or deployed artifact is
read or changed. `dispatch()` appends an inert reference to a list; it cannot
invoke a callback, send a command or speak.

From the repository root:

```sh
python -m pip install pytest
python -m pytest -q reference/sunny_gift/tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

The existing Python CI job runs both suites. The only existing file changed is
that workflow's pytest command. Gameplay source and behavior are untouched.

## Small shared model

`contract.py` contains one immutable canonical JSON record wrapper, an envelope
reader, and an in-memory reference reducer. All seven record kinds share the
schema/identity/revision/producer/world/refs/payload envelope. References name
exact record revisions. Returned dictionaries are copies; contexts freeze event
revisions for one prospective model request. Unsupported schemas and unknown
mutation-affecting choices fail closed.

Record storage and lookup key on the canonical complete `world` object plus
local record ID and revision. IDs need not be globally unique across worlds.
References inherit the enclosing record's world; `resolve()` always requires
that world and never searches other epochs. Within one world, a repeated ID and
revision must have identical content. This applies to every record kind, including
events and contexts. The inert dispatch log includes the world with each reference.

`dispatch()` returns a call-result wrapper with `epoch_status` (`current_epoch`
or `stale_epoch`), `dispatched_now`, `attempt_world`, `current_world`, and
`attempt_status`. Only a fresh, guarded dispatch sets `dispatched_now=true`.
Idempotent lookups return the original attempt status with `dispatched_now=false`.
After reload, a known old attempt returns `stale_epoch` and its unchanged historical
status under `attempt_status`; a previously unseen old attempt returns null status
without resolving stale dependencies or inserting a claim. Neither can dispatch.
Conflicting payloads for known attempts still reject, even after reload. These
wrapper fields describe the reference call, not new wire execution/dispatch enum
values. Historical running work is not fabricated as ended or rolled back.
`observe_reply()` continues to return the recorded attempt status, not a dispatch
call result.

The payloads deliberately implement the six-case subset below, rather than a
complete wire validator for every field in the review. In particular, the offer's
`responses` maps semantic response keys to indices; the synthetic prompt token
stands for an authoritative instance/revision. `fresh` is an explicit simulated
adapter assertion, not a wall-clock freshness calculation. `observe_reply()`
models acknowledgment/observed choice independently of running execution. Its
choice evidence is simulated, not a transfer predicate.

A2 verification input must cite typed P1/P2 before/after inventories, matching
variant and quantity deltas, complete/fresh source-local ordered captures, and a
causal attestation excluding intervening mutations. The reference checks those
conditions, **but trusts the synthetic A2 producer's causal attestation**. It
cannot discover whether a real observation window excluded competing changes.
A net delta by itself never certifies receipt. Missing/ambiguous evidence belongs
in an `unknown` verification, not a weakened verified record.

Events key on world identity, A2 producer, transition ID and movement ordinal.
Exact duplicates return the existing event. A conflicting transition requires an
explicit correction to the current verification revision; the canonical event ID
stays stable while its revision advances. Immutable source records and prior
event revisions remain available. Receipt is the only verified fact projected by
this subset: contradicted/unknown/other dispositions remain explicitly unresolved.
Receipt does not imply current possession or a committed game save.

## Demonstrated by synthetic tests

| Requested case | Demonstration |
| --- | --- |
| Accepted, transfer unknown | One inert dispatch; observed acceptance and `Dialogue closed` acknowledgment still produce an unresolved outcome, not a verified fact. Reply completion leaves execution running. |
| Verified receipt and optional silence | Typed matching deltas plus simulated causal evidence publish an event into the next immutable context. Silence is valid; context delivery dispatches neither acceptance nor speech. Save state stays unconfirmed and possession stays unknown. |
| Canceled/replaced prompt | Canceled, unrelated, missing, and identical-looking replacement prompts produce zero dispatches. Disappearance does not fabricate an observed cancellation or a default decline. |
| Duplicate versus identical second gift | Duplicate offer/request/publication is idempotent; a new prompt/attempt/transition creates a second event despite equal day/text/item. Conflicting attempt arguments reject. |
| Unsaved same-day reload | A simulated new load/branch excludes abandoned events from current context, invalidates old contexts, retains audit history and attempt tombstones, rejects new attempts in the old epoch, and permits a distinct new gift. |
| Unknown/corrections | Unknown → verified → contradicted updates one canonical event ID. A correction removes the fact from the next context and rejects a decision citing the older context. No correction dispatches an action. |

Additional tests cover wrong seat/fence, unknown schema/choice, STAY/defer/other
without default decline, missing source observations, stale/out-of-order captures,
variant/quantity mismatch and missing/competing causal evidence.
Architecture review regressions additionally reuse identical local IDs/revisions
across worlds for all seven record kinds, isolate save/load/branch identity,
retain same-world conflict checks, and distinguish current dispatches, idempotent
lookups, historical dispatched/acknowledged/rejected attempts and unknown stale
attempts. The reload gift test reuses offer, decision, attempt and evidence IDs
without conflating old and current actions or facts.

`tests/fixtures/gift.json` is wholly synthetic. It labels the causal window and
checkpoint mapping simulated. Failure scenarios are small copies of these JSON
records with explicit changed evidence; they contain no real game data or pilot
imports.

## Still requires validation or later implementation

This package proves reducer behavior for supplied records, not the truth of real
adapter observations or exactly-once game effects. Before any integration, actual
game validation must establish vanilla prompt identity/replacement and response
mapping, game-thread guards across every menu mutation route, human P1 read-only
inventory visibility, causal transfer proof, and capacity/partial/debris/cancel
semantics. Host load/checkpoint authority, saved predicate persistence, old-save
restoration and controller fencing must be demonstrated on backed-up `Test_`
saves under operator authorization.

Durable claims/publication/cursors, crash recovery/storage failures, cursor gaps,
ancestor-checkpoint reconciliation, reaction deduplication/recovery, lease expiry,
capability negotiation, expiry/reconsideration conditions and full payload/schema
validation are deliberately unimplemented. The list-backed cursor covers the
retained in-memory stream only; it is not a durable ingestion acknowledgment.
All prior epochs are excluded conservatively; this subset never infers eligible
ancestor history. There are no model requests, speech dispatches, mandatory
reactions, or personality policy. Real context receipt instrumentation and model
understanding/optional reaction still require separate validation.

See [VALIDATION.md](VALIDATION.md) for commands and exact results.
