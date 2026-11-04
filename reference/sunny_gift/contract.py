"""In-memory contract reducer. Dispatches are inert records, never callbacks or I/O.

The fixture A2 producer is trusted to attest causality; this is not a game verifier.
No durability, concurrency, checkpoint discovery, or complete wire schema is claimed.
"""
from copy import deepcopy
from dataclasses import dataclass
import json

SCHEMA = "sunny.gift/1.0.0"
TRACKS = {"offer": "A1", "decision": "A4", "attempt": "A1",
          "inventory": "A2", "verification": "A2", "event": "A3", "context": "A4"}


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Record:
    """Immutable canonical JSON; all returned dictionaries are detached copies."""
    encoded: str

    @classmethod
    def read(cls, value):
        required = {"schema", "kind", "record_id", "revision", "producer", "world", "refs", "payload"}
        if not required <= value.keys() or value["schema"] != SCHEMA:
            raise ContractError("unsupported or incomplete envelope")
        if value["kind"] not in TRACKS or value["producer"].get("track") != TRACKS[value["kind"]]:
            raise ContractError("wrong producer/kind")
        if not value["producer"].get("adapter_version") or not value["record_id"]:
            raise ContractError("missing identity")
        if type(value["revision"]) is not int or value["revision"] < 1:
            raise ContractError("invalid revision")
        if not {"save_id", "load_id", "branch_id", "parent_checkpoint_id"} <= value["world"].keys():
            raise ContractError("incomplete world")
        if any(not value["world"][k] for k in ("save_id", "load_id", "branch_id")):
            raise ContractError("missing world identity")
        for ref in value["refs"].values():
            if not isinstance(ref, dict) or set(ref) != {"record_id", "revision"}:
                raise ContractError("references require exact revision")
        return cls(json.dumps(value, sort_keys=True, allow_nan=False))

    @property
    def data(self):
        return json.loads(self.encoded)

    @property
    def ref(self):
        d = self.data
        return {"record_id": d["record_id"], "revision": d["revision"]}


def make(kind, identity, world, payload, refs=None, revision=1):
    return Record.read(dict(schema=SCHEMA, kind=kind, record_id=identity, revision=revision,
                            producer=dict(track=TRACKS[kind], adapter_version="synthetic"),
                            world=world, refs=refs or {}, payload=payload))


def world_key(world):
    return json.dumps(world, sort_keys=True)


class Reference:
    def __init__(self, world, fence=1):
        self.world = deepcopy(world)
        self.fence = fence
        self.records = {}
        self.attempts = {}
        self.dispatches = []
        self.events = {}
        self.publications = []

    def add(self, record):
        d = record.data
        key = (world_key(d["world"]), d["record_id"], d["revision"])
        previous = self.records.get(key)
        if previous and previous != record:
            raise ContractError("conflicting immutable record")
        self.records[key] = record
        return record

    def resolve(self, ref, kind, world):
        record = self.records.get((world_key(world), ref["record_id"], ref["revision"]))
        if record is None or record.data["kind"] != kind or record.data["world"] != world:
            raise ContractError("missing, wrong-kind or cross-world reference")
        return record

    def _dispatch_result(self, attempt, status, dispatched_now=False):
        """Separate this call's effect from the original attempt's recorded status."""
        return dict(epoch_status="current_epoch" if attempt.data["world"] == self.world else "stale_epoch",
                    dispatched_now=dispatched_now, attempt_world=attempt.data["world"],
                    current_world=deepcopy(self.world), attempt_status=deepcopy(status))

    def dispatch(self, attempt, current_offer):
        """Serialized toy claim + guard; appends one inert dispatch, never touches a game."""
        d, p = attempt.data, attempt.data["payload"]
        if d["kind"] != "attempt":
            raise ContractError("expected attempt")
        key = (world_key(d["world"]), p.get("seat"), d["record_id"])
        if key in self.attempts:
            old, result = self.attempts[key]
            if old != attempt:
                raise ContractError("attempt identity bound to different arguments")
            return self._dispatch_result(attempt, result)
        if d["world"] != self.world:
            # No original status is known. Never resolve stale dependencies or dispatch.
            return self._dispatch_result(attempt, None)
        decision = self.resolve(d["refs"]["decision"], "decision", d["world"])
        offer = self.resolve(d["refs"]["offer"], "offer", d["world"])
        dp, op = decision.data["payload"], offer.data["payload"]
        context_ref = decision.data["refs"].get("context")
        context_valid = (context_ref is None or self.context_is_current(
            self.resolve(context_ref, "context", d["world"])))
        if dp["activity"] not in {"accept", "decline", "defer", "stay", "other"}:
            raise ContractError("unknown mutation-affecting choice")
        if dp["social"] not in {"silence", "say", "none"}:
            raise ContractError("unknown social intent")
        valid = (context_valid and d["world"] == self.world and p["seat"] == "P2"
                 and p["fence"] == dp["fence"] == self.fence
                 and decision.data["refs"].get("offer") == offer.ref
                 and dp["activity"] in {"accept", "decline"}
                 and dp["expected_token"] == op["token"]
                 and dp["responses"] == op["responses"]
                 and current_offer == offer and op["family"] == "gift"
                 and op["status"] == "open" and op["fresh"]
                 and p["tool"] == "respond"
                 and p["args"] == {"option": op["responses"].get(dp["activity"])})
        result = dict(execution="running" if valid else "rejected",
                      dispatch="dispatched" if valid else "not_dispatched",
                      reply_completed=False, observed_choice="unknown", ack=None)
        self.add(attempt)
        self.attempts[key] = (attempt, result)
        if valid:
            self.dispatches.append(dict(world=d["world"], **attempt.ref))
        return self._dispatch_result(attempt, result, dispatched_now=valid)

    def observe_reply(self, attempt, *, ack, observed_choice="unknown", evidence=None):
        if observed_choice not in {"accepted", "declined", "canceled", "unknown"}:
            raise ContractError("unknown observed choice")
        if observed_choice != "unknown" and not evidence:
            raise ContractError("observed choice needs evidence")
        key = (world_key(attempt.data["world"]),
               attempt.data["payload"]["seat"], attempt.data["record_id"])
        result = self.attempts[key][1]
        if result["dispatch"] != "dispatched":
            raise ContractError("cannot acknowledge rejected dispatch")
        result.update(reply_completed=True, ack=ack, observed_choice=observed_choice)
        # A completed reply does not mark execution ended or prove any transfer.
        return deepcopy(result)

    def publish(self, verification):
        d, p = verification.data, verification.data["payload"]
        if d["kind"] != "verification" or p["verdict"] not in {"unknown", "verified", "contradicted"}:
            raise ContractError("invalid verification")
        if p["disposition"] not in {"inventory_received", "no_transfer", "partial", "debris", "unknown"}:
            raise ContractError("invalid disposition")
        self.resolve(d["refs"]["offer"], "offer", d["world"])
        if "attempt" in d["refs"]:
            self.resolve(d["refs"]["attempt"], "attempt", d["world"])
        # A2 attestation only: accepting an ack or uncorrelated delta is forbidden.
        receipt = p["verdict"] == "verified" and p["disposition"] == "inventory_received"
        if receipt:
            if (p["predicate"] != "causal_inventory_receipt/1" or not p["causal_evidence"]
                    or p["intervening_mutations"] != [] or p["source"] != "P1"
                    or p["destination"] != "P2" or not p["variant"]["qualified_item_id"]
                    or type(p["quantity"]) is not int or p["quantity"] <= 0):
                raise ContractError("receipt requires typed causal A2 evidence")
            captures = {}
            for name, seat in (("source_before", "P1"), ("source_after", "P1"),
                               ("destination_before", "P2"), ("destination_after", "P2")):
                capture = self.resolve(d["refs"][name], "inventory", d["world"]).data["payload"]
                if capture["seat"] != seat or not capture["complete"] or not capture["fresh"]:
                    raise ContractError("incomplete receipt capture")
                captures[name] = capture
            for side, sign in (("source", -1), ("destination", 1)):
                before, after = captures[side+"_before"], captures[side+"_after"]
                if (before["source"] != after["source"]
                        or before["container_instance"] != after["container_instance"]
                        or before["sequence"] >= after["sequence"]
                        or before["monotonic_capture"] >= after["monotonic_capture"]
                        or before["tick"] > after["tick"]):
                    raise ContractError("unordered or mismatched source-local captures")
                def quantity(capture):
                    return sum(e["quantity"] for e in capture["entries"] if e["variant"] == p["variant"])
                if quantity(after) - quantity(before) != sign * p["quantity"]:
                    raise ContractError("typed delta does not match actual quantity")
        self.add(verification)
        key = (world_key(d["world"]), d["producer"]["track"],
               p["transition_id"], p["movement_ordinal"])
        previous = self.events.get(key)
        if previous:
            old_v = self.resolve(previous.data["refs"]["verification"], "verification", d["world"])
            if old_v == verification:
                return previous
            if p.get("corrects") != old_v.ref:
                raise ContractError("conflicting transition needs explicit correction")
        revision = previous.data["revision"] + 1 if previous else 1
        event = make("event", previous.data["record_id"] if previous else f"E{len(self.events)+1}",
                     d["world"], dict(transition_key=list(key), eligibility="active",
                     local_record_state="in_memory", save_state="unconfirmed",
                     observed_scope="synthetic", verdict=p["verdict"], disposition=p["disposition"],
                     vocabulary="item_transfer_observed" if receipt else "gift_outcome_unresolved",
                     verified_receipt=receipt, variant=p.get("variant") if receipt else None,
                     quantity=p.get("quantity") if receipt else None,
                     corrects=previous.ref if previous else None),
                     {"verification": verification.ref}, revision)
        self.add(event)
        self.events[key] = event
        self.publications.append(event)
        return event

    def context(self, identity):
        active = [e for e in self.events.values() if e.data["world"] == self.world]
        return make("context", identity, self.world, dict(seat="P2", fence=self.fence,
                    projection_version=1, event_revisions=[e.ref for e in active],
                    verified_facts=[e.ref for e in active if e.data["payload"]["verified_receipt"]],
                    unresolved=[e.ref for e in active if not e.data["payload"]["verified_receipt"]],
                    cursor_range=[0, len(self.publications)], gaps=[],
                    current_possession="unknown", human_claims=[], reflections=[]))

    def context_is_current(self, context):
        return (context.data["world"] == self.world
                and context.data["payload"]["fence"] == self.fence
                and context.data["payload"]["event_revisions"]
                == self.context("check").data["payload"]["event_revisions"])

    def reload(self, world):
        """Caller supplies a SIMULATED authoritative epoch; no lineage inferred from day."""
        if world == self.world:
            raise ContractError("reload needs new identity")
        self.world = deepcopy(world)
        self.fence += 1
        # Retain attempt tombstones and historical evidence. No mutation replay.
