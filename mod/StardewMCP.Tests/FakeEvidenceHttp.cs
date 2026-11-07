using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using StardewMCP.Agent;

namespace StardewMCP.Tests;

// Executable transport design fixture ONLY. No listener, production credentials or live route.
internal sealed record FakeEvidenceRequest(string Method = "GET", string Host = "localhost:8770",
    bool LoopbackPeer = true, string? Origin = null, string? Authorization = "Bearer fixture-secret",
    string Query = "seat=p2&fields=metadata", string Path = "/api/evidence",
    string? ForwardedHost = null);
internal sealed record FakeEvidenceReply(int Status, string Body)
{
    public IReadOnlyDictionary<string, string> Headers { get; } = new ReadOnlyDictionary<string, string>(
        new Dictionary<string, string> { ["Cache-Control"] = "no-store", ["Content-Type"] = "application/json",
            ["X-Content-Type-Options"] = "nosniff" });
}
internal sealed record FakeEvidenceGrant(bool Enabled = true, string Secret = "fixture-secret",
    string Seat = "p2", bool Metadata = true, bool Raw = false, long ExpiresAt = 100);

internal sealed class FakeEvidenceHttp
{
    private readonly object _gate = new();
    private readonly Func<string, EvidenceRead> _read;
    private readonly Action _clear;
    private FakeEvidenceGrant _grant = new();
    private int _requests;
    public FakeEvidenceHttp(Func<string, EvidenceRead> read, Action clear) => (_read, _clear) = (read, clear);
    public void ReplaceGrant(FakeEvidenceGrant grant)
    {
        lock (_gate) { _clear(); _grant = grant; _requests = 0; }
    }
    public FakeEvidenceReply Handle(FakeEvidenceRequest r, long now = 10)
    {
        lock (_gate)
        {
            FakeEvidenceReply Reply(int status, string message) => new(status, JsonSerializer.Serialize(new { status = message }));
            // Bounded synthetic budget; a real server still needs connection/header/time limits.
            if (++_requests > 64) return Reply(429, "limited");
            if (r.Host.Length > 128 || (r.Authorization?.Length ?? 0) > 256 || r.Query.Length > 128
                || (r.Origin?.Length ?? 0) > 256) return Reply(400, "invalid_request");
            if (!r.LoopbackPeer || r.Host != "localhost:8770" && r.Host != "127.0.0.1:8770")
                return Reply(403, "forbidden");
            // Native readers only. Forwarded headers never substitute for authority/peer checks.
            if (r.Origin != null) return Reply(403, "forbidden");
            if (r.Method != "GET") return Reply(405, "method_not_allowed");
            if (r.Path == "/api/evidence/capabilities")
                return Reply(200, "diagnostic_schema_v1_auth_required_transport_not_implemented");
            if (r.Path != "/api/evidence") return Reply(404, "not_found");
            if (!_grant.Enabled) return Reply(200, "disabled");
            var expected = SHA256.HashData(Encoding.UTF8.GetBytes("Bearer " + _grant.Secret));
            var supplied = SHA256.HashData(Encoding.UTF8.GetBytes(r.Authorization ?? ""));
            if (string.IsNullOrEmpty(_grant.Secret) || now >= _grant.ExpiresAt
                || !CryptographicOperations.FixedTimeEquals(expected, supplied)) return Reply(401, "unauthorized");
            // Exact grammar prevents missing/duplicate/ambiguous/default-seat and scope expansion.
            string? seat = r.Query.StartsWith("seat=p1&", StringComparison.Ordinal) ? "p1"
                : r.Query.StartsWith("seat=p2&", StringComparison.Ordinal) ? "p2" : null;
            string fields = r.Query.EndsWith("&fields=raw", StringComparison.Ordinal) ? "raw" : "metadata";
            if (seat == null || r.Query != $"seat={seat}&fields={fields}") return Reply(400, "invalid_request");
            if (seat != _grant.Seat || fields == "metadata" && !_grant.Metadata || fields == "raw" && !_grant.Raw)
                return Reply(403, "forbidden");
            var read = _read(seat);
            var c = read.Capture;
            if (read.Status != "captured" || c == null) return Reply(200, "unavailable");
            // Fail closed on mixed/wrong seat cache entries; never serialize the entire capture.
            if (c.Scope.Seat != seat || c.Scope.Screen != (seat == "p1" ? 0 : 1)) return Reply(200, "unavailable");
            object? raw = fields == "raw" ? new { question = c.Prompt?.Question, responses = c.Prompt?.Responses } : null;
            return new FakeEvidenceReply(200, JsonSerializer.Serialize(new {
                status = "captured", sequence = c.Sequence, captured_utc = c.CapturedUtc,
                monotonic_ticks = c.MonotonicTicks, age_seconds = read.AgeSeconds,
                complete = c.Complete, raw_status = fields == "raw" ? "disclosed" : "redacted",
                raw, guarded_dispatch = false, gift_classification = false,
                transfer_verification = false, checkpoint_reconciliation = false
            }));
        }
    }
}
