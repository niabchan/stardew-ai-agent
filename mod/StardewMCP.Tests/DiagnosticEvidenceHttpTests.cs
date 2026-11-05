using System;
using System.Text.Json;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

public class DiagnosticEvidenceHttpTests
{
    private const string Canary = "P1_PRIVATE_CANARY_name_item_path";
    private readonly DiagnosticEvidenceCache _cache = new(1000);
    private readonly EvidenceCapture _p1, _p2;
    private readonly FakeEvidenceHttp _http;
    private int _reads;
    public DiagnosticEvidenceHttpTests()
    {
        _cache.Configure(true, true, false);
        _cache.HostLoaded();
        _p1 = Capture(0);
        _p2 = Capture(1); // Deliberately embeds P1 content in P2 question AND labels.
        _http = new FakeEvidenceHttp(seat => {
            _reads++;
            return _cache.Read(seat, 10, _p2.ClockId, 1);
        }, _cache.Clear);
    }
    private EvidenceCapture Capture(int screen) => _cache.Capture(screen, new object(), screen == 0 ? "human" : "ai",
        1, 10, DateTimeOffset.Parse("2026-11-05T00:00:00Z"), new object(), true, Canary,
        true, new[] { Canary, "No" }, lifecycleCoverage: false)!;
    private static void PrivateHeaders(FakeEvidenceReply r)
    {
        Assert.Equal("no-store", r.Headers["Cache-Control"]);
        Assert.Equal("application/json", r.Headers["Content-Type"]);
        Assert.Equal("nosniff", r.Headers["X-Content-Type-Options"]);
        Assert.DoesNotContain(r.Headers.Keys, k => k.StartsWith("Access-Control", StringComparison.OrdinalIgnoreCase));
    }
    private void Denied(FakeEvidenceRequest request, int status = 403, long now = 10)
    {
        var r = _http.Handle(request, now);
        Assert.Equal(status, r.Status);
        Assert.Equal(0, _reads);
        Assert.DoesNotContain(Canary, r.Body);
        Assert.DoesNotContain(_p1.Scope.LoadId, r.Body);
        PrivateHeaders(r);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("fixture-secret")]
    [InlineData("Bearer wrong")]
    [InlineData("bearer fixture-secret")]
    [InlineData("Bearer fixture-secret ")]
    public void Missing_malformed_wrong_credentials_never_read_cache(string? authorization) =>
        Denied(new(Authorization: authorization), 401);

    [Fact]
    public void Expired_revoked_query_tokens_and_empty_secret_never_authenticate()
    {
        Denied(new(), 401, now: 100);
        Denied(new(Authorization: null, Query: "seat=p2&token=fixture-secret"), 401);
        _http.ReplaceGrant(new(Secret: "rotated-fixture"));
        Denied(new(), 401);
        _http.ReplaceGrant(new(Secret: ""));
        Denied(new(Authorization: "Bearer "), 401);
    }

    [Theory]
    [InlineData("https://evil.example")]
    [InlineData("null")]
    [InlineData("http://localhost:8770")]
    [InlineData("http://localhost:8771")]
    [InlineData("http://localhost.evil:8770")]
    public void Native_mode_rejects_every_origin_even_with_valid_token(string origin) => Denied(new(Origin: origin));

    [Theory]
    [InlineData("evil.example:8770", true)]
    [InlineData("localhost.evil:8770", true)]
    [InlineData("localhost:8771", true)]
    [InlineData("localhost:8770", false)]
    [InlineData("127.0.0.1:8770.evil", true)]
    [InlineData("[::1]:8770", true)]
    public void Explicit_host_port_peer_checks_ignore_spoofed_forwarding(string host, bool loopback) =>
        Denied(new(Host: host, LoopbackPeer: loopback, ForwardedHost: "localhost:8770"));

    [Theory]
    [InlineData("POST")]
    [InlineData("OPTIONS")]
    [InlineData("DELETE")]
    [InlineData("HEAD")]
    public void Unsupported_methods_and_preflight_never_touch_cache_or_CORS(string method) => Denied(new(Method: method), 405);

    [Theory]
    [InlineData("")]
    [InlineData("fields=metadata")]
    [InlineData("seat=all&fields=metadata")]
    [InlineData("seat=p2&seat=p1&fields=metadata")]
    [InlineData("seat=p2&seat=p2&fields=metadata")]
    [InlineData("seat=P2&fields=metadata")]
    [InlineData("seat=p2&fields=metadata&fields=raw")]
    [InlineData("seat=p2&fields=inventory")]
    [InlineData("seat=%70%32&fields=metadata")]
    public void Explicit_unambiguous_seat_and_fields_are_required(string query) => Denied(new(Query: query), 400);

    [Fact]
    public void Seat_and_raw_scopes_are_explicit_and_not_inferred_from_authentication()
    {
        Denied(new(Query: "seat=p1&fields=metadata"));
        Denied(new(Query: "seat=p2&fields=raw"));
        _http.ReplaceGrant(new(Metadata: false));
        Denied(new());
    }

    [Fact]
    public void Metadata_redacts_embedded_P1_content_scope_and_tokens_and_is_passive()
    {
        var before = _cache.Read("p2", 10, _p2.ClockId, 1).Capture;
        var r = _http.Handle(new());
        var again = _http.Handle(new(Host: "127.0.0.1:8770"));
        Assert.Equal(200, r.Status);
        Assert.Equal(r.Body, again.Body);
        Assert.Equal(2, _reads);
        Assert.DoesNotContain(Canary, r.Body);
        Assert.DoesNotContain(_p2.Scope.FarmerAlias, r.Body);
        Assert.DoesNotContain(_p2.Scope.LoadId, r.Body);
        Assert.DoesNotContain(_p2.Prompt!.InstanceId, r.Body);
        Assert.Same(before, _cache.Read("p2", 10, _p2.ClockId, 1).Capture);
        using var body = JsonDocument.Parse(r.Body);
        Assert.Equal("redacted", body.RootElement.GetProperty("raw_status").GetString());
        Assert.Equal(10, body.RootElement.GetProperty("monotonic_ticks").GetInt64());
        Assert.False(body.RootElement.GetProperty("guarded_dispatch").GetBoolean());
        PrivateHeaders(r);
    }

    [Fact]
    public void Explicit_raw_scope_acknowledges_other_persons_content_and_revocation_removes_old_body()
    {
        _http.ReplaceGrant(new(Raw: true));
        Capture(1);
        var raw = _http.Handle(new(Query: "seat=p2&fields=raw"));
        Assert.Contains(Canary, raw.Body); // Seat isolation cannot sanitize arbitrary raw dialogue.
        _http.ReplaceGrant(new(Enabled: false));
        var disabled = _http.Handle(new(Query: "seat=p2&fields=raw"));
        Assert.Equal("{\"status\":\"disabled\"}", disabled.Body);
        _http.ReplaceGrant(new());
        Assert.DoesNotContain(Canary, _http.Handle(new()).Body);
    }

    [Fact]
    public void Disabled_and_discovery_are_static_and_ignore_retained_capture()
    {
        _http.ReplaceGrant(new(Enabled: false));
        Capture(0);
        Capture(1); // Retained data must not leak through disabled/discovery/error paths.
        var a = _http.Handle(new(Authorization: null));
        var b = _http.Handle(new(Authorization: null, Query: "seat=p1&fields=raw"));
        Assert.Equal(a.Body, b.Body);
        Assert.Equal(0, _reads);
        var d = _http.Handle(new(Authorization: null, Path: "/api/evidence/capabilities"));
        _cache.ReturnedToTitle();
        Assert.Equal(d.Body, _http.Handle(new(Authorization: null, Path: "/api/evidence/capabilities")).Body);
        Assert.DoesNotContain(Canary, d.Body);
        Assert.DoesNotContain(_p1.Scope.AdapterInstance, d.Body);
        PrivateHeaders(a);
        PrivateHeaders(d);
    }

    [Fact]
    public void Wrong_seat_cache_entry_is_unavailable_and_never_serialized()
    {
        var fake = new FakeEvidenceHttp(_ => new("captured", _p1, 0), () => { });
        var r = fake.Handle(new());
        Assert.Equal("{\"status\":\"unavailable\"}", r.Body);
        Assert.DoesNotContain(Canary, r.Body);
        PrivateHeaders(r);
    }

    [Fact]
    public void Request_budgets_errors_and_missing_route_never_fall_back_to_state_or_tools()
    {
        Denied(new(Host: new string('x', 129)), 400);
        Denied(new(Path: "/api/state"), 404);
        for (int i = 0; i < 65; i++) _http.Handle(new(Authorization: null));
        Denied(new(), 429);
    }
}
