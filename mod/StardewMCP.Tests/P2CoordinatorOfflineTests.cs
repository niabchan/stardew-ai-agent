using System;
using System.Collections.Concurrent;
using System.Linq;
using System.Threading.Tasks;
using Xunit;

namespace StardewMCP.Tests;

// Pure fixture tests only: neither an authenticated HTTP server nor Stardew game logic.
public sealed class P2CoordinatorOfflineTests
{
    private static (FakeP2Coordinator Coordinator, CoordinatorLease Owner) Open()
    {
        var c = new FakeP2Coordinator();
        c.HostLoaded();
        c.SetRoles(p1Human: true, p2Ai: true, externalBrainNone: true);
        c.SetGrants("luna", CoordinatorGrant.Control | CoordinatorGrant.Observe);
        var result = c.Acquire("luna");
        Assert.Equal(CoordinatorDecision.Accepted, result.Decision);
        return (c, Assert.IsType<CoordinatorLease>(result.Lease));
    }

    [Fact]
    public void Concurrent_initialize_is_atomic_and_never_grants_two_p2_owners()
    {
        var c = new FakeP2Coordinator();
        c.HostLoaded();
        c.SetRoles(true, true, true);
        c.SetGrants("luna", CoordinatorGrant.Control);
        c.SetGrants("other", CoordinatorGrant.Control);
        var results = new ConcurrentBag<CoordinatorAcquisition>();

        Parallel.For(0, 64, index => results.Add(c.Acquire(index % 2 == 0 ? "luna" : "other")));
        Assert.Equal(64, results.Count);
        Assert.Single(results.Where(r => r.Decision == CoordinatorDecision.Accepted));
        Assert.Equal(63, results.Count(r => r.Decision == CoordinatorDecision.Conflict));
        Assert.NotNull(c.Owner);
        Assert.Equal(results.Single(r => r.Decision == CoordinatorDecision.Accepted).Lease, c.Owner);
        Assert.Null(c.Acquire("luna").Lease); // same-principal initialize is not takeover
    }

    [Fact]
    public void P1_must_remain_human_and_p2_must_be_ai_without_built_in_brain()
    {
        var c = new FakeP2Coordinator();
        c.SetGrants("luna", CoordinatorGrant.Control);
        Assert.Equal(CoordinatorDecision.Closed, c.Acquire("luna").Decision);
        c.HostLoaded();
        foreach (var (p1, p2, none) in new[] { (false, true, true), (true, false, true),
                                                (true, true, false), (false, false, false) })
        {
            c.SetRoles(p1, p2, none);
            Assert.Equal(CoordinatorDecision.Closed, c.Acquire("luna").Decision);
        }
        c.SetRoles(true, true, true);
        Assert.Equal(CoordinatorDecision.Accepted, c.Acquire("luna").Decision);
    }

    [Fact]
    public void O_only_cannot_acquire_and_C_only_cannot_observe()
    {
        var c = new FakeP2Coordinator();
        c.HostLoaded();
        c.SetRoles(true, true, true);
        c.SetGrants("reader", CoordinatorGrant.Observe);
        c.SetGrants("luna", CoordinatorGrant.Control);
        Assert.Equal(CoordinatorDecision.Forbidden, c.Acquire("reader").Decision);
        var lease = Assert.IsType<CoordinatorLease>(c.Acquire("luna").Lease);
        Assert.Equal(CoordinatorDecision.Forbidden, c.Enqueue(lease, "read-1", CoordinatorLane.Observation));
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, "action-1", CoordinatorLane.Action));
        Assert.Equal(0, c.ObservationSteps);
    }

    [Fact]
    public void Removing_O_scope_fences_observation_without_revoking_C_owner()
    {
        var (c, lease) = Open();
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, "observe-running", CoordinatorLane.Observation));
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, "observe-pending", CoordinatorLane.Observation));
        Assert.Equal(CoordinatorWorkState.Running, c.StartNext(CoordinatorLane.Observation)!.State);
        c.SetGrants("luna", CoordinatorGrant.Control);
        Assert.Equal(lease, c.Owner);
        Assert.Equal(0, c.PendingObservations);
        Assert.Equal(CoordinatorWorkState.CancelledBeforeStart, c.Inspect("observe-pending")!.State);
        Assert.False(c.Step("observe-running", lease));
        Assert.True(c.Quiesce("observe-running", outcomeKnown: true));
        Assert.Equal(CoordinatorDecision.Forbidden, c.Enqueue(lease, "observe-new", CoordinatorLane.Observation));
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, "action-new", CoordinatorLane.Action));
        Assert.Equal(CoordinatorWorkState.Running, c.StartNext(CoordinatorLane.Action)!.State);
        Assert.True(c.Step("action-new", lease));
        Assert.True(c.Finish("action-new", lease));
    }

    [Fact]
    public void Two_pending_lanes_have_independent_limits_and_no_effect_on_denial()
    {
        var (c, lease) = Open();
        for (int i = 0; i < FakeP2Coordinator.MaxPendingPerLane; i++)
        {
            Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, $"a-{i}", CoordinatorLane.Action));
            Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, $"o-{i}", CoordinatorLane.Observation));
        }
        Assert.Equal(CoordinatorDecision.Capacity, c.Enqueue(lease, "extra-action", CoordinatorLane.Action));
        Assert.Equal(CoordinatorDecision.Capacity, c.Enqueue(lease, "extra-observe", CoordinatorLane.Observation));
        Assert.Equal(CoordinatorDecision.Duplicate, c.Enqueue(lease, "a-0", CoordinatorLane.Action));
        Assert.Equal(2, c.PendingActions);
        Assert.Equal(2, c.PendingObservations);
        Assert.Equal(0, c.ActionSteps + c.ObservationSteps);
        Assert.Equal(CoordinatorWorkState.Running, c.StartNext(CoordinatorLane.Action)!.State);
        Assert.Equal(CoordinatorWorkState.Running, c.StartNext(CoordinatorLane.Observation)!.State);
        Assert.True(c.Step("a-0", lease));
        Assert.True(c.Step("o-0", lease));
        Assert.Equal(1, c.ActionSteps);
        Assert.Equal(1, c.ObservationSteps);
        Assert.True(c.Finish("a-0", lease));
        Assert.True(c.Finish("o-0", lease));
    }

    [Fact]
    public void Host_reload_rotates_epoch_even_for_the_same_save_day_and_guest_does_not()
    {
        var (c, lease) = Open();
        string epoch = lease.Epoch;
        c.GuestSaveLoaded();
        c.GuestSaveLoaded();
        Assert.Equal(epoch, c.Epoch);
        Assert.Equal(lease, c.Owner);
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, "queued-1", CoordinatorLane.Action));
        c.HostLoaded(); // means reloading same save/time, not a day change
        Assert.NotEqual(epoch, c.Epoch);
        Assert.Null(c.Owner);
        Assert.Equal(CoordinatorWorkState.CancelledBeforeStart, c.Inspect("queued-1")!.State);
        Assert.Equal(0, c.PendingActions);
        Assert.Null(c.StartNext(CoordinatorLane.Action));
        Assert.Equal(CoordinatorDecision.Closed, c.Enqueue(lease, "old-2", CoordinatorLane.Action));
        c.SetRoles(true, true, true);
        var next = Assert.IsType<CoordinatorLease>(c.Acquire("luna").Lease);
        Assert.NotEqual(lease.Epoch, next.Epoch);
        Assert.NotEqual(lease.Session, next.Session);
        Assert.Equal(CoordinatorDecision.Closed, c.Enqueue(lease, "stale", CoordinatorLane.Action));
    }

    [Fact]
    public void Returned_to_title_closes_admission_and_invalidates_old_session()
    {
        var (c, lease) = Open();
        c.ReturnedToTitle();
        Assert.Null(c.Epoch);
        Assert.Null(c.Owner);
        Assert.Equal(CoordinatorDecision.Closed, c.Acquire("luna").Decision);
        Assert.Equal(CoordinatorDecision.Closed, c.Enqueue(lease, "late", CoordinatorLane.Action));
        c.HostLoaded();
        c.SetRoles(true, true, true);
        Assert.Equal(CoordinatorDecision.Accepted, c.Acquire("luna").Decision);
    }

    [Fact]
    public void Retirement_purges_both_queues_immediately_without_draining()
    {
        var (c, lease) = Open();
        for (int i = 0; i < FakeP2Coordinator.MaxPendingPerLane; i++)
        {
            c.Enqueue(lease, $"action-{i}", CoordinatorLane.Action);
            c.Enqueue(lease, $"observation-{i}", CoordinatorLane.Observation);
        }
        Assert.Equal(CoordinatorRetirement.Quiescent, c.Release(lease));
        Assert.Equal(0, c.PendingActions + c.PendingObservations);
        Assert.Null(c.StartNext(CoordinatorLane.Action));
        Assert.Null(c.StartNext(CoordinatorLane.Observation));
        Assert.Equal(CoordinatorWorkState.CancelledBeforeStart, c.Inspect("action-0")!.State);
        Assert.Equal(CoordinatorWorkState.CancelledBeforeStart, c.Inspect("observation-1")!.State);
        Assert.Equal(0, c.ActionSteps + c.ObservationSteps);
        c.SetGrants("other", CoordinatorGrant.Control);
        Assert.Equal(CoordinatorDecision.Accepted, c.Acquire("other").Decision);
        Assert.Equal(CoordinatorRetirement.Denied, c.Release(lease));
    }

    [Fact]
    public void Running_action_is_fenced_before_successor_and_partial_effect_requires_reconciliation()
    {
        var (c, lease) = Open();
        c.SetGrants("other", CoordinatorGrant.Control);
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, "walk-1", CoordinatorLane.Action));
        Assert.Equal(CoordinatorWorkState.Running, c.StartNext(CoordinatorLane.Action)!.State);
        Assert.True(c.Step("walk-1", lease)); // one synthetic effect BEFORE retirement
        int effectsBefore = c.ActionSteps;
        Assert.Equal(CoordinatorRetirement.Retiring, c.Release(lease));
        Assert.False(c.Step("walk-1", lease)); // cannot run another coroutine step
        Assert.False(c.Finish("walk-1", lease)); // cannot turn partial effect into success
        Assert.Equal(effectsBefore, c.ActionSteps);
        Assert.Equal(CoordinatorDecision.Closed, c.Acquire("other").Decision);
        Assert.True(c.Quiesce("walk-1", outcomeKnown: true));
        Assert.Equal(CoordinatorWorkState.InterruptedPartial, c.Inspect("walk-1")!.State);
        Assert.Equal(1, c.UnresolvedCount);
        var next = Assert.IsType<CoordinatorLease>(c.Acquire("other").Lease);
        Assert.Equal(CoordinatorDecision.Unresolved, c.Enqueue(next, "new-action", CoordinatorLane.Action));
        Assert.True(c.ReconcileFromOperator("walk-1")); // synthetic trusted input, NOT automatic
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(next, "new-action", CoordinatorLane.Action));
        Assert.False(c.ReconcileFromOperator("walk-1"));
    }

    [Fact]
    public void Host_reload_during_started_step_preserves_old_world_barrier_until_quiescent()
    {
        var (c, lease) = Open();
        c.Enqueue(lease, "sleep", CoordinatorLane.Action);
        c.Enqueue(lease, "look", CoordinatorLane.Observation);
        c.StartNext(CoordinatorLane.Action);
        c.StartNext(CoordinatorLane.Observation);
        Assert.True(c.Step("sleep", lease));
        c.HostLoaded();
        c.SetRoles(true, true, true);
        Assert.False(c.Step("sleep", lease));
        Assert.False(c.Step("look", lease));
        Assert.Equal(CoordinatorDecision.Closed, c.Acquire("luna").Decision);
        Assert.True(c.Quiesce("look", outcomeKnown: false));
        Assert.Equal(CoordinatorDecision.Closed, c.Acquire("luna").Decision);
        Assert.True(c.Quiesce("sleep", outcomeKnown: false));
        Assert.Equal(2, c.UnresolvedCount);
        var next = Assert.IsType<CoordinatorLease>(c.Acquire("luna").Lease);
        Assert.Equal(CoordinatorDecision.Unresolved, c.Enqueue(next, "sleep-again", CoordinatorLane.Action));
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(next, "read-reconcile", CoordinatorLane.Observation));
        Assert.Equal(1, c.ActionSteps); // old-world action never resumed after the epoch change
    }

    [Fact]
    public void Role_and_brain_changes_retire_old_owner_and_require_explicit_reacquisition()
    {
        var (c, lease) = Open();
        c.Enqueue(lease, "future-step", CoordinatorLane.Action);
        long before = c.RoleGeneration;
        c.SetRoles(true, true, false); // built-in Brain active -> external lease invalid
        Assert.True(c.RoleGeneration > before);
        Assert.Null(c.Owner);
        Assert.Equal(CoordinatorWorkState.CancelledBeforeStart, c.Inspect("future-step")!.State);
        Assert.Equal(CoordinatorDecision.Closed, c.Acquire("luna").Decision);
        c.SetRoles(true, true, true);
        Assert.Equal(CoordinatorDecision.Accepted, c.Acquire("luna").Decision);
        Assert.Equal(CoordinatorDecision.Closed, c.Enqueue(lease, "stale", CoordinatorLane.Action));
    }

    [Fact]
    public void Revoking_control_fences_both_lanes_and_cannot_grant_p1_control()
    {
        var (c, lease) = Open();
        c.Enqueue(lease, "move", CoordinatorLane.Action);
        c.Enqueue(lease, "read", CoordinatorLane.Observation);
        c.SetGrants("luna", CoordinatorGrant.Observe);
        Assert.Null(c.Owner);
        Assert.Equal(0, c.PendingActions + c.PendingObservations);
        Assert.Equal(CoordinatorDecision.Forbidden, c.Acquire("luna").Decision);
        Assert.Equal(CoordinatorDecision.Closed, c.Enqueue(lease, "move-again", CoordinatorLane.Action));
        Assert.Equal(0, c.ActionSteps);
    }

    [Fact]
    public void Lost_initialize_response_does_not_allow_takeover_until_expiry_and_cleanup()
    {
        var (c, lease) = Open();
        c.SetGrants("other", CoordinatorGrant.Control);
        // Simulate a caller that discarded the successful initialize response:
        Assert.Equal(CoordinatorDecision.Conflict, c.Acquire("other", now: 59).Decision);
        var next = c.Acquire("other", now: 60);
        Assert.Equal(CoordinatorDecision.Accepted, next.Decision);
        Assert.NotEqual(lease, next.Lease);
        Assert.Equal(CoordinatorDecision.Closed, c.Enqueue(lease, "late", CoordinatorLane.Action, now: 60));
    }

    [Fact]
    public void Expiry_does_not_auto_cancel_an_inflight_action_or_free_owner()
    {
        var (c, lease) = Open();
        c.SetGrants("other", CoordinatorGrant.Control);
        Assert.Equal(CoordinatorDecision.Accepted, c.Enqueue(lease, "bedtime", CoordinatorLane.Action, now: 1));
        c.StartNext(CoordinatorLane.Action, now: 1);
        Assert.True(c.Step("bedtime", lease, now: 250)); // test-only pinned in-flight work
        Assert.Equal(CoordinatorDecision.Conflict, c.Acquire("other", now: 250).Decision);
        Assert.True(c.Finish("bedtime", lease));
        // Only after the current work ends can expired ownership be retired.
        Assert.Equal(CoordinatorDecision.Accepted, c.Acquire("other", now: 251).Decision);
    }

    [Fact]
    public void Retiring_old_owner_cannot_erase_work_or_unknown_outcomes_via_new_host_epoch()
    {
        var (c, lease) = Open();
        c.Enqueue(lease, "respond", CoordinatorLane.Action);
        c.StartNext(CoordinatorLane.Action);
        c.HostLoaded();
        Assert.True(c.Quiesce("respond", outcomeKnown: false));
        Assert.Equal(CoordinatorWorkState.OutcomeUnknown, c.Inspect("respond")!.State);
        Assert.Equal(1, c.UnresolvedCount);
        c.HostLoaded(); // another load cannot clear history or unknown outcome
        c.SetRoles(true, true, true);
        var next = Assert.IsType<CoordinatorLease>(c.Acquire("luna").Lease);
        Assert.Equal(CoordinatorDecision.Unresolved, c.Enqueue(next, "retry-respond", CoordinatorLane.Action));
        Assert.Equal(CoordinatorDecision.Duplicate, c.Enqueue(next, "respond", CoordinatorLane.Observation));
        Assert.Equal(0, c.ActionSteps);
    }
}
