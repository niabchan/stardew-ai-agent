using System;
using System.Security.Cryptography;
using System.Text;

namespace StardewMCP.Agent;

/// <summary>
/// Dormant production-source P2 epoch/owner/STOP state primitive.
/// No HTTP or game wiring: AgentHttp, McpDispatcher and AgentRuntime do not call it.
/// No method here executes, cancels, acknowledges or reconciles any game action.
/// The trusted host must supply lifecycle signals; the current Mod does not.
/// </summary>
public sealed class SunnyP2HostFence
{
    [Flags]
    public enum Grant { None = 0, Control = 1, Observe = 2 }

    /// <summary>Opaque host-issued claims; not evidence that the real Mod loaded.</summary>
    public sealed record Lease(string Instance, string Epoch, string Session);

    private enum WorkState { None, Queued, Running }

    private readonly object _gate = new();
    private readonly string _instance = GenerateOpaque();
    private string? _epoch;
    private string? _session;
    private byte[]? _credentialDigest;
    private Grant _grants;
    private bool _rolesReady;
    private bool _stopped = true;
    private WorkState _workState;
    private string? _pendingOperation;
    private long _stopRevision;

    /// <summary>For *trusted host* diagnostics only; never serialize to a public route.</summary>
    public bool Stopped { get { lock (_gate) return _stopped; } }
    public bool PendingUnknown { get { lock (_gate) return _pendingOperation is not null; } }
    public long StopRevision { get { lock (_gate) return _stopRevision; } }

    private static string GenerateOpaque()
    {
        var raw = RandomNumberGenerator.GetBytes(32);
        return Convert.ToBase64String(raw).TrimEnd('=').Replace('+', '-').Replace('/', '_');
    }

    private void FenceUnderLock()
    {
        _stopped = true;
        _stopRevision++;
        // Queued and running work remain unresolved. A later game-thread step
        // must check the fence independently. This does NOT cancel a coroutine.
    }

    /// <summary>Trusted HOST-side load transition only, NOT a client HTTP call.</summary>
    public void HostSaveLoaded(bool p1Human, bool p2Ai, bool p2ExternalBrainNone)
    {
        lock (_gate)
        {
            FenceUnderLock();
            _epoch = GenerateOpaque();
            _rolesReady = p1Human && p2Ai && p2ExternalBrainNone;
            _session = null;
            _credentialDigest = null;
            _grants = Grant.None;
            // Prior pending work remains quarantined even across a new epoch.
            // A host event is not an authoritative completed-effect receipt.
        }
    }

    /// <summary>Trusted HOST-only Title transition, never an owner release proof.</summary>
    public void HostReturnedToTitle()
    {
        lock (_gate)
        {
            FenceUnderLock();
            _epoch = null;
            _rolesReady = false;
            _session = null;
            _credentialDigest = null;
            _grants = Grant.None;
        }
    }

    /// <summary>Host observed an unsafe role change. Always fence the old P2 owner.</summary>
    public void HostRolesChanged(bool p1Human, bool p2Ai, bool p2ExternalBrainNone)
    {
        lock (_gate)
        {
            _rolesReady = p1Human && p2Ai && p2ExternalBrainNone && _epoch is not null;
            if (!_rolesReady)
            {
                FenceUnderLock();
                _session = null;
                _credentialDigest = null;
                _grants = Grant.None;
            }
        }
    }

    /// <summary>
    /// A trusted host-only provisioner may request a fresh high-entropy P2 bearer.
    /// The plaintext return MUST be delivered via an independently reviewed secure
    /// local channel: never logs, config, CLI arguments, HTTP URL or Luna API.
    /// Nothing in this class supplies that channel or operator authorization.
    /// </summary>
    public string? HostIssueCredential(Grant grants)
    {
        lock (_gate)
        {
            if (!_rolesReady || _epoch is null || grants is Grant.None ||
                (grants & ~(Grant.Control | Grant.Observe)) != 0 ||
                _pendingOperation is not null)
                return null;
            var token = GenerateOpaque();
            _credentialDigest = SHA256.HashData(Encoding.ASCII.GetBytes(token));
            _grants = grants;
            _session = null;
            FenceUnderLock(); // Rotation cannot silently resume any activity.
            return token;
        }
    }

    private bool CredentialMatches(string? bearer)
    {
        if (_credentialDigest is null || string.IsNullOrEmpty(bearer) ||
            bearer.Length != 43)
            return false;
        foreach (char c in bearer)
            if (!(c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' ||
                  c >= '0' && c <= '9' || c is '-' or '_'))
                return false;
        var supplied = SHA256.HashData(Encoding.ASCII.GetBytes(bearer));
        return CryptographicOperations.FixedTimeEquals(_credentialDigest, supplied);
    }

    private bool LeaseMatches(Lease? lease)
    {
        return lease is not null && _epoch is not null && _session is not null &&
               lease.Instance == _instance && lease.Epoch == _epoch &&
               lease.Session == _session && _rolesReady;
    }

    /// <summary>
    /// Caller request for a P2 session. This does not install the session into
    /// McpDispatcher and does not mark any game seat as connected.
    /// </summary>
    public Lease? TryAcquire(string? bearer)
    {
        lock (_gate)
        {
            if (!_rolesReady || _epoch is null || _session is not null ||
                (_grants & Grant.Control) == 0 || !CredentialMatches(bearer) ||
                _pendingOperation is not null)
                return null;
            _session = GenerateOpaque();
            return new Lease(_instance, _epoch, _session);
        }
    }

    /// <summary>
    /// Trusted HOST-only, explicit preparation for ONE possible operation.
    /// Requires an existing owner and no unresolved earlier operation.
    /// This is not HTTP admission or a consent/authorization endpoint.
    /// </summary>
    public bool HostArmForOneOperation()
    {
        lock (_gate)
        {
            if (_session is null || !_rolesReady || _epoch is null ||
                _credentialDigest is null || _pendingOperation is not null)
                return false;
            _stopped = false;
            return true;
        }
    }

    /// <summary>
    /// Host-side in-memory reservation only. A future caller MUST atomically
    /// commit its durable SQLite/host operation identity before real dispatch,
    /// and re-check current role/epoch/STOP on the game thread. The actual
    /// Mod does neither today, and does not use this guard.
    /// </summary>
    public bool TryQueueMutation(string? bearer, Lease? lease, string? operationId)
    {
        lock (_gate)
        {
            if (_stopped || !LeaseMatches(lease) || !CredentialMatches(bearer) ||
                (_grants & Grant.Control) == 0 || _pendingOperation is not null ||
                string.IsNullOrWhiteSpace(operationId) || operationId.Length > 128)
                return false;
            _pendingOperation = operationId;
            _workState = WorkState.Queued;
            return true;
        }
    }

    /// <summary>Second gate for the actual game-thread START, not a dispatch implementation.</summary>
    public bool TryBeginOnGameThread(Lease? lease, string operationId)
    {
        lock (_gate)
        {
            if (_stopped || !LeaseMatches(lease) || _pendingOperation != operationId ||
                _workState != WorkState.Queued)
                return false;
            _workState = WorkState.Running;
            return true;
        }
    }

    /// <summary>Must be checked before EACH future coroutine effect step.</summary>
    public bool MayContinueOnGameThread(Lease? lease, string operationId)
    {
        lock (_gate)
            return !_stopped && LeaseMatches(lease) && _pendingOperation == operationId &&
                   _workState == WorkState.Running;
    }

    /// <summary>
    /// A STOP signal from trusted host code. No HTTP endpoint or independent
    /// channel is implemented. Queued/running calls remain quarantined until
    /// separately validated host retirement and effect reconciliation.
    /// </summary>
    public void HostStop()
    {
        lock (_gate)
            FenceUnderLock();
    }

    /// <summary>
    /// Do not clear pending on a tool reply. ACK is not in-game effect proof.
    /// </summary>
    public void ToolReplyObserved(string operationId, bool isError)
    {
        lock (_gate)
        {
            // Intentionally no state changes, even for apparently successful replies.
            // Callers cannot use this as a way to release unknown work.
            _ = operationId;
            _ = isError;
        }
    }
}
