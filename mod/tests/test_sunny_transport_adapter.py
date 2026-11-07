"""Game-free acceptance tests for a FUTURE authenticated P2 wire contract."""
import json
import pytest

from reference.sunny_transport import (ConnectionUnavailable, GameTransport, MutationOutcomeUnknown,
                                       OwnershipOutcomeUnknown, ProtocolFailure, RequestRejected, SessionStale, TransportResponse)


class FakeExchange:
    def __init__(self):
        self.requests = []
        self.epoch = "load-1"
        self.session = "opaque-fake-owner-1"
        self.status_override = None
        self.raise_error = None
        self.bad_epoch = False
        self.missing_session = False
        self.response_invalid = False
        self.closed = False

    def __call__(self, request):
        self.requests.append(request)
        if self.raise_error:
            raise self.raise_error
        if self.status_override:
            return TransportResponse(self.status_override, {}, b"")
        headers = {"X-Sunny-Save-Epoch": "load-2" if self.bad_epoch else self.epoch}
        if request.method == "DELETE":
            self.closed = True
            return TransportResponse(200, headers)
        if request.method == "GET":
            return TransportResponse(200, headers, json.dumps({"epoch": headers["X-Sunny-Save-Epoch"],
                           "p1Consent": True, "ready": True, "p1Human": True, "p1Active": True,
                           "p2Ai": True, "p2Active": True, "guyNearby": True, "giverWaiting": False}).encode())
        body = json.loads(request.body)
        result = {"protocolVersion": GameTransport.PROTOCOL} if body["method"] == "initialize" else {
            "content": [{"type": "text", "text": "P2 available"}], "isError": False}
        if body["method"] == "initialize" and not self.missing_session:
            headers["Mcp-Session-Id"] = self.session
        response = {"jsonrpc": "2.0", "id": body["id"], "result": result}
        return TransportResponse(200, headers, b"broken" if self.response_invalid else json.dumps(response).encode())


def client(**kw):
    fake = FakeExchange()
    return GameTransport("http://127.0.0.1:18770", fake, credential="synthetic-game-grant"), fake


@pytest.mark.parametrize("base", ["https://127.0.0.1:8770", "http://example.com:8770", "http://localhost",
                                 "http://localhost:8770/mcp", "http://user:password@localhost:8770",
                                 "http://localhost:8770?token=X", "http://localhost:8770#fragment",
                                 "http://127.0.0.1:99999", "http://127.0.0.2:8770"])
def test_reject_unsafe_game_url(base):
    with pytest.raises(ValueError):
        GameTransport(base, FakeExchange(), credential="synthetic")


@pytest.mark.parametrize("base", ["http://localhost:8770", "http://127.0.0.1:18770", "http://[::1]:8770"])
def test_explicit_loopback_port(base):
    fake = FakeExchange()
    transport = GameTransport(base, fake, credential="synthetic")
    transport.initialize()
    assert fake.requests[0].url == base + "/mcp/p2"
    assert all(r.url.startswith(base + "/") for r in fake.requests)


def test_handshake_is_required_and_no_network_by_constructor():
    t, fake = client()
    assert fake.requests == []
    with pytest.raises(ProtocolFailure):
        t.call_tool("status", {}, mutation=False)
    t.initialize()
    assert t.connected and t.epoch == "load-1"
    assert len(fake.requests) == 1
    req = fake.requests[0]
    assert req.method == "POST"
    assert req.headers["Authorization"] == "Bearer synthetic-game-grant"
    assert "Mcp-Session-Id" not in req.headers
    assert "synthetic-game-grant" not in repr(req)
    with pytest.raises(ProtocolFailure):
        t.initialize()  # no unreviewed takeover


def test_tool_session_and_correlated_json_without_assuming_unique_operation_id():
    t, fake = client()
    t.initialize()
    a = t.call_tool("status", {}, mutation=False)
    b = t.call_tool("status", {}, mutation=False)
    assert a["isError"] is False and b["isError"] is False
    assert len(fake.requests) == 3
    assert all(r.headers.get("Mcp-Session-Id") == fake.session for r in fake.requests[1:])
    ids = [json.loads(x.body)["id"] for x in fake.requests]
    assert ids == [1, 2, 3]  # correlation only


def test_mutations_claim_before_send_and_never_repeat_attempt_id():
    t, fake = client()
    t.initialize()
    before = len(fake.requests)
    with pytest.raises(ValueError):
        t.call_tool("respond", {"option": 0}, mutation=True)
    assert len(fake.requests) == before
    seen = []
    def claim(x):
        assert len(fake.requests) == before
        seen.append(x)
    result = t.call_tool("respond", {"option": 0}, mutation=True,
                         attempt_id="offer-1", claim_dispatch=claim)
    assert result["isError"] is False and seen == ["offer-1"]
    with pytest.raises(ProtocolFailure):
        t.call_tool("respond", {"option": 0}, mutation=True,
                    attempt_id="offer-1", claim_dispatch=claim)
    assert len(fake.requests) == before + 1


def test_claim_failure_sends_nothing():
    t, fake = client()
    t.initialize()
    def fail(_):
        raise OSError("journal refused to commit")
    with pytest.raises(OSError):
        t.call_tool("go_to_bed", {}, mutation=True, attempt_id="bed-1", claim_dispatch=fail)
    assert len(fake.requests) == 1


def test_mutation_timeout_unknown_and_not_retried():
    t, fake = client()
    t.initialize()
    fake.raise_error = TimeoutError("fake timeout")
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("go_to_bed", {}, mutation=True,
                    attempt_id="bed-1", claim_dispatch=lambda _: None, timeout_seconds=1200)
    assert len(fake.requests) == 2
    assert t.unresolved_mutation
    with pytest.raises(ProtocolFailure):
        t.call_tool("go_to_bed", {}, mutation=True,
                    attempt_id="bed-1", claim_dispatch=lambda _: None)
    assert len(fake.requests) == 2


def test_read_transport_error_can_be_retried_only_by_caller():
    t, fake = client()
    t.initialize()
    fake.raise_error = TimeoutError("fake timeout")
    with pytest.raises(ConnectionUnavailable):
        t.call_tool("status", {}, mutation=False)
    assert len(fake.requests) == 2  # no internal retries


@pytest.mark.parametrize("status,cls", [(401,RequestRejected),(403,RequestRejected),(409,SessionStale),
                                          (429,RequestRejected),(503,RequestRejected)])
def test_error_classification_without_implicit_retry(status, cls):
    t, fake = client()
    t.initialize()
    fake.status_override = status
    with pytest.raises(cls) as e:
        t.call_tool("status", {}, mutation=False)
    assert e.value.status == status
    assert len(fake.requests) == 2
    if status in (401,403,409):
        assert not t.connected


def test_epoch_change_fences_later_requests():
    t, fake = client()
    t.initialize()
    assert t.observe_authoritative_epoch("load-2") is True
    with pytest.raises(ProtocolFailure):
        t.call_tool("status", {}, mutation=False)
    assert len(fake.requests) == 1
    fake.epoch = "load-2"
    t.initialize()
    assert t.epoch == "load-2"


def test_epoch_change_during_mutation_is_unknown_not_safe_to_retry():
    t, fake = client()
    t.initialize()
    fake.bad_epoch = True
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("respond", {"option": 1}, mutation=True,
                    attempt_id="offer-9", claim_dispatch=lambda _: None)
    assert not t.connected
    assert len(fake.requests) == 2


def test_proposed_safe_p1_projection_no_private_fields():
    t, fake = client()
    t.initialize()
    x = t.read_safety()
    assert x["p1Human"] is True and x["giverWaiting"] is False
    assert fake.requests[-1].url == "http://127.0.0.1:18770/api/companion/v1/p2/safety"
    assert fake.requests[-1].method == "GET"


def test_release_does_not_assume_inflight_termination():
    t, fake = client()
    t.initialize()
    with pytest.raises(OwnershipOutcomeUnknown):
        t.release()
    assert fake.closed and not t.connected
    assert fake.requests[-1].method == "DELETE"
    with pytest.raises(ProtocolFailure):
        t.call_tool("status", {}, mutation=False)


def test_legacy_server_missing_epoch_and_session_is_rejected():
    t, fake = client()
    fake.missing_session = True
    with pytest.raises(ProtocolFailure):
        t.initialize()
    assert not t.connected


def test_invalid_response_is_not_retried_after_mutation():
    t, fake = client()
    t.initialize()
    fake.response_invalid = True
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("say", {"text": "Hi"}, mutation=True,
                    attempt_id="chat-1", claim_dispatch=lambda _: None)
    assert len(fake.requests) == 2


def test_unknown_outcome_blocks_different_mutation_but_allows_read_only_reconciliation():
    t, fake = client()
    t.initialize()
    fake.raise_error = TimeoutError("synthetic delay")
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("respond", {"option": 0}, mutation=True,
                    attempt_id="gift-1", claim_dispatch=lambda _: None)
    fake.raise_error = None
    assert t.call_tool("status", {}, mutation=False)["isError"] is False
    with pytest.raises(ProtocolFailure):
        t.call_tool("go_to_bed", {}, mutation=True,
                    attempt_id="bed-2", claim_dispatch=lambda _: None)
    assert len(fake.requests) == 3


def test_server_503_for_mutation_is_not_claimed_to_be_no_effect():
    t, fake = client()
    t.initialize()
    fake.status_override = 503
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("say", {"text": "Hi"}, mutation=True,
                    attempt_id="say-1", claim_dispatch=lambda _: None)
    assert t.unresolved_mutation


def test_missing_epoch_on_mutation_invalidates_session_and_marks_unknown():
    t, fake = client()
    t.initialize()
    fake.epoch = ""  # intentionally invalid future-server response
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("respond", {"option": 1}, mutation=True,
                    attempt_id="gift-3", claim_dispatch=lambda _: None)
    assert not t.connected and t.unresolved_mutation


def test_safety_projection_never_sends_legacy_host_data_fields_to_client_api():
    t, fake = client()
    t.initialize()
    t.read_safety()
    assert all("/api/state" not in request.url and "/api/feed" not in request.url
               for request in fake.requests)

@pytest.mark.parametrize("failure", [TimeoutError("synthetic"), RuntimeError("synthetic")])
def test_lost_initialize_cannot_acquire_another_lease(failure):
    t, fake = client()
    fake.raise_error = failure
    with pytest.raises(Exception):
        t.initialize()
    fake.raise_error = None
    t.invalidate()
    with pytest.raises(ProtocolFailure):
        t.initialize()
    assert len(fake.requests) == 1


@pytest.mark.parametrize("name", ["respond", "go_to_bed", "say", "unknown", "look"])
def test_effects_cannot_bypass_claim_by_calling_them_reads(name):
    t, fake = client()
    t.initialize()
    with pytest.raises(ValueError):
        t.call_tool(name, {}, mutation=False)
    assert len(fake.requests) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 409, 410, 429, 503, 500, 302])
def test_every_unproven_mutation_denial_preserves_unknown(status):
    t, fake = client()
    t.initialize()
    fake.status_override = status
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=lambda _: None)
    assert t.unresolved_mutation
    fake.status_override = None
    with pytest.raises(ProtocolFailure):
        t.call_tool("say", {}, mutation=True, attempt_id="two", claim_dispatch=lambda _: None)
    assert len(fake.requests) == 2


@pytest.mark.parametrize("status", [401, 403])
def test_revoked_credential_stops_reads_and_reinitialization(status):
    t, fake = client()
    t.initialize()
    fake.status_override = status
    with pytest.raises(RequestRejected):
        t.read_safety()
    fake.status_override = None
    with pytest.raises(ProtocolFailure):
        t.initialize()
    assert len(fake.requests) == 2


def test_nonatomic_claim_failure_is_reserved_and_cannot_be_retried():
    t, fake = client()
    t.initialize()
    journal = set()
    def persist_then_fail(attempt):
        journal.add(attempt)
        raise OSError("commit acknowledgment lost")
    with pytest.raises(OSError):
        t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=persist_then_fail)
    assert journal == {"one"} and t.unresolved_mutation
    with pytest.raises(ProtocolFailure):
        t.call_tool("say", {}, mutation=True, attempt_id="two", claim_dispatch=lambda _: None)
    assert len(fake.requests) == 1


def test_restart_requires_journal_to_reject_previously_claimed_attempt():
    durable = set()
    def claim(attempt):
        if attempt in durable:
            raise ValueError("duplicate")
        durable.add(attempt)
    for index in range(2):
        t, fake = client()
        t.initialize()
        if index == 0:
            t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=claim)
        else:
            with pytest.raises(ValueError):
                t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=claim)
            assert len(fake.requests) == 1


@pytest.mark.parametrize("bad", [None, TransportResponse(200, {}, b""),
                                   TransportResponse(200, {}, "bad"),
                                   TransportResponse(True, {}, b""), RuntimeError("synthetic")])
def test_invalid_callback_after_dispatch_is_unknown(bad):
    t, fake = client()
    t.initialize()
    def invalid(request):
        fake.requests.append(request)
        if isinstance(bad, Exception):
            raise bad
        return bad
    t._exchange = invalid
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=lambda _: None)
    assert t.unresolved_mutation and len(fake.requests) == 2


def test_claim_callback_cannot_reenter_adapter():
    t, fake = client()
    t.initialize()
    def claim(_):
        with pytest.raises(ProtocolFailure):
            t.call_tool("say", {}, mutation=True, attempt_id="nested", claim_dispatch=lambda _: None)
        with pytest.raises(ProtocolFailure):
            t.release()
    t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=claim)
    assert len(fake.requests) == 2


@pytest.mark.parametrize("projection", [
    {"epoch": "load-1"},
    {"epoch": "load-1", "p1Consent": False, "giverWaiting": True},
    {"epoch": "load-1", "p1Consent": "yes"},
    {"epoch": "load-1", "p1Consent": True},
    {"epoch": "load-1", "p1Consent": False, "privateDialogue": "canary"},
])
def test_invalid_or_unconsented_safety_is_unusable(projection):
    t, fake = client()
    t.initialize()
    t._exchange = lambda _: TransportResponse(200, {"X-Sunny-Save-Epoch": "load-1"}, json.dumps(projection).encode())
    with pytest.raises(ProtocolFailure):
        t.read_safety()


def test_consent_denied_projection_is_minimal():
    t, fake = client()
    t.initialize()
    projection = {"epoch": "load-1", "p1Consent": False}
    t._exchange = lambda _: TransportResponse(200, {"x-sunny-save-epoch": "load-1"}, json.dumps(projection).encode())
    assert t.read_safety() == projection


@pytest.mark.parametrize("timeout", [0, 1201, True])
def test_invalid_timeout_never_claims_or_sends(timeout):
    t, fake = client()
    t.initialize()
    claimed = []
    with pytest.raises(ValueError):
        t.call_tool("go_to_bed", {}, mutation=True, attempt_id="bed", claim_dispatch=claimed.append,
                    timeout_seconds=timeout)
    assert not claimed and len(fake.requests) == 1


def test_bedtime_1200_wait_is_forwarded_once_and_release_does_not_clear_unknown():
    t, fake = client()
    t.initialize()
    fake.raise_error = TimeoutError("synthetic")
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("go_to_bed", {}, mutation=True, attempt_id="bed", claim_dispatch=lambda _: None,
                    timeout_seconds=1200)
    assert fake.requests[-1].timeout_seconds == 1200
    fake.raise_error = None
    with pytest.raises(OwnershipOutcomeUnknown):
        t.release()
    with pytest.raises(ProtocolFailure):
        t.initialize()
    assert t.unresolved_mutation
    with pytest.raises(ProtocolFailure):
        t.call_tool("go_to_bed", {}, mutation=True, attempt_id="bed-new", claim_dispatch=lambda _: None)


@pytest.mark.parametrize("credential", [" ", "bad\tgrant", "bad\ngrant", "é"])
def test_credential_header_is_nonblank_ascii_token(credential):
    with pytest.raises(ValueError):
        GameTransport("http://127.0.0.1:8770", FakeExchange(), credential=credential)

@pytest.mark.parametrize("body", [
    b'{"jsonrpc":"2.0","id":2,"result":{},"result":{"isError":false}}',
    b'{"jsonrpc":"2.0","id":2,"result":{"isError":true}}',
    b'{"jsonrpc":"2.0","id":2,"result":{}}',
    b'{"jsonrpc":"2.0","id":2,"result":{"isError":false,"x":NaN}}',
])
def test_ambiguous_rpc_and_tool_errors_preserve_unknown(body):
    t, fake = client()
    t.initialize()
    t._exchange = lambda _: TransportResponse(200, {"X-Sunny-Save-Epoch": "load-1"}, body)
    with pytest.raises(MutationOutcomeUnknown):
        t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=lambda _: None)
    assert t.unresolved_mutation


def test_lost_release_reply_cannot_blindly_initialize_again():
    t, fake = client()
    t.initialize()
    fake.raise_error = TimeoutError("synthetic")
    with pytest.raises(OwnershipOutcomeUnknown):
        t.release()
    fake.raise_error = None
    with pytest.raises(ProtocolFailure):
        t.initialize()
    assert not t.connected and len(fake.requests) == 2


def test_header_names_are_case_insensitive():
    fake = FakeExchange()
    def lowercase(req):
        res = fake(req)
        return TransportResponse(res.status, {k.lower(): v for k, v in res.headers.items()}, res.body)
    t = GameTransport("http://127.0.0.1:8770", lowercase, credential="synthetic")
    t.initialize()
    assert t.connected


def test_wrong_instance_epoch_does_not_fall_back_to_other_port():
    t, fake = client()
    t.initialize()
    fake.epoch = "another-instance"
    with pytest.raises(SessionStale):
        t.call_tool("status", {}, mutation=False)
    assert not t.connected
    assert all(r.url.startswith("http://127.0.0.1:18770/") for r in fake.requests)


def test_lost_initialize_has_ownership_specific_classification():
    t, fake = client()
    fake.raise_error = TimeoutError("synthetic")
    with pytest.raises(OwnershipOutcomeUnknown):
        t.initialize()


def test_duplicate_case_variant_session_is_rejected_and_fences_handshake():
    fake = FakeExchange()
    def duplicate(req):
        res = fake(req)
        headers = dict(res.headers)
        headers["mcp-session-id"] = "other-owner"
        return TransportResponse(res.status, headers, res.body)
    t = GameTransport("http://127.0.0.1:8770", duplicate, credential="synthetic")
    with pytest.raises(ProtocolFailure):
        t.initialize()
    with pytest.raises(ProtocolFailure):
        t.initialize()
    assert len(fake.requests) == 1


def test_mutation_carries_proposed_epoch_precondition():
    t, fake = client()
    t.initialize()
    t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=lambda _: None)
    assert fake.requests[-1].headers[GameTransport.EPOCH_HEADER] == "load-1"


def test_safety_flags_cannot_be_truthy_strings():
    t, fake = client()
    t.initialize()
    res = fake(t._make("GET", "/api/companion/v1/p2/safety", session=True))
    data = json.loads(res.body)
    data["giverWaiting"] = "false"
    t._exchange = lambda _: TransportResponse(200, res.headers, json.dumps(data).encode())
    with pytest.raises(ProtocolFailure):
        t.read_safety()


# Candidate acknowledgment fields below are deliberately NOT an approved wire
# protocol. Even a matching, quiescent-looking body must remain unverified.
@pytest.mark.parametrize("response", [
    TransportResponse(200, {}),  # legacy no-op DELETE
    TransportResponse(202, {}),
    TransportResponse(204, {}),
    TransportResponse(200, {"X-Sunny-Save-Epoch": "load-1"}),
    TransportResponse(200, {}, b"broken"),
    TransportResponse(200, {}, b'{"retired":true,"retired":false}'),
    None,  # malformed exchange result
    TransportResponse(200, {}, "not bytes"),
    TransportResponse(503, {}),
    TimeoutError("DELETE reply lost"),
    *[TransportResponse(200, {"X-Sunny-Save-Epoch": epoch,
                             "Mcp-Session-Id": session},
                        json.dumps({"owner": owner, "session": session,
                                    "epoch": epoch, "state": state}).encode())
      for owner, session, epoch, state in [
          ("synthetic-owner", "opaque-fake-owner-1", "load-2", "retired-and-quiescent"),
          ("synthetic-owner", "other-session", "load-1", "retired-and-quiescent"),
          ("other-owner", "opaque-fake-owner-1", "load-1", "retired-and-quiescent"),
          ("synthetic-owner", "opaque-fake-owner-1", "load-1", "unknown"),
          ("synthetic-owner", "opaque-fake-owner-1", "load-1", "cleanup-required"),
          ("synthetic-owner", "opaque-fake-owner-1", "load-1", "retired-and-quiescent"),
      ]],
])
@pytest.mark.parametrize("pending_mutation", [False, True])
def test_unverified_retirement_never_authorizes_lease_or_action(response, pending_mutation):
    t, fake = client()
    t.initialize()
    claims = []
    if pending_mutation:
        fake.raise_error = TimeoutError("action reply lost")
        with pytest.raises(MutationOutcomeUnknown):
            t.call_tool("say", {}, mutation=True, attempt_id="one", claim_dispatch=claims.append)
        fake.raise_error = None
    before = len(fake.requests)

    def retirement(request):
        fake.requests.append(request)
        if isinstance(response, Exception):
            raise response
        return response

    t._exchange = retirement
    with pytest.raises((OwnershipOutcomeUnknown, ProtocolFailure, RequestRejected)):
        t.release()
    assert len(fake.requests) == before + 1
    request = fake.requests[-1]
    assert request.method == "DELETE"
    assert request.headers[GameTransport.SESSION_HEADER] == fake.session
    assert request.headers[GameTransport.EPOCH_HEADER] == fake.epoch
    assert not t.connected
    assert t.unresolved_mutation is pending_mutation
    assert t._claimed == ({"one"} if pending_mutation else set())
    t.invalidate()
    t.observe_authoritative_epoch("load-2")
    t.release()  # disconnected cleanup is a no-op, not evidence of retirement
    with pytest.raises(ProtocolFailure):
        t.initialize()
    for attempt in ("one", "new"):
        with pytest.raises(ProtocolFailure):
            t.call_tool("say", {}, mutation=True, attempt_id=attempt, claim_dispatch=claims.append)
    assert claims == (["one"] if pending_mutation else [])
    assert len(fake.requests) == before + 1  # no second handshake/DELETE/action
