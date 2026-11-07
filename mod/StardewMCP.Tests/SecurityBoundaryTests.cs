using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.Json;
using Xunit;

namespace StardewMCP.Tests;

// Acceptance tests for the proposed fixture policy, NOT evidence of listener security.
public class SecurityBoundaryTests
{
    private const string Initialize = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\"}";
    private const string Status = "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"status\",\"arguments\":{}}}";
    private static string Open(FakeSecurityBoundary p, string credential = "p2-a") =>
        p.Handle(new(Credential: credential, Body: Initialize)).Session!;
    private static object Effects(FakeSecurityBoundary p) =>
        (p.Contacts, p.ToolCalls, p.StateReads, p.SessionBreaks, p.ReplyDeadlineChanges,
            p.Queued, p.SessionCount, p.P1Role, p.P2Role, p.ClockReleased, p.TimedOut);
    private static void Denied(FakeSecurityBoundary p, BoundaryRequest r, int code, long now = 10)
    {
        var before = Effects(p);
        var reply = p.Handle(r, now);
        Assert.Equal(code, reply.Status);
        Assert.Equal("", reply.Body);
        Assert.Null(reply.Session);
        Assert.Equal("no-store", reply.Headers["Cache-Control"]);
        Assert.False(reply.Headers.ContainsKey("Access-Control-Allow-Origin"));
        Assert.Equal(before, Effects(p));
    }

    public static IEnumerable<object[]> Denials()
    {
        var r = new BoundaryRequest(Body: Status);
        yield return new object[] { r with { Credential = null }, 401 };
        yield return new object[] { r with { Credential = "wrong" }, 401 };
        foreach (string credential in new[] { "operator", "reader", "diagnostic" })
            yield return new object[] { r with { Credential = credential }, 403 };
        foreach (string path in new[] { "/mcp/p1", "/mcp", "/mcp/p3", "/mcp/P2", "/mcp/%70%32", "/unknown", "/api/state", "/api/control", "/api/feed", "/api/evidence" })
            yield return new object[] { r with { Path = path }, 404 };
        foreach (string host in new[] { "evil.invalid:8770", "localhost:80", "localhost:8770.evil.invalid", "::1:8770", "[::2]:8770", "localhost:8770,evil.invalid" })
            yield return new object[] { r with { Host = host }, 403 };
        foreach (string peer in new[] { "192.0.2.1", "::2", "not-an-ip" })
            yield return new object[] { r with { Peer = peer }, 403 };
        foreach (string origin in new[] { "https://evil.invalid", "null", "http://localhost:8770", "" })
            yield return new object[] { r with { Origin = origin }, 403 };
        foreach (string method in new[] { "GET", "PUT", "OPTIONS", "PATCH" })
            yield return new object[] { r with { Method = method }, 405 };
        foreach (string contentType in new[] { "text/plain", "application/x-www-form-urlencoded", "multipart/form-data" })
            yield return new object[] { r with { ContentType = contentType }, 415 };
        foreach (string query in new[] { "seat=p2&seat=p1", "token=p2-a", "seat=p2", "fields=raw" })
            yield return new object[] { r with { Query = query }, 400 };
        yield return new object[] { r with { DuplicateHeaders = true }, 400 };
        yield return new object[] { r with { Host = new string('x', 129) }, 400 };
        yield return new object[] { r with { Credential = new string('x', 129) }, 400 };
        yield return new object[] { r with { Session = new string('x', 129) }, 400 };
        yield return new object[] { r with { ReadMilliseconds = FakeSecurityBoundary.MaxReadMilliseconds + 1 }, 408 };
        yield return new object[] { r with { Disconnected = true }, 499 };
    }

    [Theory, MemberData(nameof(Denials))]
    public void Transport_and_grant_denials_precede_every_side_effect(object input, int status)
    {
        var p = new FakeSecurityBoundary();
        string session = Open(p);
        var request = (BoundaryRequest)input;
        Denied(p, request with { Session = request.Session ?? session }, status);
    }

    [Theory]
    [InlineData(false, 100)]
    [InlineData(true, 10)]
    public void Expired_and_revoked_credentials_fail_closed(bool revoked, long now)
    {
        var p = new FakeSecurityBoundary();
        string session = Open(p);
        p.Grants["p2-a"] = new(Revoked: revoked);
        Denied(p, new(Session: session, Body: Status), 401, now);
    }

    [Fact]
    public void Seat_grants_do_not_escalate_and_missing_configuration_does_not_enable_fallback()
    {
        var p = new FakeSecurityBoundary();
        p.Grants["p2-a"] = new(Seat: "p1");
        Denied(p, new(Body: Initialize), 403);
        p.Grants.Clear();
        Denied(p, new(Body: Initialize), 401);
    }

    [Theory]
    [InlineData("{")]
    [InlineData("null")]
    [InlineData("7")]
    [InlineData("[]")]
    [InlineData("[{}]")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\",\"method\":\"initialize\"}")]
    [InlineData("{\"jsonrpc\":\"1.0\",\"id\":1,\"method\":\"ping\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":{},\"method\":\"ping\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\",\"params\":[]}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"unknown\"}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"walk_to\",\"arguments\":{}}}")]
    [InlineData("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"status\",\"arguments\":{\"seat\":\"p1\"}}}")]
    public void Invalid_rpc_has_no_effects(string body)
    {
        var p = new FakeSecurityBoundary();
        Denied(p, new(Session: Open(p), Body: body), 400);
    }

    [Fact]
    public void Whole_batch_is_validated_before_accepting_any_work()
    {
        var p = new FakeSecurityBoundary();
        string session = Open(p);
        Denied(p, new(Session: session, Body: $"[{Status},{{}}]"), 400);
        Denied(p, new(Session: session, Body: $"[{Status},{Initialize}]"), 400);
        Denied(p, new(Session: session, Body: "[" + string.Join(",", Enumerable.Repeat(Status, FakeSecurityBoundary.MaxBatch + 1)) + "]"), 400);
    }

    [Fact]
    public void Sessions_require_initialization_and_belong_to_one_caller_even_with_the_same_grant()
    {
        var p = new FakeSecurityBoundary();
        Denied(p, new(Body: Status), 403);
        string a = Open(p), b = Open(p, "p2-b");
        Assert.NotEqual(a, b);
        Denied(p, new(Credential: "p2-b", Session: a, Body: Status), 403);
        Denied(p, new(Session: "stardew-p2", Body: Status), 403);
        Denied(p, new(Method: "DELETE", Credential: "p2-b", Session: a), 403);
        Assert.Equal(200, p.Handle(new(Method: "DELETE", Session: a)).Status);
        Denied(p, new(Session: a, Body: Status), 403);
        Assert.Equal(200, p.Handle(new(Credential: "p2-b", Session: b)).Status);
    }

    [Theory]
    [InlineData("initialize")]
    [InlineData("ping")]
    [InlineData("tools/list")]
    [InlineData("notifications/initialized")]
    public void Discovery_does_not_touch_contact_clock_deadlines_or_roles(string method)
    {
        var p = new FakeSecurityBoundary();
        string? session = method == "initialize" ? null : Open(p);
        var reply = p.Handle(new(Session: session, Body: $"{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"{method}\"}}"));
        Assert.Equal(method == "notifications/initialized" ? 202 : 200, reply.Status);
        Assert.Equal(0, p.Contacts + p.ToolCalls + p.StateReads + p.SessionBreaks + p.ReplyDeadlineChanges + p.Queued);
        Assert.True(p.ClockReleased);
        Assert.True(p.TimedOut);
        Assert.Equal("human", p.P1Role);
        Assert.Equal("ai", p.P2Role);
    }

    [Theory]
    [InlineData("epoch")]
    [InlineData("revoke")]
    [InlineData("rotate")]
    [InlineData("expire")]
    [InlineData("role")]
    [InlineData("inactive")]
    [InlineData("delete")]
    [InlineData("disconnect")]
    public void Queued_work_rechecks_ownership_grant_role_and_epoch_at_execution(string change)
    {
        var p = new FakeSecurityBoundary();
        string session = Open(p);
        Assert.Equal(200, p.Handle(new(Session: session, Body: Status)).Status);
        switch (change)
        {
            case "epoch": p.NewSaveEpoch(); break;
            case "revoke": p.Grants["p2-a"] = new(Revoked: true); break;
            case "rotate": p.Grants.Remove("p2-a"); p.Grants["replacement"] = new(); break;
            case "role": p.P2Role = "human"; break;
            case "inactive": p.P2Active = false; break;
            case "delete": p.Handle(new(Method: "DELETE", Session: session)); break;
        }
        var reply = p.ExecuteNext(now: change == "expire" ? 100 : 10, disconnected: change == "disconnect");
        Assert.Equal(403, reply.Status);
        Assert.Equal("", reply.Body);
        Assert.Equal(0, p.Contacts + p.ToolCalls + p.StateReads);
        Assert.Equal(0, p.Queued);
    }

    [Fact]
    public void Repeated_title_load_requires_new_sessions_even_for_the_same_caller()
    {
        var p = new FakeSecurityBoundary();
        for (int cycle = 0; cycle < 3; cycle++)
        {
            string old = Open(p);
            p.NewSaveEpoch();
            Denied(p, new(Session: old, Body: Status), 403);
            string current = Open(p);
            Assert.NotEqual(old, current);
            Assert.Equal(200, p.Handle(new(Session: current, Body: Status)).Status);
            var reply = p.ExecuteNext();
            using var body = JsonDocument.Parse(reply.Body);
            Assert.Equal(new[] { "seat", "status" }, body.RootElement.EnumerateObject().Select(x => x.Name));
            Assert.Equal("p2", body.RootElement.GetProperty("seat").GetString());
        }
        Assert.Equal(3, p.ToolCalls);
        Assert.Equal("human", p.P1Role);
    }

    [Fact]
    public void Body_limit_counts_utf8_bytes_and_accepts_the_exact_boundary()
    {
        var p = new FakeSecurityBoundary();
        string session = Open(p);
        var r = new BoundaryRequest(Session: session);
        string exact = r.Body.PadRight(FakeSecurityBoundary.MaxBodyBytes);
        Assert.Equal(200, p.Handle(r with { Body = exact, ReadMilliseconds = FakeSecurityBoundary.MaxReadMilliseconds }).Status);
        Denied(p, r with { Body = exact + " " }, 413);
        string unicode = new('ก', FakeSecurityBoundary.MaxBodyBytes / 3 + 1);
        Assert.True(unicode.Length < FakeSecurityBoundary.MaxBodyBytes);
        Assert.True(Encoding.UTF8.GetByteCount(unicode) > FakeSecurityBoundary.MaxBodyBytes);
        Denied(p, r with { Body = unicode }, 413);
    }

    [Fact]
    public void Queue_capacity_rejects_the_whole_batch_and_recovers_after_execution()
    {
        var p = new FakeSecurityBoundary();
        string session = Open(p);
        Assert.Equal(200, p.Handle(new(Session: session, Body: Status)).Status);
        Denied(p, new(Session: session, Body: $"[{Status},{Status}]"), 429);
        Assert.Equal(200, p.Handle(new(Session: session, Body: Status)).Status);
        Denied(p, new(Session: session, Body: Status), 429);
        Assert.Equal(200, p.ExecuteNext().Status);
        Assert.Equal(200, p.Handle(new(Session: session, Body: Status)).Status);
    }

    [Fact]
    public void Connection_and_request_budgets_apply_to_authorized_discovery_too()
    {
        var p = new FakeSecurityBoundary();
        string session = Open(p);
        p.Connections = FakeSecurityBoundary.MaxConnections;
        Denied(p, new(Session: session), 429);
        p.Connections--;
        for (int i = 1; i < FakeSecurityBoundary.MaxRequests; i++)
            Assert.Equal(200, p.Handle(new(Session: session)).Status);
        Denied(p, new(Session: session), 429);
    }

    [Theory]
    [InlineData("localhost:8770", "127.0.0.1")]
    [InlineData("127.0.0.1:8770", "127.0.0.1")]
    [InlineData("[::1]:8770", "::1")]
    public void Explicit_native_loopback_variants_are_accepted(string host, string peer)
    {
        var p = new FakeSecurityBoundary();
        Assert.Equal(200, p.Handle(new(Host: host, Peer: peer, Body: Initialize)).Status);
    }
}
