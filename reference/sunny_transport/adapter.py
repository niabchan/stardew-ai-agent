"""Offline Sunny transport **proposal**, not connected to Stardew or urllib.

The only I/O is the caller-supplied ``exchange`` callback. There is deliberately
no default exchange or real HTTP implementation; this module cannot reach a game
on its own. The server-side authenticated lease/epoch contract below does NOT
exist in the current mod. No production Sunny scripts import this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Mapping
from urllib.parse import urlsplit
from threading import Lock
from functools import wraps


class ClientError(Exception):
    """A classified transport/protocol failure; exception text must contain no secrets."""


class ProtocolFailure(ClientError):
    pass


class ConnectionUnavailable(ClientError):
    pass


class MutationOutcomeUnknown(ClientError):
    """Request may have run; the caller must reconcile instead of retrying."""


class OwnershipOutcomeUnknown(ClientError):
    """A lease may have been acquired or retained; do not repeat the handshake."""


class RequestRejected(ClientError):
    def __init__(self, status: int):
        super().__init__(f"Game request rejected (HTTP {status}); do not retry an action blindly")
        self.status = status


class SessionStale(RequestRejected):
    """Explicit stale/foreign session denial; requires a fresh owner decision."""


@dataclass(frozen=True)
class TransportRequest:
    method: str
    url: str
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False, default=b"")
    timeout_seconds: int = 12

    def __repr__(self) -> str:
        return (f"TransportRequest(method={self.method!r}, url={self.url!r}, "
                f"header_names={tuple(self.headers)!r}, body_bytes={len(self.body)}, "
                f"timeout_seconds={self.timeout_seconds})")


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False, default=b"")

    def __repr__(self) -> str:
        return f"TransportResponse(status={self.status}, header_names={tuple(self.headers)}, body_bytes={len(self.body)})"


Exchange = Callable[[TransportRequest], TransportResponse]
DispatchClaim = Callable[[str], None]


def _exclusive(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        if not self._busy.acquire(blocking=False):
            raise ProtocolFailure("Concurrent or reentrant adapter operation refused")
        try:
            return method(self, *args, **kwargs)
        finally:
            self._busy.release()
    return guarded


class GameTransport:
    """Strict fake-transport client for a proposed future authenticated server.

    P2 only; no implicit session acquisition, P1 control, endpoint fallback,
    transport retries or game networking. Caller supplies a non-network fake
    exchange and synthetic credential while running offline acceptance tests.
    """

    PROTOCOL = "2025-06-18"
    EPOCH_HEADER = "X-Sunny-Save-Epoch"  # PROPOSED, not supported by current mod
    SESSION_HEADER = "Mcp-Session-Id"
    MAX_BODY_BYTES = 16_384
    MAX_RESPONSE_BYTES = 262_144

    def __init__(self, base_url: str, exchange: Exchange, *, credential: str):
        if not isinstance(base_url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in base_url):
            raise ValueError("Invalid game origin")
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") \
                or parsed.username is not None or parsed.password is not None \
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise ValueError("Game URL must be an explicit loopback http origin with no path, query or credentials")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Invalid game port") from exc
        if port is None or port <= 0 or port > 65535:
            raise ValueError("Explicit valid game port required")
        if not isinstance(credential, str) or not credential.strip() or any(ord(c) <= 32 or ord(c) >= 127 for c in credential):
            raise ValueError("Separate nonblank game credential required (not the model API key)")
        self._busy = Lock()
        self._initialization_uncertain = False
        self._credential_denied = False
        self.base_url = base_url.rstrip("/")
        self._exchange = exchange
        self._credential = credential
        self._session: str | None = None
        self._epoch: str | None = None
        self._next_id = 0
        self._claimed: set[str] = set()  # in-memory defense only; durable claim belongs to caller
        self._unresolved_mutation = False  # fail closed after any ambiguous action

    @property
    def connected(self) -> bool:
        return self._session is not None and self._epoch is not None

    @property
    def epoch(self) -> str | None:
        return self._epoch

    @property
    def unresolved_mutation(self) -> bool:
        return self._unresolved_mutation

    @_exclusive
    def invalidate(self) -> None:
        self._invalidate()

    def _invalidate(self) -> None:
        self._session = None
        self._epoch = None

    @_exclusive
    def observe_authoritative_epoch(self, epoch: str) -> bool:
        """Caller must supply epoch from an authenticated server response.

        Returns True on change. Never use farm day/time or saveFolder as epoch.
        """
        if not isinstance(epoch, str) or not epoch.strip() or len(epoch) > 128:
            raise ValueError("Invalid authoritative load epoch")
        if self._epoch is not None and self._epoch != epoch:
            self._invalidate()
            return True
        return False

    def _make(self, method: str, path: str, *, body: bytes = b"", timeout: int = 12,
              session: bool = False) -> TransportRequest:
        if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1 or timeout > 1200:
            raise ValueError("Timeout must be 1..1200 seconds")
        if len(body) > self.MAX_BODY_BYTES:
            raise ValueError("Request body exceeds proposal limit")
        if self._credential_denied:
            raise ProtocolFailure("Credential denied; operator provisioning required")
        h = {"Authorization": "Bearer " + self._credential, "Accept": "application/json"}
        if method == "POST":
            h["Content-Type"] = "application/json"
        if session:
            if not self.connected:
                raise ProtocolFailure("P2 session not initialized")
            h[self.SESSION_HEADER] = self._session or ""
            h[self.EPOCH_HEADER] = self._epoch or ""  # proposed request precondition
        return TransportRequest(method, self.base_url + path, h, body, timeout)

    def _exchange_once(self, req: TransportRequest, *, mutating: bool) -> TransportResponse:
        try:
            res = self._exchange(req)
        except Exception:
            if mutating:
                raise MutationOutcomeUnknown("P2 action reply unknown; reconcile before any retry") from None
            raise ConnectionUnavailable("Game transport unavailable; read may be retried with bounds") from None
        if (not isinstance(res, TransportResponse) or type(res.status) is not int
                or not isinstance(res.headers, Mapping) or not isinstance(res.body, bytes)):
            if mutating:
                raise MutationOutcomeUnknown("Invalid callback response; outcome unknown")
            raise ProtocolFailure("Transport callback returned unexpected response type")
        if len(res.body) > self.MAX_RESPONSE_BYTES:
            if mutating:
                raise MutationOutcomeUnknown("P2 action response too large; outcome unknown")
            raise ProtocolFailure("Response exceeds proposal size limit")
        if mutating and not 200 <= res.status < 300:
            if res.status in (401, 403):
                self._credential_denied = True
            if res.status in (401, 403, 404, 409, 410):
                self._invalidate()
            # No agreed server proof of pre-dispatch rejection exists yet.
            raise MutationOutcomeUnknown(f"HTTP {res.status}; action outcome unknown")
        if res.status in (401, 403):
            self._credential_denied = True
            self._invalidate()
            raise RequestRejected(res.status)
        if res.status in (404, 409, 410):
            self._invalidate()
            raise SessionStale(res.status)
        if res.status == 429:
            raise RequestRejected(res.status)
        if not 200 <= res.status < 300:
            raise RequestRejected(res.status)
        return res

    def _check_epoch(self, res: TransportResponse, *, mutating: bool) -> str:
        epoch = self._header(res, self.EPOCH_HEADER)
        if not isinstance(epoch, str) or not epoch.strip() or len(epoch) > 128:
            if mutating:
                self._invalidate()
                raise MutationOutcomeUnknown("P2 action response lacks authoritative epoch")
            self._invalidate()
            raise ProtocolFailure("Authenticated server epoch header missing")
        if self._epoch is not None and epoch != self._epoch:
            self._invalidate()
            if mutating:
                raise MutationOutcomeUnknown("Save epoch changed during P2 action; reconcile")
            raise SessionStale(409)
        return epoch

    @staticmethod
    def _header(res: TransportResponse, name: str) -> str | None:
        values = [v for k, v in res.headers.items() if isinstance(k, str) and k.lower() == name.lower()]
        if len(values) != 1:
            return None
        value = values[0]
        if not isinstance(value, str) or not value or len(value) > 128 or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
            return None
        return value

    def _rpc(self, method: str, params: dict | None = None) -> tuple[int, bytes]:
        self._next_id += 1
        item: dict = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            item["params"] = params
        return self._next_id, json.dumps(item, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _strict_json(body: bytes):
        def object_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate JSON member")
                result[key] = value
            return result
        def constant(_):
            raise ValueError("Nonfinite JSON value")
        return json.loads(body, object_pairs_hook=object_pairs, parse_constant=constant)

    @staticmethod
    def _decode_rpc(res: TransportResponse, expected_id: int) -> dict:
        try:
            data = GameTransport._strict_json(res.body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProtocolFailure("Invalid JSON-RPC response") from exc
        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0" or type(data.get("id")) is not int or data.get("id") != expected_id:
            raise ProtocolFailure("Unexpected JSON-RPC envelope/id")
        if "error" in data:
            raise ProtocolFailure("JSON-RPC protocol error (no automatic action retry)")
        if not isinstance(data.get("result"), dict):
            raise ProtocolFailure("JSON-RPC result missing")
        return data["result"]

    @_exclusive
    def initialize(self) -> None:
        if self._initialization_uncertain:
            raise ProtocolFailure("Initialization outcome unresolved; operator lease reconciliation required")
        if self.connected:
            raise ProtocolFailure("An existing P2 owner session must be explicitly retired")
        rid, body = self._rpc("initialize", {"protocolVersion": self.PROTOCOL,
                                            "capabilities": {},
                                            "clientInfo": {"name": "sunny-offline-adapter", "version": "0.1"}})
        req = self._make("POST", "/mcp/p2", body=body)
        self._initialization_uncertain = True
        try:
            res = self._exchange_once(req, mutating=False)
        except ConnectionUnavailable:
            raise OwnershipOutcomeUnknown("Initialize reply lost; lease reconciliation required") from None
        epoch = self._check_epoch(res, mutating=False)
        session = self._header(res, self.SESSION_HEADER)
        result = self._decode_rpc(res, rid)
        if not isinstance(session, str) or not session or session == "stardew-p2" \
                or result.get("protocolVersion") != self.PROTOCOL:
            raise ProtocolFailure("Server lacks required authenticated session/version contract")
        self._session, self._epoch = session, epoch
        self._initialization_uncertain = False

    @_exclusive
    def call_tool(self, name: str, arguments: dict, *, mutation: bool,
                  attempt_id: str | None = None, claim_dispatch: DispatchClaim | None = None,
                  timeout_seconds: int = 95) -> dict:
        if not self.connected:
            raise ProtocolFailure("P2 session required before tools/call")
        if not isinstance(name, str) or not name or not isinstance(arguments, dict):
            raise ValueError("Tool name and arguments required")
        if type(mutation) is not bool:
            raise ValueError("Explicit boolean mutation classification required")
        if not mutation and (name != "status" or arguments):
            raise ValueError("Only empty-argument status is approved as a read in this prototype")
        if mutation:
            if self._unresolved_mutation:
                raise ProtocolFailure("Prior P2 mutation is unresolved; reconcile externally before another action")
            if not isinstance(attempt_id, str) or not attempt_id.strip() or not callable(claim_dispatch):
                raise ValueError("Mutations require a durable caller-provided dispatch claim")
            if attempt_id in self._claimed:
                raise ProtocolFailure("Mutation attempt already dispatched; do not resend")
        rid, body = self._rpc("tools/call", {"name": name, "arguments": arguments})
        req = self._make("POST", "/mcp/p2", body=body, timeout=timeout_seconds, session=True)
        if mutation:
            # Caller must persist and reject duplicates across process restarts.
            self._claimed.add(attempt_id)
            # Reserve before callback: it may persist then raise, or reenter.
            self._unresolved_mutation = True
            claim_dispatch(attempt_id)
        try:
            res = self._exchange_once(req, mutating=mutation)
            self._check_epoch(res, mutating=mutation)
            try:
                result = self._decode_rpc(res, rid)
                if mutation:
                    if type(result.get("isError")) is not bool or result["isError"]:
                        raise MutationOutcomeUnknown("Tool error or incomplete acknowledgment; effect unknown")
                    self._unresolved_mutation = False
                return result
            except ProtocolFailure as exc:
                if mutation:
                    raise MutationOutcomeUnknown("P2 action response invalid; outcome unknown") from exc
                raise
        except MutationOutcomeUnknown:
            self._unresolved_mutation = True
            raise
        except Exception:
            if mutation:
                raise MutationOutcomeUnknown("Dispatch callback failed; outcome unknown") from None
            raise

    @_exclusive
    def read_safety(self, *, timeout_seconds: int = 12) -> dict:
        """PROPOSED /api/companion/v1/p2/safety, not available in current mod.

        The server must filter P1-private fields *before* writing bytes; merely
        client-side filtering this JSON would not be an access control boundary.
        """
        if not self.connected:
            raise ProtocolFailure("P2 session required before companion observation")
        res = self._exchange_once(self._make("GET", "/api/companion/v1/p2/safety",
                                             timeout=timeout_seconds, session=True), mutating=False)
        self._check_epoch(res, mutating=False)
        try:
            value = self._strict_json(res.body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProtocolFailure("Invalid safety projection JSON") from exc
        if not isinstance(value, dict) or value.get("epoch") != self._epoch:
            raise ProtocolFailure("Safety projection has no matching save epoch")
        permitted = {"epoch", "p1Consent", "ready", "p1Human", "p1Active", "p2Ai", "p2Active", "guyNearby", "giverWaiting", "day", "time"}
        if not set(value).issubset(permitted):
            raise ProtocolFailure("Safety projection contains unexpected fields")
        if type(value.get("p1Consent")) is not bool:
            raise ProtocolFailure("Explicit P1 projection consent required")
        if not value["p1Consent"] and set(value) != {"epoch", "p1Consent"}:
            raise ProtocolFailure("P1 projection disclosed without consent")
        for key in set(value) - {"epoch", "day", "time"}:
            if type(value[key]) is not bool:
                raise ProtocolFailure("Safety flags must be booleans")
        for key in ("day", "time"):
            if key in value and (type(value[key]) is not int or value[key] < 0):
                raise ProtocolFailure("Invalid safety clock")
        if value["p1Consent"]:
            required = {"ready", "p1Human", "p1Active", "p2Ai", "p2Active", "guyNearby", "giverWaiting"}
            if not required.issubset(value):
                raise ProtocolFailure("Incomplete safety projection; do not act")
        return value

    @_exclusive
    def release(self) -> None:
        """Attempt DELETE once, then retain ownership uncertainty.

        No approved authenticated owner/session/epoch-bound retirement protocol
        exists yet. Neither HTTP success nor a claimed quiescence body proves
        retirement. Recovery requires an independently reviewed server-side flow;
        this object cannot authorize another lease after attempting DELETE.
        """
        if not self.connected:
            return
        req = self._make("DELETE", "/mcp/p2", session=True)
        self._initialization_uncertain = True
        try:
            self._exchange_once(req, mutating=False)
            raise OwnershipOutcomeUnknown(
                "Retirement unverified; lease reconciliation required")
        except ConnectionUnavailable:
            raise OwnershipOutcomeUnknown("Release reply lost; lease reconciliation required") from None
        finally:
            # Disconnect is not proof that server cleared an in-flight action.
            self._invalidate()
