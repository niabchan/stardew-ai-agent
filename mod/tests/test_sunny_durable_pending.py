"""G0 test: real temporary SQLite journal; fake game/HTTP only, no Sunny launch."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from reference.sunny_transport import GameTransport, ProtocolFailure, TransportResponse
from reference.sunny_transport.durable_pending import (
    LedgerUnavailable, PendingBlocked, PendingClaim, PendingLedger,
    fingerprint_arguments,
)


def scope(attempt="a1", operation="op1", **changes):
    values = dict(instance_id="fake-instance", epoch="fake-load-1",
                  owner="fake-p2-owner", operation_id=operation,
                  attempt_id=attempt, tool="say",
                  arguments_sha256=fingerprint_arguments({"text": "Private P1 example — NEVER STORE"}))
    values.update(changes)
    return PendingClaim(**values)


def new_ledger(tmp_path):
    return PendingLedger.initialize_new(tmp_path / "pending.sqlite3")


def test_restart_requires_existing_database_and_no_implicit_reprovision(tmp_path):
    path = tmp_path / "pending.sqlite3"
    with pytest.raises(LedgerUnavailable):
        PendingLedger.open_existing(path)
    ledger = PendingLedger.initialize_new(path)
    assert ledger.pending() is None
    with pytest.raises(LedgerUnavailable):
        PendingLedger.initialize_new(path)
    assert PendingLedger.open_existing(path).pending() is None


def test_atomic_pending_survives_reopen_and_blocks_fresh_attempt(tmp_path):
    ledger = new_ledger(tmp_path)
    first = scope()
    ledger.reserve(first)
    reopened = PendingLedger.open_existing(tmp_path / "pending.sqlite3")
    assert reopened.pending() == first
    for proposed in (first, scope(attempt="a2", operation="op2"),
                     scope(attempt="a3", operation="op3", epoch="fake-load-2"),
                     scope(attempt="a4", operation="op4", instance_id="another-game")):
        with pytest.raises(PendingBlocked):
            reopened.reserve(proposed)
    assert reopened.pending() == first


def test_db_contains_no_raw_tool_arguments_p1_text_or_provider_secret(tmp_path):
    ledger = new_ledger(tmp_path)
    ledger.reserve(scope())
    raw = (tmp_path / "pending.sqlite3").read_bytes()
    assert b"Private P1 example" not in raw
    assert b"NEVER STORE" not in raw
    assert b"Authorization:" not in raw
    assert ledger.pending().arguments_sha256 == fingerprint_arguments(
        {"text": "Private P1 example — NEVER STORE"})


def test_explicit_first_time_create_will_not_overwrite_existing_unknown_file(tmp_path):
    path = tmp_path / "pending.sqlite3"
    path.write_text("not a valid SQLite database", encoding="utf-8")
    with pytest.raises(LedgerUnavailable):
        PendingLedger.initialize_new(path)
    with pytest.raises(LedgerUnavailable):
        PendingLedger.open_existing(path)
    assert path.read_text(encoding="utf-8") == "not a valid SQLite database"


def test_missing_or_deleted_db_after_restart_does_not_silently_create_fresh_one(tmp_path):
    path = tmp_path / "pending.sqlite3"
    ledger = new_ledger(tmp_path)
    ledger.reserve(scope())
    path.unlink()  # only pytest temp DB; never a user's database
    with pytest.raises(LedgerUnavailable):
        PendingLedger.open_existing(path)
    assert not path.exists()


def test_abrupt_process_exit_after_commit_preserves_pending_quarantine(tmp_path):
    path = tmp_path / "pending.sqlite3"
    new_ledger(tmp_path)
    code = (
        "import os,sys; from pathlib import Path; "
        "from reference.sunny_transport.durable_pending import PendingLedger,PendingClaim; "
        "p=Path(sys.argv[1]); "
        "x=PendingClaim('fake-instance','fake-load-1','fake-owner',"
        "'op99','a99','go_to_bed','a'*64); "
        "PendingLedger.open_existing(p).reserve(x); os._exit(0)"
    )
    child = subprocess.run([sys.executable, "-c", code, str(path)],
                           cwd=Path(__file__).resolve().parents[2],
                           capture_output=True, text=True, timeout=15, check=True)
    assert child.returncode == 0
    restarted = PendingLedger.open_existing(path)
    assert restarted.pending().attempt_id == "a99"
    with pytest.raises(PendingBlocked):
        restarted.reserve(scope(attempt="new-after-restart", operation="op-new"))


class FakeP2:
    def __init__(self):
        self.calls = []

    def __call__(self, request):
        self.calls.append(request)
        payload = json.loads(request.body)
        rid = payload["id"]
        if payload["method"] == "initialize":
            result = {"protocolVersion": GameTransport.PROTOCOL}
            headers = {"X-Sunny-Save-Epoch": "fake-load-1",
                       "Mcp-Session-Id": "fake-owner-session"}
        else:
            result = {"isError": False, "content": [{"type": "text", "text": "ACK only"}]}
            headers = {"X-Sunny-Save-Epoch": "fake-load-1"}
        return TransportResponse(200, headers,
                                 json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}).encode())


def test_fake_adapter_ack_then_new_process_object_still_blocked_by_sqlite(tmp_path):
    ledger = new_ledger(tmp_path)
    fake = FakeP2()
    client = GameTransport("http://127.0.0.1:18770", fake, credential="synthetic")
    client.initialize()
    ack = client.call_tool("say", {"text": "fake private message"}, mutation=True,
                           attempt_id="a1", claim_dispatch=ledger.claim_for(scope()))
    assert ack["isError"] is False
    assert client.unresolved_mutation
    assert len(fake.calls) == 2

    restarted = PendingLedger.open_existing(tmp_path / "pending.sqlite3")
    new_fake = FakeP2()
    new_client = GameTransport("http://127.0.0.1:18770", new_fake, credential="synthetic")
    new_client.initialize()  # Fake protocol only; NOT proof of a safe new host lease
    with pytest.raises(PendingBlocked):
        new_client.call_tool("go_to_bed", {}, mutation=True, attempt_id="a2",
                             claim_dispatch=restarted.claim_for(scope(
                                 attempt="a2", operation="op2", tool="go_to_bed",
                                 arguments_sha256=fingerprint_arguments({}))))
    assert len(new_fake.calls) == 1  # initialize only; zero second game-tool sends
    assert restarted.pending().attempt_id == "a1"


def test_mismatched_claim_attempt_fails_before_effectful_fake_send(tmp_path):
    ledger = new_ledger(tmp_path)
    fake = FakeP2()
    client = GameTransport("http://127.0.0.1:8770", fake, credential="synthetic")
    client.initialize()
    with pytest.raises(PendingBlocked):
        client.call_tool("say", {"text": "hello"}, mutation=True,
                         attempt_id="wrong", claim_dispatch=ledger.claim_for(scope()))
    assert ledger.pending() is None and len(fake.calls) == 1
    assert client.unresolved_mutation  # failure to claim cannot grant another send


@pytest.mark.parametrize("invalid", [
    dict(instance_id="a b"), dict(epoch=""), dict(owner="P1 private user"),
    dict(tool="send:human"), dict(arguments_sha256="0"*63),
])
def test_invalid_or_private_scope_is_rejected_before_ledger_write(tmp_path, invalid):
    ledger = new_ledger(tmp_path)
    with pytest.raises(ValueError):
        ledger.reserve(scope(**invalid))
    assert ledger.pending() is None


def test_corrupt_db_fails_closed_and_is_not_overwritten(tmp_path):
    path = tmp_path / "pending.sqlite3"
    ledger = new_ledger(tmp_path)
    ledger.reserve(scope())
    path.write_bytes(b"broken")
    with pytest.raises(LedgerUnavailable):
        PendingLedger.open_existing(path)
    assert path.read_bytes() == b"broken"


def test_open_existing_rejects_symlinked_database(tmp_path):
    original = tmp_path / "original.sqlite3"
    PendingLedger.initialize_new(original)
    alias = tmp_path / "alias.sqlite3"
    try:
        alias.symlink_to(original)
    except OSError:
        pytest.skip("Symlink creation not supported on this machine")
    with pytest.raises(LedgerUnavailable):
        PendingLedger.open_existing(alias)


def test_sqlite_write_lock_or_unknown_ledger_state_fails_closed(tmp_path):
    path = tmp_path / "pending.sqlite3"
    new_ledger(tmp_path)
    lock = sqlite3.connect(str(path), timeout=0.1, isolation_level=None)
    try:
        lock.execute("BEGIN IMMEDIATE")
        with pytest.raises(LedgerUnavailable):
            PendingLedger.open_existing(path).reserve(scope())
    finally:
        lock.execute("ROLLBACK")
        lock.close()
    assert PendingLedger.open_existing(path).pending() is None


@pytest.mark.parametrize("arguments", [{1: "x"}, {"nested": [{False: "x"}]}])
def test_fingerprint_rejects_keys_that_json_would_coerce(arguments):
    with pytest.raises(ValueError):
        fingerprint_arguments(arguments)


def test_restart_open_deletion_race_never_creates_file(tmp_path, monkeypatch):
    path = tmp_path / "pending ?#.sqlite3"
    PendingLedger.initialize_new(path)
    real_connect = sqlite3.connect

    def disappear(*args, **kwargs):
        path.unlink()
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", disappear)
    with pytest.raises(LedgerUnavailable):
        PendingLedger.open_existing(path)
    assert not path.exists()


def test_ledger_object_rejects_replacement_database(tmp_path):
    ledger = new_ledger(tmp_path)
    ledger.reserve(scope())
    path = tmp_path / "pending.sqlite3"
    path.rename(tmp_path / "quarantined.sqlite3")
    PendingLedger.initialize_new(path)
    with pytest.raises(LedgerUnavailable):
        ledger.reserve(scope(attempt="a2"))


def test_concurrent_reservations_have_exactly_one_winner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ledger = new_ledger(tmp_path)
    start = Barrier(2)

    def reserve(attempt):
        start.wait(timeout=5)
        try:
            ledger.reserve(scope(attempt=attempt))
            return "committed"
        except (PendingBlocked, LedgerUnavailable):
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, ["a1", "a2"]))
    assert sorted(results) == ["blocked", "committed"]
    assert ledger.pending().attempt_id in ("a1", "a2")


@pytest.mark.parametrize("committed", [False, True])
def test_exit_at_commit_boundary_never_sends_and_restart_respects_commit(tmp_path, committed):
    path = tmp_path / "pending.sqlite3"
    new_ledger(tmp_path)
    code = '''
import os, sys, sqlite3
from pathlib import Path
from reference.sunny_transport.durable_pending import PendingLedger, PendingClaim
real_connect = sqlite3.connect
class Connection(sqlite3.Connection):
    def execute(self, sql, *args):
        if sql == "COMMIT":
            if sys.argv[2] == "True":
                super().execute(sql, *args)
            os._exit(23)
        return super().execute(sql, *args)
def connect(*args, **kwargs):
    return real_connect(*args, factory=Connection, **kwargs)
sqlite3.connect = connect
PendingLedger.open_existing(Path(sys.argv[1])).reserve(
    PendingClaim('i','e','o','op','a','say','a'*64))
Path(sys.argv[3]).write_text('fake send')
'''
    sent = tmp_path / "sent"
    child = subprocess.run([sys.executable, "-c", code, str(path), str(committed), str(sent)],
                           cwd=Path(__file__).resolve().parents[2], timeout=15)
    assert child.returncode == 23 and not sent.exists()
    reopened = PendingLedger.open_existing(path)
    assert (reopened.pending() is not None) == committed
    if committed:
        with pytest.raises(PendingBlocked):
            reopened.reserve(scope())
    else:
        reopened.reserve(scope())  # no committed reservation and no dispatch


def test_claim_callback_does_not_attest_tool_or_arguments(tmp_path):
    ledger = new_ledger(tmp_path)
    fake = FakeP2()
    client = GameTransport("http://127.0.0.1:18770", fake, credential="synthetic")
    client.initialize()
    client.call_tool("go_to_bed", {}, mutation=True, attempt_id="a1",
                     claim_dispatch=ledger.claim_for(scope(tool="say")))
    assert ledger.pending().tool == "say"
    assert json.loads(fake.calls[-1].body)["params"]["name"] == "go_to_bed"
    # This is an untrusted caller contract, never authenticated host evidence.


@pytest.mark.parametrize("damage", ["PRAGMA user_version=2", "ALTER TABLE pending_operation ADD COLUMN surprise TEXT"])
def test_schema_or_version_mismatch_stops_restart(tmp_path, damage):
    path = tmp_path / "pending.sqlite3"
    new_ledger(tmp_path)
    with sqlite3.connect(path) as con:
        con.execute(damage)
    with pytest.raises(LedgerUnavailable):
        PendingLedger.open_existing(path)


def test_failed_provision_leaves_quarantined_file(tmp_path, monkeypatch):
    path = tmp_path / "pending.sqlite3"
    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("synthetic setup failure")
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", unavailable)
        with pytest.raises(LedgerUnavailable):
            PendingLedger.initialize_new(path)
    assert path.exists()
    with pytest.raises(LedgerUnavailable):
        PendingLedger.open_existing(path)
    with pytest.raises(LedgerUnavailable):
        PendingLedger.initialize_new(path)


@pytest.mark.parametrize("after_commit", [False, True])
def test_commit_error_stops_fake_send_even_if_commit_succeeded(tmp_path, monkeypatch, after_commit):
    ledger = new_ledger(tmp_path)
    real_connect = sqlite3.connect
    class Connection(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql == "COMMIT":
                if after_commit:
                    super().execute(sql, *args)
                raise sqlite3.OperationalError("synthetic commit uncertainty")
            return super().execute(sql, *args)
    def connect(*args, **kwargs):
        return real_connect(*args, factory=Connection, **kwargs)
    fake = FakeP2()
    client = GameTransport("http://127.0.0.1:18770", fake, credential="synthetic")
    client.initialize()
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", connect)
        with pytest.raises(LedgerUnavailable):
            client.call_tool("say", {}, mutation=True, attempt_id="a1",
                             claim_dispatch=ledger.claim_for(scope()))
    assert len(fake.calls) == 1 and client.unresolved_mutation
    assert (ledger.pending() is not None) == after_commit
