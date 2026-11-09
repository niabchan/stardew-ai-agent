"""Tiny, inert fake-world L2 loop for Sunny. NOT a game or security adapter.

No OS/network/provider access, sockets, clock, SMAPI or credentials.
Inputs are synthetic and injected; this is a bounded offline contract example.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Observation:
    epoch: str
    owner: str
    revision: int
    p1_is_human: bool
    p2_is_ai: bool
    ready: bool
    sunny_tile: tuple[int, int]
    options: tuple[str, ...]


@dataclass(frozen=True)
class StepResult:
    verdict: str
    choice: str | None = None
    attempt: str | None = None


class FakeGame:
    """Synthetic P2-only world. No actual game state, authentication or HTTP."""

    def __init__(self):
        self.epoch = "load-1"
        self.owner = "fake-owner-1"
        self.revision = 1
        self.p1_is_human = True
        self.p2_is_ai = True
        self.ready = True
        self.sunny_tile = (3, 11)
        self.chair_tile = (7, 4)
        self.delivery = "ack"  # ack | lost_reply | ack_no_effect
        self.dispatched = []
        self.seen_attempts = set()
        self.private_p1_diary = "NEVER EXPOSE IN OBSERVATION"

    def observe(self):
        eligible = self.ready and self.p1_is_human and self.p2_is_ai
        options = ("STAY", "MOVE_TO_CHAIR") if eligible and self.sunny_tile != self.chair_tile else ("STAY",)
        return Observation(self.epoch, self.owner, self.revision, self.p1_is_human,
                           self.p2_is_ai, self.ready, self.sunny_tile, options)

    def dispatch(self, action, expected, attempt):
        """Fake atomic gate: role/owner/epoch/revision/affordance before P2 effect."""
        current = self.observe()
        if (current != expected or not current.ready or not current.p1_is_human
                or not current.p2_is_ai or action != "MOVE_TO_CHAIR"
                or action not in current.options or attempt in self.seen_attempts):
            return "rejected"
        self.seen_attempts.add(attempt)
        self.dispatched.append((attempt, action, "p2"))
        if self.delivery != "ack_no_effect":
            self.sunny_tile = self.chair_tile
            self.revision += 1
        return "lost_reply" if self.delivery == "lost_reply" else "ack"


class ScriptedChooser:
    """Deterministic injected choices, NOT Luna inference."""

    def __init__(self, *choices):
        self.choices = iter(choices)
        self.calls = 0

    def __call__(self, observation):
        self.calls += 1
        return next(self.choices)


class OfflineController:
    """Single-step illustrative contract; outcome UNKNOWN latches safe halt."""

    def __init__(self, world, chooser, expected_owner="fake-owner-1"):
        self.world = world
        self.chooser = chooser
        self.expected_owner = expected_owner
        self.halted = False
        self.serial = 0

    def step(self):
        if self.halted:
            return StepResult("BLOCKED_UNRESOLVED")
        before = self.world.observe()  # fake 'status + observe'; no raw P1 feed
        if (not before.ready or not before.p1_is_human or not before.p2_is_ai
                or before.owner != self.expected_owner):
            return StepResult("BLOCKED_PRECONDITION")
        choice = self.chooser(before)  # script, not a call to Luna
        if choice not in before.options:
            return StepResult("BLOCKED_NOT_OFFERED", choice)
        if choice == "STAY":
            return StepResult("STAY", choice)
        self.serial += 1
        attempt = f"offline-attempt-{self.serial}"
        dispatch = self.world.dispatch(choice, before, attempt)
        if dispatch == "rejected":
            self.halted = True
            return StepResult("BLOCKED_STALE_OR_DENIED", choice, attempt)
        if dispatch != "ack":
            self.halted = True
            return StepResult("UNKNOWN", choice, attempt)
        after = self.world.observe()  # requires observed change, not a 200/ACK
        if (after.epoch != before.epoch or after.owner != before.owner
                or not after.p1_is_human or not after.p2_is_ai
                or after.sunny_tile != self.world.chair_tile
                or after.sunny_tile == before.sunny_tile):
            self.halted = True
            return StepResult("UNKNOWN", choice, attempt)
        return StepResult("VERIFIED_FAKE", choice, attempt)
