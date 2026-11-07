using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Text;
using System.Text.Json;

namespace StardewMCP.Tests;

// Design fixture ONLY: deliberately not linked into the mod or wired to AgentHttp/McpDispatcher.
// Credentials and session IDs are synthetic labels, not a provisioning/entropy implementation.
internal sealed record BoundaryRequest(string Method = "POST", string Path = "/mcp/p2",
    string Host = "localhost:8770", string Peer = "127.0.0.1", string? Origin = null,
    string? Credential = "p2-a", string? Session = null, string Query = "",
    string ContentType = "application/json", string Body = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\"}",
    bool DuplicateHeaders = false, int ReadMilliseconds = 0, bool Disconnected = false);
internal sealed record BoundaryGrant(string Seat = "p2", string Scope = "mcp", long ExpiresAt = 100,
    bool Revoked = false);
internal sealed record BoundaryReply(int Status, string Body = "", string? Session = null)
{
    public IReadOnlyDictionary<string, string> Headers { get; } = new Dictionary<string, string> {
        ["Cache-Control"] = "no-store", ["Content-Type"] = "application/json"
    };
}

internal sealed class FakeSecurityBoundary
{
    internal const int MaxBodyBytes = 512, MaxBatch = 4, MaxQueue = 2, MaxConnections = 2,
        MaxRequests = 16, MaxReadMilliseconds = 100;
    internal readonly Dictionary<string, BoundaryGrant> Grants = new() {
        ["p2-a"] = new(), ["p2-b"] = new(), ["operator"] = new(Scope: "operator"),
        ["reader"] = new(Scope: "logs"), ["diagnostic"] = new(Scope: "diagnostic")
    };
    private sealed record SessionOwner(string Credential, string Seat, int Epoch);
    private sealed record Work(string Credential, string Session, int Epoch);
    private readonly Dictionary<string, SessionOwner> _sessions = new();
    private readonly Queue<Work> _queue = new();
    private int _sequence, _requests;
    internal int Epoch { get; private set; } = 1;
    internal string P1Role { get; } = "human";
    internal string P2Role { get; set; } = "ai";
    internal bool P2Active { get; set; } = true;
    internal bool ClockReleased { get; } = true;
    internal bool TimedOut { get; } = true;
    internal int Connections { get; set; }
    internal int Contacts { get; private set; }
    internal int ToolCalls { get; private set; }
    internal int StateReads { get; private set; }
    internal int SessionBreaks { get; private set; }
    internal int ReplyDeadlineChanges { get; private set; }
    internal int Queued => _queue.Count;
    internal int SessionCount => _sessions.Count;

    // A deterministic budget per fixture/epoch, not a wall-clock rate limiter.
    internal void NewSaveEpoch() { Epoch++; _sessions.Clear(); _requests = 0; }
    private bool Authorized(string credential, long now) =>
        Grants.TryGetValue(credential, out var g) && !g.Revoked && now < g.ExpiresAt
        && g.Seat == "p2" && g.Scope == "mcp" && P2Role == "ai" && P2Active;
    private bool Owned(string? session, string credential) => session != null
        && _sessions.TryGetValue(session, out var s) && s == new SessionOwner(credential, "p2", Epoch);

    internal BoundaryReply Handle(BoundaryRequest r, long now = 10)
    {
        // Every guard precedes session changes, seat reads, contact, deadline changes and enqueue.
        if (Connections >= MaxConnections || ++_requests > MaxRequests) return new(429);
        if (r.ReadMilliseconds > MaxReadMilliseconds) return new(408);
        if (Encoding.UTF8.GetByteCount(r.Body) > MaxBodyBytes) return new(413);
        if (r.Host.Length > 128 || r.Peer.Length > 64 || (r.Credential?.Length ?? 0) > 128
            || (r.Session?.Length ?? 0) > 128 || r.DuplicateHeaders || r.Query != "") return new(400);
        if (r.Host != "localhost:8770" && r.Host != "127.0.0.1:8770" && r.Host != "[::1]:8770") return new(403);
        if (!IPAddress.TryParse(r.Peer, out var peer) || !IPAddress.IsLoopback(peer) || r.Origin != null) return new(403);
        if (r.Path != "/mcp/p2") return new(404); // No default seat, human route or aggregate reads.
        if (r.Method != "POST" && r.Method != "DELETE") return new(405);
        if (r.Credential == null || !Grants.TryGetValue(r.Credential, out var grant)
            || grant.Revoked || now >= grant.ExpiresAt) return new(401);
        if (!Authorized(r.Credential, now)) return new(403);
        if (r.Disconnected) return new(499); // Synthetic cancellation before acceptance only.
        if (r.Method == "DELETE")
        {
            if (!Owned(r.Session, r.Credential)) return new(403);
            _sessions.Remove(r.Session!);
            return new(200);
        }
        if (r.ContentType != "application/json") return new(415);
        try
        {
            using var doc = JsonDocument.Parse(r.Body);
            var messages = doc.RootElement.ValueKind == JsonValueKind.Array
                ? doc.RootElement.EnumerateArray().ToArray() : new[] { doc.RootElement };
            if (messages.Length == 0 || messages.Length > MaxBatch) return new(400);
            // Preflight the WHOLE batch: a bad later element must not run an earlier call.
            if (messages.Any(m => !Valid(m))) return new(400);
            var methods = messages.Select(m => m.GetProperty("method").GetString()).ToArray();
            if (methods.Contains("initialize"))
            {
                if (messages.Length != 1 || r.Session != null) return new(400);
                string id = $"fixture-session-{++_sequence}";
                _sessions.Add(id, new(r.Credential, "p2", Epoch));
                return new(200, "initialized", id);
            }
            if (!Owned(r.Session, r.Credential)) return new(403);
            int calls = methods.Count(m => m == "tools/call");
            if (_queue.Count + calls > MaxQueue) return new(429);
            foreach (var method in methods)
                if (method == "tools/call") _queue.Enqueue(new(r.Credential, r.Session!, Epoch));
            return new(methods.All(m => m == "notifications/initialized") ? 202 : 200, "accepted");
        }
        catch (JsonException) { return new(400); }
    }

    private static bool Valid(JsonElement m)
    {
        if (m.ValueKind != JsonValueKind.Object) return false;
        var fields = m.EnumerateObject().Select(p => p.Name).ToArray();
        if (fields.Distinct().Count() != fields.Length || fields.Any(f => f != "jsonrpc" && f != "id" && f != "method" && f != "params")) return false;
        if (!m.TryGetProperty("jsonrpc", out var version) || version.ValueKind != JsonValueKind.String || version.GetString() != "2.0"
            || !m.TryGetProperty("method", out var method) || method.ValueKind != JsonValueKind.String) return false;
        string name = method.GetString()!;
        bool notification = name == "notifications/initialized";
        if (!notification && (!m.TryGetProperty("id", out var id) || id.ValueKind != JsonValueKind.String && id.ValueKind != JsonValueKind.Number)) return false;
        if (m.TryGetProperty("params", out var args) && args.ValueKind != JsonValueKind.Object) return false;
        // Narrow status-only policy: no mutation tool or raw evidence projection is modeled.
        return name switch {
            "initialize" or "ping" or "tools/list" or "notifications/initialized" => true,
            "tools/call" => m.TryGetProperty("params", out args)
                && args.EnumerateObject().Count() == 2
                && args.TryGetProperty("name", out var tool) && tool.ValueKind == JsonValueKind.String && tool.GetString() == "status"
                && args.TryGetProperty("arguments", out var input) && input.ValueKind == JsonValueKind.Object && !input.EnumerateObject().Any(),
            _ => false
        };
    }

    internal BoundaryReply ExecuteNext(long now = 10, bool disconnected = false)
    {
        var work = _queue.Dequeue();
        if (disconnected || work.Epoch != Epoch || !Owned(work.Session, work.Credential)
            || !Authorized(work.Credential, now)) return new(403);
        // This is the simulated game-thread boundary. Never invokes a real seat or dispatcher.
        Contacts++; ToolCalls++; StateReads++;
        return new(200, "{\"seat\":\"p2\",\"status\":\"available\"}");
    }
}
