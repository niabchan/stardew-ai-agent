"""G0 offline SQLite write-ahead P2 pending barrier; no game, HTTP, or recovery.

This module *persists* a single unresolved-operation barrier on a caller-chosen
trusted local database. It does not authenticate caller identity, authorize
a mutation, verify effects, cancel running work, or integrate with v0.3.10.
All scope fields are UNTRUSTED input assertions. It never clears a pending row.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from dataclasses import dataclass
from typing import Callable


class PendingBlocked(Exception):
    """An earlier unresolved operation exists; NEVER dispatch another mutation."""


class LedgerUnavailable(Exception):
    """The durable barrier cannot be verified; NEVER dispatch a mutation."""


@dataclass(frozen=True)
class PendingClaim:
    # All identity fields here are caller claims, NOT server-issued proof.
    instance_id: str
    epoch: str
    owner: str
    operation_id: str
    attempt_id: str
    tool: str
    arguments_sha256: str


def fingerprint_arguments(arguments: dict) -> str:
    """Stable fingerprint without storing actual arguments / P1 speech text."""
    if type(arguments) is not dict:
        raise ValueError("Tool arguments must be a plain dict")
    try:
        raw = json.dumps(arguments, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid tool arguments") from exc
    return hashlib.sha256(raw).hexdigest()


def _checked_claim(claim: PendingClaim) -> None:
    if type(claim) is not PendingClaim:
        raise ValueError("Invalid operation claim")
    for value in (claim.instance_id, claim.epoch, claim.owner, claim.operation_id,
                  claim.attempt_id):
        if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is None:
            raise ValueError("Expected opaque non-private operation identifiers")
    if type(claim.tool) is not str or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", claim.tool) is None:
        raise ValueError("Invalid game tool identifier")
    if (type(claim.arguments_sha256) is not str or
            re.fullmatch(r"[a-f0-9]{64}", claim.arguments_sha256) is None):
        raise ValueError("Invalid canonical arguments fingerprint")


class PendingLedger:
    """One global unresolved operation per trusted DB, permanently fail-closed.

    A *real* database is used by offline tests, but these caller-asserted fields
    are not host authorization. The DB path must be provisioned by a future
    trusted runner; choose a stable local disk protected from untrusted writers.
    There is intentionally NO clear/delete/reconcile API in G0.
    """

    _COLUMNS = ("instance_id", "epoch", "owner", "operation_id",
                "attempt_id", "tool", "arguments_sha256")

    def __init__(self, path: Path):
        self._path = path

    @staticmethod
    def _path_checked(path: Path) -> Path:
        if type(path) is not Path and not isinstance(path, Path):
            raise ValueError("Expected a local pathlib.Path")
        if not path.is_absolute() or not path.parent.is_dir() or path.is_symlink():
            raise LedgerUnavailable("Invalid or unsafe pending-ledger path")
        if str(path) in ("", ":memory:"):
            raise LedgerUnavailable("In-memory ledger is not durable")
        return path

    @classmethod
    def initialize_new(cls, path: Path) -> "PendingLedger":
        """Explicit first-time provisioning; never used as a restart fallback.

        O_EXCL fails rather than replacing an existing DB. If setup crashes
        mid-way the incomplete file is left quarantined, never erased.
        """
        path = cls._path_checked(path)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except OSError as exc:
            raise LedgerUnavailable("Cannot exclusively provision pending ledger") from exc
        instance = cls(path)
        con = None
        try:
            con = instance._connect(check_schema=False)
            mode = con.execute("PRAGMA journal_mode=DELETE").fetchone()
            if not mode or str(mode[0]).lower() != "delete":
                raise LedgerUnavailable("Unsupported SQLite journal mode")
            con.execute("BEGIN IMMEDIATE")
            con.execute("""
                CREATE TABLE pending_operation (
                    slot INTEGER PRIMARY KEY CHECK (slot = 1),
                    instance_id TEXT NOT NULL,
                    epoch TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    arguments_sha256 TEXT NOT NULL
                )
            """)
            con.execute("PRAGMA user_version=1")
            con.execute("COMMIT")
        except (sqlite3.Error, OSError, LedgerUnavailable) as exc:
            if con is not None and con.in_transaction:
                con.execute("ROLLBACK")
            raise LedgerUnavailable("Pending ledger provision failed; retain file") from exc
        finally:
            if con is not None:
                con.close()
        return instance

    @classmethod
    def open_existing(cls, path: Path) -> "PendingLedger":
        """Restart path: NEVER silently create a replacement missing database."""
        path = cls._path_checked(path)
        if not path.is_file():
            raise LedgerUnavailable("Pending ledger missing; do not reset on restart")
        instance = cls(path)
        con = instance._connect()
        con.close()
        return instance

    def _connect(self, *, check_schema: bool = True) -> sqlite3.Connection:
        if self._path.is_symlink() or not self._path.is_file():
            raise LedgerUnavailable("Pending ledger missing or redirected")
        try:
            con = sqlite3.connect(str(self._path), timeout=0.2, isolation_level=None)
            con.execute("PRAGMA synchronous=FULL")
            if check_schema:
                if con.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise LedgerUnavailable("Unexpected ledger schema version")
                actual = tuple(row[1] for row in con.execute(
                    "PRAGMA table_info(pending_operation)"))
                if actual != ("slot", *self._COLUMNS):
                    raise LedgerUnavailable("Unexpected ledger table schema")
                integrity = con.execute("PRAGMA quick_check").fetchone()
                if integrity is None or integrity[0] != "ok":
                    raise LedgerUnavailable("Pending ledger integrity unknown")
            return con
        except (sqlite3.Error, LedgerUnavailable) as exc:
            if "con" in locals():
                con.close()
            raise LedgerUnavailable("Pending ledger cannot be verified") from exc

    def pending(self) -> PendingClaim | None:
        """Read-only inventory. An empty DB is not a host authorization grant."""
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT " + ", ".join(self._COLUMNS) + " FROM pending_operation LIMIT 2"
            ).fetchall()
            if len(rows) > 1:
                raise LedgerUnavailable("Conflicting pending operations")
            return PendingClaim(*rows[0]) if rows else None
        except sqlite3.Error as exc:
            raise LedgerUnavailable("Pending ledger unreadable") from exc
        finally:
            con.close()

    def reserve(self, claim: PendingClaim) -> None:
        """Atomic write-ahead reservation; commits *before* returning to caller.

        A successful commit means ONLY that a possible dispatch is quarantined.
        Even a positive tool ACK must not release this row. Any I/O or lock
        failure is a hard STOP and cannot allow an effectful send.
        """
        _checked_claim(claim)
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT slot FROM pending_operation LIMIT 1").fetchone():
                raise PendingBlocked("Unresolved P2 operation persists; no second send")
            con.execute(
                "INSERT INTO pending_operation (slot, " + ", ".join(self._COLUMNS) +
                ") VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
                tuple(getattr(claim, name) for name in self._COLUMNS),
            )
            con.execute("COMMIT")
        except PendingBlocked:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise LedgerUnavailable("Pending claim not verified durable; no send") from exc
        finally:
            con.close()

    def claim_for(self, claim: PendingClaim) -> Callable[[str], None]:
        """Callback for future GameTransport.claim_dispatch *in offline tests*.

        The GameTransport callback receives only attempt_id: it cannot attest
        that the tool/args/epoch supplied by its caller really match this claim.
        """
        _checked_claim(claim)

        def claim_dispatch(attempt_id: str) -> None:
            if attempt_id != claim.attempt_id:
                raise PendingBlocked("Wrong attempt for reserved P2 operation")
            self.reserve(claim)

        return claim_dispatch
