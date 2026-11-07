using System;
using System.Collections.Generic;
using System.Linq;

namespace StardewMCP.Tests;

// TEST-ONLY model. Not linked into the mod, HTTP listener, or a game assembly.
// Ids and clocks are synthetic; this is NOT an authentication or cancellation implementation.
[Flags]
internal enum CoordinatorGrant { None = 0, Control = 1, Observe = 2 }
internal enum CoordinatorLane { Action, Observation }
internal enum CoordinatorDecision { Accepted, Closed, Forbidden, Conflict, Capacity, Duplicate, Unresolved }
internal enum CoordinatorWorkState { Queued, Running, CancelledBeforeStart, InterruptedPartial, Completed, OutcomeUnknown }
internal enum CoordinatorRetirement { Denied, Retiring, Quiescent }

internal sealed record CoordinatorLease(string Principal, string Session, string Epoch, long Generation);
internal sealed record CoordinatorAcquisition(CoordinatorDecision Decision, CoordinatorLease? Lease);
internal sealed record CoordinatorWorkView(string Id, CoordinatorLane Lane, CoordinatorWorkState State,
    int Steps, string Epoch, bool Fenced);

/// <summary>
/// In-memory, deterministic concurrency and lifecycle fixture for PR #28's proposed
/// P2-only server coordinator. Calls are serialized by one lock; no game or network I/O.
/// Deliberately no real token provisioning, owner recovery, persistence, or game-thread cleanup.
/// </summary>
internal sealed class FakeP2Coordinator
{
    private sealed class Work
    {
        internal readonly string Id;
        internal readonly CoordinatorLane Lane;
        internal readonly CoordinatorLease Owner;
        internal CoordinatorWorkState State = CoordinatorWorkState.Queued;
        internal int Steps;
        internal bool Fenced;
        internal Work(string id, CoordinatorLane lane, CoordinatorLease owner)
        { Id = id; Lane = lane; Owner = owner; }
        internal CoordinatorWorkView View() => new(Id, Lane, State, Steps, Owner.Epoch, Fenced);
    }

    internal const int MaxPendingPerLane = 2;
    private readonly object _gate = new();
    private readonly Dictionary<string, CoordinatorGrant> _grants = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Work> _history = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Work> _running = new(StringComparer.Ordinal);
    private readonly HashSet<string> _unresolved = new(StringComparer.Ordinal);
    private readonly Queue<Work> _actions = new();
    private readonly Queue<Work> _observations = new();

    private readonly string _instance = Guid.NewGuid().ToString("N"); // fixture incarnation, not auth
    private long _now;
    private CoordinatorLease? _owner;
    private string? _epoch;
    private long _epochNumber, _ownerNumber, _roleGeneration, _expiresAt;
    private string? _lastHostTransition; // synthetic host event key; not a real SMAPI identifier
    private bool _hostReady, _p1Human, _p2Ai, _brainNone;
    private int _actionSteps, _observationSteps;

    internal string? Epoch { get { lock (_gate) return _epoch; } }
    internal CoordinatorLease? Owner { get { lock (_gate) return _owner; } }
    internal int PendingActions { get { lock (_gate) return _actions.Count; } }
    internal int PendingObservations { get { lock (_gate) return _observations.Count; } }
    internal int RunningCount { get { lock (_gate) return _running.Count; } }
    internal int UnresolvedCount { get { lock (_gate) return _unresolved.Count; } }
    internal int ActionSteps { get { lock (_gate) return _actionSteps; } }
    internal int ObservationSteps { get { lock (_gate) return _observationSteps; } }
    internal long RoleGeneration { get { lock (_gate) return _roleGeneration; } }

    // Trusted operator/test-harness operation, NOT an unauthenticated HTTP endpoint.
    internal void SetGrants(string principal, CoordinatorGrant grants)
    {
        if (string.IsNullOrWhiteSpace(principal)) throw new ArgumentException("principal");
        lock (_gate)
        {
            _grants[principal] = grants;
            if (_owner is { } owner && owner.Principal == principal)
            {
                if (!HasGrant(owner.Principal, CoordinatorGrant.Control))
                    RetireUnderLock();
                else if (!HasGrant(owner.Principal, CoordinatorGrant.Observe))
                    FenceObservationsUnderLock();
            }
        }
    }

    // Only an authoritative HOST callback calls this. Guest callbacks are ignored.
    // If a synthetic host-transition key is provided, repeated callbacks for that
    // same transition do not revoke a valid P2 owner. Distinct reloads use new keys.
    internal void HostLoaded(string? syntheticTransition = null)
    {
        lock (_gate)
        {
            if (syntheticTransition is not null)
            {
                if (string.IsNullOrWhiteSpace(syntheticTransition))
                    throw new ArgumentException("Host transition key must not be blank");
                if (_hostReady && _lastHostTransition == syntheticTransition) return;
            }
            RetireUnderLock();
            _lastHostTransition = syntheticTransition;
            _grants.Clear(); // epoch-scoped grants require explicit trusted reprovisioning
            _epoch = "synthetic-host-load-" + _instance + "-" + (++_epochNumber);
            _hostReady = true;
            _roleGeneration++;
            _p1Human = _p2Ai = _brainNone = false; // require explicit role resolution
        }
    }

    internal void GuestSaveLoaded() { /* Must never create a host epoch or touch ownership. */ }

    internal void ReturnedToTitle()
    {
        lock (_gate)
        {
            RetireUnderLock();
            _grants.Clear();
            _lastHostTransition = null;
            _hostReady = false;
            _epoch = null;
            _roleGeneration++;
            _p1Human = _p2Ai = _brainNone = false;
        }
    }

    internal void SetRoles(bool p1Human, bool p2Ai, bool externalBrainNone)
    {
        lock (_gate)
        {
            if ((_p1Human, _p2Ai, _brainNone) != (p1Human, p2Ai, externalBrainNone))
            {
                RetireUnderLock();
                _roleGeneration++;
                _p1Human = p1Human;
                _p2Ai = p2Ai;
                _brainNone = externalBrainNone;
            }
        }
    }

    private bool RolesValid => _hostReady && _epoch is not null && _p1Human && _p2Ai && _brainNone;
    private bool HasGrant(string principal, CoordinatorGrant grant) =>
        _grants.TryGetValue(principal, out var flags) && (flags & grant) == grant;

    // Zero/default means the current fake tick. Regressing test inputs cannot rewind time.
    // Validate arithmetic bounds BEFORE changing ownership, queues or history.
    private long AdvanceClockUnderLock(long now)
    {
        if (now < 0 || now > long.MaxValue - 180)
            throw new ArgumentOutOfRangeException(nameof(now));
        return _now = Math.Max(_now, now);
    }

    // Synthetic monotonic time is supplied by tests. Expiry never clears running work.
    private void ExpireUnderLock(long now)
    {
        if (_owner is not null && now >= _expiresAt
            && !_running.Values.Any(w => w.Lane == CoordinatorLane.Action))
            RetireUnderLock();
    }

    internal CoordinatorAcquisition Acquire(string principal, long now = 0)
    {
        lock (_gate)
        {
            now = AdvanceClockUnderLock(now);
            ExpireUnderLock(now);
            if (!RolesValid) return new(CoordinatorDecision.Closed, null);
            if (!HasGrant(principal, CoordinatorGrant.Control))
                return new(CoordinatorDecision.Forbidden, null);
            if (_owner is not null) return new(CoordinatorDecision.Conflict, null);
            if (_running.Count != 0) return new(CoordinatorDecision.Closed, null);
            var owner = new CoordinatorLease(principal, "synthetic-session-" + (++_ownerNumber),
                _epoch!, _roleGeneration);
            _owner = owner;
            _expiresAt = checked(now + 60); // 60 fake ticks: provisional lease
            return new(CoordinatorDecision.Accepted, owner);
        }
    }

    private bool ValidUnderLock(CoordinatorLease lease) =>
        RolesValid && _owner == lease && _epoch == lease.Epoch
        && lease.Generation == _roleGeneration
        && HasGrant(lease.Principal, CoordinatorGrant.Control);

    internal CoordinatorDecision Enqueue(CoordinatorLease lease, string operationId, CoordinatorLane lane,
        long now = 0)
    {
        lock (_gate)
        {
            now = AdvanceClockUnderLock(now);
            ExpireUnderLock(now);
            if (!ValidUnderLock(lease)) return CoordinatorDecision.Closed;
            var required = lane == CoordinatorLane.Action ? CoordinatorGrant.Control : CoordinatorGrant.Observe;
            if (!HasGrant(lease.Principal, required)) return CoordinatorDecision.Forbidden;
            if (lane == CoordinatorLane.Action && _unresolved.Count != 0)
                return CoordinatorDecision.Unresolved;
            if (string.IsNullOrWhiteSpace(operationId)) return CoordinatorDecision.Forbidden;
            if (_history.ContainsKey(operationId)) return CoordinatorDecision.Duplicate;
            var queue = lane == CoordinatorLane.Action ? _actions : _observations;
            if (queue.Count >= MaxPendingPerLane) return CoordinatorDecision.Capacity;
            var work = new Work(operationId, lane, lease);
            _history.Add(operationId, work);
            queue.Enqueue(work);
            _expiresAt = checked(now + 180); // admitted owner activity, not discovery
            return CoordinatorDecision.Accepted;
        }
    }

    internal CoordinatorWorkView? StartNext(CoordinatorLane lane, long now = 0)
    {
        lock (_gate)
        {
            now = AdvanceClockUnderLock(now);
            ExpireUnderLock(now);
            var queue = lane == CoordinatorLane.Action ? _actions : _observations;
            if (queue.Count == 0) return null;
            var work = queue.Dequeue();
            var required = lane == CoordinatorLane.Action ? CoordinatorGrant.Control : CoordinatorGrant.Observe;
            if (!ValidUnderLock(work.Owner) || !HasGrant(work.Owner.Principal, required)
                || (lane == CoordinatorLane.Action && _unresolved.Count != 0))
            {
                work.State = CoordinatorWorkState.CancelledBeforeStart;
                return work.View();
            }
            work.State = CoordinatorWorkState.Running;
            _running.Add(work.Id, work);
            return work.View();
        }
    }

    // Simulates one coroutine MoveNext/game-thread boundary, not an actual game effect.
    internal bool Step(string operationId, CoordinatorLease lease, long now = 0)
    {
        lock (_gate)
        {
            now = AdvanceClockUnderLock(now);
            ExpireUnderLock(now);
            if (!_running.TryGetValue(operationId, out var work) || work.State != CoordinatorWorkState.Running
                || work.Owner != lease || work.Fenced || !ValidUnderLock(lease)
                || (work.Lane == CoordinatorLane.Action && _unresolved.Count != 0)
                || !HasGrant(lease.Principal, work.Lane == CoordinatorLane.Action
                    ? CoordinatorGrant.Control : CoordinatorGrant.Observe))
                return false;
            work.Steps++;
            if (work.Lane == CoordinatorLane.Action) _actionSteps++;
            else _observationSteps++;
            return true;
        }
    }

    internal bool Finish(string operationId, CoordinatorLease lease, long now = 0)
    {
        lock (_gate)
        {
            now = AdvanceClockUnderLock(now);
            ExpireUnderLock(now);
            if (!_running.TryGetValue(operationId, out var work) || work.Owner != lease
                || work.Fenced || !ValidUnderLock(lease)
                || (work.Lane == CoordinatorLane.Action && _unresolved.Count != 0)) return false;
            work.State = CoordinatorWorkState.Completed;
            _running.Remove(operationId);
            _expiresAt = checked(now + 180); // post-completion idle window
            return true; // terminal test work, NOT evidence that a game effect was saved
        }
    }

    // Simulates operator-reviewed, GAME-THREAD quiescence of a started operation.
    // A partial or unknown historical effect remains fenced until separate reconciliation.
    internal bool Quiesce(string operationId, bool outcomeKnown)
    {
        lock (_gate)
        {
            if (!_running.TryGetValue(operationId, out var work) || !work.Fenced)
                return false;
            _running.Remove(operationId);
            work.State = outcomeKnown ? CoordinatorWorkState.InterruptedPartial
                : CoordinatorWorkState.OutcomeUnknown;
            if (!outcomeKnown || work.Steps != 0) _unresolved.Add(operationId);
            return true;
        }
    }

    // Trusted evidence input from fixture; no automatic recovery or retry in code.
    internal bool ReconcileFromOperator(string operationId)
    {
        lock (_gate) return _unresolved.Remove(operationId);
    }

    internal CoordinatorRetirement Release(CoordinatorLease lease)
    {
        lock (_gate)
        {
            if (!ValidUnderLock(lease)) return CoordinatorRetirement.Denied;
            RetireUnderLock();
            return _running.Count > 0 ? CoordinatorRetirement.Retiring : CoordinatorRetirement.Quiescent;
        }
    }

    private void FenceObservationsUnderLock()
    {
        while (_observations.Count > 0)
        {
            var work = _observations.Dequeue();
            work.State = CoordinatorWorkState.CancelledBeforeStart;
        }
        foreach (var work in _running.Values.Where(w => w.Lane == CoordinatorLane.Observation))
            work.Fenced = true;
    }

    private void RetireUnderLock()
    {
        _owner = null;
        while (_actions.Count > 0)
        {
            var work = _actions.Dequeue();
            work.State = CoordinatorWorkState.CancelledBeforeStart;
        }
        FenceObservationsUnderLock();
        foreach (var work in _running.Values) work.Fenced = true;
        // NO automatic clearing of _running, _unresolved, _history or prior outcomes.
    }

    internal CoordinatorWorkView? Inspect(string operationId)
    {
        lock (_gate) return _history.TryGetValue(operationId, out var work) ? work.View() : null;
    }
}
