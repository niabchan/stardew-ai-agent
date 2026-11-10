"""Inert L2 fake-world loop. NOT Luna, game I/O, HTTP or an auth adapter.

The fake action-pending ledger lives only in this in-memory FakeGame object.
It illustrates fail-closed behavior *across controller object recreation*,
NOT a durable journal or safe process restart/reload in a real installation.
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
    """Synthetic, in-memory P2-only world; NO real game state or credentials."""

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
        self.pending_attempt = None
        self.attempt_serial = 0
        self.private_p1_diary = "NEVER EXPOSE IN OBSERVATION"

    def observe(self):
        eligible = self.ready and self.p1_is_human and self.p2_is_ai
        options = ("STAY", "MOVE_TO_CHAIR") if eligible and self.sunny_tile != self.chair_tile else ("STAY",)
        return Observation(self.epoch, self.owner, self.revision, self.p1_is_human,
                           self.p2_is_ai, self.ready, self.sunny_tile, options)

    def new_attempt(self):
        """Unique only within this fake world's in-memory lifetime."""
        self.attempt_serial += 1
        return f"offline-attempt-{self.attempt_serial}"

    def dispatch(self, action, expected, attempt):
        """Illustrative atomic snapshot gate and *pre-effect pending marker*."""
        current = self.observe()
        if (current != expected or not current.ready or not current.p1_is_human
                or not current.p2_is_ai or action != "MOVE_TO_CHAIR"
                or action not in current.options or not attempt
                or self.pending_attempt is not None or attempt in self.seen_attempts):
            return "rejected"
        # This marker exists before the fake effect. It survives controller object
        # recreation using the SAME FakeGame object, but is NOT persisted to disk.
        self.pending_attempt = attempt
        self.seen_attempts.add(attempt)
        self.dispatched.append((attempt, action, "p2"))
        if self.delivery != "ack_no_effect":
            self.sunny_tile = self.chair_tile
            self.revision += 1
        return "lost_reply" if self.delivery == "lost_reply" else "ack"

    def finish_observed_action(self, attempt):
        """Toy completion of ONE fake action after caller's verification."""
        if self.pending_attempt != attempt:
            return False
        self.pending_attempt = None
        return True


class ScriptedChooser:
    """Injected choices only: NOT Luna inference, no provider calls."""

    def __init__(self, *choices):
        self.choices = iter(choices)
        self.calls = 0

    def __call__(self, observation):
        self.calls += 1
        return next(self.choices)


class OfflineController:
    """One bounded fake decision step; unknown result blocks further decisions."""

    def __init__(self, world, chooser, expected_owner="fake-owner-1", expected_epoch="load-1"):
        self.world = world
        self.chooser = chooser
        # Both are synthetic, pre-pinned values, not inferred from an arbitrary
        # new observation. Real owner/epoch provisioning is NOT implemented.
        self.expected_owner = expected_owner
        self.expected_epoch = expected_epoch
        self.halted = False

    def step(self):
        if self.halted:
            return StepResult("BLOCKED_UNRESOLVED")
        # An earlier dispatch is unresolved, even if a fresh controller object
        # has forgotten its own halt flag. Do not ask a chooser to retry.
        if self.world.pending_attempt is not None:
            self.halted = True
            return StepResult("BLOCKED_UNRESOLVED")
        try:
            before = self.world.observe()
        except Exception:
            return StepResult("BLOCKED_OBSERVATION_UNAVAILABLE")
        if before.epoch != self.expected_epoch:
            self.halted = True
            return StepResult("BLOCKED_STALE_EPOCH")
        if (not before.ready or not before.p1_is_human or not before.p2_is_ai
                or before.owner != self.expected_owner):
            return StepResult("BLOCKED_PRECONDITION")
        try:
            choice = self.chooser(before)
        except Exception:
            return StepResult("BLOCKED_CHOICE_UNAVAILABLE")
        if choice not in before.options:
            return StepResult("BLOCKED_NOT_OFFERED", choice)
        if choice == "STAY":
            return StepResult("STAY", choice)
        attempt = self.world.new_attempt()
        try:
            dispatch = self.world.dispatch(choice, before, attempt)
        except Exception:
            # A dispatch exception might occur AFTER the fake effect.
            self.halted = True
            return StepResult("UNKNOWN", choice, attempt)
        if dispatch == "rejected":
            self.halted = True
            return StepResult("BLOCKED_STALE_OR_DENIED", choice, attempt)
        if dispatch != "ack":
            self.halted = True
            return StepResult("UNKNOWN", choice, attempt)
        try:
            after = self.world.observe()
        except Exception:
            self.halted = True
            return StepResult("UNKNOWN", choice, attempt)
        if (after.epoch != before.epoch or after.owner != before.owner
                or not after.ready or not after.p1_is_human or not after.p2_is_ai
                or after.revision <= before.revision
                or after.sunny_tile != self.world.chair_tile
                or after.sunny_tile == before.sunny_tile
                or not self.world.finish_observed_action(attempt)):
            self.halted = True
            return StepResult("UNKNOWN", choice, attempt)
        return StepResult("VERIFIED_FAKE", choice, attempt)
