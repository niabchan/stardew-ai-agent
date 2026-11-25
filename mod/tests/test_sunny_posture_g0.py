"""Data-only tests for the standalone G0 posture model."""

from dataclasses import replace

import pytest

from reference.sunny_posture_g0 import (
    Acknowledgement, Activity, Chair, Choice, Intent, Observation, Outcome,
    Posture, Scene, State, choices, choose, observe,
)


SCENE = Scene("P2", "load-1", "farmhouse")
CHAIR = Chair("A", True, True)
STANDING = Observation(SCENE, 1, True, Posture.STANDING, candidate=CHAIR)
SEATED = replace(STANDING, revision=2, posture=Posture.SEATED, current_chair_id="A")


def offered(state):
    return tuple(choice.intent for choice in choices(state))


def test_sit_stay_stand_trace():
    state = State(STANDING)
    assert offered(state) == (Intent.STAY, Intent.SIT)
    state = choose(state, choices(state)[1])
    assert state.attempt.outcome is Outcome.UNKNOWN
    assert offered(state) == (Intent.STAY,)

    state = observe(state, SEATED)
    assert state.attempt.outcome is Outcome.VERIFIED
    assert offered(state) == (Intent.STAY, Intent.STAND)
    state = choose(state, choices(state)[0])
    verified_sit = state.attempt
    state = observe(state, replace(SEATED, revision=3, tile=(7, 4)))
    assert choices(state) == ()
    assert state.attempt == verified_sit

    state = observe(state, replace(SEATED, revision=4, decision_context="TV available"))
    assert offered(state) == (Intent.STAY, Intent.STAND)
    assert state.attempt == verified_sit
    assert choices(state)[1].revision == 4
    state = choose(state, choices(state)[1])
    assert state.attempt.choice.intent is Intent.STAND
    assert state.attempt.outcome is Outcome.UNKNOWN
    state = observe(state, replace(STANDING, revision=5))
    assert state.attempt.outcome is Outcome.VERIFIED
    assert offered(state) == (Intent.STAY, Intent.SIT)


def test_stay_while_already_seated_records_no_attempt():
    state = State(SEATED)
    state = choose(state, choices(state)[0])
    state = observe(state, replace(SEATED, revision=3))
    assert state.stayed_at == SEATED
    assert state.attempt is None
    assert choices(state) == ()


@pytest.mark.parametrize(
    "observation",
    [
        replace(STANDING, candidate=None),
        replace(STANDING, candidate=Chair("A", False, True)),
        replace(STANDING, candidate=Chair("A", True, False)),
        replace(STANDING, candidate=Chair(None, True, True)),
        replace(STANDING, candidate=Chair("A", None, True)),
        replace(STANDING, candidate=Chair("A", True, None)),
        replace(STANDING, posture=Posture.UNKNOWN),
        replace(STANDING, fresh=False),
        replace(SEATED, fresh=False),
        replace(SEATED, current_chair_id=None),
    ],
)
def test_insufficient_evidence_only_offers_stay(observation):
    assert offered(State(observation)) == (Intent.STAY,)


@pytest.mark.parametrize(
    "observation, selection",
    [
        (STANDING, Choice(SCENE, 1, Intent.STAND, "A")),
        (SEATED, Choice(SCENE, 2, Intent.SIT, "A")),
        (STANDING, Choice(SCENE, 1, Intent.SIT, "B")),
        (replace(STANDING, revision=2), Choice(SCENE, 1, Intent.SIT, "A")),
        (replace(STANDING, candidate=None), Choice(SCENE, 1, Intent.SIT, "A")),
    ],
)
def test_unoffered_selection_leaves_state_intact(observation, selection):
    state = State(observation)
    assert choose(state, selection) is state


@pytest.mark.parametrize(
    "evidence",
    [
        Acknowledgement(True),
        replace(STANDING, revision=2, tile=(7, 4)),
        replace(SEATED, revision=1),
        replace(SEATED, fresh=False),
        replace(SEATED, posture=Posture.UNKNOWN),
        replace(SEATED, current_chair_id="B"),
        replace(SEATED, scene=replace(SCENE, p2_id="other")),
        replace(SEATED, scene=replace(SCENE, load_id="load-2")),
        replace(SEATED, scene=replace(SCENE, map_id="town")),
    ],
)
def test_unconfirmed_sit_blocks_mutating_choices_until_observed(evidence):
    state = State(STANDING)
    sit = choices(state)[1]
    state = choose(state, sit)
    state = observe(state, evidence)
    assert state.attempt.outcome is Outcome.UNKNOWN
    assert offered(state) == (Intent.STAY,)
    assert choose(state, replace(sit, revision=state.observation.revision)) is state
    state = observe(state, replace(SEATED, revision=3))
    assert state.attempt.outcome is Outcome.VERIFIED
    assert offered(state) == (Intent.STAY, Intent.STAND)


@pytest.mark.parametrize("activity", [Activity.TV, Activity.MOVE])
def test_verified_stand_prerequisite_requires_new_choice(activity):
    state = State(SEATED)
    stand = choices(state)[1]
    state = choose(state, stand, activity)
    for evidence in (
        Acknowledgement(True),
        replace(SEATED, revision=3),
        replace(STANDING, revision=4, current_chair_id="A"),
    ):
        state = observe(state, evidence)
        assert state.attempt.outcome is Outcome.UNKNOWN
        assert state.attempt.completed_prerequisite is None
        assert state.attempt.selected_activity_status == "not_executed"
        assert offered(state) == (Intent.STAY,)

    state = observe(state, replace(STANDING, revision=5))
    assert state.attempt.completed_prerequisite is Intent.STAND
    assert state.attempt.selected_activity_status == "not_executed"
    assert choose(state, stand, activity) is state
    state = choose(state, choices(state)[0])
    assert state.attempt.choice == stand
    assert state.attempt.selected_activity_status == "not_executed"
    assert choices(state) == ()
