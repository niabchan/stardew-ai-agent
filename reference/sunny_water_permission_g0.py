"""Inert G0 P1-help WATER permission example. No game, provider or Host authority.

Observations, stewardship and standing grants are independently fabricated fixtures.
Only a single-threaded fake Host from the reviewed G0 parent is exercised.
"""
from dataclasses import dataclass

from reference.sunny_host_stop_fake import FakeHostWaterFence, FakeWaterOperation
from reference.sunny_water_daytime_g0 import FakeDaytimeWaterBridge


@dataclass(frozen=True)
class FakePermissionCrop:
    """Observed, not authorized: even owner_tag='P2' supplies zero rights."""
    epoch: str = "fake-load-1"
    save_id: str = "fake-save-1"
    day: int = 1
    revision: int = 1
    map_id: str = "Farm"
    tile: tuple[int, int] = (4, 5)
    crop_id: str = "fake-parsnip-1"
    soil_dry: bool = True
    owner_tag: str | None = None
    can_equipped: bool = True
    water_left: int = 5
    adjacent: bool = True
    menu_closed: bool = True


@dataclass(frozen=True)
class FakePlotStewardship:
    """Separate test-owned record; never derived from a Mod crop owner tag."""
    epoch: str = "fake-load-1"
    save_id: str = "fake-save-1"
    map_id: str = "Farm"
    tile: tuple[int, int] = (4, 5)
    crop_id: str = "fake-parsnip-1"
    manager: str = "P1"


@dataclass(frozen=True)
class FakeStandingWaterGrant:
    """Test-fixture provisioned standing P1 -> P2 WATER-only scope."""
    grant_id: str = "fake-p1-help-1"
    epoch: str = "fake-load-1"
    save_id: str = "fake-save-1"
    day: int = 1
    map_id: str = "Farm"
    p2_owner: str = "fake-host-p2"
    manager: str = "P1"
    issued_by: str = "P1"
    grantee: str = "P2"
    action: str = "WATER"
    tiles: tuple[tuple[int, int], ...] = ((4, 5),)
    grant_revision: int = 1
    max_distinct_tiles: int = 1
    max_attempted_starts: int = 1
    active: bool = True


@dataclass(frozen=True)
class FakePermissionWaterResult:
    verdict: str
    selected: str | None = None
    operation_id: str | None = None
    effect_status: str = "NO_EFFECT_EVIDENCE"
    cleanup_status: str = "NOT_STARTED"
    reply_status: str = "NOT_MODELED"
    claim_real_completion: bool = False


def _identifier(value):
    return type(value) is str and 1 <= len(value) <= 64


def _tile(value):
    return (type(value) is tuple and len(value) == 2
            and all(type(n) is int and 0 <= n < 200 for n in value))


def _crop_shape(crop):
    return (type(crop) is FakePermissionCrop
            and all(_identifier(s) for s in (
                crop.epoch, crop.save_id, crop.map_id, crop.crop_id))
            and type(crop.day) is int and 1 <= crop.day <= 9999
            and type(crop.revision) is int and 0 <= crop.revision <= 1_000_000_000
            and _tile(crop.tile)
            and (crop.owner_tag is None or
                 (type(crop.owner_tag) is str and len(crop.owner_tag) <= 64))
            and all(type(x) is bool for x in (
                crop.soil_dry, crop.can_equipped, crop.adjacent, crop.menu_closed))
            and type(crop.water_left) is int and 0 <= crop.water_left <= 100)


def _steward_shape(steward):
    return (type(steward) is FakePlotStewardship
            and all(_identifier(s) for s in (
                steward.epoch, steward.save_id, steward.map_id, steward.crop_id))
            and _tile(steward.tile)
            and type(steward.manager) is str and steward.manager == "P1")


def _grant_shape(grant):
    return (type(grant) is FakeStandingWaterGrant
            and all(_identifier(s) for s in (
                grant.grant_id, grant.epoch, grant.save_id,
                grant.map_id, grant.p2_owner))
            and type(grant.day) is int and 1 <= grant.day <= 9999
            and type(grant.manager) is str and grant.manager == "P1"
            and type(grant.issued_by) is str and grant.issued_by == "P1"
            and type(grant.grantee) is str and grant.grantee == "P2"
            and type(grant.action) is str and grant.action == "WATER"
            and type(grant.tiles) is tuple and 1 <= len(grant.tiles) <= 16
            and all(_tile(t) for t in grant.tiles)
            and len(set(grant.tiles)) == len(grant.tiles)
            and type(grant.grant_revision) is int
            and 1 <= grant.grant_revision <= 1_000_000_000
            and type(grant.max_distinct_tiles) is int
            and 1 <= grant.max_distinct_tiles <= len(grant.tiles)
            and type(grant.max_attempted_starts) is int
            and 1 <= grant.max_attempted_starts <= 64
            and type(grant.active) is bool)


def _crop_identity(crop):
    return (crop.epoch, crop.save_id, crop.day, crop.revision,
            crop.map_id, crop.tile, crop.crop_id)


def _grant_scope(grant):
    """Stable fictional issuer/receiver/save/day/region/limits, not a token."""
    return (grant.grant_id, grant.epoch, grant.save_id, grant.day, grant.map_id,
            grant.p2_owner, grant.manager, grant.issued_by, grant.grantee,
            grant.action, grant.tiles, grant.max_distinct_tiles,
            grant.max_attempted_starts)


class _FakeGrantAccount:
    """Host-object-shared, single-threaded, in-memory fake permission account."""

    def __init__(self, grant):
        self.grant = grant
        self.revoked = not grant.active
        self.attempted_starts = 0
        self.started_tiles = set()


class _FakeHostPermissionStore:
    """Test-fixture-provisioned on the SAME fake Host, not caller authentication.

    A grant ID is bound to its *immutable* scope and budgets. Revocation
    permanently closes that grant ID; consent renewal requires separately
    provisioning a new ID. The store never follows a fresh ledger's counts.
    """

    def __init__(self):
        self.accounts = {}

    def provision(self, grant):
        if not _grant_shape(grant):
            return "DENIED_MALFORMED_GRANT"
        account = self.accounts.get(grant.grant_id)
        if account is None:
            self.accounts[grant.grant_id] = _FakeGrantAccount(grant)
            return "FAKE_GRANT_PROVISIONED" if grant.active else "FAKE_GRANT_REVOKED"
        if type(account) is not _FakeGrantAccount:
            return "DENIED_HOST_PERMISSION_STATE"
        old = account.grant
        if type(old) is not FakeStandingWaterGrant or not _grant_shape(old):
            return "DENIED_HOST_PERMISSION_STATE"
        if _grant_scope(old) != _grant_scope(grant):
            return "DENIED_GRANT_SCOPE_CHANGED"
        if grant.grant_revision < old.grant_revision:
            return "DENIED_STALE_GRANT_REVISION"
        if grant.grant_revision == old.grant_revision:
            if grant != old:
                return "DENIED_CONFLICTING_GRANT_REVISION"
            return "FAKE_GRANT_ALREADY_PROVISIONED"
        if account.revoked and grant.active:
            return "DENIED_GRANT_REVOKED"
        account.grant = grant
        account.revoked = not grant.active
        return "FAKE_GRANT_REVOKED" if account.revoked else "FAKE_GRANT_REVISED"

    def observe_revocation(self, grant):
        # In this toy, a test-injected, higher-revision inactive fixture is
        # treated as a monotonic Host notice even if the current step aborts.
        # This is NOT a trusted P1 revocation channel in a running game.
        if (_grant_shape(grant) and not grant.active
                and grant.grant_id in self.accounts):
            return self.provision(grant)
        return "NO_VALID_HOST_REVOCATION_NOTICE"

    def resolve(self, grant):
        if not _grant_shape(grant):
            return "DENIED_MALFORMED_GRANT", None
        account = self.accounts.get(grant.grant_id)
        if type(account) is not _FakeGrantAccount:
            return "DENIED_UNPROVISIONED_GRANT", None
        old = account.grant
        if not _grant_shape(old):
            return "DENIED_HOST_PERMISSION_STATE", None
        if _grant_scope(grant) != _grant_scope(old):
            return "DENIED_GRANT_SCOPE_CHANGED", None
        if not grant.active:
            self.observe_revocation(grant)
            return "DENIED_GRANT_REVOKED", None
        if account.revoked:
            return "DENIED_GRANT_REVOKED", None
        if grant.grant_revision != old.grant_revision or grant != old:
            return "DENIED_STALE_OR_UNPROVISIONED_GRANT", None
        if (type(account.attempted_starts) is not int
                or account.attempted_starts < 0
                or type(account.started_tiles) is not set
                or any(not _tile(t) for t in account.started_tiles)
                or len(account.started_tiles) > old.max_distinct_tiles
                or account.attempted_starts < len(account.started_tiles)):
            return "DENIED_HOST_PERMISSION_STATE", None
        return "ALLOW_FAKE", account


class FakeWaterPermissionLedger:
    """Untrusted per-world view; the fake Host account owns spent budgets.

    A fresh ledger, world or bridge cannot refill an already provisioned
    grant on that same Host. No durability, threads or trusted signer exist.
    """

    def __init__(self, grant=None):
        self.grant = grant
        self.attempted_starts = 0
        self.started_tiles = set()

    def check(self, scene, crop, steward, store):
        grant = self.grant
        if grant is None:
            return "DENIED_NO_GRANT"
        if not _grant_shape(grant):
            return "DENIED_MALFORMED_GRANT"
        if type(store) is not _FakeHostPermissionStore:
            return "DENIED_HOST_PERMISSION_STATE"
        status, account = store.resolve(grant)
        if status != "ALLOW_FAKE":
            return status
        if not _steward_shape(steward):
            return "DENIED_UNKNOWN_STEWARDSHIP"
        if (_crop_identity(crop)[:2] != (grant.epoch, grant.save_id)
                or crop.day != grant.day or crop.map_id != grant.map_id
                or crop.tile not in grant.tiles
                or grant.p2_owner != scene.owner):
            return "DENIED_GRANT_SCOPE"
        if ((steward.epoch, steward.save_id, steward.map_id,
             steward.tile, steward.crop_id, steward.manager) !=
                (crop.epoch, crop.save_id, crop.map_id,
                 crop.tile, crop.crop_id, grant.manager)):
            return "DENIED_STEWARDSHIP_MISMATCH"
        # Reject visibly corrupted views, but NEVER authorize by their counts.
        if (type(self.attempted_starts) is not int or self.attempted_starts < 0
                or type(self.started_tiles) is not set
                or any(not _tile(t) for t in self.started_tiles)):
            return "DENIED_LEDGER_STATE"
        if crop.tile in account.started_tiles:
            return "DENIED_TILE_ALREADY_STARTED"
        if (account.attempted_starts >= grant.max_attempted_starts
                or len(account.started_tiles) >= grant.max_distinct_tiles):
            return "DENIED_BUDGET"
        return "ALLOW_FAKE"

    def claim_start(self, scene, crop, steward, store):
        """One sequential fake T3 debit immediately before fake B; not atomic."""
        result = self.check(scene, crop, steward, store)
        if result == "ALLOW_FAKE":
            account = store.accounts[self.grant.grant_id]
            account.attempted_starts += 1
            account.started_tiles.add(crop.tile)
            # Diagnostic view only. A new view starts empty but cannot refill
            # Host-owned attempts/tiles.
            self.attempted_starts = account.attempted_starts
            self.started_tiles = set(account.started_tiles)
        return result

class FakePermissionWorld:
    """Mutable fixture for a new crop reading or permission revocation."""
    def __init__(self, crop=None, stewardship=None, ledger=None):
        self.crop = FakePermissionCrop() if crop is None else crop
        self.stewardship = stewardship
        self.ledger = ledger


class FakePermissionedWaterBridge:
    """Opt-in P1 help policy; accepted PR #91 bridge is left untouched."""

    def __init__(self, host):
        if type(host) is not FakeHostWaterFence:
            raise ValueError("fake_host_required")
        self.host = host
        self.base = FakeDaytimeWaterBridge(host)

    def _permission_store(self, create=False):
        store = getattr(self.host, "_fake_water_permission_store", None)
        if store is None and create:
            store = _FakeHostPermissionStore()
            self.host._fake_water_permission_store = store
        return store

    def provision_standing_grant(self, grant):
        """Explicit fake-fixture Host provisioning, NOT real P1 consent."""
        if not _grant_shape(grant):
            return "DENIED_MALFORMED_GRANT"
        store = self._permission_store(create=True)
        if type(store) is not _FakeHostPermissionStore:
            return "DENIED_HOST_PERMISSION_STATE"
        return store.provision(grant)

    def _preflight(self, scene, world, original_identity,
                   original_steward, original_ledger, original_grant):
        crop = world.crop
        if not _crop_shape(crop):
            return "DENIED_MALFORMED_CROP"
        if _crop_identity(crop) != original_identity:
            return "DENIED_CHANGED_CROP"
        if world.stewardship is not original_steward:
            return "DENIED_STEWARDSHIP_CHANGED"
        if world.ledger is not original_ledger:
            return "DENIED_LEDGER_CHANGED"
        if type(world.ledger) is not FakeWaterPermissionLedger:
            return "DENIED_NO_LEDGER"
        # A newer *inactive* fixture latches revocation even on an aborting
        # in-flight step; an old object cannot restore that Host grant later.
        store = self._permission_store()
        if type(store) is _FakeHostPermissionStore:
            store.observe_revocation(world.ledger.grant)
        if world.ledger.grant is not original_grant:
            return "DENIED_GRANT_CHANGED"
        if not crop.soil_dry:
            return "DENIED_NOW_WET"
        if (not crop.can_equipped or crop.water_left <= 0
                or not crop.adjacent or not crop.menu_closed):
            return "DENIED_TOOL_OR_POSITION"
        if crop.epoch != scene.epoch or crop.revision != scene.revision:
            return "DENIED_OBSERVATION_SCOPE"
        if (scene.weather != "sunny"
                or "WATER" not in scene.offered_actions
                or "WATER" in scene.recently_completed):
            return "DENIED_NOT_GROUNDED"
        return world.ledger.check(scene, crop, world.stewardship, store)

    def _host_check(self):
        if self.host.pending is not None:
            return "BLOCKED_UNRESOLVED"
        if self.host.stopped:
            return "BLOCKED_STOP"
        if (self.host.epoch != self.base.expected_epoch
                or self.host.owner != self.base.expected_owner):
            return "BLOCKED_HOST_EPOCH_OR_OWNER"
        return "ALLOW_FAKE"

    def step(self, scene, world, scripted_interest, at_stage=None):
        """Injected callbacks choose deterministic interleavings; TESTS ONLY.

        Stages: after_wait, after_reserve, before_b, b_entered, before_receipt.
        The synthetic after_wait precedes reservation. The before_b stage
        precedes a single-use test-owned start budget claim and fake enter_b.
        """
        if not self.base._scene_shape(scene):
            return FakePermissionWaterResult("BLOCKED_MALFORMED_SCENE")
        if type(world) is not FakePermissionWorld:
            return FakePermissionWaterResult("DENIED_MALFORMED_WORLD")
        if not _crop_shape(world.crop):
            return FakePermissionWaterResult("DENIED_MALFORMED_CROP")
        gate = self._host_check()
        if gate != "ALLOW_FAKE":
            return FakePermissionWaterResult(gate)
        base = self.base.planner.propose(scene)
        if base.status != "PROPOSED_FAKE":
            return FakePermissionWaterResult(base.status)
        if not any(c.action == "STAY" for c in base.candidates):
            return FakePermissionWaterResult("BLOCKED_NO_STAY")
        if type(scripted_interest) is not str or scripted_interest not in (
                "STAY", "WATER", "INSPECT"):
            return FakePermissionWaterResult("DENIED_UNSUPPORTED_CHOICE")
        if scripted_interest == "STAY":
            return FakePermissionWaterResult("STAY", "STAY")
        if scripted_interest == "INSPECT":
            return FakePermissionWaterResult("INSPECT_ONLY", "INSPECT")
        if at_stage is not None and not callable(at_stage):
            return FakePermissionWaterResult("DENIED_INVALID_TEST_HOOK")

        crop = world.crop
        identity = _crop_identity(crop)
        steward = world.stewardship
        ledger = world.ledger
        grant = ledger.grant if type(ledger) is FakeWaterPermissionLedger else None
        decision = self._preflight(scene, world, identity, steward, ledger, grant)
        if decision != "ALLOW_FAKE":
            return FakePermissionWaterResult(decision, "STAY")
        try:
            if at_stage is not None:
                at_stage("after_wait", self.host, world, None)
        except Exception:
            return FakePermissionWaterResult("DENIED_WAIT_FAILURE", "STAY")
        gate = self._host_check()
        if gate != "ALLOW_FAKE":
            return FakePermissionWaterResult(gate, "STAY")
        decision = self._preflight(scene, world, identity, steward, ledger, grant)
        if decision != "ALLOW_FAKE":
            return FakePermissionWaterResult(decision, "STAY")

        last = getattr(self.host, "_fake_daytime_water_last_revision", -1)
        if type(last) is not int or last < -1:
            return FakePermissionWaterResult("DENIED_HOST_SNAPSHOT_STATE", "STAY")
        if scene.revision <= last:
            return FakePermissionWaterResult("DENIED_HOST_STALE_SNAPSHOT", "STAY")
        op = FakeWaterOperation(
            self.base._snapshot_operation_id(scene, crop),
            scene.epoch, self.base.expected_owner, "P2", "WATER", crop.tile
        )
        if self.host.reserve(op) != "B_LINEAGE_RESERVED":
            return FakePermissionWaterResult("DENIED_HOST_RESERVATION", "STAY")
        # Shared with PR #91: consumed only on successful Host reservation.
        self.host._fake_daytime_water_last_revision = scene.revision

        def pending():
            return FakePermissionWaterResult(
                "UNKNOWN_PENDING", "WATER", op.operation_id,
                "PENDING_UNKNOWN", "QUARANTINED"
            )

        try:
            if at_stage is not None:
                at_stage("after_reserve", self.host, world, op)
            b_results = []

            def callback(host, operation):
                if at_stage is not None:
                    at_stage("before_b", host, world, operation)
                if host.stopped or host.epoch != operation.epoch or host.owner != operation.owner:
                    b_results.append("DENIED_HOST_AT_START")
                    return
                check = self._preflight(scene, world, identity, steward, ledger, grant)
                if check != "ALLOW_FAKE":
                    b_results.append(check)
                    return
                # Toy T3: one start budget token, immediately followed by B.
                check = ledger.claim_start(
                    scene, world.crop, world.stewardship, self._permission_store()
                )
                if check != "ALLOW_FAKE":
                    b_results.append(check)
                    return
                result = host.enter_b(operation)
                b_results.append(result)
                if result != "B_ENTERED":
                    return
                if at_stage is not None:
                    at_stage("b_entered", host, world, operation)
                b_results.append(host.finish_b(operation))

            a_result = self.host.run_a_with_callback(op, callback)
            if a_result != "A_FINISHED_FAKE" or b_results != [
                    "B_ENTERED", "B_FINISHED_FAKE"]:
                return pending()
            if at_stage is not None:
                at_stage("before_receipt", self.host, world, op)
            if self.host.confirm_fake_observation(op) != "FAKE_VERIFIED":
                return pending()
            return FakePermissionWaterResult(
                "FAKE_WATER_VERIFIED", "WATER", op.operation_id,
                "CONFIRMED_FAKE_EFFECT", "FAKE_RESOLVED"
            )
        except Exception:
            # No exception, ACK or unrelated wet observation proves no effect.
            return pending()
