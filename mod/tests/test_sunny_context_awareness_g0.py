"""Compose the posture reference with synthetic context and scripted TV interest.

The reference owns choice eligibility and posture verification. This module
supplies context projection and proposal rules as fixtures for the design.
"""

from dataclasses import dataclass, replace
from enum import Enum

import pytest

from reference.sunny_posture_g0 import (
    Acknowledgement, Activity, Intent, Observation, Outcome, Posture, Scene,
    State, choices, choose, observe,
)


class Weather(Enum):
    UNKNOWN = "unknown"
    CLEAR = "clear"
    RAIN = "rain"


class TVAvailability(Enum):
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"  # Fixture supplies an explicit offer and known reachability.


@dataclass(frozen=True)
class Context:
    weather: Weather = Weather.CLEAR
    tv: TVAvailability = TVAvailability.AVAILABLE
    rest_cue_noticed: bool = False

    def project(self, observation: Observation) -> Observation:
        cue = "noticed" if self.rest_cue_noticed else "absent"
        return replace(
            observation, decision_context=f"{self.weather.value}/{self.tv.value}/{cue}",
        )


SEATED = Observation(
    Scene("P2", "load-1", "farmhouse"), 1, True, Posture.SEATED,
    current_chair_id="A", tile=(4, 7),
)
CLEAR = Context()
RAIN = replace(CLEAR, weather=Weather.RAIN)
NO_TV = replace(CLEAR, tv=TVAvailability.UNAVAILABLE)
UNKNOWN_TV = replace(CLEAR, tv=TVAvailability.UNKNOWN)


def paused(context: Context) -> State:
    state = State(context.project(SEATED))
    stay = next(choice for choice in choices(state) if choice.intent is Intent.STAY)
    return choose(state, stay)


def tv_proposal(state: State, context: Context, *, wants_tv: bool) -> Activity | None:
    """Project a scripted preference for the context supplied to this trace."""
    if not choices(state) or not state.observation.fresh:
        return None
    if state.attempt is not None and state.attempt.outcome is Outcome.UNKNOWN:
        return None
    if wants_tv and context.tv is TVAvailability.AVAILABLE:
        return Activity.TV
    return None


@pytest.mark.parametrize("stale_context", [None, RAIN], ids=["equivalent", "stale-change"])
def test_stay_pause_survives_equivalent_or_stale_observations(stale_context):
    state = paused(NO_TV)
    original_stay = state.stayed_at
    assert original_stay == state.observation
    assert choices(state) == ()

    samples = [(NO_TV, replace(SEATED, revision=2))]
    if stale_context is not None:
        samples.append((stale_context, replace(SEATED, revision=3, fresh=False)))
    samples.extend([
        (NO_TV, replace(SEATED, revision=4)),
        (NO_TV, replace(SEATED, revision=5, tile=(5, 7))),
    ])

    for context, sample in samples:
        observation = context.project(sample)
        state = observe(state, observation)
        assert state.observation == observation
        assert state.observation.posture is Posture.SEATED
        assert state.stayed_at == original_stay
        assert choices(state) == ()
        assert tv_proposal(state, context, wants_tv=True) is None
        assert state.attempt is None


@pytest.mark.parametrize(
    "before, after, expected_proposal",
    [
        pytest.param(CLEAR, RAIN, Activity.TV, id="rain"),
        pytest.param(NO_TV, CLEAR, Activity.TV, id="tv-becomes-available"),
        pytest.param(CLEAR, NO_TV, None, id="tv-becomes-unavailable"),
        pytest.param(CLEAR, UNKNOWN_TV, None, id="tv-becomes-unknown"),
        pytest.param(
            CLEAR, replace(UNKNOWN_TV, weather=Weather.UNKNOWN), None,
            id="weather-and-tv-become-unknown",
        ),
        pytest.param(
            CLEAR, replace(CLEAR, rest_cue_noticed=True), Activity.TV, id="rest-cue",
        ),
    ],
)
def test_context_change_allows_another_voluntary_stay(before, after, expected_proposal):
    state = paused(before)
    assert choices(state) == ()
    observation = after.project(replace(SEATED, revision=2))
    state = observe(state, observation)

    assert state.stayed_at is None
    assert state.attempt is None
    stay, stand = choices(state)
    assert (stay.intent, stand.intent) == (Intent.STAY, Intent.STAND)
    assert tv_proposal(state, after, wants_tv=True) is expected_proposal

    state = choose(state, stay)
    assert state.stayed_at == observation
    assert choices(state) == ()
    assert state.attempt is None

    # Replay the same cue value for the rest of this continuous seated episode.
    for revision in (3, 4):
        state = observe(state, replace(observation, revision=revision))
        assert state.stayed_at == observation
        assert choices(state) == ()
        assert tv_proposal(state, after, wants_tv=True) is None
        assert state.attempt is None


@pytest.mark.parametrize(
    "seated_selection, wants_tv_after_standing, expected_new_proposal",
    [
        pytest.param(Intent.STAY, False, None, id="stay-seated"),
        pytest.param(Intent.STAND, False, None, id="stand-then-drop-interest"),
        pytest.param(Intent.STAND, True, Activity.TV, id="stand-then-retain-interest"),
    ],
)
def test_tv_interest_and_stand_are_separate_choices(
    seated_selection, wants_tv_after_standing, expected_new_proposal,
):
    state = paused(CLEAR)
    seated = RAIN.project(replace(SEATED, revision=2))
    state = observe(state, seated)
    assert tv_proposal(state, RAIN, wants_tv=True) is Activity.TV
    assert state.attempt is None
    stay, stand = choices(state)
    assert (stay.intent, stand.intent) == (Intent.STAY, Intent.STAND)

    if seated_selection is Intent.STAY:
        state = choose(state, stay)
        assert state.stayed_at == seated
        assert state.observation.posture is Posture.SEATED
        assert choices(state) == ()
        assert state.attempt is None
        return

    state = choose(state, stand, Activity.TV)
    pending = state.attempt
    assert pending.choice == stand
    assert pending.activity is Activity.TV
    standing = replace(seated, posture=Posture.STANDING, current_chair_id=None)
    for evidence in (
        Acknowledgement(True),
        standing,
        replace(standing, revision=3, fresh=False),
        replace(standing, revision=4, scene=replace(SEATED.scene, map_id="town")),
        replace(seated, revision=4, tile=(5, 7)),
        replace(standing, revision=5, current_chair_id="A"),
    ):
        state = observe(state, evidence)
        assert state.attempt == pending
        assert state.attempt.outcome is Outcome.UNKNOWN
        assert state.attempt.completed_prerequisite is None
        assert state.attempt.selected_activity_status == "not_executed"
        assert tuple(choice.intent for choice in choices(state)) == (Intent.STAY,)
        assert tv_proposal(state, RAIN, wants_tv=True) is None

    confirmed = replace(standing, revision=6)
    state = observe(state, confirmed)
    verified = state.attempt
    assert verified == replace(pending, outcome=Outcome.VERIFIED)
    assert verified.completed_prerequisite is Intent.STAND
    assert verified.selected_activity_status == "not_executed"
    assert choose(state, stand, Activity.TV) is state

    new_stay, = choices(state)
    assert new_stay.intent is Intent.STAY
    assert new_stay.revision == confirmed.revision
    assert tv_proposal(state, RAIN, wants_tv=wants_tv_after_standing) is expected_new_proposal
    if expected_new_proposal is None:
        state = choose(state, new_stay)
        assert state.stayed_at == confirmed
        assert choices(state) == ()
    assert state.attempt == verified
