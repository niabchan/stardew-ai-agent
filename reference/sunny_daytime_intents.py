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
        self.blocked_unresolved = False

    def propose(self, scene: FakeScene) -> ProposalResult:
        # An unresolved synthetic attempt permanently stops this toy instance.
        # A refreshed revision/cleared caller flag is not resolution evidence.
        if self.blocked_unresolved:
            return ProposalResult("BLOCKED_UNRESOLVED")
        if type(scene) is not FakeScene:
            return ProposalResult("BLOCKED_MALFORMED_SCENE")
        if scene.unresolved_attempt is True:
            self.blocked_unresolved = True
            return ProposalResult("BLOCKED_UNRESOLVED")
        boolean_fields = (scene.p1_is_human, scene.p2_is_ai, scene.p2_ready,
                          scene.chair_reachable, scene.p2_seated, scene.tv_reachable,
                          scene.p1_awake, scene.social_cooldown, scene.unresolved_attempt)
        collections = (scene.offered_actions, scene.recently_completed)
        if (any(type(value) is not bool for value in boolean_fields)
                or type(scene.epoch) is not str or type(scene.owner) is not str
                or type(scene.revision) is not int or scene.revision < 0
                or (scene.p1_distance_tiles is not None
                    and (type(scene.p1_distance_tiles) is not int or scene.p1_distance_tiles < 0))
                or any(type(values) not in (tuple, list, set, frozenset)
                       or any(type(value) is not str for value in values)
                       for values in collections)):
            return ProposalResult("BLOCKED_MALFORMED_SCENE")
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
            candidates.append(Activity("MOVE_TO_CHAIR", "synthetic reachable chair", "fake tile movement only; no sit/stand evidence"))
        if "WATCH_WEATHER_TV" in offered and scene.tv_reachable and "WATCH_WEATHER_TV" not in recently:
            candidates.append(Activity("WATCH_WEATHER_TV", "TV is reachable", "independent evidence of P2 TV interaction required"))
        if ( "SPEAK_TO_P1" in offered and scene.p1_awake and scene.p1_distance_tiles is not None
                and 0 <= scene.p1_distance_tiles <= 5 and not scene.social_cooldown
                and "SPEAK_TO_P1" not in recently):
            candidates.append(Activity("SPEAK_TO_P1", "synthetic awake/range/cooldown flags only", "no speech dispatched; no consent or receipt established"))
        return ProposalResult("PROPOSED_FAKE", tuple(candidates))

    def choose(self, scene: FakeScene, simulated_interest: str) -> ChoiceResult:
        result = self.propose(scene)
        if result.status != "PROPOSED_FAKE":
            return ChoiceResult(result.status)
        if type(simulated_interest) is not str or simulated_interest not in {candidate.action for candidate in result.candidates}:
            return ChoiceResult("DENIED_NOT_GROUNDED", candidates=result.candidates)
        return ChoiceResult("SELECTED_FAKE", simulated_interest, result.candidates)
