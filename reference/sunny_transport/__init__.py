"""Offline-only, proposed Sunny P2 HTTP/MCP transport contract."""
from .adapter import (ClientError, ConnectionUnavailable, GameTransport, MutationOutcomeUnknown,
                      OwnershipOutcomeUnknown, ProtocolFailure, RequestRejected, SessionStale, TransportRequest,
                      TransportResponse)

__all__ = ["ClientError", "ConnectionUnavailable", "GameTransport", "MutationOutcomeUnknown",
           "OwnershipOutcomeUnknown", "ProtocolFailure", "RequestRejected", "SessionStale", "TransportRequest", "TransportResponse"]
