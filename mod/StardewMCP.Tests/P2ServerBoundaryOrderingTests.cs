using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

// Acceptance tests for a future side-effect ordering PLAN, not the installed
// HttpListener, AgentRuntime, SessionBreaks or WorldClock implementation.
public sealed class P2ServerBoundaryOrderingTests
{
    private const string Token = "synthetic-p2-game-token";
    private const string Init =
        "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1\"}}}";
    private const string Say =
        "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"say\",\"arguments\":{\"text\":\"Hello\"}}}";
    private const string Status =
        "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"status\",\"arguments\":{}}}";
    private const string Ping = "{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"ping\"}";
    private const string Initialized = "{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}";

    private static SunnyP2Request Request(string body, CoordinatorLease? lease = null,
        string token = Token, string method = "POST")
    {
        var headers = new List<KeyValuePair<string, string>> {
            new("Host", "127.0.0.1:8770"),
            new("Authorization", "Bearer " + token),
            new("Content-Type", "application/json"),
            new("Accept", "application/json")
        };
        if (lease != null)
        {
            headers.Add(new("Mcp-Session-Id", lease.Session));
            headers.Add(new("X-Sunny-Save-Epoch", lease.Epoch));
        }
        return new SunnyP2Request(method, "/mcp/p2", "127.0.0.1:8770", "127.0.0.1",
            8770, headers, method == "DELETE" ? Array.Empty<byte>() : Encoding.UTF8.GetBytes(body));
    }

    private static FakeP2ServerBoundary Prepared(CoordinatorGrant grants = CoordinatorGrant.Control | CoordinatorGrant.Observe)
    {
        var f = new FakeP2ServerBoundary();
        f.HostLoaded("host-A");
        f.SetRoles(p1Human: true, p2Ai: true, externalBrainNone: true);
        f.Provision(Token, "luna", grants);
        return f;
    }

    private static (FakeP2ServerBoundary Boundary, CoordinatorLease Owner) Open(
        CoordinatorGrant grants = CoordinatorGrant.Control | CoordinatorGrant.Observe)
    {
        var f = Prepared(grants);
        var reply = f.Handle(Request(Init));
        Assert.Equal(IntakeDisposition.Acquired, reply.Disposition);
        return (f, Assert.IsType<CoordinatorLease>(reply.Lease));
    }

    private static void NoToolEffects(FakeP2BoundarySnapshot s)
    {
        Assert.Equal(0, s.AcceptedToolContactMarks);
        Assert.Equal(0, s.AcceptedToolReplyBudgetSets);
        Assert.Equal(0, s.AcceptedActionStartLogs);
        Assert.Equal(0, s.AcceptedFreezeEligibilityEvents);
        Assert.False(s.FreezeEligible);
        Assert.Equal(0, s.FakeGameSteps);
    }

    [Fact]
    public void Authenticated_initialize_only_starts_fake_context_break_session_not_gameplay_contact()
    {
        var f = Prepared();
        var response = f.Handle(Request(Init));
        Assert.Equal(IntakeDisposition.Acquired, response.Disposition);
        var state = f.Snapshot();
        Assert.Equal(1, state.AcceptedSessionBreakStarts);
        NoToolEffects(state);

        var conflict = f.Handle(Request(Init));
        Assert.Equal(409, conflict.Status);
        Assert.Equal(state, f.Snapshot()); // denied initialize must not reset context history
    }

    [Fact]
    public void Discovery_and_initialized_notification_never_mark_contact_or_deadline()
    {
        var (f, lease) = Open();
        Assert.Equal(IntakeDisposition.Discovery, f.Handle(Request(Ping, lease)).Disposition);
        Assert.Equal(IntakeDisposition.Notification, f.Handle(Request(Initialized, lease)).Disposition);
        var state = f.Snapshot();
        Assert.Equal(1, state.AcceptedSessionBreakStarts);
        NoToolEffects(state);
        Assert.Equal(0, state.QueuedActions + state.QueuedObservations);
    }

    [Fact]
    public void Queue_commit_does_not_imply_start_or_effect()
    {
        var (f, lease) = Open();
        Assert.Equal(IntakeDisposition.Queued, f.Handle(Request(Say, lease), "say-1").Disposition);
        Assert.Equal(IntakeDisposition.Queued, f.Handle(Request(Status, lease), "status-1").Disposition);
        Assert.Equal(1, f.Snapshot().QueuedActions);
        Assert.Equal(1, f.Snapshot().QueuedObservations);
        NoToolEffects(f.Snapshot());

        Assert.Equal(CoordinatorWorkState.Running, f.TryStart(CoordinatorLane.Observation)!.State);
        Assert.Equal(CoordinatorWorkState.Running, f.TryStart(CoordinatorLane.Action)!.State);
        var started = f.Snapshot();
        Assert.Equal(2, started.AcceptedToolContactMarks);
        Assert.Equal(2, started.AcceptedToolReplyBudgetSets);
        Assert.Equal(1, started.AcceptedActionStartLogs);
        Assert.Equal(2, started.AcceptedFreezeEligibilityEvents);
        Assert.True(started.FreezeEligible);
        Assert.Equal(0, started.FakeGameSteps);
        Assert.True(f.FakeStep("status-1", lease));
        Assert.True(f.FakeStep("say-1", lease));
        Assert.Equal(2, f.Snapshot().FakeGameSteps); // two SYNTHETIC counters, no game effects
    }

    [Theory]
    [InlineData("origin")]
    [InlineData("wrong-host")]
    [InlineData("wrong-port")]
    [InlineData("default-p1-alias")]
    [InlineData("p1-seat")]
    [InlineData("invalid-json")]
    [InlineData("duplicate-host")]
    [InlineData("bad-protocol")]
    [InlineData("bad-credential")]
    [InlineData("query")]
    public void Rejected_requests_do_not_trigger_contact_deadline_logging_or_queue(string issue)
    {
        var (f, lease) = Open();
        var request = Request(Say, lease);
        var headers = request.Headers.ToList();
        switch (issue)
        {
            case "origin":
                headers.Add(new("Origin", "http://localhost:8770"));
                request = request with { Headers = headers };
                break;
            case "wrong-host": request = request with { Host = "evil.invalid:8770" }; break;
            case "wrong-port": request = request with { Port = 18770 }; break;
            case "default-p1-alias": request = request with { Path = "/mcp" }; break;
            case "p1-seat": request = request with { Path = "/mcp/p1" }; break;
            case "invalid-json": request = request with { Body = new byte[] { 0xff } }; break;
            case "duplicate-host":
                headers.Add(new("host", "127.0.0.1:8770"));
                request = request with { Headers = headers };
                break;
            case "bad-protocol":
                headers.Add(new("MCP-Protocol-Version", "2024-11-05"));
                request = request with { Headers = headers };
                break;
            case "bad-credential": request = Request(Say, lease, token: "unknown-bearer-token"); break;
            case "query": request = request with { RawQuery = "?reply_within=1200" }; break;
        }
        var before = f.Snapshot();
        Assert.Equal(IntakeDisposition.Denied, f.Handle(request, trustedAttemptId: "attempt").Disposition);
        Assert.Equal(before, f.Snapshot());
        Assert.Null(f.TryStart(CoordinatorLane.Action));
    }

    [Fact]
    public void Denied_initialize_cannot_update_context_session_or_freeze()
    {
        var f = Prepared();
        var request = Request(Init) with { Path = "/mcp/p1" };
        Assert.False(f.Handle(request).Accepted);
        Assert.Equal(0, f.Snapshot().AcceptedSessionBreakStarts);
        NoToolEffects(f.Snapshot());
        Assert.Null(f.Owner);
    }

    [Fact]
    public void Queued_action_revoked_before_start_has_no_contact_or_log()
    {
        var (f, lease) = Open();
        Assert.Equal(IntakeDisposition.Queued, f.Handle(Request(Say, lease), "queued-before-revoke").Disposition);
        f.Revoke(Token);
        Assert.Null(f.TryStart(CoordinatorLane.Action));
        var state = f.Snapshot();
        Assert.Equal(0, state.QueuedActions);
        NoToolEffects(state);
        Assert.False(f.FakeStep("queued-before-revoke", lease));
    }

    [Fact]
    public void Already_running_action_fenced_on_revoke_cannot_emit_further_fake_steps()
    {
        var (f, lease) = Open();
        f.Handle(Request(Say, lease), "walk");
        Assert.Equal(CoordinatorWorkState.Running, f.TryStart(CoordinatorLane.Action)!.State);
        Assert.True(f.FakeStep("walk", lease));
        var before = f.Snapshot();
        Assert.Equal(1, before.AcceptedActionStartLogs);
        Assert.True(before.FreezeEligible);
        f.Revoke(Token);
        var after = f.Snapshot();
        Assert.False(after.FreezeEligible);
        Assert.Equal(before.AcceptedActionStartLogs, after.AcceptedActionStartLogs);
        Assert.Equal(before.FakeGameSteps, after.FakeGameSteps);
        Assert.False(f.FakeStep("walk", lease));
        Assert.False(f.Finish("walk", lease));
        Assert.True(f.Quiesce("walk", outcomeKnown: false));
        Assert.False(f.ReconcileFromTrustedHarness("missing-operation"));
    }

    [Fact]
    public void Host_reload_purges_queued_work_and_resets_freeze_eligibility()
    {
        var (f, lease) = Open();
        f.Handle(Request(Say, lease), "began");
        f.TryStart(CoordinatorLane.Action);
        Assert.True(f.FakeStep("began", lease));
        f.Handle(Request(Say, lease), "queued");
        f.HostLoaded("host-B");
        Assert.Null(f.Owner);
        Assert.Null(f.TryStart(CoordinatorLane.Action));
        Assert.False(f.FakeStep("began", lease));
        Assert.False(f.Snapshot().FreezeEligible);
        Assert.Equal(1, f.Snapshot().AcceptedActionStartLogs); // lifetime historical counts
        Assert.Equal(1, f.Snapshot().FakeGameSteps);          // old synthetic work does not resume
        Assert.Equal(0, f.Snapshot().QueuedActions + f.Snapshot().QueuedObservations);
        Assert.False(f.Handle(Request(Init)).Accepted); // grants reset on true host reload
        Assert.Equal(1, f.Snapshot().AcceptedSessionBreakStarts);
        Assert.True(f.Quiesce("began", outcomeKnown: false));
    }

    [Fact]
    public void Duplicate_host_callback_and_guest_join_do_not_reset_valid_contact()
    {
        var (f, lease) = Open();
        f.Handle(Request(Say, lease), "run");
        f.TryStart(CoordinatorLane.Action);
        var before = f.Snapshot();
        f.HostLoaded("host-A");
        f.GuestLoaded();
        Assert.Equal(before, f.Snapshot());
        Assert.Equal(lease, f.Owner);
        Assert.True(f.FakeStep("run", lease));
    }

    [Fact]
    public void Read_only_C_only_grant_is_rejected_without_contact_but_C_mutation_can_start()
    {
        var (f, lease) = Open(CoordinatorGrant.Control);
        Assert.Equal(403, f.Handle(Request(Status, lease), "read-denied").Status);
        NoToolEffects(f.Snapshot());
        Assert.Equal(IntakeDisposition.Queued, f.Handle(Request(Say, lease), "speak").Disposition);
        NoToolEffects(f.Snapshot());
        Assert.Equal(CoordinatorWorkState.Running, f.TryStart(CoordinatorLane.Action)!.State);
        Assert.Equal(1, f.Snapshot().AcceptedToolContactMarks);
    }

    [Fact]
    public void Unverified_delete_never_proves_retirement_or_changes_contact_history()
    {
        var (f, lease) = Open();
        f.Handle(Request(Say, lease), "bedtime");
        f.TryStart(CoordinatorLane.Action);
        Assert.True(f.FakeStep("bedtime", lease, now: 1200));
        var before = f.Snapshot();
        var response = f.Handle(Request("", lease, method: "DELETE"), now: 1200);
        Assert.Equal(IntakeDisposition.RetirementUnverified, response.Disposition);
        Assert.Equal(202, response.Status); // FAKE disposition, never a wire proof
        var after = f.Snapshot();
        Assert.Equal(before.AcceptedToolContactMarks, after.AcceptedToolContactMarks);
        Assert.Equal(before.AcceptedActionStartLogs, after.AcceptedActionStartLogs);
        Assert.False(after.FreezeEligible);
        Assert.False(f.FakeStep("bedtime", lease, now: 1200));
        Assert.True(f.Quiesce("bedtime", outcomeKnown: false));
        // Local fake quiescence may permit server-side lease re-acquisition;
        // that is NOT permission for the PR #26 client to retry unverified DELETE.
        var newLease = Assert.IsType<CoordinatorLease>(f.Handle(Request(Init)).Lease);
        Assert.False(f.Handle(Request(Say, newLease), "blind-retry").Accepted);
        // Existing unknown-effect barrier and independent client fence both matter.
    }

    [Fact]
    public void Denial_after_positive_snapshot_cannot_start_contact_or_logs()
    {
        var (f, lease) = Open();
        var reply = f.Handle(Request(Say, lease), "stale",
            betweenPhases: () => f.Revoke(Token));
        Assert.False(reply.Accepted);
        Assert.Null(f.TryStart(CoordinatorLane.Action));
        NoToolEffects(f.Snapshot());
    }

    [Fact]
    public void Noop_discovery_cannot_rearm_freeze_or_renew_provisional_owner()
    {
        var (f, lease) = Open();
        Assert.Equal(IntakeDisposition.Discovery, f.Handle(Request(Ping, lease), now: 59).Disposition);
        Assert.False(f.Handle(Request(Ping, lease), now: 60).Accepted);
        Assert.Null(f.Owner);
        NoToolEffects(f.Snapshot());
    }

    [Fact]
    public async Task Concurrent_invalid_requests_cannot_trigger_request_side_effects()
    {
        var (f, lease) = Open();
        var bad = Request(Say, lease) with { Path = "/mcp/p1" };
        var replies = new ConcurrentBag<IntakeReply>();
        await Task.WhenAll(Enumerable.Range(0, 64).Select(_ => Task.Run(() =>
            replies.Add(f.Handle(bad, "bad")))));
        Assert.Equal(64, replies.Count);
        Assert.All(replies, reply => Assert.Equal(IntakeDisposition.Denied, reply.Disposition));
        Assert.Equal(0, f.Snapshot().QueuedActions + f.Snapshot().QueuedObservations);
        NoToolEffects(f.Snapshot());
    }

    [Fact]
    public void Started_action_on_role_change_is_fenced_and_new_context_session_requires_new_init()
    {
        var (f, lease) = Open();
        f.Handle(Request(Say, lease), "walk");
        f.TryStart(CoordinatorLane.Action);
        f.SetRoles(true, true, false);
        Assert.False(f.Snapshot().FreezeEligible);
        Assert.False(f.FakeStep("walk", lease));
        Assert.False(f.Handle(Request(Say, lease), "late").Accepted);
        Assert.True(f.Quiesce("walk", outcomeKnown: false));
        f.SetRoles(true, true, true);
        var newLease = Assert.IsType<CoordinatorLease>(f.Handle(Request(Init)).Lease);
        Assert.NotEqual(lease, newLease);
        Assert.Equal(2, f.Snapshot().AcceptedSessionBreakStarts);
        Assert.False(f.Handle(Request(Say, newLease), "blind-retry").Accepted); // unresolved effect
    }
}
