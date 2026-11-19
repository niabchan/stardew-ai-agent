"""G0-only bridge between fake daytime proposals and fake Host WATER A/B STOP.

All inputs, plot permissions, event ordering and receipts are synthetic.
No real game, SMAPI, provider, file, HTTP, authority or physical STOP.
"""

from dataclasses import dataclass
from typing import Callable

from reference.sunny_daytime_intents import FakeDaytimePlanner, FakeScene
from reference.sunny_host_stop_fake import FakeHostWaterFence, FakeWaterOperation


@dataclass(frozen=True)
class FakeCropObservation:
    """Pretend soil reading for ONE P2 plot tile, not real farm perception."""

    epoch: str = "fake-load-1"
    revision: int = 1
    tile: tuple[int, int] = (4, 5)
    plot_owner: str = "P2"
    soil_dry: bool = True
    watering_can_equipped: bool = True
    water_left: int = 5
    adjacent: bool = True
    menu_closed: bool = True


@dataclass(frozen=True)
class FakeWaterStep:
    verdict: str
    selected: str | None = None
    offered: tuple[str, ...] = ()
    operation_id: str | None = None


class FakeDaytimeWaterBridge:
    """Single threaded deterministic scripted decision -> fake A/B effect.

    Uses existing FakeDaytimePlanner's revision, role, epoch and STAY gate.
    Adds a separate WATER candidate only if explicitly offered *and* every
    synthetic crop condition and local test-only allowlisted tile matches.
    A candidate is NOT authorization; FakeHostWaterFence decides region entry.
    """

    def __init__(self, host: FakeHostWaterFence, allowed_tiles=((4, 5),)):
        if type(host) is not FakeHostWaterFence:
            raise ValueError("fake_host_required")
        if (type(allowed_tiles) is not tuple or not 1 <= len(allowed_tiles) <= 16
                or any(type(t) is not tuple or len(t) != 2
                       or any(type(n) is not int or not 0 <= n < 200 for n in t)
                       for t in allowed_tiles)
                or len(set(allowed_tiles)) != len(allowed_tiles)):
            raise ValueError("fake_allowlist_invalid")
        self.host = host
        self.allowed_tiles = frozenset(allowed_tiles)
        # Intentional fixed synthetic P2 identity: not a Host-issued grant.
        self.expected_epoch = "fake-load-1"
        self.expected_owner = "fake-host-p2"
        self.planner = FakeDaytimePlanner(
            expected_epoch=self.expected_epoch, expected_owner=self.expected_owner
        )
        self.serial = 0

    @staticmethod
    def _scene_shape(scene):
        # The existing planner has broader collection acceptance. The bridge
        # narrows its own input contract before calling the planner.
        return (type(scene) is FakeScene
                and type(scene.weather) is str
                and type(scene.offered_actions) is tuple
                and len(scene.offered_actions) <= 16
                and all(type(a) is str for a in scene.offered_actions)
                and len(set(scene.offered_actions)) == len(scene.offered_actions)
                and type(scene.recently_completed) is tuple
                and len(scene.recently_completed) <= 16
                and all(type(a) is str for a in scene.recently_completed))

    @staticmethod
    def _crop_shape(crop):
        return (type(crop) is FakeCropObservation
                and type(crop.epoch) is str
                and type(crop.revision) is int and crop.revision >= 0
                and type(crop.tile) is tuple and len(crop.tile) == 2
                and all(type(v) is int and 0 <= v < 200 for v in crop.tile)
                and type(crop.plot_owner) is str
                and all(type(x) is bool for x in (
                    crop.soil_dry, crop.watering_can_equipped,
                    crop.adjacent, crop.menu_closed
                ))
                and type(crop.water_left) is int and 0 <= crop.water_left <= 100)

    def _water_grounded(self, scene, crop):
        return (crop.epoch == scene.epoch
                and crop.revision == scene.revision
                and crop.tile in self.allowed_tiles
                and crop.plot_owner == "P2"
                and crop.soil_dry
                and crop.watering_can_equipped
                and crop.water_left > 0
                and crop.adjacent and crop.menu_closed
                and scene.weather == "sunny"
                and "WATER" in scene.offered_actions
                and "WATER" not in scene.recently_completed)

    def step(self, scene, crop, scripted_interest, at_stage: Callable | None = None):
        """One fake proposal/decision and, if allowed, one fake Host operation.

        at_stage is an explicitly test-injected callback for choosing a STOP
        interleaving; it is NOT an arbitrary untrusted request handler.
        """
        if not self._scene_shape(scene):
            return FakeWaterStep("BLOCKED_MALFORMED_SCENE")
        if not self._crop_shape(crop):
            return FakeWaterStep("BLOCKED_MALFORMED_CROP")
        if self.host.pending is not None:
            return FakeWaterStep("BLOCKED_UNRESOLVED")
        if self.host.stopped:
            return FakeWaterStep("BLOCKED_STOP")
        if (self.host.epoch != self.expected_epoch
                or self.host.owner != self.expected_owner):
            return FakeWaterStep("BLOCKED_HOST_EPOCH_OR_OWNER")
        base = self.planner.propose(scene)
        if base.status != "PROPOSED_FAKE":
            return FakeWaterStep(base.status)
        if not any(candidate.action == "STAY" for candidate in base.candidates):
            return FakeWaterStep("BLOCKED_NO_STAY")
        grounded = self._water_grounded(scene, crop)
        offered = ("STAY", "WATER") if grounded else ("STAY",)
        if type(scripted_interest) is not str or scripted_interest not in ("STAY", "WATER"):
            return FakeWaterStep("DENIED_UNSUPPORTED_CHOICE", offered=offered)
        if scripted_interest == "STAY":
            return FakeWaterStep("STAY", "STAY", offered)
        if not grounded:
            return FakeWaterStep("STAY_NOT_GROUNDED", "STAY", offered)
        if at_stage is not None and not callable(at_stage):
            return FakeWaterStep("DENIED_INVALID_TEST_HOOK", offered=offered)

        # This operation ID is synthetic and only unique inside this instance.
        # A new instance cannot bypass host.pending or host.used_ids.
        self.serial += 1
        operation = FakeWaterOperation(
            f"fake-day-water-{self.serial}", scene.epoch,
            self.expected_owner, "P2", "WATER", crop.tile
        )
        if self.host.reserve(operation) != "B_LINEAGE_RESERVED":
            return FakeWaterStep("DENIED_HOST_RESERVATION", offered=offered)
        # Once reserved, any failure remains pending/unknown. No auto retry.
        try:
            if at_stage is not None:
                at_stage("after_reserve", self.host, operation)

            callback_outcome = []

            def synthetic_callback(host, op):
                if at_stage is not None:
                    at_stage("in_a_before_b", host, op)
                result = host.enter_b(op)
                callback_outcome.append(result)
                if result != "B_ENTERED":
                    return
                if at_stage is not None:
                    at_stage("b_entered", host, op)
                callback_outcome.append(host.finish_b(op))

            a_result = self.host.run_a_with_callback(operation, synthetic_callback)
            if a_result != "A_FINISHED_FAKE" or callback_outcome != [
                "B_ENTERED", "B_FINISHED_FAKE"
            ]:
                return FakeWaterStep(
                    "UNKNOWN_PENDING", "WATER", offered, operation.operation_id
                )
            if at_stage is not None:
                at_stage("before_fake_receipt", self.host, operation)
            receipt = self.host.confirm_fake_observation(operation)
            verdict = "FAKE_WATER_VERIFIED" if receipt == "FAKE_VERIFIED" else "UNKNOWN_PENDING"
            return FakeWaterStep(verdict, "WATER", offered, operation.operation_id)
        except Exception:
            # Includes injected test callback failure before/after a fake effect.
            # Never use an exception as proof that no effect happened.
            return FakeWaterStep(
                "UNKNOWN_PENDING", "WATER", offered, operation.operation_id
            )
