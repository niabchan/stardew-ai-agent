"""Follow supplied events through one synthetic day with scripted preferences."""

from dataclasses import dataclass, replace

import pytest

from reference.sunny_posture_g0 import (
    Acknowledgement, Activity, Choice, Intent, Outcome, Posture, State, observe,
)
from test_sunny_context_awareness_g0 import Context, TVAvailability, Weather, tv_proposal
from test_sunny_experiential_memory_g0 import (
    MATCHING_SEAT, Record, capture_verification, historical_fact, morning_state,
    posture_trace, recall,
)
from test_sunny_morning_awareness_g0 import (
    CLEAR, RAIN, Morning, is_observed_morning, morning_options, observe_morning, scripted_choice,
)
from test_sunny_optional_reflection_g0 import Reflection, SEATING, TELEVISION


PRIOR_SCENE = replace(CLEAR.observation.scene, load_id="earlier-load")
PRIOR = replace(RAIN, observation=replace(RAIN.observation, scene=PRIOR_SCENE))
_, H0 = posture_trace(
    "earlier-sit", PRIOR, morning_state(PRIOR), Intent.SIT,
    replace(MATCHING_SEAT, scene=PRIOR_SCENE),
)
START = replace(CLEAR, farm_day=23, tv_offered=False, tv_reachable=False)


def sample(revision, chair=None, *, clock="06:00", rain=False):
    return replace(
        START, morning_cue=False, clock=clock, weather="rain" if rain else "clear",
        tv_offered=rain, tv_reachable=rain,
        observation=replace(
            START.observation, revision=revision, current_chair_id=chair,
            posture=Posture.SEATED if chair else Posture.STANDING,
        ),
    )


@dataclass(frozen=True)
class Transition:
    event: Morning | Acknowledgement | None
    before: State
    after: State
    offers: tuple[Choice, ...]
    tv_eligible: bool
    interest: Intent | Activity | None
    selection: Choice | Activity | None
    offer_revision: int | None
    pending: Record | None
    evidence_revision: int | None
    added: tuple[Record, ...]
    recalled_keys: tuple[str, ...]
    recalled_facts: tuple
    reflection: Reflection | None
    reflection_status: str
    tv_status: str | None

    @property
    def intents(self):
        return tuple(offer.intent for offer in self.offers)


class Day:
    def __init__(self):
        self.state = State(replace(START.project(), revision=0, fresh=False))
        self.sample = START
        self.history = (H0,)
        self.pending = None
        self.trace = []

    def step(
        self, event=None, *, prefer=None, remember=False, after_seating=None,
        fallback=None, record_key=None, reflection=None, consider_hint=None,
    ):
        before = state = self.state
        added = ()
        if isinstance(event, Morning):
            self.sample = event
            assert event.farm_day == 23
            if not self.trace:
                state, day, advanced = observe_morning(state, None, event)
                assert (day, advanced) == (23, False)
                assert is_observed_morning(state, event)
            else:
                assert not event.morning_cue
                state = observe(state, event.project())
                assert not is_observed_morning(state, event)
            assert state.observation == event.project()
            if self.pending and state.attempt.outcome is Outcome.VERIFIED:
                assert self.pending.selection == before.attempt.choice == state.attempt.choice
                assert before.attempt.outcome is Outcome.UNKNOWN
                captured = capture_verification(self.pending, before, state)
                assert captured.evidence is state.observation
                assert captured.posture_outcome is Outcome.VERIFIED
                added = (captured,)
                self.history += added
                self.pending = None
        elif isinstance(event, Acknowledgement):
            state = observe(state, event)
            assert state is before

        offers, tv = morning_options(state, self.sample)
        remembered = self.history if remember else ()
        facts = recall(remembered)
        reflection_status = "absent"
        interest = prefer
        if reflection is not None:
            assert set(reflection.cited_keys) <= {r.fixture for r in self.history}
            reflection_status = {None: "supplied", True: "considered", False: "ignored"}[consider_hint]
            if consider_hint:
                interest = reflection.future_interest
        if after_seating is not None:
            # The scripted preference depends on recalling this particular verified seating.
            seat = next((r.selection for r in remembered if r.fixture == after_seating), None)
            if seat is None or seat.intent is not Intent.SIT or ("posture", seat) not in facts:
                interest = fallback

        context = Context(Weather(self.sample.weather), TVAvailability(self.sample.tv_availability))
        wants_tv = interest is Activity.TV and tv_proposal(state, context, wants_tv=True) is Activity.TV
        requested = interest
        if interest is Activity.TV:
            if not (tv and wants_tv):
                requested = fallback
            elif state.observation.posture is Posture.SEATED:
                requested = Intent.STAND

        updated, tv_status = scripted_choice(state, self.sample, requested, wants_tv=wants_tv)
        selection = None
        if tv_status is not None:
            selection = Activity.TV
        elif updated is not state:
            selection = next(offer for offer in offers if offer.intent is requested)
            if selection.intent is not Intent.STAY:
                assert record_key is not None and self.pending is None
                attempt = updated.attempt
                assert attempt.choice == selection
                self.pending = replace(
                    historical_fact(record_key, self.sample, interest),
                    selection=attempt.choice, posture_outcome=attempt.outcome,
                    activity=attempt.activity, activity_status=attempt.selected_activity_status,
                )
        evidence_revision = next((
            r.evidence.revision for r in self.history
            if updated.attempt and r.selection == updated.attempt.choice
        ), None)
        self.state = updated
        transition = Transition(
            event, before, updated, offers, tv, interest, selection,
            state.observation.revision if selection is not None else None,
            self.pending, evidence_revision, added, tuple(r.fixture for r in remembered), facts,
            reflection, reflection_status,
            tv_status or (updated.attempt and updated.attempt.selected_activity_status),
        )
        self.trace.append(transition)
        return transition


def test_restful_day():
    day = Day()
    first = day.step(START, prefer=Intent.STAY)
    equivalent = day.step(sample(2))
    clock = day.step(sample(3, clock="09:00"))
    later = day.step(sample(4, clock="12:00", rain=True), prefer=Intent.STAY)
    last = day.step(sample(5, clock="12:00", rain=True))

    assert [row.intents for row in day.trace] == [
        (Intent.STAY, Intent.SIT), (), (), (Intent.STAY, Intent.SIT), (),
    ]
    assert [row.tv_eligible for row in day.trace] == [False, False, False, True, False]
    assert first.selection == Choice(START.observation.scene, 1, Intent.STAY)
    assert later.selection == Choice(START.observation.scene, 4, Intent.STAY)
    assert equivalent.after.stayed_at is clock.after.stayed_at is first.after.observation
    assert clock.event.clock != equivalent.event.clock
    assert clock.after.observation.choice_facts == equivalent.after.observation.choice_facts
    assert last.after.stayed_at is later.after.observation
    assert all(row.after.attempt is None and row.pending is None for row in day.trace)
    assert all(row.reflection_status == "absent" and not row.added for row in day.trace)
    assert day.history == (H0,)


@pytest.mark.parametrize("watch", [True, False], ids=["tv-intention", "stay"])
def test_active_but_flexible_day(watch):
    day = Day()
    sit = day.step(START, prefer=Intent.SIT, remember=True, after_seating=H0.fixture, record_key="S1")
    seated = day.step(sample(2, "A"))
    rest = day.step(prefer=Intent.STAY)
    clock = day.step(sample(3, "A", clock="09:00"))
    stand = day.step(
        sample(4, "A", clock="12:00", rain=True), prefer=Activity.TV,
        remember=True, after_seating="S1", fallback=Intent.STAY, record_key="S2",
    )
    standing = day.step(sample(5, clock="12:00", rain=True))
    final = day.step(
        prefer=Intent.STAY, reflection=replace(TELEVISION, cited_keys=("S2",)),
        consider_hint=watch,
    )

    scene = START.observation.scene
    assert sit.recalled_keys == (H0.fixture,)
    assert sit.selection == Choice(scene, 1, Intent.SIT, "A")
    assert sit.after.attempt.outcome is sit.pending.posture_outcome is Outcome.UNKNOWN
    assert sit.pending.evidence is None
    s1, = seated.added
    assert s1.selection == sit.selection and s1.evidence.revision == 2
    assert s1.evidence.current_chair_id == "A"
    assert seated.selection is None and seated.pending is None
    assert seated.intents == (Intent.STAY, Intent.STAND) and not seated.tv_eligible
    assert rest.selection == Choice(scene, 2, Intent.STAY)
    assert rest.after.attempt is clock.after.attempt is seated.after.attempt
    assert clock.after.stayed_at is rest.after.observation
    assert clock.intents == () and clock.selection is None
    assert clock.after.observation.choice_facts == seated.after.observation.choice_facts
    assert stand.recalled_keys == (H0.fixture, "S1")
    assert stand.recalled_facts == recall((H0, s1))
    assert ("posture", s1.selection) in stand.recalled_facts
    assert stand.intents == (Intent.STAY, Intent.STAND)
    assert stand.interest is Activity.TV and stand.tv_eligible
    assert stand.selection == Choice(scene, 4, Intent.STAND, "A")
    assert stand.after.stayed_at is None
    assert stand.after.attempt.outcome is Outcome.UNKNOWN and stand.pending.evidence is None
    assert stand.after.attempt.activity is Activity.TV
    assert stand.after.attempt.completed_prerequisite is None
    s2, = standing.added
    assert s2.selection == stand.selection and s2.evidence.revision == 5
    assert s2.evidence.posture is Posture.STANDING and s2.evidence.current_chair_id is None
    assert standing.after.attempt.completed_prerequisite is Intent.STAND
    assert standing.selection is None and standing.pending is None
    assert standing.intents == (Intent.STAY, Intent.SIT) and standing.tv_eligible
    assert final.after.attempt is standing.after.attempt
    assert final.offer_revision == 5
    if watch:
        assert final.reflection_status == "considered" and final.selection is Activity.TV
        assert final.after is standing.after
    else:
        assert final.reflection_status == "ignored"
        assert final.selection == Choice(scene, 5, Intent.STAY)
        assert final.after.stayed_at is standing.after.observation
    assert stand.tv_status == standing.tv_status == final.tv_status == s2.activity_status == "not_executed"
    assert tuple(record for row in day.trace for record in row.added) == (s1, s2)
    assert [row.evidence_revision for row in day.trace] == [None, 2, 2, 2, None, 5, 5]
    assert all(row.reflection_status == "absent" for row in day.trace[:-1])
    assert day.history == (H0, s1, s2)


def test_unresolved_outcome():
    day = Day()
    sit = day.step(START, prefer=Intent.SIT, record_key="S1")
    ack = day.step(Acknowledgement(True))
    standing = day.step(sample(2))
    rest = day.step(prefer=Intent.STAY)
    clock = day.step(sample(3, clock="09:00"), remember=True, reflection=SEATING, consider_hint=True)
    later = day.step(sample(4, clock="12:00", rain=True), prefer=Activity.TV, fallback=Intent.STAY)
    mismatch = day.step(sample(5, "B", clock="12:00", rain=True))

    scene = START.observation.scene
    assert sit.selection == Choice(scene, 1, Intent.SIT, "A")
    assert ack.after is sit.after
    assert standing.intents == rest.intents == later.intents == mismatch.intents == (Intent.STAY,)
    assert rest.selection == Choice(scene, 2, Intent.STAY)
    assert clock.intents == () and clock.selection is None
    assert clock.after.stayed_at is rest.after.observation
    assert clock.reflection_status == "considered" and clock.interest is Intent.SIT
    assert clock.recalled_keys == (H0.fixture,)
    assert clock.recalled_facts == recall((H0,))
    assert later.interest is Activity.TV and later.selection == Choice(scene, 4, Intent.STAY)
    assert mismatch.after.observation.current_chair_id == "B"
    assert mismatch.after.stayed_at is mismatch.selection is None
    assert sit.after.attempt.outcome is Outcome.UNKNOWN
    assert sit.pending.selection == sit.selection and sit.pending.evidence is None
    assert all(row.after.attempt is sit.after.attempt for row in day.trace)
    assert all(row.evidence_revision is None for row in day.trace)
    assert all(row.pending is sit.pending and not row.added for row in day.trace)
    assert all(not row.tv_eligible and row.tv_status is None for row in day.trace)
    assert day.history == (H0,)
