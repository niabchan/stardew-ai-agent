using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using StardewMCP.Agent;

namespace StardewMCP.Tests;

// TEST-ONLY admission integration. Not an HttpListener, controller, or security provider.
// The source policy's positive decision is a SNAPSHOT, not a lease/capability.
internal enum IntakeDisposition { Denied, Acquired, Queued, Discovery, Notification, RetirementUnverified }
internal sealed record IntakeReply(int Status, IntakeDisposition Disposition,
    CoordinatorLease? Lease = null, string? OperationId = null)
{
    internal bool Accepted => Disposition is not IntakeDisposition.Denied;
}

/// <summary>
/// Synthetic in-process request path: strict preflight -> atomic fake coordinator
/// admission -> later fake start/step. A single gate also serializes all test-harness
/// lifecycle and grant changes. Actual authenticated HTTP/SMAPI integration is absent.
/// </summary>
internal sealed class FakeP2AtomicIntake : ISunnyP2PolicyAuthority
{
    private sealed record TestCredential(string Principal, CoordinatorGrant Grants);
    private readonly object _gate = new();
    private readonly FakeP2Coordinator _coordinator = new();
    private readonly Dictionary<string, TestCredential> _credentials = new(StringComparer.Ordinal);
    private bool _rolesReady;

    internal string? Epoch { get { lock (_gate) return _coordinator.Epoch; } }
    internal CoordinatorLease? Owner { get { lock (_gate) return _coordinator.Owner; } }
    internal int PendingActions { get { lock (_gate) return _coordinator.PendingActions; } }
    internal int PendingObservations { get { lock (_gate) return _coordinator.PendingObservations; } }
    internal int RunningCount { get { lock (_gate) return _coordinator.RunningCount; } }
    internal int UnresolvedCount { get { lock (_gate) return _coordinator.UnresolvedCount; } }
    internal int EffectSteps { get { lock (_gate) return _coordinator.ActionSteps + _coordinator.ObservationSteps; } }

    internal void HostLoaded(string? transition = null)
    {
        lock (_gate)
        {
            var prior = _coordinator.Epoch;
            _coordinator.HostLoaded(transition);
            if (_coordinator.Epoch == prior) return; // duplicate current transition
            _credentials.Clear(); // no old epoch credentials silently reused
            _rolesReady = false;
        }
    }

    internal void GuestSaveLoaded() { lock (_gate) _coordinator.GuestSaveLoaded(); }

    internal void ReturnedToTitle()
    {
        lock (_gate)
        {
            _coordinator.ReturnedToTitle();
            _credentials.Clear();
            _rolesReady = false;
        }
    }

    internal void SetRoles(bool p1Human, bool p2Ai, bool externalBrainNone)
    {
        lock (_gate)
        {
            _coordinator.SetRoles(p1Human, p2Ai, externalBrainNone);
            _rolesReady = p1Human && p2Ai && externalBrainNone && _coordinator.Epoch is not null;
        }
    }

    // Operator-only fake provisioning. This is not a bearer issuer, token entropy
    // source, credential store or general-purpose runtime API.
    internal void Provision(string rawToken, string principal, CoordinatorGrant grants)
    {
        if (string.IsNullOrWhiteSpace(rawToken) || string.IsNullOrWhiteSpace(principal))
            throw new ArgumentException("Test credential and principal required");
        lock (_gate)
        {
            if (_coordinator.Epoch is null) throw new InvalidOperationException("Host epoch required");
            _credentials[rawToken] = new(principal, grants);
            _coordinator.SetGrants(principal, grants);
        }
    }

    internal void ChangeGrants(string rawToken, CoordinatorGrant grants)
    {
        lock (_gate)
        {
            if (!_credentials.TryGetValue(rawToken, out var record)) return;
            _credentials[rawToken] = record with { Grants = grants };
            _coordinator.SetGrants(record.Principal, grants);
        }
    }

    internal void Revoke(string rawToken)
    {
        lock (_gate)
        {
            if (!_credentials.Remove(rawToken, out var record)) return;
            _coordinator.SetGrants(record.Principal, CoordinatorGrant.None);
        }
    }

    SunnyP2Principal? ISunnyP2PolicyAuthority.ResolveGameCredential(string rawBearer)
    {
        lock (_gate)
        {
            return _credentials.TryGetValue(rawBearer, out var record)
                ? new(record.Principal, "p2",
                    (record.Grants & CoordinatorGrant.Control) != 0,
                    (record.Grants & CoordinatorGrant.Observe) != 0)
                : null;
        }
    }

    bool ISunnyP2PolicyAuthority.HumanP1AiP2ExternalBrainReady
    {
        get { lock (_gate) return _rolesReady; }
    }

    bool ISunnyP2PolicyAuthority.IsCurrentOwnerSession(string principalId, string session, string epoch)
    {
        lock (_gate)
        {
            var lease = _coordinator.Owner;
            return lease is not null && lease.Principal == principalId
                && lease.Session == session && lease.Epoch == epoch;
        }
    }

    bool ISunnyP2PolicyAuthority.ValidateMutationArguments(string name, JsonElement arguments)
    {
        lock (_gate)
        {
            return name == "say" && arguments.ValueKind == JsonValueKind.Object
                && arguments.EnumerateObject().Count() == 1
                && arguments.TryGetProperty("text", out var text)
                && text.ValueKind == JsonValueKind.String
                && text.GetString() is { Length: > 0 and <= 120 };
        }
    }

    private static string? Header(SunnyP2Request request, string name) =>
        request.Headers.FirstOrDefault(h => string.Equals(h.Key, name, StringComparison.OrdinalIgnoreCase)).Value;

    private static int Status(CoordinatorDecision decision) => decision switch
    {
        CoordinatorDecision.Accepted => 200,
        CoordinatorDecision.Forbidden => 403,
        CoordinatorDecision.Capacity => 429,
        CoordinatorDecision.Closed => 503,
        CoordinatorDecision.Conflict or CoordinatorDecision.Duplicate or
        CoordinatorDecision.Unresolved => 409,
        _ => 503
    };

    /// <summary>
    /// The optional betweenPhases callback is a PRIVILEGED TEST ONLY interleaving
    /// injection, not client-controlled middleware. It can change fake world state
    /// to prove a stale positive preflight NEVER commits without revalidation.
    /// </summary>
    internal IntakeReply Admit(SunnyP2Request request, string? trustedAttemptId = null,
        Action? betweenPhases = null, long now = 0)
    {
        lock (_gate)
        {
            var snapshot = SunnyP2Preflight.Evaluate(request, this);
            if (!snapshot.Allowed) return new(snapshot.Status, IntakeDisposition.Denied);

            betweenPhases?.Invoke();

            // Re-resolve the credential under the same fixture lock: snapshot
            // claims or a formerly valid bearer cannot authorize a new operation.
            var authorization = Header(request, "Authorization");
            var token = authorization is not null && authorization.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
                ? authorization.Substring(7) : null;
            if (token is null || !_credentials.TryGetValue(token, out var current))
                return new(401, IntakeDisposition.Denied);
            if ((current.Grants & CoordinatorGrant.Control) == 0)
                return new(403, IntakeDisposition.Denied);

            if (snapshot.Operation == SunnyP2Operation.Initialize)
            {
                var acquired = _coordinator.Acquire(current.Principal, now);
                return acquired.Decision == CoordinatorDecision.Accepted
                    ? new(200, IntakeDisposition.Acquired, acquired.Lease)
                    : new(Status(acquired.Decision), IntakeDisposition.Denied);
            }

            var held = _coordinator.Owner;
            if (held is null || held.Principal != current.Principal ||
                held.Session != Header(request, SunnyP2Preflight.SessionHeader) ||
                held.Epoch != Header(request, SunnyP2Preflight.EpochHeader) ||
                !_coordinator.ValidateLease(held, now))
                return new(409, IntakeDisposition.Denied);

            if (snapshot.Operation == SunnyP2Operation.Retire)
            {
                var retirement = _coordinator.Release(held);
                return retirement == CoordinatorRetirement.Denied
                    ? new(409, IntakeDisposition.Denied)
                    // This has NO wire-retirement meaning. Even a quiescent fake
                    // coordinator cannot supply a server-verified DELETE proof.
                    : new(202, IntakeDisposition.RetirementUnverified);
            }

            if (snapshot.Operation is SunnyP2Operation.Discovery or SunnyP2Operation.Notification)
                return new(snapshot.Operation == SunnyP2Operation.Notification ? 202 : 200,
                    snapshot.Operation == SunnyP2Operation.Notification
                        ? IntakeDisposition.Notification : IntakeDisposition.Discovery);

            if (snapshot.Operation is not (SunnyP2Operation.Status or SunnyP2Operation.Mutation))
                return new(400, IntakeDisposition.Denied);
            if (snapshot.Operation == SunnyP2Operation.Status &&
                (current.Grants & CoordinatorGrant.Observe) == 0)
                return new(403, IntakeDisposition.Denied);

            // This ID is a TRUSTED CALLER TEST CLAIM, never an HTTP JSON-RPC id.
            // Production needs an independently reviewed persistent attempt journal.
            if (string.IsNullOrWhiteSpace(trustedAttemptId))
                return new(400, IntakeDisposition.Denied);
            var lane = snapshot.Operation == SunnyP2Operation.Status
                ? CoordinatorLane.Observation : CoordinatorLane.Action;
            var result = _coordinator.Enqueue(held, trustedAttemptId, lane, now);
            return result == CoordinatorDecision.Accepted
                ? new(200, IntakeDisposition.Queued, OperationId: trustedAttemptId)
                : new(Status(result), IntakeDisposition.Denied);
        }
    }

    internal CoordinatorWorkView? Start(CoordinatorLane lane, long now = 0)
    { lock (_gate) return _coordinator.StartNext(lane, now); }

    internal bool Step(string id, CoordinatorLease lease, long now = 0)
    { lock (_gate) return _coordinator.Step(id, lease, now); }

    internal bool Finish(string id, CoordinatorLease lease, long now = 0)
    { lock (_gate) return _coordinator.Finish(id, lease, now); }

    // Trusted test-harness cleanup/reconciliation, never an exposed HTTP endpoint.
    internal bool Quiesce(string id, bool outcomeKnown)
    { lock (_gate) return _coordinator.Quiesce(id, outcomeKnown); }

    internal bool ReconcileFromOperator(string id)
    { lock (_gate) return _coordinator.ReconcileFromOperator(id); }
}
