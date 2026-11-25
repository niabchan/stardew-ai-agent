"""Standalone synthetic P2 posture and choice model."""

from dataclasses import dataclass, replace
from enum import Enum


class Posture(Enum):
    STANDING = "standing"
    SEATED = "seated"
    UNKNOWN = "unknown"


class Intent(Enum):
    STAY = "stay"
    SIT = "sit"
    STAND = "stand"


class Activity(Enum):
    MOVE = "move"
    TV = "tv"


class Outcome(Enum):
    UNKNOWN = "unknown"
    VERIFIED = "verified"


@dataclass(frozen=True)
class Scene:
    p2_id: str
    load_id: str
    map_id: str


@dataclass(frozen=True)
class Chair:
    chair_id: str | None
    available: bool | None
    reachable: bool | None


@dataclass(frozen=True)
class Observation:
    scene: Scene
    revision: int
    fresh: bool
    posture: Posture
    current_chair_id: str | None = None
    candidate: Chair | None = None
    decision_context: str = ""
    tile: tuple[int, int] | None = None

    @property
    def choice_facts(self) -> tuple:
        return (
            self.posture, self.current_chair_id, self.candidate,
            self.decision_context,
        )


@dataclass(frozen=True)
class Acknowledgement:
    accepted: bool


@dataclass(frozen=True)
class Choice:
    scene: Scene
    revision: int
    intent: Intent
    chair_id: str | None = None


@dataclass(frozen=True)
class Attempt:
    choice: Choice
    activity: Activity | None = None
    outcome: Outcome = Outcome.UNKNOWN

    @property
    def completed_prerequisite(self) -> Intent | None:
        if self.activity is not None and self.outcome is Outcome.VERIFIED:
            return Intent.STAND
        return None

    @property
    def selected_activity_status(self) -> str | None:
        if self.activity is not None:
            return "not_executed"
        return None


@dataclass(frozen=True)
class State:
    observation: Observation
    stayed_at: Observation | None = None
    attempt: Attempt | None = None


def choices(state: State) -> tuple[Choice, ...]:
    obs = state.observation
    if state.stayed_at is not None and (
        not obs.fresh or obs.choice_facts == state.stayed_at.choice_facts
    ):
        return ()

    stay = Choice(obs.scene, obs.revision, Intent.STAY)
    if not obs.fresh or (
        state.attempt is not None and state.attempt.outcome is Outcome.UNKNOWN
    ):
        return (stay,)

    if obs.posture is Posture.SEATED and obs.current_chair_id:
        return (stay, Choice(obs.scene, obs.revision, Intent.STAND, obs.current_chair_id))

    chair = obs.candidate
    if (
        obs.posture is Posture.STANDING
        and obs.current_chair_id is None
        and chair is not None
        and chair.chair_id
        and chair.available is True
        and chair.reachable is True
    ):
        return (stay, Choice(obs.scene, obs.revision, Intent.SIT, chair.chair_id))
    return (stay,)


def choose(state: State, choice: Choice, activity: Activity | None = None) -> State:
    """Record an eligible choice. Invalid or superseded choices leave state intact."""
    if choice not in choices(state):
        return state
    if activity is not None and (
        not isinstance(activity, Activity) or choice.intent is not Intent.STAND
    ):
        return state
    if choice.intent is Intent.STAY:
        return replace(state, stayed_at=state.observation)
    return replace(state, attempt=Attempt(choice, activity))


def observe(state: State, evidence: Observation | Acknowledgement) -> State:
    """Accept a new same-scene revision and verify only its explicit posture."""
    if isinstance(evidence, Acknowledgement):
        return state
    previous = state.observation
    if evidence.scene != previous.scene or evidence.revision <= previous.revision:
        return state

    stayed_at = state.stayed_at
    if (
        stayed_at is not None
        and evidence.fresh
        and evidence.choice_facts != stayed_at.choice_facts
    ):
        stayed_at = None

    attempt = state.attempt
    if attempt is not None and attempt.outcome is Outcome.UNKNOWN and evidence.fresh:
        choice = attempt.choice
        if choice.intent is Intent.SIT:
            verified = (
                evidence.posture is Posture.SEATED
                and evidence.current_chair_id == choice.chair_id
            )
        else:
            verified = (
                evidence.posture is Posture.STANDING
                and evidence.current_chair_id is None
            )
        if verified:
            attempt = replace(attempt, outcome=Outcome.VERIFIED)

    return State(evidence, stayed_at, attempt)
