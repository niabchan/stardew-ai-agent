"""Compose the posture reference with synthetic morning facts and preferences.

Calendar recognition and readiness apply only in this fixture. The posture
reference supplies scoped observation ordering, STAY, and attempt verification.
"""

from dataclasses import dataclass, replace
from enum import Enum

import pytest

from reference.sunny_posture_g0 import (
    Activity, Chair, Intent, Observation, Outcome, Posture, Scene,
    State, choices, choose, observe,
)


class Readiness(Enum):
    UNKNOWN = "unknown"
    NOT_READY = "not_ready"
    READY = "ready"


@dataclass(frozen=True)
class Morning:
    observation: Observation
    farm_day: int | None = None
    morning_cue: bool = False
    clock: str = "06:00"
    readiness: Readiness = Readiness.UNKNOWN
    weather: str = "unknown"
    tv_offered: bool | None = None
    tv_reachable: bool | None = None

    @property
    def tv_availability(self):
        if self.tv_offered is False or self.tv_reachable is False:
            return "unavailable"
        if self.tv_offered is True and self.tv_reachable is True:
            return "available"
        return "unknown"

    def project(self):
        return replace(
            self.observation,
            decision_context=f"{self.readiness.value}/{self.weather}/{self.tv_availability}",
        )


def observe_morning(state, previous_day, sample):
    observation = sample.project()
    updated = observe(state, observation)
    if updated is state or not observation.fresh or sample.farm_day is None:
        return updated, previous_day, False
    advanced = previous_day is not None and sample.farm_day > previous_day
    day = sample.farm_day if previous_day is None or advanced else previous_day
    return updated, day, advanced


def is_observed_morning(state, sample):
    return state.observation == sample.project() and state.observation.fresh and sample.morning_cue


def morning_options(state, sample):
    posture_choices = choices(state)
    obs = state.observation
    if not (
        obs == sample.project() and obs.fresh
        and sample.readiness is Readiness.READY
        and obs.posture is not Posture.UNKNOWN
    ):
        return tuple(c for c in posture_choices if c.intent is Intent.STAY), False

    compatible = (
        obs.posture is Posture.STANDING and obs.current_chair_id is None
        or obs.posture is Posture.SEATED and bool(obs.current_chair_id)
    )
    tv = (
        bool(posture_choices) and compatible
        and (state.attempt is None or state.attempt.outcome is Outcome.VERIFIED)
        and sample.tv_availability == "available"
    )
    return posture_choices, tv


def scripted_choice(state, sample, intent, *, wants_tv=False):
    offers, tv = morning_options(state, sample)
    if intent is Activity.TV:
        if wants_tv and tv and state.observation.posture is Posture.STANDING:
            return state, "not_executed"
        return state, None
    for choice in offers:
        if choice.intent is intent:
            annotation = Activity.TV if intent is Intent.STAND and wants_tv and tv else None
            return choose(state, choice, annotation), None
    return state, None


STANDING = Observation(
    Scene("P2", "load-1", "farmhouse"), 1, True, Posture.STANDING,
    candidate=Chair("A", True, True), tile=(4, 7),
)
CLEAR = Morning(STANDING, 22, morning_cue=True, readiness=Readiness.READY, weather="clear")
RAIN = replace(CLEAR, weather="rain", tv_offered=True, tv_reachable=True)
UNKNOWN_WEATHER = replace(RAIN, weather="unknown")
UNKNOWN_POSTURE = replace(STANDING, posture=Posture.UNKNOWN)
SEATED = replace(STANDING, posture=Posture.SEATED, current_chair_id="A")


@pytest.mark.parametrize(
    "sample, expected_intents, tv, selection, expected_status",
    [
        pytest.param(CLEAR, (Intent.STAY, Intent.SIT), False, Intent.STAY, None,
                     id="clear-voluntary-stay"),
        pytest.param(RAIN, (Intent.STAY, Intent.SIT), True, Activity.TV, "not_executed",
                     id="rain-optional-tv"),
        pytest.param(RAIN, (Intent.STAY, Intent.SIT), True, Intent.STAY, None,
                     id="rain-decline-tv"),
        pytest.param(replace(RAIN, tv_reachable=None), (Intent.STAY, Intent.SIT),
                     False, Activity.TV, None, id="rain-does-not-ground-tv"),
        pytest.param(UNKNOWN_WEATHER, (Intent.STAY, Intent.SIT), True,
                     Activity.TV, "not_executed", id="unknown-weather-known-tv"),
        pytest.param(replace(UNKNOWN_WEATHER, tv_offered=None, tv_reachable=None),
                     (Intent.STAY, Intent.SIT), False, Activity.TV, None,
                     id="unknown-weather-unknown-tv"),
        pytest.param(replace(RAIN, readiness=Readiness.UNKNOWN), (Intent.STAY,),
                     False, Intent.SIT, None, id="unknown-readiness"),
        pytest.param(replace(RAIN, observation=SEATED, readiness=Readiness.NOT_READY),
                     (Intent.STAY,), False, Intent.STAND, None, id="not-ready"),
        pytest.param(replace(RAIN, observation=UNKNOWN_POSTURE), (Intent.STAY,),
                     False, Activity.TV, None, id="ready-unknown-posture"),
    ],
)
def test_initial_morning_options(sample, expected_intents, tv, selection, expected_status):
    projected = sample.project()
    state = State(replace(projected, revision=0, fresh=False))
    state, day, advanced = observe_morning(state, None, sample)
    assert is_observed_morning(state, sample)
    assert not is_observed_morning(state, replace(sample, morning_cue=False))
    assert day == 22
    assert not advanced
    assert state.observation.decision_context.split("/")[1] == sample.weather

    offers, tv_available = morning_options(state, sample)
    assert tuple(choice.intent for choice in offers) == expected_intents
    assert tv_available is tv
    selected, status = scripted_choice(state, sample, selection, wants_tv=True)
    assert status == expected_status
    assert selected.attempt is None
    assert selected.observation is state.observation
    if selection is Intent.STAY:
        assert selected.stayed_at is state.observation
        assert morning_options(selected, sample) == ((), False)
    else:
        assert selected is state

    if not tv:
        assert scripted_choice(state, sample, Activity.TV, wants_tv=True) == (state, None)
    if selection in (Intent.SIT, Intent.STAND):
        # The raw reference accepts this posture choice without the fixture gate.
        raw_choice = next(c for c in choices(state) if c.intent is selection)
        assert choose(state, raw_choice).attempt is not None
        assert scripted_choice(state, sample, Intent.STAY)[0].stayed_at is state.observation


@pytest.mark.parametrize(
    "observation, farm_day",
    [
        pytest.param(replace(STANDING, revision=2, fresh=False), 25, id="stale"),
        pytest.param(STANDING, 25, id="out-of-order"),
        pytest.param(replace(STANDING, revision=2, scene=replace(STANDING.scene, load_id="load-2")),
                     25, id="different-scene"),
        pytest.param(replace(STANDING, revision=2), None, id="missing-day"),
        pytest.param(replace(STANDING, revision=2), 21, id="lower-day"),
    ],
)
def test_rejected_calendar_evidence_preserves_baseline(observation, farm_day):
    state = State(CLEAR.project())
    sample = replace(CLEAR, observation=observation, farm_day=farm_day)
    state, day, advanced = observe_morning(state, 22, sample)
    assert (day, advanced) == (22, False)

    # A smaller subsequent advance would be lost if the earlier day 25 leaked in.
    next_sample = replace(CLEAR, observation=replace(STANDING, revision=3), farm_day=23)
    _, day, advanced = observe_morning(state, day, next_sample)
    assert (day, advanced) == (23, True)


@pytest.mark.parametrize("pending_stand", [False, True], ids=["no-attempt", "unresolved-stand"])
def test_day_advance_without_confirmed_readiness_or_posture(pending_stand):
    before = replace(RAIN, observation=SEATED) if pending_stand else RAIN
    state = State(before.project())
    if pending_stand:
        state, status = scripted_choice(state, before, Intent.STAND, wants_tv=True)
        assert status is None
        assert state.attempt.choice.intent is Intent.STAND
        assert state.attempt.activity is Activity.TV
    attempt = state.attempt
    next_morning = Morning(replace(UNKNOWN_POSTURE, revision=2), 23, morning_cue=True)
    state, day, advanced = observe_morning(state, 22, next_morning)
    assert (day, advanced) == (23, True)
    assert state.observation.posture is Posture.UNKNOWN
    assert state.observation.current_chair_id is None
    assert state.observation.decision_context == "unknown/unknown/unknown"
    assert state.attempt is attempt
    offers, tv = morning_options(state, next_morning)
    assert tuple(choice.intent for choice in offers) == (Intent.STAY,)
    assert not tv
    assert scripted_choice(state, next_morning, Intent.STAND, wants_tv=True)[0] is state
    if pending_stand:
        assert attempt.outcome is Outcome.UNKNOWN
        assert attempt.completed_prerequisite is None
        assert attempt.selected_activity_status == "not_executed"


@pytest.mark.parametrize(
    "change, observation_change, advances",
    [
        pytest.param({}, {}, False, id="equivalent"),
        pytest.param({"clock": "09:20"}, {}, False, id="clock-only"),
        pytest.param({}, {"tile": (5, 7)}, False, id="tile-only"),
        pytest.param({"tv_offered": True}, {}, False, id="equivalent-unknown-tv"),
        pytest.param({"weather": "rain", "tv_offered": True, "tv_reachable": True},
                     {"fresh": False}, False, id="stale-context"),
        pytest.param({"farm_day": 23}, {}, True, id="calendar-only"),
    ],
)
def test_stay_survives_non_meaningful_changes(change, observation_change, advances):
    state, _ = scripted_choice(State(CLEAR.project()), CLEAR, Intent.STAY)
    paused_at = state.stayed_at
    sample = replace(
        CLEAR, observation=replace(STANDING, revision=2, **observation_change), **change,
    )
    state, day, advanced = observe_morning(state, 22, sample)
    assert (day, advanced) == (23 if advances else 22, advances)
    assert state.observation == sample.project()
    assert is_observed_morning(state, sample) is sample.observation.fresh
    assert state.stayed_at is paused_at
    assert morning_options(state, sample) == ((), False)
    assert state.attempt is None


@pytest.mark.parametrize(
    "before, after",
    [
        pytest.param(CLEAR, replace(CLEAR, weather="rain"), id="weather"),
        pytest.param(replace(RAIN, readiness=Readiness.UNKNOWN), RAIN, id="readiness"),
        pytest.param(replace(RAIN, tv_reachable=None), RAIN, id="tv-reachability"),
    ],
)
def test_fresh_meaningful_change_allows_another_stay(before, after):
    state, _ = scripted_choice(State(before.project()), before, Intent.STAY)
    assert morning_options(state, before) == ((), False)

    sample = replace(after, observation=replace(STANDING, revision=2))
    state, day, advanced = observe_morning(state, 22, sample)
    assert (day, advanced) == (22, False)
    assert state.stayed_at is None
    offers, tv = morning_options(state, sample)
    assert tuple(choice.intent for choice in offers) == (Intent.STAY, Intent.SIT)
    assert tv is (after.tv_offered is True and after.tv_reachable is True)

    state, _ = scripted_choice(state, sample, Intent.STAY, wants_tv=True)
    paused_at = state.observation
    replay = replace(sample, observation=replace(STANDING, revision=3))
    state, _, _ = observe_morning(state, day, replay)
    assert state.stayed_at is paused_at
    assert morning_options(state, replay) == ((), False)
    assert state.attempt is None
