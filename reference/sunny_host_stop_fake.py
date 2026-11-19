"""G0-only deterministic *model* of P2 Host A/B entry and STOP.

No Stardew, SMAPI, transports, threads, clocks, file I/O, or actual
authorization are involved. Calls are sequentially ordered by the test.
This model DOES NOT establish a linearizable Host, physical STOP or quiescence.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class FakeWaterOperation:
    operation_id: str
    epoch: str
    owner: str
    seat: str
    action: str
    tile: tuple[int, int]


class FakeHostWaterFence:
    """Single unresolved synthetic operation; B lineage reserved before A.

    The test chooses the order of calls (including reentrant callback),
    which is a *simulation*, not a cross-thread atomicity guarantee.
    """

    def __init__(self):
        self.epoch = "fake-load-1"
        self.owner = "fake-host-p2"
        self.stopped = False
        self.stop_revision = 0
        self.pending: FakeWaterOperation | None = None
        self.used_ids: set[str] = set()
        self.b_reserved = False
        self.a_entered = False
        self.a_finished = False
        self.b_entered = False
        self.b_finished = False
        self.fake_wet = False
        self.events: list[str] = []

    def _valid(self, op):
        return (type(op) is FakeWaterOperation
                and type(op.operation_id) is str and bool(op.operation_id)
                and len(op.operation_id) <= 64
                and type(op.epoch) is str and type(op.owner) is str
                and op.seat == "P2" and op.action == "WATER"
                and type(op.tile) is tuple and len(op.tile) == 2
                and all(type(n) is int and 0 <= n < 200 for n in op.tile))

    def _same(self, op):
        return type(op) is FakeWaterOperation and self.pending is not None and op == self.pending

    def reserve(self, op):
        """Synthetic unresolved reservation, including callback B lineage."""
        if not self._valid(op):
            return "DENY_INVALID"
        if self.stopped:
            return "DENY_STOP"
        if self.pending is not None:
            return "DENY_UNRESOLVED"
        if op.operation_id in self.used_ids:
            return "DENY_REPLAY"
        if op.epoch != self.epoch or op.owner != self.owner:
            return "DENY_OWNER_OR_EPOCH"
        self.pending = op
        self.used_ids.add(op.operation_id)
        self.b_reserved = True  # NOT authorization to enter B yet.
        self.events.append("RESERVE_B_LINEAGE")
        return "B_LINEAGE_RESERVED"

    def enter_a(self, op):
        if self.stopped:
            return "DENY_STOP"
        if not self._same(op) or op.epoch != self.epoch or op.owner != self.owner:
            return "DENY_STALE_OR_UNRESERVED"
        if not self.b_reserved or self.a_entered:
            return "DENY_DUPLICATE_A"
        self.a_entered = True
        self.events.append("ENTER_A")
        return "A_ENTERED"

    def run_a_with_callback(self, op, callback: Callable[["FakeHostWaterFence", FakeWaterOperation], None]):
        """Call back while synthetic A remains entered but unfinished."""
        result = self.enter_a(op)
        if result != "A_ENTERED":
            return result
        callback(self, op)
        return self.finish_a(op)

    def enter_b(self, op):
        if self.stopped:
            return "DENY_STOP"
        if not self._same(op) or op.epoch != self.epoch or op.owner != self.owner:
            return "DENY_STALE_OR_UNRESERVED"
        if not self.b_reserved or not self.a_entered:
            return "DENY_B_BEFORE_A"
        if self.b_entered:
            return "DENY_DUPLICATE_B"
        self.b_entered = True
        self.events.append("ENTER_B")
        return "B_ENTERED"

    def finish_b(self, op):
        """Simulate residual effect: a B entered before STOP may finish after it."""
        if not self._same(op) or not self.b_entered or self.b_finished:
            return "DENY_B_NOT_INFLIGHT"
        self.fake_wet = True
        self.b_finished = True
        self.events.append("FAKE_EFFECT")
        return "B_FINISHED_FAKE"

    def finish_a(self, op):
        if not self._same(op) or not self.a_entered or self.a_finished:
            return "DENY_A_NOT_INFLIGHT"
        self.a_finished = True
        self.events.append("FINISH_A")
        return "A_FINISHED_FAKE"

    def latch_stop(self):
        if not self.stopped:
            self.stopped = True
            self.stop_revision += 1
            self.events.append("STOP_LATCHED")
        return "STOP_LATCHED"

    def rotate_epoch(self):
        """Never silently clear STOP/pending/seen IDs on a fake reload."""
        self.epoch = "fake-load-2"
        self.events.append("FAKE_EPOCH_CHANGED")

    def confirm_fake_observation(self, op):
        """Internally grounded synthetic receipt, NOT a game or durable receipt."""
        if not self._same(op) or not self.a_finished or not self.b_finished or not self.fake_wet:
            return "UNKNOWN_PENDING"
        self.pending = None
        self.b_reserved = False
        self.a_entered = False
        self.a_finished = False
        self.b_entered = False
        self.b_finished = False
        self.events.append("FAKE_OBSERVED_AND_RESOLVED")
        # Crucially, STOP remains latched and operation_id remains used.
        return "FAKE_VERIFIED"
