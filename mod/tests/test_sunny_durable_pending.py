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
