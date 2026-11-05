"""Synthetic evidence only: no game, transport, filesystem save or model API."""
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sunny_gift.contract import ContractError, make
from sunny_gift.observation import Observation, ObservedReference, Prompt

POLICY = dict(now=10, max_age=2, clock="synthetic")


@pytest.fixture
def scene():
    f = json.loads((Path(__file__).parent / "fixtures/lifecycle.json").read_text())
    o = Observation()
    o.host_load(f["save_id"], f["first_load"], "branch-1")
    scope = o.join("P2", 1, "fixture-sunny")
    p = Prompt(**f["prompt"])
    return o, scope, p, f


def capture(o, scope, p, sequence=1, **kwargs):
    return o.capture(scope, sequence, 10 + sequence - 1, 100 + sequence,
                     prompt=p, **kwargs)


def decision_attempt(m, offer, suffix="1"):
    decision = m.add(make("decision", "D"+suffix, m.world,
                         dict(activity="accept", social="silence", fence=m.fence,
                              expected_token=offer.data["payload"]["token"],
                              responses=offer.data["payload"]["responses"]),
                         {"offer": offer.ref}))
    return make("attempt", "A"+suffix, m.world,
                dict(seat="P2", fence=m.fence, tool="respond", args={"option":0}),
                {"offer":offer.ref, "decision":decision.ref})


def test_host_load_join_unready_and_rejoin_are_separate(scene):
    o, scope, p, _ = scene
    world = dict(o.world)
    c = o.capture(scope, 1, 10, 1, ready=False, unavailable_reason="character_pending")
    assert c.prompt is None and o.offer("O", **POLICY) is None
    capture(o, scope, p, 2)
    o.leave("P2")
    new = o.join("P2", 2, "fixture-new-farmer")
    assert o.world == world and new.incarnation > scope.incarnation
    assert o.cached("P2") is None
    with pytest.raises(ContractError):
        capture(o, scope, p, 3)
    assert not o.fresh(c, seat="P2", **POLICY)
    unknown = Observation()
    with pytest.raises(ContractError):
        unknown.join("P2", 1, "fixture-sunny")
    assert unknown.world is None


def test_ordering_is_seat_specific_and_cached_reads_never_restamp(scene):
    o, s, p, _ = scene
    c = capture(o, s, p)
    assert o.cached("P2") is c
    assert capture(o, s, p) is c
    p1 = o.join("P1", 0, "fixture-guy")
    other = o.capture(p1, 1, 1, 1)
    assert other.sequence == c.sequence and other.identity != c.identity
    assert not o.fresh(other, seat="P2", **POLICY)
    for args in [(1, 11, 102), (2, 9, 102), (2, 11, 100)]:
        with pytest.raises(ContractError):
            o.capture(s, *args, prompt=replace(p, question="Different"))
    assert o.cached("P2") == c


@pytest.mark.parametrize("policy", [dict(now=13), dict(now=9), dict(clock="other-process"),
                                   dict(max_age=-1), dict(now=float("nan"))])
def test_freshness_uses_explicit_source_clock_and_age(scene, policy):
    o, s, p, _ = scene
    c = capture(o, s, p)
    assert o.fresh(c, seat="P2", **POLICY)
    assert not o.fresh(c, seat="P2", **(POLICY | policy))
    assert o.cached("P2").monotonic == 10


def test_prompt_poll_revision_and_identical_replacement(scene):
    o, s, p, _ = scene
    first = capture(o, s, p)
    offer = o.offer("O1", **POLICY)
    second = capture(o, s, p, 2)
    assert second.token == first.token and second.prompt_revision == 1
    assert o.current_offer(offer, **(POLICY | dict(now=11))) == offer
    changed = capture(o, s, replace(p, responses=tuple(reversed(p.responses))), 3)
    assert changed.prompt_revision == 2 and changed.token != first.token
    assert o.current_offer(offer, **(POLICY | dict(now=12))) is None
    replacement = capture(o, s, replace(p, instance="menu-2"), 4)
    assert replacement.prompt_revision == 1 and replacement.token != first.token
    assert replacement.prompt.question == first.prompt.question
    assert capture(o, s, p) is first  # delayed duplicate stays historical, never current
    assert o.cached("P2") is replacement
    with pytest.raises(ContractError):
        capture(o, s, p, 5)  # retired instance cannot become a new equal prompt


@pytest.mark.parametrize("change", [dict(question="Other"), dict(is_question=False),
                                    dict(family="sleep"), dict(classified=False)])
def test_in_place_prompt_changes_revision(scene, change):
    o, s, p, _ = scene
    c = capture(o, s, p)
    changed = capture(o, s, replace(p, **change), 2)
    assert changed.prompt_revision == 2 and changed.token != c.token


@pytest.mark.parametrize("fault", ["transition", "identity", "coverage", "incomplete", "missing", "keys"])
def test_unknown_or_unsafe_prompt_evidence_rejects_without_default_choice(scene, fault):
    o, s, p, _ = scene
    capture(o, s, p)
    offer = o.offer("O", **POLICY)
    m = ObservedReference(o)
    m.add(offer)
    a = decision_attempt(m, offer)
    kwargs = {}
    if fault == "transition": p = replace(p, transitioning=True)
    if fault == "identity": p = replace(p, identity_known=False)
    if fault == "coverage": kwargs["coverage"] = False
    if fault == "incomplete": kwargs["complete"] = False
    if fault == "missing": p = None
    if fault == "keys": p = replace(p, responses=(("unknown", "Yes"), ("decline", "No")))
    capture(o, s, p, 2, **kwargs)
    status = m.dispatch(a, offer, **(POLICY | dict(now=11)))
    assert not status["dispatched_now"] and m.dispatches == []
    assert status["attempt_status"]["observed_choice"] == "unknown"
    assert not o.guarded_dispatch


@pytest.mark.parametrize("transition", ["reload", "seat-change", "leave"])
def test_old_decisions_tokens_and_context_are_invalidated(scene, transition):
    o, s, p, f = scene
    old = capture(o, s, p)
    offer = o.offer("O", **POLICY)
    m = ObservedReference(o)
    m.add(offer)
    context = m.context("C")
    a = decision_attempt(m, offer)
    if transition == "reload":
        o.host_load(f["save_id"], f["reload"], "branch-2")
        s = o.join("P2", 1, "fixture-sunny")
    elif transition == "seat-change":
        s = o.join("P2", 2, "fixture-other")
    else:
        o.leave("P2")
    if transition != "leave":
        new = capture(o, s, p)
        assert new.token != old.token
    assert not m.context_is_current(context)
    assert not m.dispatch(a, offer, **POLICY)["dispatched_now"]
    assert m.dispatches == []
    assert old in o.history


def test_same_day_unsaved_reload_ambiguous_checkpoint_and_historical_attempt(scene):
    o, s, p, f = scene
    capture(o, s, p)
    offer = o.offer("O", **POLICY)
    m = ObservedReference(o)
    m.add(offer)
    a = decision_attempt(m, offer)
    assert m.dispatch(a, offer, **POLICY)["dispatched_now"]
    o.host_load(f["save_id"], f["reload"], "branch-2",
                checkpoint_candidates=f["checkpoint_candidates"])
    assert o.checkpoint_status == "ambiguous" and o.world["parent_checkpoint_id"] is None
    assert f["day"] == 24  # unchanged label cannot preserve eligibility
    s = o.join("P2", 1, "fixture-sunny")
    capture(o, s, p)
    m.sync()
    historical = m.dispatch(a, offer, **POLICY)
    assert historical["epoch_status"] == "stale_epoch"
    assert historical["attempt_status"]["execution"] == "running"
    assert not historical["dispatched_now"]
    fresh = m.add(o.offer("O2", **POLICY))
    new_a = decision_attempt(m, fresh, "2")
    assert m.dispatch(new_a, fresh, **POLICY)["dispatched_now"]
    assert len(m.dispatches) == 2
    assert m.context("new").data["payload"]["current_possession"] == "unknown"


def test_save_start_completion_and_unknown_checkpoint_remain_distinct(scene):
    o, _, _, _ = scene
    o.save_started("load-1", "save-1", "synthetic Saving")
    start = o.saves[("load-1", "save-1")]
    assert start.state == "in_progress" and start.checkpoint_candidates == ()
    assert o.checkpoint_status == "unknown" and o.world["parent_checkpoint_id"] is None
    o.save_started("load-1", "save-1", "synthetic Saving")
    o.save_completed("load-1", "save-1", "synthetic Saved", checkpoint_candidates=["a", "b"])
    completed = o.saves[("load-1", "save-1")]
    assert completed.state == "completion_observed" and completed.checkpoint_candidates == ("a", "b")
    assert start.state == "in_progress"  # immutable historical evidence
    assert o.world["parent_checkpoint_id"] is None
    count = len(o.history)
    o.save_completed("load-1", "save-1", "synthetic Saved", checkpoint_candidates=["b", "a"])
    assert len(o.history) == count
    with pytest.raises(ContractError):
        o.save_started("load-1", "save-1", "late Saving")
    with pytest.raises(ContractError):
        o.save_completed("old-load", "save-2", "late Saved")
    o.save_completed("load-1", "unpaired-completion", "synthetic missing-start Saved")
    assert o.saves[("load-1", "unpaired-completion")].state == "completion_observed"
    assert o.checkpoint_status == "unknown"


def test_single_checkpoint_candidate_does_not_establish_loaded_identity(scene):
    o, _, _, f = scene
    o.host_load(f["save_id"], "load-2", "branch-2", checkpoint_candidates=["candidate"])
    assert o.checkpoint_candidates == ("candidate",)
    assert o.checkpoint_status == "unknown" and o.world["parent_checkpoint_id"] is None
    with pytest.raises(ContractError):
        o.host_load(f["save_id"], "load-2", "branch-3")
