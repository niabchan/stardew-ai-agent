using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net;
using System.Text.Json;

namespace StardewMCP.Agent;

/// <summary>
/// Dormant, game-free REQUEST-SHAPE policy proposal for a future Sunny P2 listener.
/// NOT invoked by AgentHttp or McpDispatcher. NEVER treat a successful preflight
/// as permission to enqueue: the server must atomically recheck owner, epoch,
/// role, grant, tool schema, capacity and revocation at queue admission and each
/// game-thread coroutine step. No credential provisioner is implemented here.
/// </summary>
public static class SunnyP2Preflight
{
    public const int MaxBodyBytes = 16 * 1024;
    public const string Protocol = "2025-06-18";
    public const string EpochHeader = "X-Sunny-Save-Epoch";
    public const string SessionHeader = "Mcp-Session-Id";

    public static SunnyP2Decision Evaluate(SunnyP2Request request, ISunnyP2PolicyAuthority authority)
    {
        if (request is null || authority is null) return SunnyP2Decision.Deny(400);
        if (request.Port is < 1 or > 65535 || !string.IsNullOrEmpty(request.RawQuery))
            return SunnyP2Decision.Deny(400);
        if (request.Path != "/mcp/p2") return SunnyP2Decision.Deny(404);
        if (request.Method is not ("POST" or "DELETE")) return SunnyP2Decision.Deny(405);

        // No DNS trust, proxy headers, browser-Origin bypass or default-seat aliases.
        if (request.Host != "localhost:" + request.Port
            && request.Host != "127.0.0.1:" + request.Port)
            return SunnyP2Decision.Deny(403);
        if (!IPAddress.TryParse(request.PeerAddress, out var peer) || !IPAddress.IsLoopback(peer))
            return SunnyP2Decision.Deny(403);

        var headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (request.Headers is null || request.Headers.Count > 64) return SunnyP2Decision.Deny(400);
        foreach (var pair in request.Headers)
        {
            if (string.IsNullOrEmpty(pair.Key) || pair.Key.Length > 128 ||
                pair.Key.Any(c => !(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' ||
                                    c >= '0' && c <= '9' || c == '-')) ||
                pair.Value is null || pair.Value.Length > 4096 ||
                pair.Value.Any(c => c < 32 || c > 126) ||
                !headers.TryAdd(pair.Key, pair.Value))
                return SunnyP2Decision.Deny(400);
        }
        if (headers.ContainsKey("Origin")) return SunnyP2Decision.Deny(403);
        if (!headers.TryGetValue("Authorization", out var authorization) ||
            !authorization.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
            return SunnyP2Decision.Deny(401);
        var token = authorization.Substring(7);
        if (token.Length is < 8 or > 256 || token.Any(c => c < '!' || c > '~'))
            return SunnyP2Decision.Deny(401);

        SunnyP2Principal? principal;
        try { principal = authority.ResolveGameCredential(token); }
        catch { return SunnyP2Decision.Deny(503); }
        if (principal is null) return SunnyP2Decision.Deny(401);
        if (principal.Seat != "p2" || !principal.Control)
            return SunnyP2Decision.Deny(403);
        bool rolesReady;
        try { rolesReady = authority.HumanP1AiP2ExternalBrainReady; }
        catch { return SunnyP2Decision.Deny(503); }
        if (!rolesReady) return SunnyP2Decision.Deny(503);

        var hasSession = headers.TryGetValue(SessionHeader, out var session);
        var hasEpoch = headers.TryGetValue(EpochHeader, out var epoch);
        if (hasSession && !Opaque(session!) || hasEpoch && !Opaque(epoch!))
            return SunnyP2Decision.Deny(400);

        if (request.Method == "DELETE")
        {
            if (request.Body is null || request.Body.Length != 0) return SunnyP2Decision.Deny(400);
            if (!hasSession || !hasEpoch) return SunnyP2Decision.Deny(409);
            if (!CurrentSession(authority, principal, session!, epoch!)) return SunnyP2Decision.Deny(409);
            return SunnyP2Decision.Permit(SunnyP2Operation.Retire, null);
        }

        if (!headers.TryGetValue("Content-Type", out var media) ||
            media != "application/json") return SunnyP2Decision.Deny(415);
        if (headers.TryGetValue("Accept", out var accept) &&
            !accept.Split(',').Any(x => x.Trim().Equals("application/json", StringComparison.OrdinalIgnoreCase)))
            return SunnyP2Decision.Deny(406);
        if (request.Body is null || request.Body.Length == 0) return SunnyP2Decision.Deny(400);
        if (request.Body.Length > MaxBodyBytes) return SunnyP2Decision.Deny(413);

        try
        {
            using var doc = JsonDocument.Parse(request.Body, new JsonDocumentOptions {
                MaxDepth = 32, AllowTrailingCommas = false, CommentHandling = JsonCommentHandling.Disallow
            });
            var root = doc.RootElement;
            if (root.ValueKind != JsonValueKind.Object || !StrictTree(root)) return SunnyP2Decision.Deny(400);
            if (root.EnumerateObject().Any(x => x.Name is not ("jsonrpc" or "id" or "method" or "params")))
                return SunnyP2Decision.Deny(400);
            if (!root.TryGetProperty("jsonrpc", out var v) || v.ValueKind != JsonValueKind.String
                || v.GetString() != "2.0" || !root.TryGetProperty("method", out var m)
                || m.ValueKind != JsonValueKind.String) return SunnyP2Decision.Deny(400);
            string? method = m.GetString();
            bool notification = method == "notifications/initialized";
            if (root.TryGetProperty("id", out var id))
            {
                if (notification || !ValidRpcId(id)) return SunnyP2Decision.Deny(400);
            }
            else if (!notification) return SunnyP2Decision.Deny(400);
            if (root.TryGetProperty("params", out var p) && p.ValueKind != JsonValueKind.Object)
                return SunnyP2Decision.Deny(400);

            if (method == "initialize")
            {
                if (hasSession || hasEpoch || !root.TryGetProperty("params", out p)
                    || !p.TryGetProperty("protocolVersion", out var pv)
                    || pv.ValueKind != JsonValueKind.String || pv.GetString() != Protocol
                    || p.EnumerateObject().Any(x => x.Name is not ("protocolVersion" or "capabilities" or "clientInfo")))
                    return SunnyP2Decision.Deny(400);
                if (p.TryGetProperty("capabilities", out var cap) && cap.ValueKind != JsonValueKind.Object)
                    return SunnyP2Decision.Deny(400);
                if (p.TryGetProperty("clientInfo", out var info) && info.ValueKind != JsonValueKind.Object)
                    return SunnyP2Decision.Deny(400);
                // The atomic, conflict-aware lease acquisition is NOT performed here.
                return SunnyP2Decision.Permit(SunnyP2Operation.Initialize, null);
            }

            if (!hasSession || !hasEpoch) return SunnyP2Decision.Deny(409);
            if (!CurrentSession(authority, principal, session!, epoch!)) return SunnyP2Decision.Deny(409);
            if (method == "notifications/initialized")
                return SunnyP2Decision.Permit(SunnyP2Operation.Notification, null);
            if (method == "ping" || method == "tools/list")
                return SunnyP2Decision.Permit(SunnyP2Operation.Discovery, null);
            if (method != "tools/call") return SunnyP2Decision.Deny(400);
            if (!root.TryGetProperty("params", out p)
                || p.EnumerateObject().Count() != 2
                || !p.TryGetProperty("name", out var nameEl)
                || nameEl.ValueKind != JsonValueKind.String
                || !p.TryGetProperty("arguments", out var args)
                || args.ValueKind != JsonValueKind.Object)
                return SunnyP2Decision.Deny(400);
            string? tool = nameEl.GetString();
            if (string.IsNullOrWhiteSpace(tool) || tool.Length > 128)
                return SunnyP2Decision.Deny(400);
            if (tool == "status")
            {
                if (args.EnumerateObject().Any()) return SunnyP2Decision.Deny(400);
                if (!principal.Observe) return SunnyP2Decision.Deny(403);
                return SunnyP2Decision.Permit(SunnyP2Operation.Status, tool);
            }
            // No tool may be admitted without a separately supplied schema validator.
            // This callback is NOT a substitute for atomic game-thread authorization.
            bool valid;
            try { valid = authority.ValidateMutationArguments(tool, args); }
            catch { return SunnyP2Decision.Deny(503); }
            if (!valid) return SunnyP2Decision.Deny(400);
            return SunnyP2Decision.Permit(SunnyP2Operation.Mutation, tool);
        }
        catch (JsonException) { return SunnyP2Decision.Deny(400); }
        catch (ArgumentException) { return SunnyP2Decision.Deny(400); }
    }

    private static bool CurrentSession(ISunnyP2PolicyAuthority authority, SunnyP2Principal principal,
        string session, string epoch)
    {
        try { return authority.IsCurrentOwnerSession(principal.PrincipalId, session, epoch); }
        catch { return false; }
    }

    private static bool Opaque(string value) => value.Length is >= 8 and <= 128 &&
        value.All(c => c >= '!' && c <= '~');

    private static bool ValidRpcId(JsonElement id)
    {
        if (id.ValueKind == JsonValueKind.String)
        {
            var s = id.GetString();
            return s is { Length: >= 1 and <= 64 } && s.All(c => c >= 32 && c <= 126);
        }
        if (id.ValueKind != JsonValueKind.Number) return false;
        string raw = id.GetRawText();
        if (raw.Length == 0 || raw.Any(c => !(c >= '0' && c <= '9' || c == '-')))
            return false; // no decimal point or exponent
        return long.TryParse(raw, NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out long n)
               && n is >= -9007199254740991L and <= 9007199254740991L;
    }

    private static bool StrictTree(JsonElement node)
    {
        switch (node.ValueKind)
        {
            case JsonValueKind.Object:
                var seen = new HashSet<string>(StringComparer.Ordinal);
                foreach (var p in node.EnumerateObject())
                    if (!seen.Add(p.Name) || !StrictTree(p.Value)) return false;
                return true;
            case JsonValueKind.Array:
                foreach (var x in node.EnumerateArray())
                    if (!StrictTree(x)) return false;
                return true;
            case JsonValueKind.Number:
                return node.TryGetDouble(out double v) && !double.IsInfinity(v) && !double.IsNaN(v);
            default:
                return true;
        }
    }
}

public enum SunnyP2Operation { Denied, Initialize, Notification, Discovery, Status, Mutation, Retire }

/// <summary>Not an authorization token; consumer MUST recheck under coordinator lock.</summary>
public sealed record SunnyP2Decision(int Status, SunnyP2Operation Operation, string? Tool)
{
    public bool Allowed => Status == 200;
    public bool MayMarkContact => Allowed && Operation is SunnyP2Operation.Status or SunnyP2Operation.Mutation;
    public static SunnyP2Decision Deny(int status) => new(status, SunnyP2Operation.Denied, null);
    public static SunnyP2Decision Permit(SunnyP2Operation operation, string? tool) =>
        new(200, operation, tool);
}

public sealed record SunnyP2Request(string Method, string Path, string Host, string PeerAddress,
    int Port, IReadOnlyList<KeyValuePair<string, string>> Headers, byte[] Body,
    string RawQuery = ""); // no v1 query grammar approved in this seam: reject all until specified
public sealed record SunnyP2Principal(string PrincipalId, string Seat, bool Control, bool Observe);

/// <summary>
/// Synthetic authority seam. Real implementation MUST authenticate the game credential,
/// enforce epoch-scoped grants, and verify owner/epoch atomically with real admission.
/// Never inject a permissive verifier or use provider API credentials.
/// </summary>
public interface ISunnyP2PolicyAuthority
{
    SunnyP2Principal? ResolveGameCredential(string rawBearer);
    bool HumanP1AiP2ExternalBrainReady { get; }
    bool IsCurrentOwnerSession(string principalId, string session, string epoch);
    bool ValidateMutationArguments(string name, JsonElement arguments);
}
