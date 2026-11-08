using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

// End-to-end FAKE preflight + atomic fake admission checks, with zero network/game I/O.
public sealed class P2AtomicIntakeTests
{
    private const string Token = "synthetic-p2-game-token";
    private const string Init = "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-06-18\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1\"}}}";
    private const string Status = "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"status\",\"arguments\":{}}}";
    private const string Say = "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"say\",\"arguments\":{\"text\":\"Hello\"}}}";
    private const string Ping = "{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"ping\"}";
    private const string Notify = "{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}";

    private static SunnyP2Request Request(string body, CoordinatorLease? lease = null,
        string token = Token, string method = "POST")
    {
        var headers = new List<KeyValuePair<string, string>> {
            new("Host", "127.0.0.1:8770"),
            new("Authorization", "Bearer " + token),
            new("Accept", "application/json"),
            new("Content-Type", "application/json")
        };
        if (lease is not null)
        {
            headers.Add(new("Mcp-Session-Id", lease.Session));
            headers.Add(new("X-Sunny-Save-Epoch", lease.Epoch));
        }
        return new(method, "/mcp/p2", "127.0.0.1:8770", "127.0.0.1", 8770,
            headers, method == "DELETE" ? Array.Empty<byte>() : Encoding.UTF8.GetBytes(body));
    }

    private static FakeP2AtomicIntake Prepare()
    {
        var f = new FakeP2AtomicIntake();
        f.HostLoaded("host-transition-A");
        f.SetRoles(true, true, true);
        f.Provision(Token, "luna", CoordinatorGrant.Control | CoordinatorGrant.Observe);
        return f;
    }

    private static (FakeP2AtomicIntake Intake, CoordinatorLease Lease) Open()
    {
        var f = Prepare();
        var reply = f.Admit(Request(Init));
        Assert.Equal(200, reply.Status);
        Assert.Equal(IntakeDisposition.Acquired, reply.Disposition);
        return (f, Assert.IsType<CoordinatorLease>(reply.Lease));
    }

    [Fact]
    public void Preflight_plus_atomic_admission_keeps_discovery_side_effect_free()
    {
        var (f, lease) = Open();
        Assert.Equal(IntakeDisposition.Discovery, f.Admit(Request(Ping, lease)).Disposition);
        Assert.Equal(IntakeDisposition.Notification, f.Admit(Request(Notify, lease)).Disposition);
        Assert.Equal(0, f.PendingActions + f.PendingObservations + f.EffectSteps);

        var read = f.Admit(Request(Status, lease), trustedAttemptId: "read-1");
        var action = f.Admit(Request(Say, lease), trustedAttemptId: "action-1");
        Assert.Equal(IntakeDisposition.Queued, read.Disposition);
        Assert.Equal(IntakeDisposition.Queued, action.Disposition);
        Assert.Equal(1, f.PendingActions);
        Assert.Equal(1, f.PendingObservations);
        Assert.Equal(0, f.EffectSteps); // even accepted work is not a game effect
        Assert.Equal(CoordinatorWorkState.Running, f.Start(CoordinatorLane.Action)!.State);
        Assert.Equal(CoordinatorWorkState.Running, f.Start(CoordinatorLane.Observation)!.State);
        Assert.True(f.Step("action-1", lease));
        Assert.True(f.Step("read-1", lease));
        Assert.True(f.Finish("action-1", lease));
        Assert.True(f.Finish("read-1", lease));
        Assert.Equal(2, f.EffectSteps); // ONLY synthetic counter ticks
    }

    [Fact]
    public void Concurrent_initialize_reserves_exactly_one_P2_lease()
    {
        var f = Prepare();
        f.Provision("synthetic-rival-token", "rival", CoordinatorGrant.Control);
        var results = new ConcurrentBag<IntakeReply>();
        Parallel.For(0, 64, i => results.Add(f.Admit(Request(Init, token: i % 2 == 0
            ? Token : "synthetic-rival-token"))));
        Assert.Equal(64, results.Count);
        Assert.Single(results.Where(x => x.Disposition == IntakeDisposition.Acquired));
        Assert.Equal(63, results.Count(x => x.Status == 409));
        Assert.NotNull(f.Owner);
        Assert.Equal(0, f.PendingActions + f.PendingObservations + f.EffectSteps);
    }

    [Fact]
    public void Concurrent_mutations_never_exceed_atomic_action_queue_budget()
    {
        var (f, lease) = Open();
        var results = new ConcurrentBag<IntakeReply>();
        Parallel.For(0, 64, i =>
            results.Add(f.Admit(Request(Say, lease), trustedAttemptId: "attempt-" + i)));
        Assert.Equal(2, results.Count(x => x.Disposition == IntakeDisposition.Queued));
        Assert.Equal(62, results.Count(x => x.Status == 429));
        Assert.Equal(2, f.PendingActions);
        Assert.Equal(0, f.EffectSteps);
    }

    [Fact]
    public void Trusted_attempt_claim_is_required_and_cannot_be_reused()
    {
        var (f, lease) = Open();
        Assert.Equal(400, f.Admit(Request(Say, lease)).Status);
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Say, lease), "claim-1").Disposition);
        Assert.Equal(409, f.Admit(Request(Say, lease), "claim-1").Status);
        Assert.Equal(1, f.PendingActions);
        Assert.Equal(0, f.EffectSteps);
    }

    [Theory]
    [InlineData("origin")]
    [InlineData("invalid-host")]
    [InlineData("p1")]
    [InlineData("bad-json")]
    [InlineData("missing-bearer")]
    [InlineData("wrong-instance-port")]
    [InlineData("fallback")]
    [InlineData("duplicate-host")]
    [InlineData("wrong-token")]
    [InlineData("malformed-json")]
    public void Denied_preflight_never_reaches_coordinator_queue(string caseName)
    {
        var (f, lease) = Open();
        var req = Request(Say, lease);
        var headers = req.Headers.ToList();
        switch (caseName)
        {
            case "fallback": req = req with { Path = "/mcp" }; break;
            case "duplicate-host":
                headers.Add(new("host", req.Host));
                req = req with { Headers = headers };
                break;
            case "wrong-token": req = Request(Say, lease, token: "synthetic-wrong-token"); break;
            case "malformed-json": req = req with { Body = Encoding.UTF8.GetBytes("{") }; break;
            case "origin":
                headers.Add(new("Origin", "https://evil.invalid"));
                req = req with { Headers = headers };
                break;
            case "invalid-host":
                req = req with { Host = "evil.invalid:8770" };
                break;
            case "p1":
                req = req with { Path = "/mcp/p1" };
                break;
            case "bad-json":
                req = req with { Body = new byte[] { 0xff } };
                break;
            case "missing-bearer":
                req = req with { Headers = headers.Where(x => x.Key != "Authorization").ToList() };
                break;
            case "wrong-instance-port":
                req = req with { Port = 18770 };
                break;
        }
        bool reachedCommit = false;
        var response = f.Admit(req, trustedAttemptId: "bad-attempt",
            betweenPhases: () => reachedCommit = true);
        Assert.False(reachedCommit);
        Assert.False(response.Accepted);
        Assert.Equal(IntakeDisposition.Denied, response.Disposition);
        Assert.Equal(0, f.PendingActions + f.PendingObservations + f.EffectSteps);
    }

    [Fact]
    public void Host_reload_between_preflight_and_commit_cannot_enqueue_stale_action()
    {
        var (f, lease) = Open();
        var response = f.Admit(Request(Say, lease), "stale-operation",
            betweenPhases: () => f.HostLoaded("host-transition-B"));
        Assert.False(response.Accepted);
        Assert.Null(f.Owner);
        Assert.Equal(0, f.PendingActions + f.PendingObservations + f.EffectSteps);
        Assert.Equal(401, f.Admit(Request(Init)).Status); // epoch requires reprovisioning
        f.SetRoles(true, true, true);
        f.Provision(Token, "luna", CoordinatorGrant.Control | CoordinatorGrant.Observe);
        var next = Assert.IsType<CoordinatorLease>(f.Admit(Request(Init)).Lease);
        Assert.NotEqual(lease.Epoch, next.Epoch);
        Assert.Equal(409, f.Admit(Request(Say, lease), "stale-reuse").Status);
    }

    [Theory]
    [InlineData("revoke")]
    [InlineData("remove-C")]
    [InlineData("remove-O")]
    [InlineData("role")]
    [InlineData("title")]
    public void Changes_after_positive_preflight_are_rechecked_before_commit(string change)
    {
        var (f, lease) = Open();
        bool observation = change == "remove-O";
        var req = Request(observation ? Status : Say, lease);
        var response = f.Admit(req, "late", betweenPhases: () =>
        {
            switch (change)
            {
                case "revoke": f.Revoke(Token); break;
                case "remove-C": f.ChangeGrants(Token, CoordinatorGrant.Observe); break;
                case "remove-O": f.ChangeGrants(Token, CoordinatorGrant.Control); break;
                case "role": f.SetRoles(true, true, false); break;
                case "title": f.ReturnedToTitle(); break;
            }
        });
        Assert.False(response.Accepted);
        Assert.Equal(0, f.PendingActions + f.PendingObservations + f.EffectSteps);
        if (change == "remove-O")
        {
            Assert.Equal(lease, f.Owner); // C retains ownership
            Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Say, lease), "still-C").Disposition);
        }
        else Assert.Null(f.Owner);
    }

    [Fact]
    public void Duplicate_host_callback_and_guest_join_keep_existing_lease()
    {
        var (f, lease) = Open();
        f.HostLoaded("host-transition-A"); // same true-host transition repeated
        f.GuestSaveLoaded(); // farmhand event is not a new host epoch
        Assert.Equal(lease.Epoch, f.Epoch);
        Assert.Equal(lease, f.Owner);
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Say, lease), "still-owner").Disposition);
    }

    [Fact]
    public void Failed_owner_or_observation_grants_never_enable_P1_automation()
    {
        var f = new FakeP2AtomicIntake();
        f.HostLoaded();
        f.SetRoles(p1Human: false, p2Ai: true, externalBrainNone: true);
        f.Provision(Token, "luna", CoordinatorGrant.Control | CoordinatorGrant.Observe);
        Assert.False(f.Admit(Request(Init)).Accepted);
        f.SetRoles(true, true, true);
        f.ChangeGrants(Token, CoordinatorGrant.Observe);
        Assert.Equal(403, f.Admit(Request(Init)).Status); // Observe-only cannot acquire
        f.ChangeGrants(Token, CoordinatorGrant.Control);
        var lease = Assert.IsType<CoordinatorLease>(f.Admit(Request(Init)).Lease);
        Assert.Equal(403, f.Admit(Request(Status, lease), "read-forbidden").Status);
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Say, lease), "C-allowed").Disposition);
    }

    [Fact]
    public void Fake_discovery_does_not_renew_expired_provisional_lease()
    {
        var (f, lease) = Open();
        Assert.Equal(IntakeDisposition.Discovery, f.Admit(Request(Ping, lease), now: 59).Disposition);
        Assert.False(f.Admit(Request(Ping, lease), now: 60).Accepted);
        Assert.Null(f.Owner);
        Assert.Equal(0, f.EffectSteps);
    }

    [Fact]
    public void Retirement_remains_unverified_and_cannot_infer_unknown_action_result()
    {
        var (f, lease) = Open();
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Say, lease), "walk").Disposition);
        Assert.Equal(CoordinatorWorkState.Running, f.Start(CoordinatorLane.Action)!.State);
        Assert.True(f.Step("walk", lease)); // synthetic prior partial effect
        var delete = f.Admit(Request("", lease, method: "DELETE"));
        Assert.Equal(IntakeDisposition.RetirementUnverified, delete.Disposition);
        Assert.Equal(202, delete.Status); // fixture disposition only, NOT HTTP retirement proof
        Assert.Equal(1, f.RunningCount);
        Assert.False(f.Step("walk", lease));
        Assert.False(f.Admit(Request(Init)).Accepted); // running cleanup blocks successor
        Assert.True(f.Quiesce("walk", outcomeKnown: false));
        Assert.Equal(1, f.UnresolvedCount);
        var next = Assert.IsType<CoordinatorLease>(f.Admit(Request(Init)).Lease);
        Assert.Equal(409, f.Admit(Request(Say, next), "blind-retry").Status);
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Status, next), "read-to-reconcile").Disposition);
        Assert.True(f.ReconcileFromOperator("walk")); // trusted fake hook, not live API
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Say, next), "reconciled-action").Disposition);
    }

    [Fact]
    public void New_coordinator_incarnation_rejects_stale_session_and_epoch()
    {
        var (_, oldLease) = Open();
        var (fresh, newLease) = Open();
        Assert.NotEqual(oldLease.Epoch, newLease.Epoch);
        var stale = fresh.Admit(Request(Say, oldLease), trustedAttemptId: "stale");
        Assert.False(stale.Accepted);
        Assert.Equal(0, fresh.PendingActions + fresh.PendingObservations + fresh.EffectSteps);
        Assert.Equal(newLease, fresh.Owner);
    }

    [Theory]
    [InlineData("revoke")]
    [InlineData("reload")]
    [InlineData("title")]
    [InlineData("role")]
    [InlineData("rebind")]
    public async Task Invalidation_racing_with_enqueues_has_no_post_invalidation_accepted_effect(string change)
    {
        for (int iteration = 0; iteration < 16; iteration++)
        {
            var (f, lease) = Open();
            using var start = new Barrier(2);
            var replies = new ConcurrentBag<IntakeReply>();
            await Task.WhenAll(
                Task.Run(() =>
                {
                    start.SignalAndWait();
                    switch (change)
                    {
                        case "reload": f.HostLoaded("raced-load"); break;
                        case "title": f.ReturnedToTitle(); break;
                        case "role": f.SetRoles(true, true, false); break;
                        case "rebind": f.Provision(Token, "rival", CoordinatorGrant.Control); break;
                        default: f.Revoke(Token); break;
                    }
                }),
                Task.Run(() =>
                {
                    start.SignalAndWait();
                    replies.Add(f.Admit(Request(Say, lease), "raced"));
                }));
            Assert.Single(replies);
            Assert.Null(f.Owner);
            Assert.Equal(0, f.EffectSteps);
            Assert.Null(f.Start(CoordinatorLane.Action)); // if admitted before revoke, purge wins
            Assert.Equal(0, f.PendingActions + f.PendingObservations);
            Assert.False(f.Admit(Request(Say, lease), "late").Accepted);
        }
    }

    [Fact]
    public void Queue_capacity_and_rejected_discovery_cannot_touch_game_counters()
    {
        var (f, lease) = Open();
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Status, lease), "r1").Disposition);
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Status, lease), "r2").Disposition);
        Assert.Equal(429, f.Admit(Request(Status, lease), "r3").Status);
        Assert.Equal(0, f.EffectSteps);
        var bad = Request(Ping, lease) with { RawQuery = "?breaks=1" };
        Assert.Equal(400, f.Admit(bad).Status);
        Assert.Equal(2, f.PendingObservations);
        Assert.Equal(0, f.EffectSteps);
    }

    [Theory]
    [InlineData("identity")]
    [InlineData("same-identity")]
    [InlineData("grants-ABA")]
    [InlineData("roles-ABA")]
    [InlineData("reload")]
    public void Initialize_snapshot_cannot_cross_authority_generation(string change)
    {
        var f = Prepare();
        var reply = f.Admit(Request(Init), betweenPhases: () =>
        {
            switch (change)
            {
                case "identity": f.Provision(Token, "rival", CoordinatorGrant.Control); break;
                case "same-identity": f.Provision(Token, "luna", CoordinatorGrant.Control | CoordinatorGrant.Observe); break;
                case "grants-ABA":
                    f.ChangeGrants(Token, CoordinatorGrant.Control);
                    f.ChangeGrants(Token, CoordinatorGrant.Control | CoordinatorGrant.Observe);
                    break;
                case "roles-ABA":
                    f.SetRoles(true, true, false);
                    f.SetRoles(true, true, true);
                    break;
                case "reload":
                    f.HostLoaded("reload");
                    f.SetRoles(true, true, true);
                    f.Provision(Token, "luna", CoordinatorGrant.Control | CoordinatorGrant.Observe);
                    break;
            }
        });
        Assert.False(reply.Accepted);
        Assert.Null(f.Owner);
        Assert.Equal(0, f.PendingActions + f.PendingObservations + f.EffectSteps);
        Assert.Equal(IntakeDisposition.Acquired, f.Admit(Request(Init)).Disposition);
    }

    [Fact]
    public void Credential_rebinding_fences_old_principal_work_and_preserves_unknown_barrier()
    {
        var (f, lease) = Open();
        f.Admit(Request(Say, lease), "running");
        f.Start(CoordinatorLane.Action);
        Assert.True(f.Step("running", lease));
        f.Admit(Request(Say, lease), "queued");
        f.Provision(Token, "rival", CoordinatorGrant.Control | CoordinatorGrant.Observe);
        Assert.Null(f.Owner);
        Assert.Equal(0, f.PendingActions);
        Assert.False(f.Step("running", lease));
        Assert.False(f.Finish("running", lease));
        Assert.False(f.Admit(Request(Init)).Accepted);
        Assert.True(f.Quiesce("running", outcomeKnown: false));
        var next = Assert.IsType<CoordinatorLease>(f.Admit(Request(Init)).Lease);
        Assert.Equal(409, f.Admit(Request(Say, next), "new").Status);
        Assert.Equal(1, f.UnresolvedCount);
    }

    [Fact]
    public void Principal_aliases_cannot_restore_revoked_observation_claims()
    {
        var (f, lease) = Open();
        f.Provision("synthetic-alias", "luna", CoordinatorGrant.Control | CoordinatorGrant.Observe);
        f.Admit(Request(Status, lease), "running-read");
        f.Start(CoordinatorLane.Observation);
        f.Admit(Request(Status, lease), "pending-read");
        f.Admit(Request(Say, lease), "pending-action");
        f.ChangeGrants(Token, CoordinatorGrant.Control);
        Assert.Equal(lease, f.Owner);
        Assert.Equal(0, f.PendingObservations);
        Assert.Equal(1, f.PendingActions);
        Assert.False(f.Step("running-read", lease));
        Assert.False(f.Finish("running-read", lease));
        Assert.Equal(403, f.Admit(Request(Status, lease, token: "synthetic-alias"), "alias-read").Status);
        f.ChangeGrants("synthetic-alias", CoordinatorGrant.Control | CoordinatorGrant.Observe);
        Assert.False(f.Step("running-read", lease)); // restoring O cannot revive fenced work
        f.Revoke(Token);
        Assert.Equal(401, f.Admit(Request(Init, token: "synthetic-alias")).Status);
        Assert.Null(f.Owner);
        Assert.Equal(0, f.PendingActions);
    }

    [Fact]
    public void Same_principal_lost_initialize_reply_has_no_recovery_takeover()
    {
        var f = Prepare();
        var replies = new ConcurrentBag<IntakeReply>();
        Parallel.For(0, 64, _ => replies.Add(f.Admit(Request(Init))));
        Assert.Single(replies.Where(r => r.Disposition == IntakeDisposition.Acquired));
        Assert.Equal(63, replies.Count(r => r.Status == 409));
        Assert.Equal(409, f.Admit(Request(Init), now: 59).Status);
        Assert.Equal(IntakeDisposition.Acquired, f.Admit(Request(Init), now: 60).Disposition);
    }

    [Fact]
    public void Active_discovery_never_renews_but_running_action_pins_lease()
    {
        var (f, lease) = Open();
        f.Admit(Request(Say, lease), "bedtime");
        f.Start(CoordinatorLane.Action);
        Assert.True(f.Step("bedtime", lease, now: 1200));
        Assert.Equal(IntakeDisposition.Discovery, f.Admit(Request(Ping, lease), now: 1200).Disposition);
        Assert.True(f.Finish("bedtime", lease, now: 1200));
        Assert.Equal(IntakeDisposition.Discovery, f.Admit(Request(Ping, lease), now: 1379).Disposition);
        Assert.False(f.Admit(Request(Ping, lease), now: 1380).Accepted);
        Assert.Null(f.Owner);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Reload_purges_both_queues_and_keeps_claim_history_and_unknown_effects(bool roleOnly)
    {
        var (f, lease) = Open();
        f.Admit(Request(Say, lease), "started");
        f.Start(CoordinatorLane.Action);
        f.Step("started", lease);
        f.Admit(Request(Say, lease), "queued-action");
        f.Admit(Request(Status, lease), "queued-read");
        if (roleOnly) { f.SetRoles(true, true, false); f.SetRoles(true, true, true); }
        else { f.HostLoaded("next-world"); f.SetRoles(true, true, true); f.Provision(Token, "luna", CoordinatorGrant.Control | CoordinatorGrant.Observe); }
        Assert.Equal(0, f.PendingActions + f.PendingObservations);
        Assert.False(f.Step("started", lease));
        Assert.True(f.Quiesce("started", outcomeKnown: true));
        var next = Assert.IsType<CoordinatorLease>(f.Admit(Request(Init)).Lease);
        Assert.Equal(409, f.Admit(Request(Say, next), "fresh").Status);
        Assert.True(f.ReconcileFromOperator("started"));
        Assert.Equal(409, f.Admit(Request(Say, next), "queued-action").Status);
        Assert.Equal(409, f.Admit(Request(Status, next), "queued-read").Status);
        Assert.Equal(IntakeDisposition.Queued, f.Admit(Request(Say, next), "fresh").Disposition);
    }
}
