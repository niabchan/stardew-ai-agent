using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net;
using System.Text;
using System.Text.Json;

namespace StardewMCP.Tests;

// PHASE 2D GAME-FREE FIXTURE ONLY, not compiled into or invoked by AgentHttp.
// A positive result is a *candidate for additional route-specific validation*
// and CANNOT dispatch work, serve a file, or serialize private information.
[Flags]
public enum FakeRouteGrant
{
    None = 0,
    P2Control = 1 << 0,
    P2Observe = 1 << 1,
    OperatorRawState = 1 << 2,
    OperatorRawHistory = 1 << 3,
    OperatorPrivateRead = 1 << 4,
    OperatorRunControl = 1 << 5,
    OperatorReleaseP2 = 1 << 6,
    OperatorReleaseAll = 1 << 7,
    OperatorMetadata = 1 << 8,
    OperatorDebugP2 = 1 << 9,
    OperatorPrivateShell = 1 << 10,
    WatchdogHealth = 1 << 11,
    ReplayProjected = 1 << 12,
    ViewerProjected = 1 << 13
}

internal enum FakeRouteDisposition
{
    Denied,
    NeedsP2Preflight,
    NeedsOperatorValidation,
    NeedsPrivateProjection,
    NeedsHealthProjection,
    NeedsViewerProjection,
    NeedsReplayProjection,
    ConsentDeniedProjectionOnly
}

internal sealed record FakeRouteRequest(
    string Method, string RawPath, string RawQuery, string Host, string PeerAddress,
    int ConfiguredPort, IReadOnlyList<KeyValuePair<string, string>> Headers, byte[] Body);

internal sealed record FakeRoutePrincipal(string PrincipalId, string InstanceId, FakeRouteGrant Grants);

internal interface IFakeRouteAuthority
{
    string IntendedInstanceId { get; }
    int BoundPort { get; }
    FakeRoutePrincipal? ResolveGameBearer(string token);
    bool CurrentP2Owner(FakeRoutePrincipal principal, string session, string epoch);
    bool P1Consent { get; }
    bool DebugEnabled { get; }
    bool ViewerPublicationEnabled { get; }
    bool ViewerProjectionReady { get; }
    bool ReplayProjectionReady { get; }
}

// Status is a test-fixture *decision hint*, not a real HTTP response.
// No response body is produced by this fixture, even for its 200 candidates.
internal sealed record FakeRouteDecision(
    int Status, FakeRouteDisposition Disposition, FakeRouteGrant Required,
    string? RouteId)
{
    internal bool CandidateForFurtherValidation => Status == 200 &&
        Disposition is not (FakeRouteDisposition.Denied or
                            FakeRouteDisposition.ConsentDeniedProjectionOnly);
    internal static FakeRouteDecision Deny(int status) =>
        new(status, FakeRouteDisposition.Denied, FakeRouteGrant.None, null);
    internal static FakeRouteDecision Candidate(FakeRouteDisposition disposition,
        FakeRouteGrant grants, string routeId) => new(200, disposition, grants, routeId);
}

/// <summary>
/// Test-only allowlist reflecting AgentHttp's route inventory and the PR #28 proposal.
/// All calls are side-effect-free. Deliberately supports BEARER-only native/provisioned
/// subjects; browser cookie/CSRF pairing and real projection handlers are not built.
/// </summary>
internal static class FakeAllRoutesBoundary
{
    private const int MaxBodyBytes = 16 * 1024;
    private static readonly UTF8Encoding Utf8Strict = new(false, true);

    private sealed record Route(string Id, string Methods, FakeRouteGrant Grants,
        FakeRouteDisposition Next, string Query = "", bool P2Owner = false,
        bool Consent = false, bool Debug = false, bool Published = false,
        bool ViewerProjection = false, bool ReplayProjection = false);

    private static readonly IReadOnlyDictionary<string, Route> Routes =
        new Dictionary<string, Route>(StringComparer.Ordinal)
        {
            ["/mcp/p2"] = new("mcp-p2", "POST DELETE", FakeRouteGrant.P2Control,
                FakeRouteDisposition.NeedsP2Preflight),
            ["/api/state"] = new("raw-state", "GET", FakeRouteGrant.OperatorRawState,
                FakeRouteDisposition.NeedsPrivateProjection),
            ["/api/feed"] = new("raw-feed", "GET", FakeRouteGrant.OperatorRawHistory,
                FakeRouteDisposition.NeedsPrivateProjection, "after"),
            ["/api/days"] = new("raw-days", "GET", FakeRouteGrant.OperatorRawHistory,
                FakeRouteDisposition.NeedsPrivateProjection),
            ["/api/day"] = new("raw-day", "GET", FakeRouteGrant.OperatorRawHistory,
                FakeRouteDisposition.NeedsPrivateProjection, "n"),
            ["/api/memory"] = new("raw-memory", "GET", FakeRouteGrant.OperatorRawHistory,
                FakeRouteDisposition.NeedsPrivateProjection),
            ["/api/briefing"] = new("raw-briefing", "GET", FakeRouteGrant.OperatorPrivateRead,
                FakeRouteDisposition.NeedsPrivateProjection, "seat"),
            ["/api/relationships"] = new("raw-relationships", "GET", FakeRouteGrant.OperatorPrivateRead,
                FakeRouteDisposition.NeedsPrivateProjection),
            ["/api/stats"] = new("raw-stats", "GET", FakeRouteGrant.OperatorPrivateRead,
                FakeRouteDisposition.NeedsPrivateProjection, "n"),
            ["/api/control"] = new("run-control", "GET POST", FakeRouteGrant.OperatorRunControl,
                FakeRouteDisposition.NeedsOperatorValidation),
            ["/api/release_freeze"] = new("release-freeze", "POST", FakeRouteGrant.OperatorReleaseP2,
                FakeRouteDisposition.NeedsOperatorValidation),
            ["/api/meta"] = new("metadata", "POST", FakeRouteGrant.OperatorMetadata,
                FakeRouteDisposition.NeedsOperatorValidation),
            ["/overlay"] = new("private-overlay-shell", "GET", FakeRouteGrant.OperatorPrivateShell,
                FakeRouteDisposition.NeedsPrivateProjection),
            ["/replay"] = new("private-replay-shell", "GET", FakeRouteGrant.OperatorPrivateShell,
                FakeRouteDisposition.NeedsPrivateProjection),
            ["/"] = new("private-root-shell", "GET", FakeRouteGrant.OperatorPrivateShell,
                FakeRouteDisposition.NeedsPrivateProjection),
            ["/api/companion/v1/p2/safety"] = new("consented-p2-safety", "GET",
                FakeRouteGrant.P2Control | FakeRouteGrant.P2Observe,
                FakeRouteDisposition.NeedsPrivateProjection, P2Owner: true, Consent: true),
            ["/api/health/v1"] = new("watchdog-health-projection", "GET",
                FakeRouteGrant.WatchdogHealth, FakeRouteDisposition.NeedsHealthProjection),
            ["/api/replay/v1/config"] = new("replay-config", "GET",
                FakeRouteGrant.ReplayProjected, FakeRouteDisposition.NeedsReplayProjection, ReplayProjection: true),
            ["/api/replay/v1/days"] = new("replay-days", "GET",
                FakeRouteGrant.ReplayProjected, FakeRouteDisposition.NeedsReplayProjection, ReplayProjection: true),
            ["/api/replay/v1/day"] = new("replay-day", "GET",
                FakeRouteGrant.ReplayProjected, FakeRouteDisposition.NeedsReplayProjection, ReplayProjection: true),
            ["/api/replay/v1/memory"] = new("replay-memory", "GET",
                FakeRouteGrant.ReplayProjected, FakeRouteDisposition.NeedsReplayProjection, ReplayProjection: true),
            ["/api/view/v1/config"] = new("viewer-config", "GET",
                FakeRouteGrant.ViewerProjected, FakeRouteDisposition.NeedsViewerProjection,
                Published: true, ViewerProjection: true),
            ["/api/view/v1/feed"] = new("viewer-feed", "GET",
                FakeRouteGrant.ViewerProjected, FakeRouteDisposition.NeedsViewerProjection,
                Published: true, ViewerProjection: true),
            ["/api/view/v1/summary"] = new("viewer-summary", "GET",
                FakeRouteGrant.ViewerProjected, FakeRouteDisposition.NeedsViewerProjection,
                Published: true, ViewerProjection: true)
        };

    internal static IReadOnlyList<string> ListedPaths => Routes.Keys.OrderBy(s => s, StringComparer.Ordinal).ToArray();

    internal static FakeRouteDecision Check(FakeRouteRequest? request, IFakeRouteAuthority? authority)
    {
        // Authority property reads can fail too; never let store failure escape as authority.
        try { return CheckCore(request, authority); }
        catch { return FakeRouteDecision.Deny(503); }
    }

    private static FakeRouteDecision CheckCore(FakeRouteRequest? request, IFakeRouteAuthority? authority)
    {
        if (request is null || authority is null || request.Headers is null || request.Body is null)
            return FakeRouteDecision.Deny(400);

        if (request.ConfiguredPort is < 1 or > 65535 || request.ConfiguredPort != authority.BoundPort ||
            request.RawPath is null ||
            request.RawQuery is null || request.Host is null || request.PeerAddress is null)
            return FakeRouteDecision.Deny(400);

        // The real adapter MUST capture RAW target, not HttpListener's normalized URL.
        if (!request.RawPath.StartsWith("/", StringComparison.Ordinal) ||
            request.RawPath.Length > 160 || request.RawPath.Contains('%') ||
            request.RawPath.Contains('\\') || request.RawPath.Contains("//", StringComparison.Ordinal) ||
            request.RawPath.Contains('#') || request.RawPath.Contains('?') ||
            request.RawPath.Split('/').Any(s => s is "." or "..") ||
            (request.RawPath.EndsWith("/", StringComparison.Ordinal) && request.RawPath != "/") ||
            request.RawPath.Any(c => c < 33 || c > 126))
            return FakeRouteDecision.Deny(400);

        Route? route = null;
        if (!Routes.TryGetValue(request.RawPath, out route))
        {
            // Debug operations are never allowed to default to host/P1.
            if (request.RawPath.StartsWith("/api/debug/", StringComparison.Ordinal))
            {
                string op = request.RawPath.Substring("/api/debug/".Length);
                if (op.StartsWith("p2/", StringComparison.Ordinal))
                {
                    op = op.Substring(3);
                    // Deliberately narrow subset of DebugApi.All, NOT every existing op.
                    // Explicit p2 does not make load_save/save/hang/world mutations P2-local.
                    if (op is "look" or "set_health" or "set_stamina")
                        route = new Route("debug-p2-schema-pending", "POST",
                            FakeRouteGrant.OperatorDebugP2,
                            FakeRouteDisposition.NeedsOperatorValidation, Debug: true);
                }
            }
            if (route is null) return FakeRouteDecision.Deny(404);
        }

        if (!route.Methods.Split(' ').Contains(request.Method, StringComparer.Ordinal))
            return FakeRouteDecision.Deny(405);

        if (!ValidQuery(request.RawQuery, route.Query) ||
            (route.Id == "raw-briefing" && request.RawQuery != "?seat=p2"))
            return FakeRouteDecision.Deny(400);

        if (request.Body.Length > MaxBodyBytes) return FakeRouteDecision.Deny(413);
        if (request.Method == "GET" && request.Body.Length != 0)
            return FakeRouteDecision.Deny(400);

        if (request.Headers.Count is < 1 or > 64) return FakeRouteDecision.Deny(400);
        var headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var kv in request.Headers)
        {
            if (string.IsNullOrEmpty(kv.Key) || kv.Key.Length > 128 ||
                kv.Key.Any(c => !(c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' ||
                                  c >= '0' && c <= '9' || c == '-')) ||
                kv.Value is null || kv.Value.Length > 4096 ||
                kv.Value.Any(c => c < 32 || c > 126) ||
                !headers.TryAdd(kv.Key, kv.Value))
                return FakeRouteDecision.Deny(400);
        }
        if (headers.ContainsKey("Origin") || headers.ContainsKey("Cookie") ||
            headers.ContainsKey("Transfer-Encoding") || headers.ContainsKey("Forwarded") ||
            headers.ContainsKey("X-Forwarded-Host") || headers.ContainsKey("X-Forwarded-For") ||
            headers.ContainsKey("Proxy-Authorization") || headers.ContainsKey("Expect"))
            return FakeRouteDecision.Deny(403);

        string target = request.ConfiguredPort.ToString(CultureInfo.InvariantCulture);
        if (!headers.TryGetValue("Host", out var host) || host != request.Host ||
            (host != "localhost:" + target && host != "127.0.0.1:" + target) ||
            !IPAddress.TryParse(request.PeerAddress, out var peer) || !IPAddress.IsLoopback(peer))
            return FakeRouteDecision.Deny(403);

        if (headers.TryGetValue("Content-Length", out var size))
        {
            if (size.Length is < 1 or > 8 || size.Any(c => c < '0' || c > '9') ||
                !int.TryParse(size, NumberStyles.None, CultureInfo.InvariantCulture, out var count) ||
                count != request.Body.Length)
                return FakeRouteDecision.Deny(400);
        }
        else if (request.Body.Length != 0) return FakeRouteDecision.Deny(411);

        if (request.Method == "POST")
        {
            if (!headers.TryGetValue("Content-Type", out var media) || media != "application/json")
                return FakeRouteDecision.Deny(415);
            if (request.Body.Length == 0) return FakeRouteDecision.Deny(400);
            if (!StrictObject(request.Body)) return FakeRouteDecision.Deny(400);
        }
        else if (request.Method == "DELETE" && request.Body.Length != 0)
            return FakeRouteDecision.Deny(400);

        if (!headers.TryGetValue("Authorization", out var auth) ||
            !auth.StartsWith("Bearer ", StringComparison.Ordinal))
            return FakeRouteDecision.Deny(401);
        var secret = auth.Substring(7);
        if (secret.Length is < 8 or > 256 || secret.Any(c => c < '!' || c > '~'))
            return FakeRouteDecision.Deny(401);
        FakeRoutePrincipal? principal;
        try { principal = authority.ResolveGameBearer(secret); }
        catch { return FakeRouteDecision.Deny(503); }
        if (principal is null) return FakeRouteDecision.Deny(401);
        try
        {
            if (string.IsNullOrWhiteSpace(principal.PrincipalId) ||
                string.IsNullOrWhiteSpace(principal.InstanceId) ||
                principal.InstanceId != authority.IntendedInstanceId)
                return FakeRouteDecision.Deny(403);
            if ((principal.Grants & route.Grants) != route.Grants)
                return FakeRouteDecision.Deny(403);
            if (route.Debug && !authority.DebugEnabled) return FakeRouteDecision.Deny(404);
            if (route.Published && !authority.ViewerPublicationEnabled)
                return FakeRouteDecision.Deny(403);
            if (route.ViewerProjection && !authority.ViewerProjectionReady)
                return FakeRouteDecision.Deny(503);
            if (route.ReplayProjection && !authority.ReplayProjectionReady)
                return FakeRouteDecision.Deny(503);

            if (route.Id == "release-freeze")
            {
                string? seat = ParseReleaseSeat(request.Body);
                if (seat is null) return FakeRouteDecision.Deny(400);
                if (seat == "all" && (principal.Grants & FakeRouteGrant.OperatorReleaseAll) == 0)
                    return FakeRouteDecision.Deny(403);
            }

            if (route.P2Owner)
            {
                if (!headers.TryGetValue("Mcp-Session-Id", out var session) ||
                    !headers.TryGetValue("X-Sunny-Save-Epoch", out var epoch) ||
                    !Opaque(session) || !Opaque(epoch) ||
                    !authority.CurrentP2Owner(principal, session, epoch))
                    return FakeRouteDecision.Deny(409);
                if (route.Consent && !authority.P1Consent)
                    return new(200, FakeRouteDisposition.ConsentDeniedProjectionOnly,
                        route.Grants, route.Id);
            }
            // Route candidate is NOT data release: still needs independent grant-generation
            // recheck at commit, exact body/schema, fresh P1/seat context, projection and
            // stable role, plus real on-game-thread gates before touching state.
            return FakeRouteDecision.Candidate(route.Next, route.Grants, route.Id);
        }
        catch { return FakeRouteDecision.Deny(503); }
    }

    private static bool StrictObject(byte[] bytes)
    {
        try
        {
            _ = Utf8Strict.GetString(bytes); // JsonDocument may defer decoding unused strings.
            using var doc = JsonDocument.Parse(bytes, new JsonDocumentOptions {
                MaxDepth = 32, AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow
            });
            return doc.RootElement.ValueKind == JsonValueKind.Object && StrictTree(doc.RootElement);
        }
        catch (JsonException) { return false; }
        catch (ArgumentException) { return false; }
        catch (InvalidOperationException) { return false; }
    }

    private static bool StrictTree(JsonElement node)
    {
        if (node.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in node.EnumerateObject())
                if (!names.Add(p.Name) || !StrictTree(p.Value)) return false;
        }
        else if (node.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in node.EnumerateArray())
                if (!StrictTree(item)) return false;
        }
        else if (node.ValueKind == JsonValueKind.Number)
            return node.TryGetDouble(out double n) && !double.IsInfinity(n) && !double.IsNaN(n);
        else if (node.ValueKind == JsonValueKind.String)
            _ = node.GetString();
        return true;
    }

    private static bool ValidQuery(string raw, string allowed)
    {
        if (raw.Length == 0) return true;
        if (allowed.Length == 0 || raw.Length > 96 ||
            raw[0] != '?' || raw.Count(c => c == '?') != 1 ||
            raw.Contains('&') || raw.Contains('%') || raw.Contains('#'))
            return false;
        string prefix = "?" + allowed + "=";
        if (!raw.StartsWith(prefix, StringComparison.Ordinal)) return false;
        string value = raw.Substring(prefix.Length);
        if (allowed == "seat") return value == "p2";
        return value.Length is > 0 and <= 9 && value.All(c => c >= '0' && c <= '9');
    }

    private static bool Opaque(string value) => value.Length is >= 8 and <= 128 &&
        value.All(c => c >= '!' && c <= '~');

    private static string? ParseReleaseSeat(byte[] bytes)
    {
        try
        {
            using var doc = JsonDocument.Parse(bytes, new JsonDocumentOptions {
                MaxDepth = 8, AllowTrailingCommas = false, CommentHandling = JsonCommentHandling.Disallow
            });
            if (doc.RootElement.ValueKind != JsonValueKind.Object) return null;
            var fields = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in doc.RootElement.EnumerateObject())
            {
                if (!fields.Add(p.Name) || p.Name is not ("seat" or "on")) return null;
                if (p.Name == "on" && p.Value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                    return null;
            }
            if (!doc.RootElement.TryGetProperty("seat", out var s) ||
                s.ValueKind != JsonValueKind.String) return null;
            string? seat = s.GetString();
            return seat is "p2" or "all" ? seat : null;
        }
        catch (JsonException) { return null; }
    }
}
