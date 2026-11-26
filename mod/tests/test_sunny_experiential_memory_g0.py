"""Exercise synthetic history against independently observed morning offers."""

from dataclasses import dataclass, replace

import pytest

from reference.sunny_posture_g0 import (
    Acknowledgement, Activity, Chair, Choice, Intent, Observation, Outcome,
    Posture, Scene, State, choose, observe,
)
from test_sunny_morning_awareness_g0 import (
    CLEAR, RAIN, SEATED, is_observed_morning, morning_options, observe_morning,
    scripted_choice,
)


@dataclass(frozen=True)
class Record:
    fixture: str
    scene: Scene
    revision: int
    farm_day: int | None
    weather: str
    interest: Activity | Intent | None = None
    selection: Choice | Activity | None = None
    posture_outcome: Outcome | None = None
    evidence: Observation | None = None
    activity: Activity | None = None
    activity_status: str | None = None


def historical_fact(fixture, sample, interest=None):
    obs = sample.project()
    assert obs.fresh
    return Record(fixture, obs.scene, obs.revision, sample.farm_day, sample.weather, interest)


def select_from_offers(state, sample, intent, annotation=None):
    offers, _ = morning_options(state, sample)
    offered = next((choice for choice in offers if choice.intent is intent), None)
    return state if offered is None else choose(state, offered, annotation)


def capture_verification(record, before, after):
    if before.attempt.outcome is Outcome.UNKNOWN and after.attempt.outcome is Outcome.VERIFIED:
        return replace(record, posture_outcome=Outcome.VERIFIED, evidence=after.observation)
    return record


def posture_trace(fixture, sample, state, intent, *observations, annotation=None):
    selected = select_from_offers(state, sample, intent, annotation)
    assert selected is not state
    record = historical_fact(fixture, sample)
    if intent is Intent.STAY:
        assert selected.stayed_at is state.observation
        return selected, replace(record, selection=Choice(record.scene, record.revision, intent))

    attempt = selected.attempt
    record = replace(
        record, selection=attempt.choice, posture_outcome=attempt.outcome,
        activity=attempt.activity, activity_status=attempt.selected_activity_status,
    )
    for observation in observations:
        updated = observe(selected, observation)
        record = capture_verification(record, selected, updated)
        selected = updated
    return selected, record


def recall(history):
    return tuple(
        fact
        for record in history
        for fact in (
            ("weather", record.weather),
            ("interest", record.interest),
            ("posture", record.selection) if record.evidence is not None else None,
        )
        if fact is not None and fact[1] is not None
    )


def recall_choice(state, sample, history, *, wants_tv=False, sit_after_seating=False):
    offers, tv = morning_options(state, sample)
    if not (is_observed_morning(state, sample) and offers):
        return state, None
    facts = recall(history)
    if wants_tv and ("interest", Activity.TV) in facts and tv:
        return scripted_choice(state, sample, Activity.TV, wants_tv=True)
    recalls_seating = any(kind == "posture" and choice.intent is Intent.SIT for kind, choice in facts)
    if sit_after_seating and recalls_seating and any(offer.intent is Intent.SIT for offer in offers):
        return scripted_choice(state, sample, Intent.SIT)
    return scripted_choice(state, sample, Intent.STAY)


def morning_state(sample):
    state = State(replace(sample.project(), revision=0, fresh=False))
    return observe_morning(state, None, sample)[0]


MATCHING_SEAT = replace(SEATED, revision=2)
TODAY = replace(
    CLEAR, farm_day=23, tv_offered=True, tv_reachable=True,
    observation=replace(CLEAR.observation, revision=4, candidate=Chair("B", True, True)),
)


def sit_trace(*observations):
    return posture_trace("earlier-sit", RAIN, morning_state(RAIN), Intent.SIT, *observations)


def test_rain_and_tv_interest_are_independent_historical_facts():
    record = historical_fact("earlier-rain", RAIN, Activity.TV)
    assert recall((record,)) == (("weather", "rain"), ("interest", Activity.TV))
    assert record.selection is record.posture_outcome is record.evidence is None
    assert record.activity is record.activity_status is None


def test_seating_evidence_is_captured_once_at_the_verification_transition():
    later = replace(MATCHING_SEAT, revision=3)
    state, record = sit_trace(MATCHING_SEAT, later)
    assert state.observation is later
    assert state.attempt.outcome is record.posture_outcome is Outcome.VERIFIED
    assert record.selection.chair_id == record.evidence.current_chair_id == "A"
    assert record.selection.revision == 1
    assert record.evidence is MATCHING_SEAT
    assert ("posture", record.selection) in recall((record,))

    # A later snapshot and even a retained verified attempt cannot backfill a record.
    _, unresolved = sit_trace()
    assert state.attempt.choice == unresolved.selection
    later_state = observe(state, replace(later, revision=4))
    assert capture_verification(unresolved, state, later_state) is unresolved
    assert unresolved.posture_outcome is Outcome.UNKNOWN
    assert unresolved.evidence is None
    assert ("posture", unresolved.selection) not in recall((unresolved,))


@pytest.mark.parametrize(
    "observations",
    [
        pytest.param((Acknowledgement(True),), id="ack-only"),
        pytest.param((), id="missing"),
        pytest.param((replace(MATCHING_SEAT, revision=1),), id="old-revision"),
        pytest.param((replace(MATCHING_SEAT, fresh=False),), id="not-fresh"),
        pytest.param((replace(MATCHING_SEAT, current_chair_id="B"),), id="wrong-chair"),
        pytest.param((replace(MATCHING_SEAT, scene=Scene("P2", "other-load", "farmhouse")),),
                     id="wrong-scene"),
    ],
)
def test_inadequate_evidence_does_not_complete_seating(observations):
    state, record = sit_trace(*observations)
    assert state.attempt.outcome is record.posture_outcome is Outcome.UNKNOWN
    assert record.evidence is None
    assert recall((record,)) == (("weather", "rain"),)


@pytest.mark.parametrize("activity", [Activity.TV, Activity.MOVE])
def test_stand_verifies_only_the_annotated_activity_prerequisite(activity):
    sample = replace(RAIN, observation=SEATED)
    standing = replace(RAIN.project(), revision=2)
    state, record = posture_trace(
        "earlier-stand", sample, morning_state(sample), Intent.STAND, standing,
        annotation=activity,
    )
    assert state.attempt.completed_prerequisite is Intent.STAND
    assert record.posture_outcome is Outcome.VERIFIED
    assert record.evidence is standing
    assert record.selection.chair_id == "A"
    assert record.activity is activity
    assert record.activity_status == "not_executed"
    assert recall((record,)) == (("weather", "rain"), ("posture", record.selection))


@pytest.mark.parametrize("retain_verified", [False, True])
def test_voluntary_stay_records_no_new_attempt(retain_verified):
    sample = replace(RAIN, observation=MATCHING_SEAT)
    state = morning_state(sample)
    if retain_verified:
        state, _ = sit_trace(sample.project())
    stayed, record = posture_trace("voluntary-stay", sample, state, Intent.STAY)
    assert stayed.attempt is state.attempt
    assert stayed.stayed_at is state.observation
    assert record.selection.intent is Intent.STAY
    assert record.posture_outcome is record.evidence is record.activity is None


def test_same_offers_and_script_select_differently_with_verified_seating():
    _, verified = sit_trace(MATCHING_SEAT)
    _, unverified = sit_trace(Acknowledgement(True))
    state = morning_state(TODAY)
    offers = morning_options(state, TODAY)
    assert tuple(choice.intent for choice in offers[0]) == (Intent.STAY, Intent.SIT)
    assert offers[1] is True

    for history in ((verified,), (unverified,), ()):
        selected, status = recall_choice(state, TODAY, history, sit_after_seating=True)
        assert morning_options(state, TODAY) == offers
        assert selected.observation is state.observation
        assert status is None
        if history == (verified,):
            assert selected.attempt.choice == offers[0][1]
            assert selected.attempt.choice.chair_id == "B"
            assert selected.attempt.outcome is Outcome.UNKNOWN
            assert selected.stayed_at is None
        else:
            assert selected.attempt is None
            assert selected.stayed_at is state.observation


@pytest.mark.parametrize(
    "chair_available, tv_reachable, expected",
    [
        (True, True, Activity.TV),
        (True, False, Intent.SIT),
        (False, True, Activity.TV),
        (False, False, Intent.STAY),
        (None, None, Intent.STAY),
    ],
)
def test_current_availability_limits_choices_with_fixed_history(chair_available, tv_reachable, expected):
    _, verified = sit_trace(MATCHING_SEAT)
    history = (verified, historical_fact("earlier-tv", RAIN, Activity.TV))
    sample = replace(
        TODAY,
        observation=replace(TODAY.observation, candidate=Chair("B", chair_available, True)),
        tv_reachable=tv_reachable,
    )
    state = morning_state(sample)
    offers, tv = morning_options(state, sample)
    assert any(offer.intent is Intent.SIT for offer in offers) is (chair_available is True)
    assert tv is (tv_reachable is True)
    selected, status = recall_choice(state, sample, history, wants_tv=True, sit_after_seating=True)
    if expected is Activity.TV:
        assert selected is state
        assert status == "not_executed"
    elif expected is Intent.SIT:
        assert selected.attempt.choice.intent is Intent.SIT
        assert selected.attempt.outcome is Outcome.UNKNOWN
        assert status is None
    else:
        assert selected.stayed_at is state.observation
        assert selected.attempt is None
        assert status is None


@pytest.mark.parametrize("retain_interest", [False, True])
def test_script_can_retain_or_abandon_interest_and_still_stay(retain_interest):
    history = (historical_fact("earlier-tv", RAIN, Activity.TV),)
    state = morning_state(TODAY)
    assert morning_options(state, TODAY)[1] is True
    past_interest = recall(history)[1][1]
    interest = past_interest if retain_interest else None
    stayed, record = posture_trace("later-stay", TODAY, state, Intent.STAY)
    record = replace(record, interest=interest)
    assert record.interest is (Activity.TV if retain_interest else None)
    assert record.selection.intent is Intent.STAY
    assert record.activity is record.activity_status is None
    assert stayed.stayed_at is state.observation
    assert stayed.attempt is None


def test_history_and_calendar_alone_do_not_reopen_stay():
    state = morning_state(TODAY)
    paused, _ = recall_choice(state, TODAY, ())
    assert paused.stayed_at is state.observation
    _, verified = sit_trace(MATCHING_SEAT)
    history = (verified,)
    assert recall_choice(paused, TODAY, history, sit_after_seating=True) == (paused, None)

    tomorrow = replace(TODAY, farm_day=24, observation=replace(TODAY.observation, revision=5))
    updated, day, advanced = observe_morning(paused, TODAY.farm_day, tomorrow)
    assert advanced and day == 24
    assert updated.stayed_at is paused.stayed_at
    assert morning_options(updated, tomorrow) == ((), False)
    assert recall_choice(updated, tomorrow, history, sit_after_seating=True) == (updated, None)

    changed = replace(tomorrow, weather="rain", observation=replace(tomorrow.observation, revision=6))
    reopened, _, _ = observe_morning(updated, day, changed)
    assert reopened.stayed_at is reopened.attempt is None
    assert recall_choice(reopened, changed, history)[0].stayed_at is reopened.observation


def test_new_day_and_omitted_history_preserve_unresolved_attempt():
    pending, record = sit_trace(Acknowledgement(True))
    assert record.posture_outcome is Outcome.UNKNOWN
    tomorrow = replace(RAIN, farm_day=23, observation=replace(RAIN.observation, revision=2))
    updated, day, advanced = observe_morning(pending, RAIN.farm_day, tomorrow)
    assert advanced and day == tomorrow.farm_day
    assert updated.observation.choice_facts == pending.observation.choice_facts
    assert updated.attempt is pending.attempt
    assert updated.attempt.outcome is Outcome.UNKNOWN
    assert tuple(choice.intent for choice in morning_options(updated, tomorrow)[0]) == (Intent.STAY,)
    assert morning_options(updated, tomorrow)[1] is False
    assert scripted_choice(updated, tomorrow, Intent.SIT) == (updated, None)
    assert scripted_choice(updated, tomorrow, Activity.TV, wants_tv=True) == (updated, None)
    for history in ((record,), ()):
        stayed, status = recall_choice(updated, tomorrow, history, wants_tv=True, sit_after_seating=True)
        assert stayed.attempt is pending.attempt
        assert stayed.stayed_at is updated.observation
        assert status is None
