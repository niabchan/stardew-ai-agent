"""Compose optional synthetic reflection with the accepted G0 fixtures."""

from dataclasses import dataclass, field, replace
from typing import Literal

import pytest

from reference.sunny_posture_g0 import (
    Acknowledgement, Activity, Intent, Outcome, observe,
)
from test_sunny_experiential_memory_g0 import (
    MATCHING_SEAT, TODAY, morning_state, posture_trace, recall, sit_trace,
)
from test_sunny_morning_awareness_g0 import (
    RAIN, SEATED, is_observed_morning, morning_options, observe_morning,
    scripted_choice,
)


@dataclass(frozen=True)
class Reflection:
    cited_keys: tuple[str, ...] = ()
    text: str | None = None
    future_interest: Literal[Intent.SIT, Activity.TV] | None = None
    author: str = field(default="scripted_synthetic_sunny", init=False)


SEATING = Reflection(("earlier-sit",), "I might try sitting again.", Intent.SIT)
TELEVISION = Reflection(("earlier-stand",), "I might try TV later.", Activity.TV)


def preference(state, sample, reflection, *, consider_hint=True, fallback=Intent.STAY):
    offers, tv = morning_options(state, sample)
    if not offers or not is_observed_morning(state, sample):
        return state, None, None

    hint = reflection.future_interest if reflection is not None and consider_hint else None
    if hint is Activity.TV and tv:
        updated, status = scripted_choice(state, sample, hint, wants_tv=True)
        if status is not None:
            return updated, hint, status

    intents = tuple(offer.intent for offer in offers)
    selection = Intent.SIT if hint is Intent.SIT and Intent.SIT in intents else fallback
    if selection not in intents:
        return state, None, None
    updated, status = scripted_choice(state, sample, selection)
    return updated, selection, status


@pytest.mark.parametrize("reflection", [None, SEATING], ids=["absent", "authored"])
def test_same_verified_history_and_eligible_sit_with_or_without_reflection(reflection):
    _, record = sit_trace(MATCHING_SEAT)
    history = (record,)
    facts = (("weather", "rain"), ("posture", record.selection))
    state = morning_state(TODAY)
    offers = morning_options(state, TODAY)

    updated, selection, status = preference(
        state, TODAY, reflection, consider_hint=False, fallback=Intent.SIT,
    )

    assert selection is Intent.SIT and status is None
    assert updated.attempt.choice.chair_id == "B"
    assert updated.attempt.outcome is Outcome.UNKNOWN
    assert recall(history) == facts
    assert record.posture_outcome is Outcome.VERIFIED
    assert record.evidence is MATCHING_SEAT
    assert record.selection.chair_id == "A"
    assert morning_options(state, TODAY) == offers


def test_seating_hint_changes_selection_without_changing_offers_or_evidence():
    _, record = sit_trace(MATCHING_SEAT)
    state = morning_state(TODAY)
    offers, tv = morning_options(state, TODAY)
    assert tv
    assert SEATING.cited_keys == (record.fixture,)
    assert SEATING.author == "scripted_synthetic_sunny"

    # The same prose and citation without the typed hint leave the fallback in effect.
    no_hint = replace(SEATING, future_interest=None)
    assert preference(state, TODAY, no_hint)[1:] == (Intent.STAY, None)
    updated, selection, status = preference(state, TODAY, SEATING)

    assert (selection, status) == (Intent.SIT, None)
    assert updated.attempt.choice in offers
    assert updated.attempt.choice.chair_id == "B"
    assert updated.attempt.outcome is Outcome.UNKNOWN
    assert updated.observation is state.observation
    assert morning_options(state, TODAY) == (offers, tv)
    assert recall((record,)) == (("weather", "rain"), ("posture", record.selection))
    assert record.selection.chair_id == record.evidence.current_chair_id == "A"
    assert record.evidence is MATCHING_SEAT


def test_verified_stand_with_tv_annotation_requires_a_separate_tv_selection():
    seated = replace(RAIN, observation=SEATED)
    standing = replace(RAIN, observation=replace(RAIN.observation, revision=2))
    verified, record = posture_trace(
        "earlier-stand", seated, morning_state(seated), Intent.STAND,
        standing.project(), annotation=Activity.TV,
    )
    assert verified.attempt.completed_prerequisite is Intent.STAND
    assert record.posture_outcome is Outcome.VERIFIED
    assert record.evidence is verified.observation
    facts = (("weather", "rain"), ("posture", record.selection))
    assert recall((record,)) == facts

    later, _, _ = observe_morning(verified, standing.farm_day, TODAY)
    assert later.attempt is verified.attempt
    assert later.stayed_at is None
    assert later.observation == TODAY.project()
    assert record.activity is Activity.TV
    assert record.activity_status == "not_executed"
    assert TELEVISION.cited_keys == (record.fixture,)
    assert morning_options(later, TODAY)[1]
    updated, selection, status = preference(later, TODAY, TELEVISION)

    assert (selection, status) == (Activity.TV, "not_executed")
    assert updated is later
    assert updated.attempt is verified.attempt
    assert updated.attempt.selected_activity_status == record.activity_status == "not_executed"
    assert recall((record,)) == facts


@pytest.mark.parametrize(
    "reflection, consider_hint, expected",
    [
        pytest.param(SEATING, True, Intent.SIT, id="retain"),
        pytest.param(replace(SEATING, future_interest=Activity.TV), True, Activity.TV, id="switch"),
        pytest.param(SEATING, False, Intent.STAY, id="ignore"),
        pytest.param(replace(SEATING, future_interest=None), True, Intent.STAY, id="abandon"),
        pytest.param(None, True, Intent.STAY, id="voluntary-stay-without-reflection"),
    ],
)
def test_script_can_change_preferences_under_the_same_current_observations(
    reflection, consider_hint, expected,
):
    state = morning_state(TODAY)
    offers, tv = morning_options(state, TODAY)
    assert tuple(offer.intent for offer in offers) == (Intent.STAY, Intent.SIT)
    assert tv

    updated, selected, status = preference(state, TODAY, reflection, consider_hint=consider_hint)

    assert selected is expected
    assert morning_options(state, TODAY) == (offers, tv)
    if expected is Intent.STAY:
        assert updated.stayed_at is state.observation
        assert updated.attempt is None
        assert status is None
    elif expected is Intent.SIT:
        assert updated.attempt.choice == offers[1]
        assert updated.attempt.outcome is Outcome.UNKNOWN
        assert status is None
    else:
        assert updated is state
        assert status == "not_executed"


@pytest.mark.parametrize("available", [False, None], ids=["unavailable", "unknown"])
@pytest.mark.parametrize(
    "reflection, attribute",
    [(SEATING, "available"), (SEATING, "reachable"),
     (TELEVISION, "tv_offered"), (TELEVISION, "tv_reachable")],
)
def test_unavailable_or_unknown_affordance_suppresses_reflected_selection(
    available, reflection, attribute,
):
    if reflection is SEATING:
        chair = replace(TODAY.observation.candidate, **{attribute: available})
        sample = replace(TODAY, observation=replace(TODAY.observation, candidate=chair))
    else:
        sample = replace(TODAY, **{attribute: available})
    state = morning_state(sample)
    offers, tv = morning_options(state, sample)
    if reflection is SEATING:
        assert tuple(offer.intent for offer in offers) == (Intent.STAY,)
        assert tv
    else:
        assert tuple(offer.intent for offer in offers) == (Intent.STAY, Intent.SIT)
        assert not tv

    updated, selected, status = preference(state, sample, reflection)

    assert (selected, status) == (Intent.STAY, None)
    assert updated.stayed_at is state.observation
    assert updated.attempt is None


def test_reflection_edits_preserve_an_equivalent_stay_pause():
    state = morning_state(TODAY)
    paused, selection, _ = preference(state, TODAY, None)
    assert selection is Intent.STAY
    anchor = paused.stayed_at
    sample = replace(TODAY, observation=replace(TODAY.observation, revision=5))
    equivalent, _, _ = observe_morning(paused, TODAY.farm_day, sample)
    assert equivalent.observation.revision > anchor.revision

    for reflection in (SEATING, TELEVISION, None):
        assert equivalent.observation.choice_facts == anchor.choice_facts
        assert morning_options(equivalent, sample) == ((), False)
        updated, selected, status = preference(equivalent, sample, reflection)
        assert updated is equivalent
        assert updated.stayed_at is anchor
        assert updated.attempt is None
        assert selected is status is None


@pytest.mark.parametrize("observations", [(), (Acknowledgement(True),)], ids=["unresolved", "ack-only"])
def test_reflection_cannot_complete_an_unverified_experience(observations):
    unresolved, record = sit_trace(*observations)
    reflection = replace(SEATING, text="I wonder whether I could sit there later.")
    assert reflection.cited_keys == (record.fixture,)
    facts = (("weather", "rain"),)
    assert recall((record,)) == facts

    updated, selected, status = preference(unresolved, RAIN, reflection)

    assert (selected, status) == (Intent.STAY, None)
    assert updated.attempt is unresolved.attempt
    assert updated.attempt.outcome is record.posture_outcome is Outcome.UNKNOWN
    assert record.evidence is None
    assert recall((record,)) == facts


def test_missing_citation_cannot_supply_facts_or_verify_a_new_sit():
    reflection = replace(SEATING, cited_keys=("missing-sit",))
    state = morning_state(TODAY)
    history = ()
    assert recall(history) == ()

    updated, selected, status = preference(state, TODAY, reflection)

    assert (selected, status) == (Intent.SIT, None)
    assert updated.attempt.choice.chair_id == "B"
    assert updated.attempt.outcome is Outcome.UNKNOWN
    assert updated.observation is state.observation
    assert recall(history) == ()


@pytest.mark.parametrize("include_history", [True, False], ids=["history", "no-history"])
@pytest.mark.parametrize("reflection", [SEATING, TELEVISION, None], ids=["sit", "tv", "absent"])
def test_optional_inputs_preserve_the_exact_active_unresolved_attempt(include_history, reflection):
    unresolved, record = sit_trace(Acknowledgement(True))
    history = (record,) if include_history else ()
    attempt = unresolved.attempt
    current, _, _ = observe_morning(unresolved, RAIN.farm_day, TODAY)
    assert current.attempt is attempt
    assert observe(current, Acknowledgement(True)) is current

    offers, tv = morning_options(current, TODAY)
    assert tuple(offer.intent for offer in offers) == (Intent.STAY,)
    assert not tv
    updated, selected, status = preference(current, TODAY, reflection)

    assert (selected, status) == (Intent.STAY, None)
    assert updated.attempt is attempt
    assert updated.attempt.outcome is Outcome.UNKNOWN
    assert updated.stayed_at is current.observation
    assert morning_options(updated, TODAY) == ((), False)
    assert preference(updated, TODAY, reflection) == (updated, None, None)
    assert recall(history) == ((("weather", "rain"),) if include_history else ())
