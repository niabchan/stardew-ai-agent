"""G0-only, game-free illustration of grounded daytime *proposals* for Sunny.

This is not a runtime adapter or Luna chooser; inputs are synthetic and cannot
establish authorization, reliable perception, tool support or game effects.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FakeScene:
    epoch: str = "fake-load-1"
    owner: str = "fake-p2-owner"
    revision: int = 1
    p1_is_human: bool = True
    p2_is_ai: bool = True
    p2_ready: bool = True
    offered_actions: tuple[str, ...] = ("STAY", "MOVE_TO_CHAIR", "WATCH_WEATHER_TV", "SPEAK_TO_P1")
    weather: str = "sunny"
    chair_reachable: bool = True
    p2_seated: bool = False
    tv_reachable: bool = True
    p1_awake: bool = True
    p1_distance_tiles: int | None = 3
    social_cooldown: bool = False
    recently_completed: tuple[str, ...] = ()
    unresolved_attempt: bool = False


@dataclass(frozen=True)
class Activity:
    action: str
    grounding: str
    expected_observation: str


@dataclass(frozen=True)
class ProposalResult:
    status: str
    candidates: tuple[Activity, ...] = ()


@dataclass(frozen=True)
class ChoiceResult:
    status: str
    action: str | None = None
    candidates: tuple[Activity, ...] = ()


class FakeDaytimePlanner:
    """A toy candidate filter, not a model, executor, or real authorization gate.

    One proposal round per synthetic revision prevents endless 'try again'
    decisions without observing a changed situation. There is no fixed daily
    time window, daily action quota or mandatory conversation.
    """

    def __init__(self, expected_epoch="fake-load-1", expected_owner="fake-p2-owner"):
        self.expected_epoch = expected_epoch
        self.expected_owner = expected_owner
        self.last_seen_revision = None

    def propose(self, scene: FakeScene) -> ProposalResult:
        if scene.unresolved_attempt:
            return ProposalResult("BLOCKED_UNRESOLVED")
        if scene.epoch != self.expected_epoch:
            return ProposalResult("BLOCKED_EPOCH")
        if (scene.owner != self.expected_owner or not scene.p1_is_human
                or not scene.p2_is_ai or not scene.p2_ready):
            return ProposalResult("BLOCKED_ROLE_OR_OWNER")
        if self.last_seen_revision is not None and scene.revision <= self.last_seen_revision:
            return ProposalResult("WAIT_NEW_OBSERVATION")
        self.last_seen_revision = scene.revision
        offered = set(scene.offered_actions)
        if "STAY" not in offered:
            return ProposalResult("BLOCKED_NO_STAY")
        candidates = [Activity("STAY", "rest or observe without acting", "no dispatched activity")]
        recently = set(scene.recently_completed)
        if ("MOVE_TO_CHAIR" in offered and scene.chair_reachable and not scene.p2_seated
                and "MOVE_TO_CHAIR" not in recently):
            candidates.append(Activity("MOVE_TO_CHAIR", "reachable empty chair", "new P2 location or seating evidence required"))
        if "WATCH_WEATHER_TV" in offered and scene.tv_reachable and "WATCH_WEATHER_TV" not in recently:
            candidates.append(Activity("WATCH_WEATHER_TV", "TV is reachable", "independent evidence of P2 TV interaction required"))
        if ( "SPEAK_TO_P1" in offered and scene.p1_awake and scene.p1_distance_tiles is not None
                and 0 <= scene.p1_distance_tiles <= 5 and not scene.social_cooldown
                and "SPEAK_TO_P1" not in recently):
            candidates.append(Activity("SPEAK_TO_P1", "P1 is awake and nearby; no cooldown", "P2 speech receipt required"))
        return ProposalResult("PROPOSED_FAKE", tuple(candidates))

    def choose(self, scene: FakeScene, simulated_interest: str) -> ChoiceResult:
        result = self.propose(scene)
        if result.status != "PROPOSED_FAKE":
            return ChoiceResult(result.status)
        if simulated_interest not in {candidate.action for candidate in result.candidates}:
            return ChoiceResult("DENIED_NOT_GROUNDED", candidates=result.candidates)
        return ChoiceResult("SELECTED_FAKE", simulated_interest, result.candidates)
