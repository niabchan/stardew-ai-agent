using System;
using StardewMCP.Agent;

namespace StardewMCP.Tests;

// Test-only, proposed ordering of request-specific effects; none of this is wired
// to AgentHttp, McpDispatcher, PlayerSlot, SessionBreaks, WorldClock or AgentRuntime.
// Simulated event counters are NOT real game contact, pause, diagnostics or logs.
internal sealed record FakeP2BoundarySnapshot(
    int AcceptedSessionBreakStarts,
    int AcceptedToolContactMarks,
    int AcceptedToolReplyBudgetSets,
    int AcceptedActionStartLogs,
    int AcceptedFreezeEligibilityEvents,
    bool FreezeEligible,
    int QueuedActions,
    int QueuedObservations,
    int StartedWork,
    int FakeGameSteps);

internal sealed class FakeP2ServerBoundary
{
    private readonly object _gate = new();
    private readonly FakeP2AtomicIntake _intake = new();

    private int _sessionStarts, _contactMarks, _replyBudgets, _actionLogs, _freezeEvents;
    private bool _freezeEligible;

    internal FakeP2BoundarySnapshot Snapshot()
    {
        lock (_gate)
            return new(_sessionStarts, _contactMarks, _replyBudgets, _actionLogs,
                _freezeEvents, _freezeEligible,
                _intake.PendingActions, _intake.PendingObservations,
                _intake.RunningCount, _intake.EffectSteps);
    }

    internal string? Epoch { get { lock (_gate) return _intake.Epoch; } }
    internal CoordinatorLease? Owner { get { lock (_gate) return _intake.Owner; } }

    internal void HostLoaded(string? transition = null)
    {
        lock (_gate)
        {
            var previousEpoch = _intake.Epoch;
            _intake.HostLoaded(transition);
            if (previousEpoch != _intake.Epoch) _freezeEligible = false;
        }
    }

    internal void GuestLoaded()
    { lock (_gate) _intake.GuestSaveLoaded(); }

    internal void ReturnedToTitle()
    {
        lock (_gate)
        {
            _intake.ReturnedToTitle();
            _freezeEligible = false;
        }
    }

    internal void SetRoles(bool p1Human, bool p2Ai, bool externalBrainNone)
    {
        lock (_gate)
        {
            _intake.SetRoles(p1Human, p2Ai, externalBrainNone);
            if (!p1Human || !p2Ai || !externalBrainNone) _freezeEligible = false;
        }
    }

    internal void Provision(string token, string principal, CoordinatorGrant grants)
    { lock (_gate) _intake.Provision(token, principal, grants); }

    internal void ChangeGrants(string token, CoordinatorGrant grants)
    {
        lock (_gate)
        {
            _intake.ChangeGrants(token, grants);
            if ((grants & CoordinatorGrant.Control) == 0) _freezeEligible = false;
        }
    }

    internal void Revoke(string token)
    {
        lock (_gate)
        {
            _intake.Revoke(token);
            _freezeEligible = false;
        }
    }

    /// <summary>
    /// Mirrors a proposed SAFE order: preflight -> authority+epoch+role+queue
    /// admission -> only then request-specific effects. The fake core's own
    /// critical section rechecks after any privileged betweenPhases injection.
    /// </summary>
    internal IntakeReply Handle(SunnyP2Request request, string? trustedAttemptId = null,
        Action? betweenPhases = null, long now = 0)
    {
        lock (_gate)
        {
            // IMPORTANT: test-only injection, not a request-controlled callback.
            var reply = _intake.Admit(request, trustedAttemptId, betweenPhases, now);
            // A validated and acquired initialize may reset *context break*
            // bookkeeping only; it does not mark gameplay contact or set deadlines.
            if (reply.Disposition == IntakeDisposition.Acquired)
                _sessionStarts++;
            if (reply.Disposition == IntakeDisposition.RetirementUnverified)
                _freezeEligible = false;
            // Queued != started. A queued request is not enough to mark contact,
            // modify per-seat deadline, emit an action log, or trigger gameplay.
            return reply;
        }
    }

    /// <summary>
    /// Only when fake coordinator STARTS valid work, mirror post-admission
    /// contact/deadline/freeze and action-log notifications. This is NOT
    /// an AgentRuntime.Lane.Start call and holds no real game-thread lock.
    /// </summary>
    internal CoordinatorWorkView? TryStart(CoordinatorLane lane, long now = 0)
    {
        lock (_gate)
        {
            var view = _intake.Start(lane, now);
            if (view?.State != CoordinatorWorkState.Running) return view;
            _contactMarks++;
            _replyBudgets++; // per admitted started operation, not PlayerSlot's global volatile field
            _freezeEligible = true;
            _freezeEvents++;
            if (lane == CoordinatorLane.Action) _actionLogs++;
            return view;
        }
    }

    internal bool FakeStep(string id, CoordinatorLease owner, long now = 0)
    { lock (_gate) return _intake.Step(id, owner, now); }

    internal bool Finish(string id, CoordinatorLease owner, long now = 0)
    { lock (_gate) return _intake.Finish(id, owner, now); }

    internal bool Quiesce(string id, bool outcomeKnown)
    { lock (_gate) return _intake.Quiesce(id, outcomeKnown); }

    internal bool ReconcileFromTrustedHarness(string id)
    { lock (_gate) return _intake.ReconcileFromOperator(id); }
}
