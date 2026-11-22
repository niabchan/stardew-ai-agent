"""G0-only mixed Sunny daytime loop: fake P1-help WATER -> fake P2 chair -> STAY.

Composes existing, UNMODIFIED offline L2 fake-game action controller and the
independently G0-reviewed, fake Host-bound WATER permission path. The two fake
dispatchers have no shared production atomic Host entry or real game authority.
All observation and chooser inputs here are synthetic fixtures; no I/O or AI.
"""
from dataclasses import dataclass

from reference.sunny_daytime_intents import Activity, FakeDaytimePlanner, FakeScene
from reference.sunny_gameplay_slice import FakeGame, OfflineController, Observation
from reference.sunny_host_stop_fake import FakeHostWaterFence
from reference.sunny_water_permission_g0 import (
    FakePermissionWorld, FakePermissionedWaterBridge, FakeWaterPermissionLedger,
    _crop_identity, _crop_shape,
)


@dataclass(frozen=True)
class FakeMixedDayResult:
    status: str
    choice: str | None = None
    offered: tuple[str, ...] = ()
    operation_id: str | None = None
    claim_real_completion: bool = False



class _HostGatedChairWorld:
    """Toy L2 view: recheck shared fake Host immediately at admission.

    The unchanged L2 OfflineController sees this proxy, while all attempts,
    results and fake positions remain on the SAME underlying FakeGame. This
    is sequential guard composition, NOT an atomic real game/Host boundary.
    """

    def __init__(self, game, allowed, expected_observation,
                 valid_observation, ingest_revocation):
        self._game = game
        # Preserve the original observer before the toy Game's own prepare/
        # dispatch calls are scoped through the validating adapter below.
        self._raw_observe = game.observe
        self._allowed = allowed
        self._before = expected_observation
        self._valid_observation = valid_observation
        self._ingest_revocation = ingest_revocation
        self._started = False
        self._admitted_attempt = None

    def __getattr__(self, attr):
        return getattr(self._game, attr)

    def observe(self):
        try:
            snapshot = self._raw_observe()
            # Strict shape AND the fake Game's own option-set contract. A
            # dataclass's bool/int or float/int equality is NOT enough to
            # authorize movement or confirm an effect.
            if not self._valid_observation(snapshot):
                raise ValueError("malformed_fake_chair_observation")
        finally:
            # A read may install an inactive P1 grant and then fail; retain
            # that shared-Host tombstone at EVERY underlying read exit.
            self._ingest_revocation()
        if not self._allowed(self._admitted_attempt):
            raise RuntimeError("fake_host_not_ready_during_chair_observation")
        if not self._started and snapshot != self._before:
            raise RuntimeError("fake_chair_snapshot_changed_before_start")
        return snapshot

    def _run_with_checked_reads(self, operation, *args):
        """Temporarily route raw FakeGame's own reads through validation.

        FakeGame.prepare/dispatch call self.observe() internally. Wrapping
        only this bounded synchronous toy call prevents equality-based
        authorization with bool/float revisions or inconsistent options.
        Always restore the observer even if the raw operation fails. This
        does not model concurrency, and must not be used on live objects.
        """
        original = self._game.observe
        self._game.observe = self.observe
        try:
            return operation(*args)
        finally:
            self._game.observe = original
            self._ingest_revocation()

    def prepare(self, action, expected, attempt):
        if not self._allowed(None):
            return False
        # FakeGame.prepare performs its OWN read. Strictly validate that
        # read before its dataclass equality check can reserve an attempt.
        admitted = self._run_with_checked_reads(
            self._game.prepare, action, expected, attempt
        )
        if not admitted:
            return False
        self._admitted_attempt = attempt
        if not self._allowed(attempt):
            # Nothing dispatched yet; explicitly retire the toy reservation.
            self._game.finish_rejected(attempt)
            self._admitted_attempt = None
            return False
        return True

    def dispatch(self, action, expected, attempt):
        if not self._allowed(attempt):
            return "rejected_before_effect"
        # Once this fake callback starts an effect may be possible. A STOP
        # discovered AFTER invoking it cannot be described as pre-effect.
        self._started = True
        # FakeGame.dispatch also reads internally. A malformed read must
        # never dispatch an effect based solely on Python value equality.
        result = self._run_with_checked_reads(
            self._game.dispatch, action, expected, attempt
        )
        if not self._allowed(attempt):
            return "unknown_after_fake_host_change"
        return result

    def finish_observed_action(self, attempt):
        if not self._allowed(attempt):
            return False
        return self._game.finish_observed_action(attempt)

    def finish_rejected(self, attempt):
        return self._game.finish_rejected(attempt)


class FakeMixedDaytimeLoop:
    """One optional decision per fresh synthetic farm revision.

    Intent is externally scripted in tests, NOT inferred from an actual model.
    WATER uses the accepted G0 fake Host permission; chair uses the existing
    L2 fake P2-only world; STAY never dispatches. Unresolved on EITHER side
    suppresses ALL further actions even across new coordinator instances.
    """

    def __init__(self, game: FakeGame, host: FakeHostWaterFence,
                 water_world: FakePermissionWorld, interest, *,
                 weather="unknown", expected_epoch="fake-load-1",
                 expected_owner="fake-host-p2"):
        if (not isinstance(game, FakeGame)
                or type(host) is not FakeHostWaterFence
                or type(water_world) is not FakePermissionWorld):
            raise ValueError("synthetic_fixtures_required")
        if (type(weather) is not str or weather not in ("sunny", "rainy", "unknown")
                or type(expected_epoch) is not str or not expected_epoch
                or type(expected_owner) is not str or not expected_owner):
            raise ValueError("invalid_pinned_fake_scope")
        self.game = game
        self.host = host
        self.water_world = water_world
        self.interest = interest
        self.weather = weather
        self.expected_epoch = expected_epoch
        self.expected_owner = expected_owner
        self.planner = FakeDaytimePlanner(expected_epoch, expected_owner)
        self.watering = FakePermissionedWaterBridge(host)
        self.completed = set()

    @staticmethod
    def _valid_observation(observed):
        """Strict toy observation shape before revision/position comparisons."""
        return (type(observed) is Observation
                and type(observed.epoch) is str and bool(observed.epoch)
                and type(observed.owner) is str and bool(observed.owner)
                and type(observed.revision) is int and observed.revision >= 0
                and all(type(v) is bool for v in (
                    observed.p1_is_human, observed.p2_is_ai, observed.ready))
                and type(observed.sunny_tile) is tuple
                and len(observed.sunny_tile) == 2
                and all(type(n) is int and 0 <= n < 200
                        for n in observed.sunny_tile)
                and type(observed.options) is tuple
                and len(observed.options) <= 12
                and all(type(a) is str for a in observed.options)
                and len(set(observed.options)) == len(observed.options))

    def _valid_chair_observation(self, observed, pinned_target):
        """Validate options against FakeGame's *actual* option algorithm.

        The synthetic Game always offers STAY and offers MOVE_TO_CHAIR
        only while eligible and still away from the pinned destination.
        A malformed post-move option set is not valid completion evidence.
        """
        if not self._valid_observation(observed):
            return False
        if pinned_target is None:
            return False
        eligible = observed.ready and observed.p1_is_human and observed.p2_is_ai
        expected = (("STAY", "MOVE_TO_CHAIR") if (
            eligible and observed.sunny_tile != pinned_target
        ) else ("STAY",))
        return observed.options == expected

    def _chair_target(self):
        """Pin toy chair destination outside the P2 observation contract."""
        tile = self.game.chair_tile
        if (type(tile) is tuple and len(tile) == 2
                and all(type(n) is int and 0 <= n < 200 for n in tile)):
            return tile
        return None

    def _gate(self):
        if getattr(self.game, "_fake_mixed_quarantined", False) is not False:
            return "BLOCKED_UNRESOLVED"
        if self.game.pending_attempt is not None or self.host.pending is not None:
            return "BLOCKED_UNRESOLVED"
        if self.host.stopped:
            return "BLOCKED_STOP"
        if (self.host.epoch != self.expected_epoch
                or self.host.owner != self.expected_owner
                or self.game.epoch != self.expected_epoch
                or self.game.owner != self.expected_owner):
            return "BLOCKED_OWNER_OR_EPOCH"
        return None

    def _chair_admitted(self, pinned_target, attempt=None):
        """L2 adapter entry guard; this permits only its OWN fake pending ID."""
        if self._chair_target() != pinned_target:
            return False
        if getattr(self.game, "_fake_mixed_quarantined", False) is not False:
            return False
        if (self.host.pending is not None or self.host.stopped
                or self.host.epoch != self.expected_epoch
                or self.host.owner != self.expected_owner
                or self.game.epoch != self.expected_epoch
                or self.game.owner != self.expected_owner
                or self.game.p1_is_human is not True
                or self.game.p2_is_ai is not True
                or self.game.ready is not True):
            return False
        return (self.game.pending_attempt is None
                or (attempt is not None and self.game.pending_attempt == attempt))

    def _scene(self, observation):
        # No invented P1 awake/distance/diary, TV reachability or seating state.
        # 'sunny' weather is supplied ONLY by an explicit synthetic fixture.
        offered = tuple(observation.options)
        if "WATER" not in offered:
            offered += ("WATER",)  # Permission is checked separately below.
        return FakeScene(
            epoch=observation.epoch, owner=observation.owner,
            revision=observation.revision,
            p1_is_human=observation.p1_is_human,
            p2_is_ai=observation.p2_is_ai, p2_ready=observation.ready,
            offered_actions=offered, weather=self.weather,
            chair_reachable="MOVE_TO_CHAIR" in observation.options,
            p2_seated=False, tv_reachable=False, p1_awake=False,
            p1_distance_tiles=None, social_cooldown=True,
            recently_completed=tuple(sorted(self.completed)),
            unresolved_attempt=False,
        )

    def _water_candidate(self, scene, observation):
        # Independent position evidence: do NOT trust only crop.adjacent=True.
        world = self.water_world
        if not _crop_shape(world.crop):
            return False
        crop = world.crop
        if (crop.epoch != observation.epoch or crop.revision != observation.revision
                or abs(observation.sunny_tile[0] - crop.tile[0])
                   + abs(observation.sunny_tile[1] - crop.tile[1]) != 1):
            return False
        if (type(world.ledger) is not FakeWaterPermissionLedger
                or self.watering._host_check() != "ALLOW_FAKE"):
            return False
        ledger = world.ledger
        return (self.watering._preflight(
            scene, world, _crop_identity(crop), world.stewardship,
            ledger, ledger.grant
        ) == "ALLOW_FAKE")

    def _water_still_admitted(self, scene, observed, crop, steward,
                              ledger, grant, operation=None):
        """Pin the P2 position AND the exact P1 crop through fake WATER start.

        The accepted G0 water bridge checks its own crop.adjacent flag, not
        P2's separate fake position. This synthetic mixed layer MUST recheck
        independent Manhattan adjacency and selected object identities.
        A reserved matching Host operation is permitted only for pre-B hooks.
        """
        self.watering._ingest_fixture_revocation(self.water_world)
        if (self.host.stopped or self.host.epoch != self.expected_epoch
                or self.host.owner != self.expected_owner
                or (self.host.pending is not None
                    and (operation is None or self.host.pending is not operation))
                or self.game.pending_attempt is not None
                or getattr(self.game, "_fake_mixed_quarantined", False) is not False
                or self.game.epoch != observed.epoch
                or self.game.owner != observed.owner
                or self.game.revision != observed.revision
                or self.game.sunny_tile != observed.sunny_tile
                or self.game.p1_is_human is not True
                or self.game.p2_is_ai is not True
                or self.game.ready is not True
                or self.water_world.crop is not crop
                or self.water_world.stewardship is not steward
                or self.water_world.ledger is not ledger
                or type(ledger) is not FakeWaterPermissionLedger
                or ledger.grant is not grant
                or not _crop_shape(crop)
                or crop.epoch != observed.epoch
                or crop.revision != observed.revision
                or (abs(observed.sunny_tile[0] - crop.tile[0])
                    + abs(observed.sunny_tile[1] - crop.tile[1])) != 1):
            return False
        return (self.watering._preflight(
            scene, self.water_world, _crop_identity(crop),
            steward, ledger, grant
        ) == "ALLOW_FAKE")

    def step(self):
        # Revocation is a separate fake Host-side event, even if there is
        # already an unresolved action or another activity is selected.
        self.watering._ingest_fixture_revocation(self.water_world)
        gate = self._gate()
        if gate is not None:
            return FakeMixedDayResult(gate)
        try:
            try:
                observed = self.game.observe()
            finally:
                # The very first fake observation may deliver a valid inactive
                # P1 grant notice *then throw* or return a malformed scene.
                # Its Host tombstone must survive EVERY observation exit,
                # just as it does for the chooser and second observation.
                self.watering._ingest_fixture_revocation(self.water_world)
        except Exception:
            return FakeMixedDayResult("BLOCKED_OBSERVATION_UNAVAILABLE")
        # Re-evaluate STOP/pending/identity changed by the read itself,
        # even if the returned fake game snapshot looks otherwise valid.
        if self._gate() is not None:
            return FakeMixedDayResult("BLOCKED_CHANGED_BEFORE_DISPATCH")
        # Validate before using revision or tile in comparison/arithmetic.
        if not self._valid_observation(observed):
            return FakeMixedDayResult("BLOCKED_MALFORMED_OBSERVATION")
        chair_target = self._chair_target()
        # Cross-coordinator shared replay fence for even voluntary STAY.
        last = getattr(self.game, "_fake_mixed_last_revision", -1)
        if type(last) is not int or last < -1:
            return FakeMixedDayResult("BLOCKED_SNAPSHOT_STATE")
        if observed.revision <= last:
            return FakeMixedDayResult("WAIT_NEW_OBSERVATION")
        scene = self._scene(observed)
        proposal = self.planner.propose(scene)
        if proposal.status != "PROPOSED_FAKE":
            return FakeMixedDayResult(proposal.status)
        offered = [a for a in proposal.candidates
                   if a.action == "STAY"
                   or (a.action == "MOVE_TO_CHAIR" and chair_target is not None)]
        # WATER is *not* automatically authorized by the daytime planner.
        if self._water_candidate(scene, observed):
            offered.append(Activity(
                "WATER", "fake dry adjacent P1 plot with standing Host grant",
                "fake Host operation-matched water effect receipt"
            ))
        choices = tuple(a.action for a in offered)
        self.game._fake_mixed_last_revision = observed.revision
        crop = self.water_world.crop
        steward = self.water_world.stewardship
        ledger = self.water_world.ledger
        grant = ledger.grant if type(ledger) is FakeWaterPermissionLedger else None
        try:
            try:
                selected = self.interest(tuple(offered))
            finally:
                # P1 revocation is a fake Host event, not conditional on the
                # chooser returning a valid interest or returning at all.
                self.watering._ingest_fixture_revocation(self.water_world)
        except Exception:
            return FakeMixedDayResult("BLOCKED_INTEREST_UNAVAILABLE", offered=choices)
        if type(selected) is not str or selected not in choices:
            return FakeMixedDayResult("DENIED_NOT_GROUNDED", offered=choices)
        # FakeGame.observe() omits chair_tile: pin that destination separately
        # so an untrusted chooser cannot move the target but keep the same
        # apparent scene revision/options and obtain a false VERIFIED_FAKE.
        if (self._gate() is not None or self._chair_target() != chair_target
                or self.water_world.crop is not crop
                or self.water_world.stewardship is not steward
                or self.water_world.ledger is not ledger
                or type(ledger) is not FakeWaterPermissionLedger
                or ledger.grant is not grant):
            return FakeMixedDayResult("BLOCKED_CHANGED_BEFORE_DISPATCH",
                                      selected, choices)
        try:
            try:
                after_choice = self.game.observe()
            finally:
                # Observation callbacks may also deliver a P1 revocation;
                # no exception or stale reading may mask that Host tombstone.
                self.watering._ingest_fixture_revocation(self.water_world)
        except Exception:
            return FakeMixedDayResult("BLOCKED_OBSERVATION_UNAVAILABLE",
                                      selected, choices)
        if not self._valid_observation(after_choice) or after_choice != observed:
            return FakeMixedDayResult("BLOCKED_CHANGED_BEFORE_DISPATCH",
                                      selected, choices)
        # The observation callback itself can change Host STOP/pending without
        # changing any game field. Do NOT reuse the pre-read gate result.
        if self._gate() is not None:
            return FakeMixedDayResult("BLOCKED_CHANGED_BEFORE_DISPATCH",
                                      selected, choices)
        if selected == "STAY":
            return FakeMixedDayResult("STAY", selected, choices)
        if selected == "WATER":
            # Both crops may be inside the standing grant: permission alone
            # does not preserve which one was offered or prove P2 adjacency.
            # The second game observation can mutate water_world without
            # changing FakeGame.observe()'s equality-visible fields.
            if not self._water_still_admitted(
                    scene, after_choice, crop, steward, ledger, grant):
                return FakeMixedDayResult("BLOCKED_CHANGED_BEFORE_DISPATCH",
                                          selected, choices)

            def water_pre_b_guard(stage, _host, _world, operation):
                if stage in ("after_wait", "after_reserve", "before_b"):
                    if not self._water_still_admitted(
                            scene, observed, crop, steward, ledger, grant,
                            operation):
                        # Accepted G0 bridge translates pre-reservation
                        # hook failure to DENIED_WAIT_FAILURE; after reserve
                        # it leaves UNKNOWN_PENDING without entering B.
                        raise RuntimeError("mixed_fake_water_scope_changed")

            result = self.watering.step(
                scene, self.water_world, "WATER", at_stage=water_pre_b_guard
            )
            # Do not impose a one-WATER-per-day rule: the Host grant's
            # per-tile spending and snapshot revision enforce the toy bound.
            return FakeMixedDayResult(result.verdict, selected, choices,
                                      result.operation_id)
        def choose_pinned_chair(_observation):
            if (self._gate() is not None
                    or not self._chair_admitted(chair_target)
                    or _observation != observed):
                raise RuntimeError("changed_fake_chair_admission")
            return "MOVE_TO_CHAIR"

        # The reviewed L2 controller has no Host STOP input of its own.
        # Its toy world adapter fences both the reservation and the actual
        # dispatch call, including Host changes during its own observe/prepare.
        guarded_game = _HostGatedChairWorld(
            self.game,
            lambda attempt: self._chair_admitted(chair_target, attempt),
            observed,
            lambda snapshot: self._valid_chair_observation(snapshot, chair_target),
            lambda: self.watering._ingest_fixture_revocation(self.water_world),
        )
        result = OfflineController(
            guarded_game, choose_pinned_chair,
            expected_epoch=self.expected_epoch,
            expected_owner=self.expected_owner,
        ).step()
        # The guarded L2 adapter may already have downgraded the outcome
        # to UNKNOWN after a fake dispatch changed the chair target. Preserve
        # the more specific reason AND a shared-world quarantine.
        if result.verdict == "UNKNOWN" and self._chair_target() != chair_target:
            self.game._fake_mixed_quarantined = True
            return FakeMixedDayResult("UNKNOWN_UNVERIFIED_CHAIR_TARGET",
                                      selected, choices, result.attempt)
        # Existing L2 toy verifies against game.chair_tile (a mutable value).
        # Independently compare the pinned proposal target after L2 execution.
        # An unexpected change means its VERIFIED_FAKE cannot be trusted.
        if result.verdict == "VERIFIED_FAKE" and (
                self._chair_target() != chair_target
                or self.game.sunny_tile != chair_target):
            self.game._fake_mixed_quarantined = True
            return FakeMixedDayResult("UNKNOWN_UNVERIFIED_CHAIR_TARGET",
                                      selected, choices, result.attempt)
        if result.verdict == "VERIFIED_FAKE":
            self.completed.add("MOVE_TO_CHAIR")
        return FakeMixedDayResult(result.verdict, selected, choices,
                                  result.attempt)

    def run_bounded(self, max_decisions=3, after_verified=None):
        """No clock/background loop. Fake observation hook is test-supplied.

        Without a NEW observation after watering, the next step waits rather
        than fabricating a changed soil/revision or blindly repeating WATER.
        """
        if type(max_decisions) is not int or not 1 <= max_decisions <= 4:
            raise ValueError("invalid_fake_decision_bound")
        if after_verified is not None and not callable(after_verified):
            raise ValueError("invalid_fake_observation_hook")
        results = []
        for _ in range(max_decisions):
            result = self.step()
            results.append(result)
            if result.status not in ("FAKE_WATER_VERIFIED", "VERIFIED_FAKE"):
                break
            if after_verified is not None:
                try:
                    after_verified(result, self.game, self.water_world, self.host)
                except Exception:
                    # A fixture publisher may have partially mutated the fake
                    # scene before raising. Do not resume it with a fresh
                    # coordinator until independently reconciled.
                    self.game._fake_mixed_quarantined = True
                    results.append(FakeMixedDayResult("BLOCKED_OBSERVATION_UPDATE"))
                    break
                finally:
                    # Even a callback on the LAST bounded decision may
                    # deliver valid P1 revocation and then return or raise.
                    # Record its Host tombstone before any exit from this run.
                    self.watering._ingest_fixture_revocation(self.water_world)
        return tuple(results)
