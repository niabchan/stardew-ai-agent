using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;

namespace StardewMCP.Agent;

/// <summary>Independent opt-ins. HTTP is reserved and has no listener implementation in this spike.</summary>
public sealed class DiagnosticObservationConfig
{
    public bool CollectionEnabled { get; set; }
    public bool AllowHumanP1Collection { get; set; }
    public bool HttpDisclosureEnabled { get; set; }
}

public sealed record EvidenceScope(string AdapterInstance, string LoadId, string BranchId,
    int Screen, string Seat, string FarmerAlias, long Incarnation)
{
    public string? SaveId => null; // No save discovery or checkpoint authority.
    public string? ParentCheckpointId => null;
}

public sealed record EvidenceResponse(int Index, string Label);

/// <summary>Constructor takes a defensive copy; no mutable game objects or arrays escape.</summary>
public sealed class EvidencePrompt
{
    public string InstanceId { get; }
    public long Revision { get; }
    public string Question { get; }
    public bool IsQuestion { get; }
    public IReadOnlyList<EvidenceResponse> Responses { get; }
    public EvidencePrompt(string instance, long revision, string question, bool isQuestion,
        IEnumerable<EvidenceResponse> responses)
    {
        InstanceId = instance;
        Revision = revision;
        Question = question;
        IsQuestion = isQuestion;
        Responses = new ReadOnlyCollection<EvidenceResponse>(responses.ToArray());
    }
}

public sealed record EvidenceCapture(EvidenceScope Scope, long Sequence, long Tick,
    long MonotonicTicks, long ClockFrequency, DateTimeOffset CapturedUtc, bool Complete,
    bool ContinuityObserved, bool LifecycleCoverage, string PromptStatus, EvidencePrompt? Prompt,
    string? MenuType, bool Transitioning, string? UnavailableReason)
{
    public bool Ready => true; // Unready screens retire the slot; they never manufacture an empty capture.
    public string Source => "own_screen";
    public string ClockId => Scope.AdapterInstance;
    public bool IdentityKnown => Prompt != null && Complete && ContinuityObserved && LifecycleCoverage;
    // Diagnostic instance IDs are NOT Sunny Gift offer tokens, even in fixtures.
    public string? OfferToken => null;
    public bool GuardedDispatch => false;
    public bool GiftClassification => false;
    public bool TransferVerification => false;
    public bool CheckpointReconciliation => false;
    public bool ResponseKeys => false;
    public bool InventorySupported => false;
}

public sealed record EvidenceRead(string Status, EvidenceCapture? Capture, double? AgeSeconds);

/// <summary>
/// Two latest-only slots. Writers are ordinary game-thread callbacks; readers only inspect immutable
/// copies under the same lock as lifecycle invalidation. No history, I/O, controllers or game types.
/// </summary>
public sealed class DiagnosticEvidenceCache
{
    public const int MaxQuestionChars = 2048;
    public const int MaxLabelChars = 256;
    public const int MaxResponses = 16;
    public const double MaxGapSeconds = 1;
    private sealed class SeatState
    {
        public object? Farmer;
        public object? Menu;
        public EvidenceCapture? Latest;
        public long Incarnation;
        public EvidenceScope? Scope;
        public long Sequence;
        public bool Broken = true;
    }
    private readonly object _gate = new();
    private readonly SeatState[] _seats = { new(), new() };
    private readonly string _adapter = Guid.NewGuid().ToString("N");
    private readonly long _frequency;
    private string? _load;
    private string? _branch;
    private bool _enabled, _p1, _disclosure;
    public DiagnosticEvidenceCache(long clockFrequency)
    {
        if (clockFrequency <= 0) throw new ArgumentOutOfRangeException(nameof(clockFrequency));
        _frequency = clockFrequency;
    }

    public void Configure(bool collection, bool allowP1, bool disclosure)
    {
        lock (_gate)
        {
            if ((_enabled, _p1, _disclosure) != (collection, allowP1, disclosure)) ClearSeats();
            (_enabled, _p1, _disclosure) = (collection, allowP1, disclosure);
        }
    }
    public void HostLoaded()
    {
        lock (_gate)
        {
            ClearSeats();
            _load = Guid.NewGuid().ToString("N");
            _branch = Guid.NewGuid().ToString("N");
        }
    }
    public void ReturnedToTitle()
    {
        lock (_gate) { ClearSeats(); _load = _branch = null; }
    }
    public void Clear() { lock (_gate) ClearSeats(); }
    private void ClearSeats()
    {
        foreach (var s in _seats) Retire(s);
    }
    private static void Retire(SeatState s)
    {
        s.Farmer = s.Menu = null;
        s.Latest = null;
        s.Scope = null;
        s.Sequence = 0;
        s.Broken = true;
    }
    /// <summary>Candidate menu events invalidate immediately, including identical close/reopen.</summary>
    public void BreakScreen(int screen)
    {
        if (screen is < 0 or > 1) return;
        lock (_gate)
        {
            var s = _seats[screen];
            s.Menu = null;
            s.Latest = null;
            s.Broken = true;
        }
    }
    public void SeatUnavailable(int screen)
    {
        if (screen is < 0 or > 1) return;
        lock (_gate) Retire(_seats[screen]);
    }

    /// <summary>
    /// Only the current screen's update may call this. Farmer/menu references stay private for
    /// reference identity comparisons. Coverage is an asserted fixture input; the live bridge uses false.
    /// </summary>
    public EvidenceCapture? Capture(int screen, object farmer, string role, long tick,
        long monotonicTicks, DateTimeOffset utc, object? menu, bool dialogue,
        string? question, bool isQuestion, IReadOnlyList<string>? labels,
        bool complete = true, bool transitioning = false, bool lifecycleCoverage = false)
    {
        if (screen is < 0 or > 1) return null;
        lock (_gate)
        {
            var s = _seats[screen];
            if (!_enabled || _load == null || (screen == 0 && !_p1)
                || role != (screen == 0 ? "human" : "ai"))
            { Retire(s); return null; }
            if (tick < 0 || monotonicTicks < 0) throw new ArgumentOutOfRangeException(nameof(tick));
            if (farmer == null) throw new ArgumentNullException(nameof(farmer));
            if (!ReferenceEquals(farmer, s.Farmer))
            {
                Retire(s);
                s.Farmer = farmer;
                s.Incarnation++;
            }
            var old = s.Latest;
            if (old != null && (tick <= old.Tick || monotonicTicks < old.MonotonicTicks))
            {
                // Invalid ordering cannot leave the old identity eligible.
                Retire(s);
                throw new InvalidOperationException("Out-of-order diagnostic capture");
            }
            bool gap = old != null && (tick != old.Tick + 1
                || (monotonicTicks - old.MonotonicTicks) / (double)_frequency > MaxGapSeconds);
            bool continuous = old != null && !s.Broken && !gap && lifecycleCoverage && old.LifecycleCoverage
                && old.Complete && complete && !transitioning;
            bool bounded = (question?.Length ?? 0) <= MaxQuestionChars
                && (labels?.Count ?? 0) <= MaxResponses
                && (labels == null || labels.All(l => l != null && l.Length <= MaxLabelChars));
            complete &= bounded && (!dialogue || (menu != null && question != null && (!isQuestion || labels != null)));
            continuous &= complete;
            EvidencePrompt? prompt = null;
            if (dialogue && menu != null)
            {
                string q = (question ?? "")[..Math.Min(question?.Length ?? 0, MaxQuestionChars)];
                var responses = (labels ?? Array.Empty<string>()).Take(MaxResponses)
                    .Select((l, i) => new EvidenceResponse(i, (l ?? "")[..Math.Min(l?.Length ?? 0, MaxLabelChars)])).ToArray();
                var prior = old?.Prompt;
                bool same = continuous && ReferenceEquals(menu, s.Menu) && prior != null;
                string instance = same ? prior!.InstanceId : Guid.NewGuid().ToString("N");
                long revision = same ? prior!.Revision + (prior.Question != q || prior.IsQuestion != isQuestion
                    || !prior.Responses.SequenceEqual(responses) ? 1 : 0) : 1;
                prompt = new EvidencePrompt(instance, revision, q, isQuestion, responses);
            }
            var scope = s.Scope ??= new EvidenceScope(_adapter, _load, _branch!, screen,
                screen == 0 ? "p1" : "p2", Guid.NewGuid().ToString("N"), s.Incarnation);
            var capture = new EvidenceCapture(scope, ++s.Sequence, tick,
                monotonicTicks, _frequency, utc, complete, continuous, lifecycleCoverage,
                !complete ? "unavailable" : dialogue ? "present" : menu == null ? "absent" : "unsupported",
                prompt, menu?.GetType().Name, transitioning, !complete ? "incomplete_copy"
                    : !lifecycleCoverage ? "lifecycle_unverified" : !continuous ? "continuity_uncertain" : null);
            s.Menu = menu;
            s.Latest = capture;
            // Uncertainty on entry AND recovery retires candidate identity.
            s.Broken = !complete || transitioning || !lifecycleCoverage || gap;
            return capture;
        }
    }

    public EvidenceRead Read(string seat, long nowTicks, string clockId, double maxAgeSeconds)
    {
        lock (_gate)
        {
            if (seat != "p1" && seat != "p2") return new("invalid_seat", null, null);
            if (!_enabled) return new("disabled", null, null);
            var c = _seats[seat == "p1" ? 0 : 1].Latest;
            if (c == null) return new("unavailable", null, null);
            double age = (nowTicks - (double)c.MonotonicTicks) / _frequency;
            if (clockId != _adapter || !double.IsFinite(maxAgeSeconds) || maxAgeSeconds < 0
                || age < 0 || age > maxAgeSeconds)
                return new("stale", null, null);
            return new("captured", c, age);
        }
    }
}
