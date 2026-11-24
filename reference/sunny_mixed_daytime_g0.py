"""G0-only mixed Sunny daytime loop: fake P1-help WATER -> fake P2 chair -> STAY.

Composes existing, UNMODIFIED offline L2 fake-game action controller and the
independently G0-reviewed, fake Host-bound WATER permission path. The two fake
dispatchers have no shared production atomic Host entry or real game authority.
All observation and chooser inputs here are synthetic fixtures; no I/O or AI.
"""
from dataclasses import dataclass

from reference.sunny_daytime_intents import Activity, FakeDaytimePlanner, FakeScene
from reference.sunny_gameplay_slice import FakeGame, OfflineController, Observation

# Retain the original toy release function, never an injected per-instance
# cleanup method. This method only clears a matching pending_attempt; it
# cannot dispatch a chair effect. This is INERT G0, not a production Host API.
_ORIGINAL_FAKE_REJECT = FakeGame.finish_rejected
_ORIGINAL_FAKE_DISPATCH = FakeGame.dispatch
from reference.sunny_host_stop_fake import FakeEffectEvidence, FakeHostWaterFence
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
    # A verified fake effect may coexist with a DIFFERENT unresolved nested
    # action. Keep the verified receipt AND expose the pending ID on step().
    pending_operation_id: str | None = None
    # Distinguish verified toy completion from an exceptional post-commit
    # callback that must quarantine later decisions.
    post_verification_block_status: str | None = None



class _HostGatedChairWorld:
    """Toy L2 view: recheck shared fake Host immediately at admission.

    The unchanged L2 OfflineController sees this proxy, while all attempts,
    results and fake positions remain on the SAME underlying FakeGame. This
    is sequential guard composition, NOT an atomic real game/Host boundary.
    """

    def __init__(self, game, allowed, expected_observation,
                 valid_observation, ingest_revocation, pinned_target):
        self._game = game
        # Preserve the original observer before the toy Game's own prepare/
        # dispatch calls are scoped through the validating adapter below.
        self._raw_observe = game.observe
        self._allowed = allowed
        self._before = expected_observation
        self._valid_observation = valid_observation
        self._ingest_revocation = ingest_revocation
        self._pinned_target = pinned_target
        self._started = False
        self._admitted_attempt = None
        self._finalization_callback_failed = False
        # Any injected dispatch has write access to the toy Game and can
        # invoke a saved original bound/unbound dispatcher, erase its row,
        # then lie that it rejected before effect. Neither its ACK nor its
        # pre-effect denial can authorize operation resolution.
        self._untrusted_dispatch_invoked = False
        # L2 still calls finish_rejected, but the adapter owns that release.
        # Per-instance injectable Game cleanup is not a trusted boundary
        # and is NEVER invoked; this also rules out saved-callable dispatch
        # bypasses inside that malicious callback.
        self._rejection_cleanup_attempt = None
        self._rejection_cleanup_contradicted = False

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
            # The injected observer can fabricate a well-shaped post-move
            # snapshot even when ack_no_effect left the underlying FakeGame
            # at its old tile/revision. Cross-check against FakeGame's own
            # authoritative in-memory fields, without calling the injected
            # observer again. L2 must NOT clear pending on a fictional move.
            canonical = FakeGame.observe(self._game)
            # Both sides MUST satisfy the same strict contract before
            # Python dataclass equality: True == 1 and 1.0 == 1 would
            # otherwise hide malformed authoritative toy revisions.
            if (not self._valid_observation(canonical)
                    or snapshot != canonical):
                raise ValueError("inconsistent_fake_chair_observation")
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
        try:
            admitted = self._run_with_checked_reads(
                self._game.prepare, action, expected, attempt
            )
        except Exception:
            # Strict input validation and Host STOP can raise INSIDE the
            # raw FakeGame.prepare read. The toy game's prepare cannot apply
            # movement: when it has NOT reserved this attempt, that failure
            # is a known pre-effect denial, not UNKNOWN without a pending ID.
            # A reservation or evidence of a dispatch instead stays UNKNOWN
            # and must retain the same pending attempt for reconciliation.
            if (self._game.pending_attempt != attempt
                    and not any(row[0] == attempt
                                for row in self._game.dispatched)):
                # A reentrant fake callback can reserve a DIFFERENT
                # operation. The outer prepare has not reserved/effected
                # its own ID. Do not emit UNKNOWN for the *outer* ID:
                # preserve the foreign pending in the shared FakeGame.
                return False
            raise
        if not admitted:
            return False
        self._admitted_attempt = attempt
        if not self._allowed(attempt):
            # Nothing dispatched yet; explicitly retire the toy reservation.
            self.finish_rejected(attempt)
            self._admitted_attempt = None
            return False
        return True

    def dispatch(self, action, expected, attempt):
        if not self._allowed(attempt):
            return "rejected_before_effect"
        # The original toy dispatcher is pinned. No injected Game.dispatch
        # callback is permitted to prove either successful movement OR an
        # absence of effects: it may hold a saved original callable and
        # erase all subsequent Game evidence. Permit such callbacks to run
        # only as offline adversarial probes and quarantine their operation
        # unconditionally, even if their final log/tile looks unchanged.
        self._started = True
        injected = (type(self._game) is not FakeGame
                    or "dispatch" in vars(self._game))
        self._untrusted_dispatch_invoked = injected
        operation = (self._game.dispatch if injected
                     else lambda a, e, i: _ORIGINAL_FAKE_DISPATCH(
                         self._game, a, e, i
                     ))
        try:
            result = self._run_with_checked_reads(
                operation, action, expected, attempt
            )
        finally:
            if injected:
                self._game._fake_mixed_quarantined = True
        if injected:
            # Reject *all* untrusted callback receipts. In particular L2
            # MUST NOT run finish_rejected on a forged pre-effect string.
            return "unknown_untrusted_fake_dispatch"
        if not self._allowed(attempt):
            return "unknown_after_fake_host_change"
        if (type(result) is not str
                or result not in ("ack", "lost_reply", "rejected_before_effect")):
            return "unknown_after_fake_host_change"
        # Only the pinned base dispatcher can return a known pre-effect
        # rejection. Validate its evidence BEFORE L2's adapter-owned release.
        try:
            rows = self._game.dispatched
            if (type(rows) is not list
                    or any(type(row) is not tuple or len(row) != 3
                           or any(type(value) is not str for value in row)
                           for row in rows)):
                raise ValueError("malformed_chair_dispatch_evidence")
            matched = rows.count((attempt, "MOVE_TO_CHAIR", "p2"))
            canonical = FakeGame.observe(self._game)
            if not self._valid_observation(canonical):
                raise ValueError("invalid_chair_dispatch_observation")
        except Exception:
            self._game._fake_mixed_quarantined = True
            return "unknown_malformed_chair_dispatch_evidence"
        if result == "rejected_before_effect":
            if matched != 0 or canonical != expected:
                return "unknown_after_fake_host_change"
            return result
        if result == "ack" and matched != 1:
            return "unknown_after_fake_host_change"
        return result

    def finish_observed_action(self, attempt):
        # The unchanged L2 controller calls this only after its observation
        # checks. Revalidate the *underlying fake Game's* actual tile and
        # revision BEFORE allowing L2 to release the attempt reservation.
        # A plausible but untrue observation must remain UNKNOWN + pending.
        if (not self._allowed(attempt)
                or self._game.pending_attempt != attempt
                or self._game.sunny_tile != self._game.chair_tile
                or self._game.sunny_tile == self._before.sunny_tile
                or type(self._game.revision) is not int
                or self._game.revision <= self._before.revision):
            return False
        try:
            try:
                completed = self._game.finish_observed_action(attempt)
            except Exception:
                # A callback can clear pending without ever calling the
                # authoritative fake finalizer. Dispatch/tile/revision show
                # movement, NOT operation-matched finalization. The accepted
                # FakeGame has no durable completion record. Therefore NEVER
                # convert any exceptional finalizer to VERIFIED_FAKE.
                self._finalization_callback_failed = True
                self._game._fake_mixed_quarantined = True
                return False
            # The parent L2 uses Python truthiness, not `is True`. Never
            # forward a string/int/object standing in for the exact boolean
            # finalization receipt. A false or malformed result after the
            # attempted reservation VANISHED is also unknown, not a clean
            # rejection: quarantine the shared Game before anyone can retry.
            if completed is not True:
                if (completed is not False
                        or self._game.pending_attempt is None):
                    self._finalization_callback_failed = True
                    self._game._fake_mixed_quarantined = True
                return False
            return True
        finally:
            # A finalizer may publish an inactive P1 grant and then return or
            # throw. Ingest BEFORE a test later restores the old active grant.
            self._ingest_revocation()

    def finish_rejected(self, attempt):
        """G0-only adapter-owned release; never run injectable cleanup.

        A callback that has captured the original FakeGame.dispatch function
        can bypass any temporary class hook, erase its own effect row, and
        make post-hoc inspection falsely look clean. Refuse to *execute* that
        callback while a reserved chair attempt could still be dispatched.
        Only this pinned, original FakeGame method may release the attempt.
        """
        self._rejection_cleanup_attempt = attempt
        self._rejection_cleanup_contradicted = True  # pessimistic by default
        try:
            before = FakeGame.observe(self._game)
            before_rows = tuple(self._game.dispatched)
            if (not self._valid_observation(before)
                    or not self._valid_observation(self._before)
                    or before != self._before
                    or self._game.chair_tile != self._pinned_target
                    or type(self._game.chair_tile) is not tuple
                    or len(self._game.chair_tile) != 2
                    or any(type(v) is not int
                           for v in self._game.chair_tile)
                    or type(self._game.pending_attempt) is not str
                    or self._game.pending_attempt != attempt
                    or attempt not in self._game.seen_attempts
                    or any(row[0] == attempt for row in before_rows)):
                return False

            # No user-controlled Game.finish_rejected callback is invoked.
            # The pinned base method never calls dispatch or observe.
            released = _ORIGINAL_FAKE_REJECT(self._game, attempt)
            after = FakeGame.observe(self._game)
            after_rows = tuple(self._game.dispatched)
            clean = (
                released is True
                and self._game.pending_attempt is None
                and self._valid_observation(after)
                and after == before
                and self._game.chair_tile == self._pinned_target
                and type(self._game.chair_tile) is tuple
                and len(self._game.chair_tile) == 2
                and all(type(v) is int for v in self._game.chair_tile)
                and after_rows == before_rows
                and not any(row[0] == attempt for row in after_rows)
            )
            if clean:
                self._rejection_cleanup_contradicted = False
                return True
            return False
        except Exception:
            # Malformed evidence remains an unresolved attempted chair.
            # The cleanup is never allowed to clear its own quarantine flag.
            raise
        finally:
            # P1 grants are delivered by the *separate* fake permission
            # fixture, not as side effects of untrusted cleanup callbacks.
            try:
                self._ingest_revocation()
            finally:
                if self._rejection_cleanup_contradicted:
                    self._game._fake_mixed_quarantined = True


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

    def _pending_operation_id(self):
        """Identity of an unresolved fake chair OR fake Host WATER attempt.

        This accessor is bookkeeping only: it does not authorize an action.
        When the toy Game and Host have simultaneous pending work the Game
        takes priority for the one-ID result shape; both still block in _gate.
        """
        if self.game.pending_attempt is not None:
            return self.game.pending_attempt
        if self.host.pending is not None:
            return getattr(self.host.pending, "operation_id", None)
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

    def _water_game_matches(self, observation):
        """Compare a checked fake reading with STRICT actual toy Game state.

        FakeGame.observe(self.game) reads the in-memory Game fields directly,
        bypassing the injectable observer. Validate *both* sides before ==:
        Python otherwise considers True/1.0 equal to integer 1, and a
        float-coordinate tile equal to an integer-coordinate tile.
        This is only an inert FakeGame consistency check, NOT real telemetry.
        """
        if not self._valid_observation(observation):
            return False
        try:
            canonical = FakeGame.observe(self.game)
        except Exception:
            return False
        return (self._valid_observation(canonical)
                and canonical == observation)

    def _water_candidate(self, scene, observation):
        # Independent position evidence: do NOT trust only crop.adjacent=True.
        world = self.water_world
        if not self._water_game_matches(observation) or not _crop_shape(world.crop):
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
        # Recheck on initial admission AND on every pre-B fixture hook.
        # Do not trust int/bool/float value equality from raw Game fields.
        if not self._water_game_matches(observed):
            return False
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

    def _pending_aware_result(self, status, choice=None, offered=()):
        """Report actual pending identity on all pre-effect callback exits.

        A nested fake action may be a P2 chair reservation in FakeGame or a
        WATER reservation in FakeHostWaterFence. A blocked outer decision
        must not hide that ID, even if its chooser/read threw or lied.
        """
        pending = self._pending_operation_id()
        if pending is not None:
            return FakeMixedDayResult(
                "BLOCKED_UNRESOLVED", choice, offered, pending
            )
        return FakeMixedDayResult(status, choice, offered)

    def step(self):
        # Revocation is a separate fake Host-side event, even if there is
        # already an unresolved action or another activity is selected.
        self.watering._ingest_fixture_revocation(self.water_world)
        gate = self._gate()
        if gate is not None:
            return self._pending_aware_result(gate)
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
            return self._pending_aware_result("BLOCKED_OBSERVATION_UNAVAILABLE")
        # Re-evaluate STOP/pending/identity changed by the read itself,
        # even if the returned fake game snapshot looks otherwise valid.
        if self._gate() is not None:
            return self._pending_aware_result("BLOCKED_CHANGED_BEFORE_DISPATCH")
        # A fabricated high revision must NOT advance the shared replay
        # watermark. Check the direct canonical FakeGame observation before
        # planning or consuming this candidate's revision.
        if not self._valid_observation(observed):
            return self._pending_aware_result("BLOCKED_MALFORMED_OBSERVATION")
        if not self._water_game_matches(observed):
            return self._pending_aware_result("BLOCKED_CHANGED_BEFORE_DISPATCH")
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
            return self._pending_aware_result(
                "BLOCKED_INTEREST_UNAVAILABLE", offered=choices
            )
        # An arbitrary chooser is allowed to reenter the *same* synthetic
        # Game/Host. Before interpreting even an invalid choice, surface any
        # nested pending WATER or chair ID instead of hiding it as invalid.
        gate = self._gate()
        if gate is not None:
            return self._pending_aware_result(
                "BLOCKED_CHANGED_BEFORE_DISPATCH",
                selected if type(selected) is str else None, choices
            )
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
            return self._pending_aware_result(
                "BLOCKED_CHANGED_BEFORE_DISPATCH", selected, choices
            )
        try:
            try:
                after_choice = self.game.observe()
            finally:
                # Observation callbacks may also deliver a P1 revocation;
                # no exception or stale reading may mask that Host tombstone.
                self.watering._ingest_fixture_revocation(self.water_world)
        except Exception:
            return self._pending_aware_result(
                "BLOCKED_OBSERVATION_UNAVAILABLE", selected, choices
            )
        if (not self._water_game_matches(after_choice)
                or after_choice != observed):
            return self._pending_aware_result(
                "BLOCKED_CHANGED_BEFORE_DISPATCH", selected, choices
            )
        # The observation callback itself can change Host STOP/pending without
        # changing any game field. Do NOT reuse the pre-read gate result.
        if self._gate() is not None:
            return self._pending_aware_result(
                "BLOCKED_CHANGED_BEFORE_DISPATCH", selected, choices
            )
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

            # The accepted G0 bridge reads the Host revision watermark
            # BEFORE invoking reserve(), then writes it AFTER reserve()
            # succeeds. An injected reserve callback may run and fully
            # confirm newer WATER in between. Fence that TOCTOU gap at
            # the toy mixed layer; do not modify the accepted parent bridge.
            raw_reserve = self.host.reserve
            own_water_id = self.watering.base._snapshot_operation_id(
                scene, crop
            )

            def reserve_with_pinned_revision(operation):
                # Nested coordinators share the fake Host and can encounter
                # this installed wrapper as their own raw_reserve. Never
                # apply OUTER revision/crop cleanup to another operation.
                # The nested coordinator's own wrapper owns its validation.
                if operation.operation_id != own_water_id:
                    return raw_reserve(operation)
                decision = raw_reserve(operation)
                if decision != "B_LINEAGE_RESERVED":
                    return decision
                current_last = getattr(
                    self.host, "_fake_daytime_water_last_revision", -1
                )
                stale = (
                    type(current_last) is not int or current_last < -1
                    or scene.revision <= current_last
                    or not self._water_game_matches(observed)
                    or self.water_world.crop is not crop
                    or self.water_world.stewardship is not steward
                    or self.water_world.ledger is not ledger
                    or ledger.grant is not grant
                )
                if not stale:
                    return decision
                # Only the fake Host's exactly matching *pre-A/pre-B*
                # reservation may be retired here. Keep its used-ID
                # tombstone, all nested confirmed evidence, Host STOP and
                # the NEWER watermark. If there is any sign A/B began,
                # leave pending for reconciliation instead.
                if (self.host.pending is operation
                        and self.host.b_reserved is True
                        and self.host.a_entered is False
                        and self.host.a_finished is False
                        and self.host.b_entered is False
                        and self.host.b_finished is False):
                    self.host.pending = None
                    self.host.b_reserved = False
                    self.host.events.append(
                        "FAKE_STALE_PRE_A_RESERVATION_RETIRED"
                    )
                return "DENY_REENTRANT_STALE_FAKE"

            # Record before bridge entry: its confirmation callback can
            # successfully resolve WATER at the fake Host and THEN raise.
            # The accepted bridge would label that exception UNKNOWN_PENDING
            # even though this operation has an exact fake receipt.
            prior_effect_count = self.host.events.count("FAKE_EFFECT")
            prior_receipt_count = self.host.events.count(
                "FAKE_OBSERVED_AND_RESOLVED"
            )
            self.host.reserve = reserve_with_pinned_revision
            try:
                result = self.watering.step(
                    scene, self.water_world, "WATER", at_stage=water_pre_b_guard
                )
            except Exception:
                # The parent bridge's reserve() is outside its own try/except.
                # A raising fake callback can still leave nested WATER pending.
                # Never leak the exception and lose its true operation ID.
                pending = self._pending_operation_id()
                if pending is not None:
                    return FakeMixedDayResult(
                        "BLOCKED_UNRESOLVED", selected, choices, pending
                    )
                # No pending evidence: a callback may have had side effects.
                # Quarantine the shared fake Game rather than retry blindly.
                self.game._fake_mixed_quarantined = True
                return FakeMixedDayResult(
                    "BLOCKED_WATER_BRIDGE_EXCEPTION", selected, choices
                )
            finally:
                self.host.reserve = raw_reserve
                self.watering._ingest_fixture_revocation(self.water_world)
            pending = self._pending_operation_id()
            # FAKE_VERIFIED may be a forged callback return. Verify BOTH
            # bridge verdict paths against a real matching fake Host receipt,
            # not merely the callback string. The accepted parent remains
            # untouched, and nested unrelated receipts must not count.
            if (result.verdict in ("UNKNOWN_PENDING", "FAKE_WATER_VERIFIED")
                    and result.operation_id is not None):
                evidence = self.host.last_effect_evidence
                host_confirmed_this_op = (
                    type(evidence) is FakeEffectEvidence
                    and result.operation_id == own_water_id
                    and evidence == FakeEffectEvidence(
                        result.operation_id, scene.epoch,
                        self.expected_owner, crop.tile
                    )
                    and self.host.pending is None
                    and self.host.epoch == scene.epoch
                    and self.host.owner == self.expected_owner
                    and self.host.fake_wet is True
                    and result.operation_id in self.host.used_ids
                    and self.host.events.count("FAKE_EFFECT")
                        > prior_effect_count
                    and self.host.events.count("FAKE_OBSERVED_AND_RESOLVED")
                        > prior_receipt_count
                )
                if host_confirmed_this_op:
                    return FakeMixedDayResult(
                        "FAKE_WATER_VERIFIED", selected, choices,
                        result.operation_id,
                        pending_operation_id=(
                            pending if pending != result.operation_id else None
                        )
                    )
                # If Host still holds THIS operation, the effect is not
                # verified. Its original ID must remain explicitly pending
                # whether the bridge said verified or unknown.
                if (self.host.pending is not None
                        and self.host.pending.operation_id
                            == result.operation_id):
                    return FakeMixedDayResult(
                        "UNKNOWN_PENDING", selected, choices,
                        result.operation_id,
                        pending_operation_id=(
                            pending if pending != result.operation_id else None
                        )
                    )
                # No matching Host confirmation and the supposed pending
                # operation vanished or changed identity: quarantine rather
                # than fabricate verified or pending evidence.
                self.game._fake_mixed_quarantined = True
                if pending is not None and pending != result.operation_id:
                    return FakeMixedDayResult(
                        "BLOCKED_UNRESOLVED", selected, choices, pending
                    )
                return FakeMixedDayResult(
                    "UNKNOWN_UNVERIFIED_WATER_RECEIPT",
                    selected, choices, result.operation_id
                )
            if pending is not None and pending != result.operation_id:
                return FakeMixedDayResult(
                    "BLOCKED_UNRESOLVED", selected, choices, pending
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
            chair_target,
        )
        try:
            result = OfflineController(
                guarded_game, choose_pinned_chair,
                expected_epoch=self.expected_epoch,
                expected_owner=self.expected_owner,
            ).step()
        except Exception:
            # No uncontrolled exception may escape once an effect could
            # have occurred. A rejected-cleanup callback can apply a move
            # and throw after erasing its original attempt reservation.
            # Keep its own attempted ID plus any other pending WATER ID.
            self.game._fake_mixed_quarantined = True
            pending = self._pending_operation_id()
            if guarded_game._rejection_cleanup_contradicted:
                attempt = guarded_game._rejection_cleanup_attempt
                return FakeMixedDayResult(
                    "UNKNOWN", selected, choices, attempt,
                    pending_operation_id=(
                        pending if pending != attempt else None
                    )
                )
            if pending is not None:
                return FakeMixedDayResult(
                    "BLOCKED_UNRESOLVED", selected, choices, pending
                )
            return FakeMixedDayResult(
                "UNKNOWN_CHAIR_CALLBACK_EXCEPTION", selected, choices
            )
        # A post-dispatch callback may have a verified chair action AND a
        # foreign WATER Host pending. Verify the pinned chair independently
        # BEFORE reconciling the pending ID; never discard a real fake chair
        # completion, and never mark it complete based on an L2 claim alone.
        if (guarded_game._rejection_cleanup_contradicted
                and result.verdict == "BLOCKED_STALE_OR_DENIED"):
            # L2 already decided the dispatch was a clean pre-effect
            # rejection, but its later injectable finish_rejected callback
            # applied new movement/dispatch evidence or returned malformed
            # cleanup proof. A false denial must not release this attempt.
            # Even when the cleanup cleared pending, keep the original ID
            # as UNKNOWN and quarantine before another coordinator starts.
            self.game._fake_mixed_quarantined = True
            attempt = result.attempt or guarded_game._rejection_cleanup_attempt
            pending = self._pending_operation_id()
            return FakeMixedDayResult(
                "UNKNOWN", selected, choices, attempt,
                pending_operation_id=(
                    pending if pending != attempt else None
                )
            )
        if guarded_game._finalization_callback_failed:
            # Neither an exception nor a malformed/truthy fake finalizer
            # value proves operation-matched completion. Keep the OUTER chair
            # attempted ID and report a DIFFERENT nested pending WATER/chair
            # identity in its own field, so run_bounded can show both.
            self.game._fake_mixed_quarantined = True
            pending = self._pending_operation_id()
            return FakeMixedDayResult(
                "UNKNOWN_UNVERIFIED_CHAIR_FINALIZATION",
                selected, choices, result.attempt,
                pending_operation_id=(
                    pending if pending != result.attempt else None
                )
            )
        if result.verdict == "VERIFIED_FAKE":
            canonical = FakeGame.observe(self.game)
            if (self._chair_target() != chair_target
                    or self.game.sunny_tile != chair_target
                    or self.game.pending_attempt is not None
                    or canonical.epoch != observed.epoch
                    or canonical.owner != observed.owner
                    or canonical.p1_is_human is not True
                    or canonical.p2_is_ai is not True
                    or canonical.ready is not True
                    or canonical.revision <= observed.revision
                    or self.game.dispatched.count((
                        result.attempt, "MOVE_TO_CHAIR", "p2"
                    )) != 1
                    or result.attempt not in self.game.seen_attempts
                    or not self._valid_chair_observation(
                        canonical, chair_target
                    )):
                self.game._fake_mixed_quarantined = True
                return FakeMixedDayResult(
                    "UNKNOWN_UNVERIFIED_CHAIR_TARGET",
                    selected, choices, result.attempt
                )
            self.completed.add("MOVE_TO_CHAIR")
            pending = self._pending_operation_id()
            return FakeMixedDayResult(
                "VERIFIED_FAKE", selected, choices, result.attempt,
                pending_operation_id=(
                    pending if pending != result.attempt else None
                ),
            )
        # UNKNOWN after a dispatch attempt must preserve the original
        # chair ID even when a mutable effect log is missing, has malformed
        # entries, or was erased by an injected callback. Never iterate
        # arbitrary Game evidence outside this guarded read. In particular,
        # an erased reservation is unresolved regardless of the row count.
        pending = self._pending_operation_id()
        if result.verdict == "UNKNOWN" and result.attempt is not None:
            try:
                rows = self.game.dispatched
                if (type(rows) is not list
                        or any(type(row) is not tuple or len(row) != 3
                               or any(type(v) is not str for v in row)
                               for row in rows)):
                    raise ValueError("malformed_chair_dispatch_log")
                has_row = any(row[0] == result.attempt for row in rows)
                invalid_log = False
            except Exception:
                has_row = False
                invalid_log = True
            if (invalid_log or guarded_game._untrusted_dispatch_invoked
                    or self.game.pending_attempt != result.attempt
                    or self._chair_target() != chair_target):
                self.game._fake_mixed_quarantined = True
            if self._chair_target() != chair_target:
                return FakeMixedDayResult(
                    "UNKNOWN_UNVERIFIED_CHAIR_TARGET",
                    selected, choices, result.attempt,
                    pending_operation_id=(
                        pending if pending != result.attempt else None
                    )
                )
            if pending is not None and pending != result.attempt:
                return FakeMixedDayResult(
                    "UNKNOWN", selected, choices, result.attempt,
                    pending_operation_id=pending
                )
            return FakeMixedDayResult(
                "UNKNOWN", selected, choices, result.attempt
            )
        # For non-UNKNOWN verdicts, retain the old pending-ID priority.
        if pending is not None and pending != result.attempt:
            return FakeMixedDayResult(
                "BLOCKED_UNRESOLVED", selected, choices, pending
            )
        return FakeMixedDayResult(
            result.verdict, selected, choices, result.attempt
        )

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
            if result.pending_operation_id is not None:
                results.append(FakeMixedDayResult(
                    "BLOCKED_UNRESOLVED",
                    operation_id=result.pending_operation_id
                ))
                break
            if result.post_verification_block_status is not None:
                results.append(FakeMixedDayResult(
                    result.post_verification_block_status,
                    operation_id=result.operation_id
                ))
                break
            if result.status not in ("FAKE_WATER_VERIFIED", "VERIFIED_FAKE"):
                break
            # The fake Host may latch STOP *inside* a finalization callback,
            # after the chair movement has been genuinely observed. Keep the
            # verified fake receipt but never publish/choose another activity
            # after that STOP (including on the last bounded decision).
            post_step_gate = self._gate()
            if post_step_gate is not None:
                results.append(self._pending_aware_result(post_step_gate))
                break
            if after_verified is not None:
                try:
                    after_verified(result, self.game, self.water_world, self.host)
                except Exception:
                    # A fixture publisher may have partially mutated the fake
                    # scene before raising. Do not resume it with a fresh
                    # coordinator until independently reconciled.
                    self.game._fake_mixed_quarantined = True
                    results.append(self._pending_aware_result(
                        "BLOCKED_OBSERVATION_UPDATE"
                    ))
                    break
                finally:
                    # Even a callback on the LAST bounded decision may
                    # deliver valid P1 revocation and then return or raise.
                    # Record its Host tombstone before any exit from this run.
                    self.watering._ingest_fixture_revocation(self.water_world)
                # Successful fixture publication is NOT evidence that no
                # other nested work became pending. Preserve the already
                # verified effect receipt above, then explicitly report its
                # shared pending ID before looping or returning (even at the
                # final max_decisions=1 boundary).
                pending = self._pending_operation_id()
                if pending is not None:
                    results.append(FakeMixedDayResult(
                        "BLOCKED_UNRESOLVED", operation_id=pending
                    ))
                    break
        return tuple(results)
