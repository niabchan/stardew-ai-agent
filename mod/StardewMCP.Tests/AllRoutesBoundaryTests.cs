using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using Xunit;

namespace StardewMCP.Tests;

// No HttpListener, private state, file IO, real bearer, game thread or response body.
public sealed class AllRoutesBoundaryTests
{
    private const string P2 = "synthetic-p2-control-token";
    private const string Operator = "synthetic-operator-token";
    private const string Viewer = "synthetic-viewer-token";
    private const string Replay = "synthetic-replay-token";
    private const string Watchdog = "synthetic-watchdog-token";
    private const string Session = "synthetic-p2-session";
    private const string Epoch = "synthetic-host-epoch";

    private sealed class Authority : IFakeRouteAuthority
    {
        internal readonly Dictionary<string, FakeRoutePrincipal> Credentials = new(StringComparer.Ordinal);
        internal int Resolutions, OwnerChecks;
        internal bool FailCredential, FailOwner;
        internal int Port = 8770;
        internal string Instance = "synthetic-instance-8770";
        internal bool Consent, DebugOn, Published, ViewerReady, ReplayReady;
        public string IntendedInstanceId => Instance;
        public int BoundPort => Port;
        public bool P1Consent => Consent;
        public bool DebugEnabled => DebugOn;
        public bool ViewerPublicationEnabled => Published;
        public bool ViewerProjectionReady => ViewerReady;
        public bool ReplayProjectionReady => ReplayReady;
        public FakeRoutePrincipal? ResolveGameBearer(string token)
        {
            Resolutions++;
            if (FailCredential) throw new InvalidOperationException("offline credential store");
            return Credentials.GetValueOrDefault(token);
        }
        public bool CurrentP2Owner(FakeRoutePrincipal principal, string session, string epoch)
        {
            OwnerChecks++;
            if (FailOwner) throw new InvalidOperationException("stale owner store");
            return principal.PrincipalId == "luna" &&
                session == Session && epoch == Epoch;
        }
        internal Authority Grant(string token, string id, FakeRouteGrant grants, string? instance = null)
        {
            Credentials[token] = new(id, instance ?? Instance, grants);
            return this;
        }
    }

    private static Authority Setup()
    {
        var a = new Authority();
        a.Grant(P2, "luna", FakeRouteGrant.P2Control | FakeRouteGrant.P2Observe);
        a.Grant(Operator, "operator", FakeRouteGrant.OperatorRawState |
            FakeRouteGrant.OperatorRawHistory | FakeRouteGrant.OperatorPrivateRead |
            FakeRouteGrant.OperatorRunControl | FakeRouteGrant.OperatorReleaseP2 |
            FakeRouteGrant.OperatorMetadata | FakeRouteGrant.OperatorDebugP2 |
            FakeRouteGrant.OperatorPrivateShell);
        a.Grant(Viewer, "opt-in-published-viewer", FakeRouteGrant.ViewerProjected);
        a.Grant(Replay, "private-replay", FakeRouteGrant.ReplayProjected);
        a.Grant(Watchdog, "local-watchdog", FakeRouteGrant.WatchdogHealth);
        return a;
    }

    private static FakeRouteRequest Request(string path = "/api/state", string method = "GET",
        string credential = P2, string rawQuery = "", string? body = null, int port = 8770,
        bool ownerHeaders = false)
    {
        var headers = new List<KeyValuePair<string, string>>
        {
            new("Host", $"127.0.0.1:{port}"),
            new("Authorization", "Bearer " + credential)
        };
        var bytes = Encoding.UTF8.GetBytes(body ?? (method == "POST" ? "{}" : ""));
        if (method == "POST")
        {
            headers.Add(new("Content-Type", "application/json"));
            headers.Add(new("Content-Length", bytes.Length.ToString()));
        }
        if (ownerHeaders)
        {
            headers.Add(new("Mcp-Session-Id", Session));
            headers.Add(new("X-Sunny-Save-Epoch", Epoch));
        }
        return new(method, path, rawQuery, $"127.0.0.1:{port}",
            "127.0.0.1", port, headers, bytes);
    }

    private static FakeRouteRequest Add(FakeRouteRequest req, string name, string value) =>
        req with { Headers = req.Headers.Concat(new[] { new KeyValuePair<string, string>(name, value) }).ToList() };

    private static FakeRouteRequest Replace(FakeRouteRequest req, string name, string value) =>
        req with
        {
            Headers = req.Headers.Where(x => !x.Key.Equals(name, StringComparison.OrdinalIgnoreCase))
                .Concat(new[] { new KeyValuePair<string, string>(name, value) }).ToList()
        };

    [Theory]
    [InlineData("/api/state", "GET", FakeRouteGrant.OperatorRawState)]
    [InlineData("/api/feed", "GET", FakeRouteGrant.OperatorRawHistory)]
    [InlineData("/api/days", "GET", FakeRouteGrant.OperatorRawHistory)]
    [InlineData("/api/day", "GET", FakeRouteGrant.OperatorRawHistory)]
    [InlineData("/api/memory", "GET", FakeRouteGrant.OperatorRawHistory)]
    [InlineData("/api/briefing", "GET", FakeRouteGrant.OperatorPrivateRead)]
    [InlineData("/api/relationships", "GET", FakeRouteGrant.OperatorPrivateRead)]
    [InlineData("/api/stats", "GET", FakeRouteGrant.OperatorPrivateRead)]
    [InlineData("/api/control", "GET", FakeRouteGrant.OperatorRunControl)]
    [InlineData("/api/control", "POST", FakeRouteGrant.OperatorRunControl)]
    [InlineData("/api/release_freeze", "POST", FakeRouteGrant.OperatorReleaseP2)]
    [InlineData("/api/meta", "POST", FakeRouteGrant.OperatorMetadata)]
    [InlineData("/", "GET", FakeRouteGrant.OperatorPrivateShell)]
    [InlineData("/overlay", "GET", FakeRouteGrant.OperatorPrivateShell)]
    [InlineData("/replay", "GET", FakeRouteGrant.OperatorPrivateShell)]
    public void Legacy_routes_require_explicit_individual_operator_subscope(
        string path, string method, FakeRouteGrant needed)
    {
        var a = Setup();
        a.Grant("limited-operator-token", "limited-operator", needed);
        string query = path == "/api/briefing" ? "?seat=p2" : "";
        string? body = path == "/api/release_freeze" ? "{\"seat\":\"p2\",\"on\":true}" : null;
        var req = Request(path, method, "limited-operator-token", query, body);
        var accepted = FakeAllRoutesBoundary.Check(req, a);
        Assert.True(accepted.CandidateForFurtherValidation);
        Assert.Equal(needed, accepted.Required);
        Assert.NotEqual(FakeRouteDisposition.NeedsP2Preflight, accepted.Disposition);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(
            req with { Headers = Replace(req, "Authorization", "Bearer " + P2).Headers }, a).Status);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(
            req with { Headers = Replace(req, "Authorization", "Bearer " + Watchdog).Headers }, a).Status);
    }

    [Fact]
    public void No_broad_admin_grant_or_composite_scope_implies_raw_operator_access()
    {
        var a = Setup();
        var all = FakeRouteGrant.P2Control | FakeRouteGrant.P2Observe |
                  FakeRouteGrant.WatchdogHealth | FakeRouteGrant.ReplayProjected |
                  FakeRouteGrant.ViewerProjected;
        a.Grant("composite-nonoperator-token", "nonoperator", all);
        foreach (string path in new[] { "/api/state", "/api/feed", "/api/day", "/api/memory",
                  "/api/control", "/api/meta", "/api/release_freeze", "/overlay", "/replay" })
        {
            string method = path is "/api/control" or "/api/meta" or "/api/release_freeze" ? "POST" : "GET";
            string? body = path == "/api/release_freeze" ? "{\"seat\":\"p2\"}" : null;
            Assert.Equal(403, FakeAllRoutesBoundary.Check(
                Request(path, method, "composite-nonoperator-token", body: body), a).Status);
        }
    }

    [Theory]
    [InlineData("/mcp")]
    [InlineData("/mcp/p1")]
    [InlineData("/mcp/p3")]
    [InlineData("/mcp/p4")]
    [InlineData("/api/debug/say")]
    [InlineData("/api/debug/p1/say")]
    [InlineData("/api/debug/p3/say")]
    [InlineData("/api/debug/p2/")]
    [InlineData("/api/debug/p2/say/")]
    [InlineData("/api/unknown")]
    [InlineData("/api/view/v1/raw")]
    [InlineData("/api/replay/v1/full")]
    public void P1_alias_other_seats_and_unlisted_routes_are_never_candidates(string path)
    {
        var a = Setup();
        var r = FakeAllRoutesBoundary.Check(Request(path, "POST", Operator), a);
        Assert.Equal(404, r.Status);
        Assert.False(r.CandidateForFurtherValidation);
    }

    [Theory]
    [InlineData("/api/state")]
    [InlineData("/api/feed")]
    [InlineData("/api/days")]
    [InlineData("/api/day")]
    [InlineData("/api/memory")]
    [InlineData("/api/briefing")]
    [InlineData("/api/relationships")]
    [InlineData("/api/stats")]
    [InlineData("/api/control")]
    [InlineData("/api/release_freeze")]
    [InlineData("/api/meta")]
    [InlineData("/overlay")]
    [InlineData("/replay")]
    [InlineData("/")]
    public void Viewer_and_controller_cannot_fetch_raw_legacy_data(string path)
    {
        var a = Setup();
        string method = path is "/api/meta" or "/api/release_freeze" ? "POST" : "GET";
        string query = path == "/api/briefing" ? "?seat=p2" : "";
        string? body = path == "/api/release_freeze" ? "{\"seat\":\"p2\"}" : null;
        foreach (string token in new[] { P2, Viewer, Replay, Watchdog })
        {
            var x = FakeAllRoutesBoundary.Check(Request(path, method, token, query, body), a);
            Assert.False(x.CandidateForFurtherValidation);
            Assert.True(x.Status is 403 or 405);
        }
    }

    [Fact]
    public void P2_mcp_requires_C_and_delegates_real_session_and_tool_verification()
    {
        var a = Setup();
        a.Grant("observe-only-token", "observer", FakeRouteGrant.P2Observe);
        var candidate = FakeAllRoutesBoundary.Check(Request("/mcp/p2", "POST", P2), a);
        Assert.Equal(FakeRouteDisposition.NeedsP2Preflight, candidate.Disposition);
        Assert.Equal(FakeRouteGrant.P2Control, candidate.Required);
        Assert.True(candidate.CandidateForFurtherValidation);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(Request("/mcp/p2", "POST", "observe-only-token"), a).Status);
        Assert.Equal(405, FakeAllRoutesBoundary.Check(Request("/mcp/p2", "GET", P2), a).Status);
        Assert.Equal(200, FakeAllRoutesBoundary.Check(Request("/mcp/p2", "DELETE", P2), a).Status);
        // The fixture only classifies a potential downstream call: it issues NO lease
        // and does NOT turn existing legacy DELETE 200 into a retirement proof.
    }

    [Fact]
    public void P2_safety_requires_C_and_O_current_owner_and_independent_P1_consent()
    {
        var a = Setup();
        var req = Request("/api/companion/v1/p2/safety", credential: P2, ownerHeaders: true);
        Assert.Equal(FakeRouteDisposition.ConsentDeniedProjectionOnly,
            FakeAllRoutesBoundary.Check(req, a).Disposition);
        Assert.False(FakeAllRoutesBoundary.Check(req, a).CandidateForFurtherValidation);
        a.Consent = true;
        var outcome = FakeAllRoutesBoundary.Check(req, a);
        Assert.Equal(FakeRouteDisposition.NeedsPrivateProjection, outcome.Disposition);
        Assert.Equal(FakeRouteGrant.P2Control | FakeRouteGrant.P2Observe, outcome.Required);
        Assert.True(outcome.CandidateForFurtherValidation);
        Assert.Equal(409, FakeAllRoutesBoundary.Check(
            req with { Headers = req.Headers.Where(x => x.Key != "Mcp-Session-Id").ToList() }, a).Status);
        Assert.Equal(409, FakeAllRoutesBoundary.Check(
            Replace(req, "X-Sunny-Save-Epoch", "old-host-epoch"), a).Status);
        a.Grant("c-only-token", "luna", FakeRouteGrant.P2Control);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(Request("/api/companion/v1/p2/safety",
            credential: "c-only-token", ownerHeaders: true), a).Status);
        a.FailOwner = true;
        Assert.Equal(503, FakeAllRoutesBoundary.Check(req, a).Status);
    }

    [Fact]
    public void Watchdog_gets_only_proposed_narrow_health_endpoint()
    {
        var a = Setup();
        var health = FakeAllRoutesBoundary.Check(Request("/api/health/v1", credential: Watchdog), a);
        Assert.Equal(FakeRouteDisposition.NeedsHealthProjection, health.Disposition);
        Assert.Equal(FakeRouteGrant.WatchdogHealth, health.Required);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(Request("/api/state", credential: Watchdog), a).Status);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(Request("/api/control", credential: Watchdog), a).Status);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(Request("/api/health/v1", credential: P2), a).Status);
    }

    [Theory]
    [InlineData("/api/view/v1/config")]
    [InlineData("/api/view/v1/feed")]
    [InlineData("/api/view/v1/summary")]
    public void Viewer_projection_denies_default_unpublished_and_unready(string path)
    {
        var a = Setup();
        var req = Request(path, credential: Viewer);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(req, a).Status);
        a.Published = true;
        Assert.Equal(503, FakeAllRoutesBoundary.Check(req, a).Status);
        a.ViewerReady = true;
        Assert.Equal(FakeRouteDisposition.NeedsViewerProjection,
            FakeAllRoutesBoundary.Check(req, a).Disposition);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(
            Request("/api/day", credential: Viewer), a).Status);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(
            Request("/api/view/v1/feed", credential: P2), a).Status);
    }

    [Theory]
    [InlineData("/api/replay/v1/config")]
    [InlineData("/api/replay/v1/days")]
    [InlineData("/api/replay/v1/day")]
    [InlineData("/api/replay/v1/memory")]
    public void Replay_projections_require_separate_R_and_prepared_projection(string path)
    {
        var a = Setup();
        var req = Request(path, credential: Replay);
        Assert.Equal(503, FakeAllRoutesBoundary.Check(req, a).Status);
        a.ReplayReady = true;
        var decision = FakeAllRoutesBoundary.Check(req, a);
        Assert.Equal(FakeRouteDisposition.NeedsReplayProjection, decision.Disposition);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(Request(path, credential: Viewer), a).Status);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(Request(path, credential: P2), a).Status);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(Request("/api/memory", credential: Replay), a).Status);
    }

    [Fact]
    public void Explicit_release_p2_cannot_release_all_or_P1_without_extra_scope()
    {
        var a = Setup();
        var p2 = Request("/api/release_freeze", "POST", Operator,
            body: "{\"seat\":\"p2\",\"on\":true}");
        Assert.True(FakeAllRoutesBoundary.Check(p2, a).CandidateForFurtherValidation);
        foreach (var json in new[] { "{}", "{\"seat\":\"p1\"}", "{\"seat\":\"p3\"}",
                  "{\"seat\":\"p2\",\"on\":\"true\"}", "{\"seat\":\"p2\",\"seat\":\"all\"}",
                  "{\"seat\":\"p2\",\"extra\":5}", "[]" })
            Assert.Equal(400, FakeAllRoutesBoundary.Check(p2 with {
                Body = Encoding.UTF8.GetBytes(json),
                Headers = Replace(p2, "Content-Length", Encoding.UTF8.GetByteCount(json).ToString()).Headers
            }, a).Status);
        var all = Request("/api/release_freeze", "POST", Operator,
            body: "{\"seat\":\"all\",\"on\":true}");
        Assert.Equal(403, FakeAllRoutesBoundary.Check(all, a).Status);
        a.Grant(Operator, "operator", a.Credentials[Operator].Grants | FakeRouteGrant.OperatorReleaseAll);
        Assert.Equal(200, FakeAllRoutesBoundary.Check(all, a).Status);
    }

    [Fact]
    public void Debug_requires_p2_explicit_target_operator_and_local_switch()
    {
        var a = Setup();
        var request = Request("/api/debug/p2/say", "POST", Operator);
        Assert.Equal(404, FakeAllRoutesBoundary.Check(request, a).Status);
        a.DebugOn = true;
        Assert.Equal(FakeRouteDisposition.NeedsOperatorValidation,
            FakeAllRoutesBoundary.Check(request, a).Disposition);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(
            Request("/api/debug/p2/say", "POST", P2), a).Status);
        Assert.Equal(404, FakeAllRoutesBoundary.Check(
            Request("/api/debug/p1/say", "POST", Operator), a).Status);
    }

    [Theory]
    [InlineData("Origin", "http://localhost:8770")]
    [InlineData("Origin", "null")]
    [InlineData("Origin", "")]
    [InlineData("Cookie", "session=forged")]
    [InlineData("Transfer-Encoding", "chunked")]
    [InlineData("X-Forwarded-Host", "127.0.0.1:8770")]
    [InlineData("X-Forwarded-For", "127.0.0.1")]
    [InlineData("Forwarded", "for=127.0.0.1")]
    [InlineData("Proxy-Authorization", "Basic forged")]
    public void Browser_and_proxy_channels_are_not_native_credentials(string header, string value)
    {
        var a = Setup();
        var result = FakeAllRoutesBoundary.Check(Add(Request("/api/control", "POST", Operator),
            header, value), a);
        Assert.Equal(403, result.Status);
        Assert.Equal(0, a.Resolutions);
    }

    [Fact]
    public void Malformed_duplicate_headers_or_ambiguous_body_framing_denied_before_auth()
    {
        var a = Setup();
        var req = Request("/api/control", "POST", Operator);
        var candidates = new[] {
            Add(req, "host", "127.0.0.1:8770"),
            Add(req, "authorization", "Bearer different"),
            Add(req, "Content-Length", "999"),
            Replace(req, "Content-Length", "999"),
            Add(req, "X-Bad", "value\r\nInjected: x"),
            Replace(req, "Content-Length", "-1"),
            req with { Headers = req.Headers.Where(x => x.Key != "Content-Length").ToList() },
            req with { Body = new byte[FakeAllRoutesBoundaryListedBodyLimit + 1] },
            req with { Body = new byte[] { 0xff },
                Headers = Replace(req, "Content-Length", "1").Headers }
        };
        foreach (var bad in candidates)
        {
            var decision = FakeAllRoutesBoundary.Check(bad, a);
            Assert.False(decision.CandidateForFurtherValidation);
            Assert.True(decision.Status is 400 or 403 or 411 or 413);
        }
        Assert.Equal(0, a.Resolutions);
    }

    private const int FakeAllRoutesBoundaryListedBodyLimit = 16 * 1024;

    [Theory]
    [InlineData("/api/control/")]
    [InlineData("//api/control")]
    [InlineData("/api%2Fcontrol")]
    [InlineData("/api\\control")]
    [InlineData("/api/control%3f")]
    [InlineData("/api/../control")]
    [InlineData("http://127.0.0.1:8770/api/control")]
    public void Noncanonical_raw_paths_never_dispatch(string path)
    {
        var a = Setup();
        var result = FakeAllRoutesBoundary.Check(Request(path, "POST", Operator), a);
        Assert.False(result.CandidateForFurtherValidation);
        Assert.True(result.Status is 400 or 404);
        Assert.Equal(0, a.Resolutions);
    }

    [Theory]
    [InlineData("?breaks=1")]
    [InlineData("?reply_within=1200")]
    [InlineData("?n=1&seat=p1")]
    [InlineData("?n=%31")]
    [InlineData("?n=-1")]
    [InlineData("?n=1#fragment")]
    public void Query_grammar_rejects_legacy_MCP_and_injected_raw_queries(string query)
    {
        var a = Setup();
        var route = query.StartsWith("?n", StringComparison.Ordinal) ?
            Request("/api/day", credential: Operator, rawQuery: query) :
            Request("/mcp/p2", credential: P2, rawQuery: query);
        var result = FakeAllRoutesBoundary.Check(route, a);
        Assert.Equal(400, result.Status);
    }

    [Fact]
    public void Raw_legacy_query_is_bounded_and_p2_briefing_explicit()
    {
        var a = Setup();
        Assert.Equal(200, FakeAllRoutesBoundary.Check(Request("/api/feed", credential: Operator, rawQuery: "?after=12"), a).Status);
        Assert.Equal(200, FakeAllRoutesBoundary.Check(Request("/api/day", credential: Operator, rawQuery: "?n=7"), a).Status);
        Assert.Equal(200, FakeAllRoutesBoundary.Check(Request("/api/stats", credential: Operator, rawQuery: "?n=3"), a).Status);
        Assert.Equal(400, FakeAllRoutesBoundary.Check(Request("/api/briefing", credential: Operator), a).Status);
        Assert.Equal(400, FakeAllRoutesBoundary.Check(Request("/api/briefing", credential: Operator, rawQuery: "?seat=p1"), a).Status);
        Assert.Equal(200, FakeAllRoutesBoundary.Check(Request("/api/briefing", credential: Operator, rawQuery: "?seat=p2"), a).Status);
    }

    [Fact]
    public void Wrong_instance_port_and_host_cannot_fall_back_to_first_game()
    {
        var a = Setup();
        var req = Request("/api/state", credential: Operator);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(req with { Host = "evil.invalid:8770" }, a).Status);
        Assert.Equal(403, FakeAllRoutesBoundary.Check(req with { PeerAddress = "192.0.2.1" }, a).Status);
        Assert.Equal(400, FakeAllRoutesBoundary.Check(req with { ConfiguredPort = 18770 }, a).Status);
        a.Grant("wrong-instance-token", "operator", FakeRouteGrant.OperatorRawState,
            instance: "synthetic-instance-18770");
        Assert.Equal(403, FakeAllRoutesBoundary.Check(
            Request("/api/state", credential: "wrong-instance-token"), a).Status);
        Assert.Equal(401, FakeAllRoutesBoundary.Check(
            Request("/api/state", credential: "unknown-token"), a).Status);
        a.FailCredential = true;
        Assert.Equal(503, FakeAllRoutesBoundary.Check(req, a).Status);
    }

    [Fact]
    public void Every_known_route_deny_fails_without_grant_and_none_of_this_is_a_response()
    {
        var a = Setup();
        a.Grant("no-permissions-token", "generic", FakeRouteGrant.None);
        foreach (string path in FakeAllRoutesBoundary.ListedPaths)
        {
            var req = Request(path, credential: "no-permissions-token",
                method: path is "/mcp/p2" or "/api/control" or "/api/release_freeze" or "/api/meta" ? "POST" : "GET",
                rawQuery: path == "/api/briefing" ? "?seat=p2" : "",
                body: path == "/api/release_freeze" ? "{\"seat\":\"p2\"}" : null);
            var result = FakeAllRoutesBoundary.Check(req, a);
            Assert.False(result.CandidateForFurtherValidation);
            Assert.Equal(403, result.Status);
            Assert.Null(result.RouteId);
        }
    }
}
