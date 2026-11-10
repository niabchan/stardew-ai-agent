"""G0-only bridge of two *fake* contracts: daytime proposal -> L2 fake dispatch.

This references only in-memory FakeGame/Observation and the toy proposal policy.
No actual Stardew Mod, HTTP, Luna, credentials, game files or process access.
"""
from dataclasses import dataclass

from reference.sunny_daytime_intents import Activity, FakeDaytimePlanner, FakeScene
from reference.sunny_gameplay_slice import OfflineController


@dataclass(frozen=True)
class IntegratedResult:
    status: str
    choice: str | None = None
    attempt: str | None = None
    offered: tuple[str, ...] = ()


class OfflineIntentToAction:
    """One synthetic proposal+dispatch per newly observed revision.

    The interest callback sees only toy Activity proposals, not P1 data.
    A selected action is snapshot-pinned before passing to L2. An unknown
    outcome stays unresolved in the shared FakeGame object, not on disk.
    """

    def __init__(self, world, interest, *, expected_epoch="load-1", expected_owner="fake-owner-1"):
        self.world = world
        self.interest = interest
        self.planner = FakeDaytimePlanner(
            expected_epoch=expected_epoch, expected_owner=expected_owner
        )
        self.source_snapshot = None
        self.selection = None
        self.executor = OfflineController(
            world, self._l2_choice, expected_epoch=expected_epoch,
            expected_owner=expected_owner
        )
        self.recently_completed: set[str] = set()

    def _l2_choice(self, observation):
        if observation != self.source_snapshot:
            raise RuntimeError("fake observation changed since intention")
        return self.selection

    def _make_scene(self, observed):
        # The L2 fake observes no weather, social availability or TV access.
        # Fail-closed defaults must not fabricate these as verified facts.
        return FakeScene(
            epoch=observed.epoch,
            owner=observed.owner,
            revision=observed.revision,
            p1_is_human=observed.p1_is_human,
            p2_is_ai=observed.p2_is_ai,
            p2_ready=observed.ready,
            offered_actions=observed.options,
            weather="unknown",
            chair_reachable="MOVE_TO_CHAIR" in observed.options,
            p2_seated=False,  # L2 fake knows tile, NOT actual chair sit state
            tv_reachable=False,
            p1_awake=False,
            p1_distance_tiles=None,
            social_cooldown=True,
            recently_completed=tuple(sorted(self.recently_completed)),
            unresolved_attempt=self.world.pending_attempt is not None,
        )

    def step(self):
        if self.world.pending_attempt is not None:
            return IntegratedResult("BLOCKED_UNRESOLVED")
        if self.executor.halted:
            return IntegratedResult("BLOCKED_L2_HALTED")
        try:
            observed = self.world.observe()
        except Exception:
            return IntegratedResult("BLOCKED_OBSERVATION_UNAVAILABLE")

        proposal = self.planner.propose(self._make_scene(observed))
        if proposal.status != "PROPOSED_FAKE":
            return IntegratedResult(proposal.status)
        offered = tuple(activity.action for activity in proposal.candidates)
        try:
            selected = self.interest(proposal.candidates)
        except Exception:
            return IntegratedResult("BLOCKED_INTEREST_UNAVAILABLE", offered=offered)
        if not isinstance(selected, str) or selected not in offered:
            return IntegratedResult("DENIED_NOT_GROUNDED", offered=offered)

        # These are fake-world candidates, not real supported MCP calls.
        if selected not in ("STAY", "MOVE_TO_CHAIR"):
            return IntegratedResult("DENIED_NO_L2_ADAPTER", selected, offered=offered)
        self.source_snapshot = observed
        self.selection = selected
        executed = self.executor.step()
        if executed.verdict == "VERIFIED_FAKE":
            self.recently_completed.add(selected)
        return IntegratedResult(executed.verdict, selected, executed.attempt, offered)
