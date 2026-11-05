"""Game-free synthetic observation/lifecycle reducer; no checkpoint discovery or I/O.

Inputs assert fixture evidence, not facts about SMAPI. guarded_dispatch stays false.
"""
from dataclasses import dataclass
import json
import math

from .contract import ContractError, Reference, make

SCHEMA = "sunny.observation/1.0.0"


@dataclass(frozen=True)
class Scope:
    adapter: str
    save_id: str
    load_id: str
    branch_id: str
    seat: str
    incarnation: int
    screen: int
    farmer: str

    def world(self):
        # Checkpoint ancestry is deliberately not promoted from candidate evidence.
        return dict(save_id=self.save_id, load_id=self.load_id,
                    branch_id=self.branch_id, parent_checkpoint_id=None)


@dataclass(frozen=True)
class Prompt:
    # Instance is an explicit synthetic lifecycle discriminator, never a text hash.
    instance: str
    question: str
    responses: tuple  # ordered (semantic key, label) pairs
    is_question: bool = True
    family: str = "gift"
    transitioning: bool = False
    identity_known: bool = True
    classified: bool = True

    def __post_init__(self):
        object.__setattr__(self, "responses", tuple(tuple(r) for r in self.responses))
        if not self.instance or any(len(r) != 2 for r in self.responses):
            raise ContractError("invalid synthetic prompt")

    def content(self):
        return self.question, self.responses, self.is_question, self.family, self.classified


@dataclass(frozen=True)
class Capture:
    scope: Scope
    sequence: int
    monotonic: float
    tick: int
    ready: bool
    complete: bool
    coverage: bool
    prompt: Prompt | None
    prompt_revision: int | None
    unavailable_reason: str | None = None
    schema: str = SCHEMA

    @property
    def identity(self):
        return self.scope, self.sequence

    @property
    def token(self):
        if self.prompt is None or not self.prompt.identity_known:
            return None
        return json.dumps([self.scope.__dict__, self.prompt.instance,
                           self.prompt_revision], sort_keys=True)


@dataclass(frozen=True)
class SaveEvidence:
    load_id: str
    operation: str
    state: str
    evidence: str
    checkpoint_candidates: tuple = ()


class Observation:
    guarded_dispatch = False

    def __init__(self, adapter="synthetic"):
        self.adapter = adapter
        self.world = None
        self.generation = 0
        self.seats = {}
        self._incarnations = {}
        self._loads = set()
        self._branches = set()
        self._captures = {}
        self._latest = {}
        self._instances = {}
        self._prompt = {}
        self.history = []
        self.saves = {}
        self.checkpoint_candidates = ()
        self.checkpoint_status = "unknown"

    def host_load(self, save_id, load_id, branch_id, *, checkpoint_candidates=()):
        """One explicit fixture host-load event. Folder/day never establish identity."""
        if not all((save_id, load_id, branch_id)) or load_id in self._loads or branch_id in self._branches:
            raise ContractError("host load requires new nonempty load and branch identities")
        self._loads.add(load_id)
        self._branches.add(branch_id)
        self.world = dict(save_id=save_id, load_id=load_id, branch_id=branch_id,
                          parent_checkpoint_id=None)
        self.checkpoint_candidates = tuple(sorted(set(checkpoint_candidates)))
        self.checkpoint_status = "ambiguous" if len(self.checkpoint_candidates) > 1 else "unknown"
        self.seats.clear()
        self.generation += 1
        self.history.append(("host_load", dict(self.world), self.checkpoint_candidates))
        return dict(self.world)

    def join(self, seat, screen, farmer):
        if self.world is None:
            raise ContractError("host identity unknown; seat attachment quarantined")
        if seat not in {"P1", "P2"} or type(screen) is not int or screen < 0 or not farmer:
            raise ContractError("invalid seat identity")
        self._incarnations[seat] = self._incarnations.get(seat, 0) + 1
        w = self.world
        scope = Scope(self.adapter, w["save_id"], w["load_id"], w["branch_id"],
                      seat, self._incarnations[seat], screen, farmer)
        self.seats[seat] = scope
        self.generation += 1
        self.history.append(("join", scope))
        return scope

    def leave(self, seat):
        self.seats.pop(seat, None)
        self.generation += 1
        self.history.append(("leave", seat))

    def capture(self, scope, sequence, monotonic, tick, *, ready=True, complete=True,
                coverage=True, prompt=None, unavailable_reason=None):
        if self.seats.get(scope.seat) != scope:
            raise ContractError("old load or seat identity")
        if (type(sequence) is not int or sequence < 1 or type(tick) is not int or tick < 0
                or not isinstance(monotonic, (int, float)) or not math.isfinite(monotonic) or monotonic < 0):
            raise ContractError("invalid source-local ordering")
        if not ready and (prompt is not None or not unavailable_reason):
            raise ContractError("unready screen needs unavailable evidence, not a prompt")
        key = scope, sequence
        if key in self._captures:
            # Revision was already assigned: compare the original input, not recomputation.
            stored = self._captures[key]
            candidate = Capture(scope, sequence, monotonic, tick, ready, complete, coverage,
                                prompt, stored.prompt_revision, unavailable_reason)
            if candidate != stored:
                raise ContractError("conflicting capture identity")
            return stored
        previous = self._latest.get(scope)
        old_prompt, revision = self._prompt.get(scope, (None, None))
        if prompt is not None:
            if old_prompt is not None and old_prompt.instance == prompt.instance:
                revision += prompt.content() != old_prompt.content()
            else:
                if (scope, prompt.instance) in self._instances:
                    raise ContractError("retired prompt instance reused")
                revision = 1
        else:
            revision = None
        candidate = Capture(scope, sequence, monotonic, tick, ready, complete, coverage,
                            prompt, revision, unavailable_reason)
        if previous and (sequence <= previous.sequence or monotonic < previous.monotonic or tick < previous.tick):
            raise ContractError("out-of-order capture")
        if prompt is not None:
            self._instances[(scope, prompt.instance)] = True
        self._prompt[scope] = prompt, revision
        self._captures[key] = candidate
        self._latest[scope] = candidate
        self.history.append(candidate)
        return candidate

    def cached(self, seat):
        return self._latest.get(self.seats.get(seat))

    def fresh(self, capture, *, seat, now, max_age, clock):
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (now, max_age)):
            return False
        return bool(capture and clock == self.adapter and max_age >= 0
                    and capture.scope.seat == seat and self.seats.get(seat) == capture.scope
                    and self.cached(seat) == capture and capture.ready and capture.complete
                    and capture.coverage and 0 <= now - capture.monotonic <= max_age)

    def current_offer(self, offer, *, now, max_age, clock):
        """Return the original immutable gift offer or None; never restamp fresh."""
        c = self.cached("P2")
        if not self.fresh(c, seat="P2", now=now, max_age=max_age, clock=clock):
            return None
        p = c.prompt
        if (p is None or not p.identity_known or not p.classified or p.transitioning
                or not p.is_question or p.family != "gift"):
            return None
        mapping = {key: i for i, (key, _) in enumerate(p.responses)}
        if len(mapping) != len(p.responses) or set(mapping) != {"accept", "decline"}:
            return None
        d = offer.data
        op = d["payload"]
        return offer if (d["world"] == self.world and op.get("token") == c.token
                         and op.get("responses") == mapping and op.get("fresh")
                         and op.get("family") == "gift" and op.get("status") == "open") else None

    def offer(self, identity, **policy):
        c = self.cached("P2")
        if c is None or c.prompt is None:
            return None
        p = c.prompt
        offer = make("offer", identity, self.world, dict(token=c.token, family=p.family,
                     status="open", fresh=True, question=p.question,
                     responses={key: i for i, (key, _) in enumerate(p.responses)}))
        return self.current_offer(offer, **policy)

    def save_started(self, load_id, operation, evidence):
        self._save(load_id, operation, "in_progress", evidence, ())

    def save_completed(self, load_id, operation, evidence, *, checkpoint_candidates=()):
        self._save(load_id, operation, "completion_observed", evidence, checkpoint_candidates)

    def _save(self, load_id, operation, state, evidence, candidates):
        if self.world is None or load_id != self.world["load_id"] or not operation or not evidence:
            raise ContractError("save evidence needs current host load and operation")
        key = load_id, operation
        record = SaveEvidence(load_id, operation, state, evidence, tuple(sorted(set(candidates))))
        old = self.saves.get(key)
        if old == record:
            return
        if old and (old.state == "completion_observed" or state == "in_progress"):
            raise ContractError("conflicting or regressing save evidence")
        self.saves[key] = record
        self.history.append(record)
        # Completion does not identify loaded bytes, ancestry, or persisted predicates.


class ObservedReference(Reference):
    """Opt-in inert gift reducer. No game guard/atomicity or live dispatch capability."""
    def __init__(self, observation):
        if observation.world is None:
            raise ContractError("host load required")
        super().__init__(observation.world)
        self.observation = observation
        self._generation = observation.generation

    def sync(self):
        if self.observation.world != self.world:
            super().reload(self.observation.world)
        elif self._generation != self.observation.generation:
            self.fence += 1
        self._generation = self.observation.generation

    def context(self, identity):
        self.sync()
        return super().context(identity)

    def context_is_current(self, context):
        self.sync()
        return super().context_is_current(context)

    def dispatch(self, attempt, current_offer, *, now, max_age, clock):
        self.sync()
        current = (self.observation.current_offer(current_offer, now=now, max_age=max_age, clock=clock)
                   if current_offer is not None else None)
        return super().dispatch(attempt, current)
