using System;
using StardewMCP.Agent;

namespace StardewMCP.Tests;

// Test-only, proposed ordering of request-specific effects; none of this is wired
// to AgentHttp, McpDispatcher, PlayerSlot, SessionBreaks, WorldClock or AgentRuntime.
// Simulated event counters are NOT real game contact, pause, diagnostics or logs.
internal sealed record FakeP2BoundarySnapshot(
    int AcceptedSessionBreakStarts,
    int AcceptedOwnerPresenceEvents,
    int AcceptedToolContactMarks,
    int AcceptedExecutionBudgetStarts,
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

    private int _presenceEvents;
    private int _sessionStarts, _contactMarks, _replyBudgets, _actionLogs, _freezeEvents;
    private bool _freezeEligible;

    internal FakeP2BoundarySnapshot Snapshot()
    {
        lock (_gate)
            return new(_sessionStarts, _presenceEvents, _contactMarks, _replyBudgets, _actionLogs,
                _freezeEvents, _freezeEligible && _intake.Owner is not null,
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
    {
        lock (_gate)
        {
            _intake.Provision(token, principal, grants);
            if (_intake.Owner is null) _freezeEligible = false;
        }
    }

    internal void ChangeGrants(string token, CoordinatorGrant grants)
    {
        lock (_gate)
        {
            _intake.ChangeGrants(token, grants);
            if (_intake.Owner is null) _freezeEligible = false;
        }
    }

    internal void Revoke(string token)
    {
        lock (_gate)
        {
            _intake.Revoke(token);
            if (_intake.Owner is null) _freezeEligible = false;
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
            // Presence is separate from admitted tool start: otherwise the first
            // planning interval after initialize would advance game time.
            // This does NOT call PlayerSlot.MarkContact or model timeout/release reset.
            if (reply.Disposition == IntakeDisposition.Acquired)
            {
                _sessionStarts++;
                _presenceEvents++;
                _freezeEligible = true;
            }
            // Trusted expiry/retirement may invalidate presence even on a denial;
            // that is lifecycle housekeeping, not authority granted to the request.
            if (_intake.Owner is null) _freezeEligible = false;
            // Queued != started: no tool-start counters, execution budget or action log.
            // Discovery/notifications never refresh presence or lease lifetime.
            return reply;
        }
    }

    /// <summary>
    /// Only when fake coordinator STARTS valid work, mirror post-admission
    /// tool-start/execution-budget/rearm and action-log notifications. Presence already
    /// exists after acquired initialize; eligibility is not actual WorldClock pause. This is NOT
    /// an AgentRuntime.Lane.Start call and holds no real game-thread lock.
    /// </summary>
    internal CoordinatorWorkView? TryStart(CoordinatorLane lane, long now = 0)
    {
        lock (_gate)
        {
            var view = _intake.Start(lane, now);
            if (view?.State != CoordinatorWorkState.Running) return view;
            _contactMarks++;
            _replyBudgets++; // execution budget only; response deadline must include queue wait
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
