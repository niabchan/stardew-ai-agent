using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

// Tests real (but dormant) source-file parsing, with synthetic credentials and sessions.
// No HttpListener, game network, OpenAI request or AgentRuntime side effects.
public sealed class SunnyP2PreflightTests
{
    private const string Initialize = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"sunny\",\"version\":\"0.1\"}}}";
    private const string Status = "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"status\",\"arguments\":{}}}";
    private const string Say = "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"say\",\"arguments\":{\"text\":\"Hi\"}}}";
    private const string Ready = "{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"ping\"}";
    private const string Notification = "{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}";
    private const string Session = "opaque-session-1", Epoch = "host-epoch-1";
    private const string GameToken = "synthetic-game-token";

    private sealed class FakeAuthority : ISunnyP2PolicyAuthority
    {
        public int CredentialLookups, SessionLookups, MutationChecks;
        public bool Ready = true, C = true, O = true, FailSchema, ThrowCredential, ThrowSchema;
        public string Seat = "p2", CurrentSession = Session, CurrentEpoch = Epoch;
        public SunnyP2Principal? ResolveGameCredential(string rawBearer)
        {
            CredentialLookups++;
            if (ThrowCredential) throw new InvalidOperationException("synthetic credential store offline");
            return rawBearer == GameToken ? new("luna", Seat, C, O) : null;
        }
        public bool HumanP1AiP2ExternalBrainReady => Ready;
        public bool IsCurrentOwnerSession(string principalId, string session, string epoch)
        {
            SessionLookups++;
            return principalId == "luna" && CurrentSession == session && CurrentEpoch == epoch;
        }
        public bool ValidateMutationArguments(string name, JsonElement arguments)
        {
            MutationChecks++;
            if (ThrowSchema) throw new InvalidOperationException("synthetic schema missing");
            return !FailSchema && name == "say" && arguments.EnumerateObject().Count() == 1
                && arguments.TryGetProperty("text", out var text) && text.ValueKind == JsonValueKind.String;
        }
    }

    private static SunnyP2Request Request(string body = Status, bool initialized = true)
    {
        var headers = new List<KeyValuePair<string, string>> {
            new("Authorization", "Bearer " + GameToken),
            new("Content-Type", "application/json"),
            new("Accept", "application/json")
        };
        if (initialized)
        {
            headers.Add(new("Mcp-Session-Id", Session));
            headers.Add(new("X-Sunny-Save-Epoch", Epoch));
        }
        return new("POST", "/mcp/p2", "127.0.0.1:8770", "127.0.0.1", 8770, headers, Encoding.UTF8.GetBytes(body));
    }

    private static SunnyP2Request WithHeader(SunnyP2Request source, string key, string value)
    {
        var headers = source.Headers.ToList();
        headers.Add(new(key, value));
        return source with { Headers = headers };
    }
    private static SunnyP2Request ReplaceHeader(SunnyP2Request source, string name, string value)
    {
        var headers = source.Headers.Where(x => !x.Key.Equals(name, StringComparison.OrdinalIgnoreCase)).ToList();
        headers.Add(new(name, value));
        return source with { Headers = headers };
    }

    [Fact]
    public void Accepts_only_preflight_contract_not_actual_gameplay_admission()
    {
        var authority = new FakeAuthority();
        var init = SunnyP2Preflight.Evaluate(Request(Initialize, initialized: false), authority);
        Assert.True(init.Allowed);
        Assert.Equal(SunnyP2Operation.Initialize, init.Operation);
        Assert.False(init.MayMarkContact);
        Assert.Equal(0, authority.SessionLookups);
        var discovery = SunnyP2Preflight.Evaluate(Request(Ready), authority);
        Assert.Equal(SunnyP2Operation.Discovery, discovery.Operation);
        Assert.False(discovery.MayMarkContact);
        var status = SunnyP2Preflight.Evaluate(Request(Status), authority);
        Assert.Equal(SunnyP2Operation.Status, status.Operation);
        Assert.True(status.MayMarkContact);
        Assert.Equal("status", status.Tool);
        var mutation = SunnyP2Preflight.Evaluate(Request(Say), authority);
        Assert.Equal(SunnyP2Operation.Mutation, mutation.Operation);
        Assert.Equal("say", mutation.Tool);
        Assert.True(mutation.MayMarkContact);
        Assert.Equal(1, authority.MutationChecks);
        var notify = SunnyP2Preflight.Evaluate(Request(Notification), authority);
        Assert.Equal(SunnyP2Operation.Notification, notify.Operation);
        Assert.False(notify.MayMarkContact);
    }

    [Theory]
    [InlineData("localhost:8770", "127.0.0.1", 8770)]
    [InlineData("127.0.0.1:18770", "127.0.0.1", 18770)]
    public void Accepts_only_explicit_configured_loopback_host(string host, string peer, int port)
    {
        var decision = SunnyP2Preflight.Evaluate(Request(Ready) with { Host = host, PeerAddress = peer, Port = port }, new FakeAuthority());
        Assert.Equal(200, decision.Status);
    }

    [Theory]
    [InlineData("evil.invalid:8770", "127.0.0.1", 8770)]
    [InlineData("127.0.0.1:18770", "127.0.0.1", 8770)]
    [InlineData("127.0.0.2:8770", "127.0.0.1", 8770)]
    [InlineData("localhost:8770.evil.invalid", "127.0.0.1", 8770)]
    [InlineData("127.0.0.1:8770", "192.0.2.1", 8770)]
    [InlineData("127.0.0.1:8770", "not-ip", 8770)]
    [InlineData("[::1]:8770", "::1", 8770)] // requires separate reviewed listener binding
    public void Denies_wrong_authority_peer_and_unverified_ipv6(string host, string peer, int port)
    {
        var authority = new FakeAuthority();
        var decision = SunnyP2Preflight.Evaluate(Request(Ready) with { Host = host, PeerAddress = peer, Port = port }, authority);
        Assert.Equal(403, decision.Status);
        Assert.Equal(0, authority.CredentialLookups + authority.SessionLookups + authority.MutationChecks);
    }

    [Theory]
    [InlineData("/mcp", "POST", 404)]
    [InlineData("/mcp/p1", "POST", 404)]
    [InlineData("/mcp/p3", "POST", 404)]
    [InlineData("/mcp/p2/", "POST", 404)]
    [InlineData("/mcp/%70%32", "POST", 404)]
    [InlineData("/api/state", "POST", 404)]
    [InlineData("/mcp/p2", "GET", 405)]
    [InlineData("/mcp/p2", "OPTIONS", 405)]
    [InlineData("/mcp/p2", "PATCH", 405)]
    public void Denies_aliases_other_seats_and_methods_before_credential_lookup(string path, string method, int status)
    {
        var authority = new FakeAuthority();
        var decision = SunnyP2Preflight.Evaluate(Request(Say) with { Path = path, Method = method }, authority);
        Assert.Equal(status, decision.Status);
        Assert.Equal(0, authority.CredentialLookups);
        Assert.False(decision.MayMarkContact);
    }

    [Theory]
    [InlineData("https://evil.invalid")]
    [InlineData("http://localhost:8770")]
    [InlineData("null")]
    [InlineData("")]
    public void Native_origin_is_denied_even_if_same_origin(string origin)
    {
        var authority = new FakeAuthority();
        var result = SunnyP2Preflight.Evaluate(WithHeader(Request(Say), "Origin", origin), authority);
        Assert.Equal(403, result.Status);
        Assert.Equal(0, authority.CredentialLookups);
    }

    [Fact]
    public void Duplicate_case_variant_security_headers_and_control_characters_fail_closed()
    {
        var authority = new FakeAuthority();
        foreach (var headers in new[] {
            WithHeader(Request(Say), "authorization", "Bearer fake-credential"),
            WithHeader(Request(Say), "MCP-SESSION-ID", Session),
            WithHeader(Request(Say), "x-sunny-save-epoch", Epoch),
            WithHeader(Request(Say), "Origin", "x\nInjected: 1")
        })
        {
            Assert.Equal(400, SunnyP2Preflight.Evaluate(headers, authority).Status);
        }
        Assert.Equal(0, authority.CredentialLookups);
    }

    [Fact]
    public void Bad_credentials_and_absent_credentials_fail_closed_without_logging_secret()
    {
        var a = new FakeAuthority();
        foreach (var auth in new[] { "Basic some-password", "Bearer wrong-token", "Bearer bad token",
                                     "Bearer ", "Bearer fakesecret\r\nOrigin: https://evil" })
        {
            var outcome = SunnyP2Preflight.Evaluate(ReplaceHeader(Request(Say), "Authorization", auth), a);
            Assert.True(outcome.Status is 400 or 401);
            Assert.Equal(SunnyP2Operation.Denied, outcome.Operation);
            Assert.Null(outcome.Tool);
        }
        var missing = Request(Say) with {
            Headers = Request(Say).Headers.Where(h => h.Key != "Authorization").ToList()
        };
        Assert.Equal(401, SunnyP2Preflight.Evaluate(missing, a).Status);
        a.ThrowCredential = true;
        Assert.Equal(503, SunnyP2Preflight.Evaluate(Request(Say), a).Status);
    }

    [Fact]
    public void Independent_C_O_scopes_and_role_config_are_checked_before_tools()
    {
        var authority = new FakeAuthority { C = true, O = false };
        Assert.Equal(200, SunnyP2Preflight.Evaluate(Request(Initialize, false), authority).Status);
        Assert.Equal(403, SunnyP2Preflight.Evaluate(Request(Status), authority).Status);
        Assert.Equal(200, SunnyP2Preflight.Evaluate(Request(Say), authority).Status);
        authority.C = false; authority.O = true;
        Assert.Equal(403, SunnyP2Preflight.Evaluate(Request(Initialize, false), authority).Status);
        Assert.Equal(403, SunnyP2Preflight.Evaluate(Request(Status), authority).Status);
        authority.C = true; authority.O = true; authority.Seat = "p1";
        Assert.Equal(403, SunnyP2Preflight.Evaluate(Request(Say), authority).Status);
        authority.Seat = "p2"; authority.Ready = false;
        Assert.Equal(503, SunnyP2Preflight.Evaluate(Request(Say), authority).Status);
    }

    [Fact]
    public void Direct_tools_call_requires_valid_session_and_epoch()
    {
        var a = new FakeAuthority();
        Assert.Equal(409, SunnyP2Preflight.Evaluate(Request(Say, false), a).Status);
        Assert.Equal(409, SunnyP2Preflight.Evaluate(ReplaceHeader(Request(Say), "Mcp-Session-Id", "other-session"), a).Status);
        Assert.Equal(409, SunnyP2Preflight.Evaluate(ReplaceHeader(Request(Say), "X-Sunny-Save-Epoch", "other-epoch"), a).Status);
        Assert.Equal(409, SunnyP2Preflight.Evaluate(Request(Ready, false), a).Status);
        Assert.Equal(0, a.MutationChecks); // never validate/dispatch tools for missing owner
    }

    [Fact]
    public void Release_must_be_session_bound_and_does_not_retire_anything_itself()
    {
        var a = new FakeAuthority();
        var req = Request() with { Method = "DELETE", Body = Array.Empty<byte>() };
        var ok = SunnyP2Preflight.Evaluate(req, a);
        Assert.Equal(SunnyP2Operation.Retire, ok.Operation);
        Assert.False(ok.MayMarkContact);
        Assert.Equal(200, ok.Status); // policy admission, NOT retirement HTTP proof
        Assert.Equal(409, SunnyP2Preflight.Evaluate(req with {
            Headers = req.Headers.Where(x => x.Key != "Mcp-Session-Id").ToList()
        }, a).Status);
        Assert.Equal(400, SunnyP2Preflight.Evaluate(req with { Body = Encoding.UTF8.GetBytes("{}") }, a).Status);
        Assert.Equal(200, SunnyP2Preflight.Evaluate(Request(Status), a).Status); // no lease was retired!
    }

    [Theory]
    [InlineData("{")]
    [InlineData("null")]
    [InlineData("[]")]
    [InlineData("[{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\"},{}]")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\",\"method\":\"tools/call\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\",\"params\":{\"x\":1,\"x\":2}}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\",\"params\":{\"x\":NaN}}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\",\"params\":{\"x\":1e999}}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1.5,\"method\":\"ping\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1e2,\"method\":\"ping\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":true,\"method\":\"ping\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":null,\"method\":\"ping\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"unknown\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"say\",\"arguments\":{\"text\":\"Hi\",\"text\":\"Again\"}}}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"status\",\"arguments\":{\"seat\":\"p1\"}}}")]
    public void Strict_parser_denies_malformed_rpc_or_unsafe_batch(string body)
    {
        var a = new FakeAuthority();
        var result = SunnyP2Preflight.Evaluate(Request(body), a);
        Assert.Equal(400, result.Status);
        Assert.False(result.MayMarkContact);
        Assert.Equal(0, a.MutationChecks);
    }

    [Theory]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"unsupported\"}}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"unknown\":1}}")]
    public void Initialize_version_and_shape_must_match_profile(string body)
    {
        Assert.Equal(400, SunnyP2Preflight.Evaluate(Request(body, false), new FakeAuthority()).Status);
    }

    [Fact]
    public void Mutation_requires_server_supplied_schema_validator_not_unknown_tool_fallback()
    {
        var a = new FakeAuthority { FailSchema = true };
        Assert.Equal(400, SunnyP2Preflight.Evaluate(Request(Say), a).Status);
        Assert.Equal(1, a.MutationChecks);
        a.FailSchema = false; a.ThrowSchema = true;
        Assert.Equal(503, SunnyP2Preflight.Evaluate(Request(Say), a).Status);
        Assert.Equal(SunnyP2Operation.Denied, SunnyP2Preflight.Evaluate(Request(Say), a).Operation);
    }

    [Fact]
    public void Body_media_and_utf8_limits_are_hard_gates()
    {
        var a = new FakeAuthority();
        var req = Request(Say);
        Assert.Equal(415, SunnyP2Preflight.Evaluate(ReplaceHeader(req, "Content-Type", "text/plain"), a).Status);
        Assert.Equal(406, SunnyP2Preflight.Evaluate(ReplaceHeader(req, "Accept", "text/event-stream"), a).Status);
        Assert.Equal(413, SunnyP2Preflight.Evaluate(req with {
            Body = Encoding.UTF8.GetBytes(new string('a', SunnyP2Preflight.MaxBodyBytes + 1))
        }, a).Status);
        Assert.Equal(400, SunnyP2Preflight.Evaluate(req with { Body = new byte[] { 0xFF } }, a).Status);
        Assert.Equal(0, a.MutationChecks);
    }

    [Fact]
    public void Future_server_must_revalidate_under_owner_lock_after_positive_preflight()
    {
        var c = new FakeP2Coordinator();
        c.HostLoaded();
        c.SetRoles(true, true, true);
        c.SetGrants("luna", CoordinatorGrant.Control | CoordinatorGrant.Observe);
        var lease = Assert.IsType<CoordinatorLease>(c.Acquire("luna").Lease);
        var a = new FakeAuthority { CurrentSession = lease.Session, CurrentEpoch = lease.Epoch };
        var req = ReplaceHeader(ReplaceHeader(Request(Say), "Mcp-Session-Id", lease.Session),
                                "X-Sunny-Save-Epoch", lease.Epoch);
        var decision = SunnyP2Preflight.Evaluate(req, a);
        Assert.True(decision.Allowed);
        c.HostLoaded(); // real owner was fenced AFTER preflight but BEFORE enqueue
        Assert.Equal(CoordinatorDecision.Closed, c.Enqueue(lease, "attempt", CoordinatorLane.Action));
        Assert.Equal(0, c.ActionSteps);
        Assert.Null(c.Owner);
    }
}
