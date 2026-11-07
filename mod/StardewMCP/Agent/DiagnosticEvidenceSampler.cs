using System;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Menus;

namespace StardewMCP.Agent;

/// <summary>Only ModEntry's normal callbacks call this bridge. No HTTP or runtime references.</summary>
internal sealed class DiagnosticEvidenceSampler
{
    private readonly DiagnosticObservationConfig _config;
    private readonly DiagnosticEvidenceCache _cache = new(Stopwatch.Frequency);
    public DiagnosticEvidenceSampler(DiagnosticObservationConfig config) => _config = config;

    // Internal process-lifetime diagnostics only: no exception details, identifiers or logging.
    internal long CaptureFailureCount { get; private set; }
    internal bool LastSampleFailed { get; private set; }

    // Metadata-only event ordering makes late Title/SaveLoaded callbacks visible after a reload.
    // These counters are deliberately process-scoped; they do not identify saves or farmers.
    private long _eventSequence, _hostLoadCount, _titleCount, _p2JoinCount;
    private long _lastHostLoadOrder, _lastTitleOrder, _lastP2JoinOrder;
    private long _p2SampleAttempts, _p2CaptureSuccesses;
    private string _p2LastGate = "not_observed";

    private void SetP2Gate(string gate) => Volatile.Write(ref _p2LastGate, gate);
    private void MarkEvent(ref long count, ref long lastOrder)
    {
        Interlocked.Increment(ref count);
        Interlocked.Exchange(ref lastOrder, Interlocked.Increment(ref _eventSequence));
    }

    // Explicit local reads only. Do not Configure, Sample, or access Game1/Players fields here.
    internal string ReadStatus()
    {
        var status = _cache.ReadStatus(_config.CollectionEnabled,
            _config.AllowHumanP1Collection, _config.HttpDisclosureEnabled, Stopwatch.GetTimestamp())
            .Format(CaptureFailureCount, LastSampleFailed);
        return status
            + "\nReload diagnostics (process counters; read-only, P2-only):"
            + $"\nHost SaveLoaded events: {Interlocked.Read(ref _hostLoadCount)}; "
            + $"Title return events: {Interlocked.Read(ref _titleCount)}; "
            + $"P2 SaveLoaded events: {Interlocked.Read(ref _p2JoinCount)}"
            + $"\nLast event order (host/title/p2 join): "
            + $"{Interlocked.Read(ref _lastHostLoadOrder)}/"
            + $"{Interlocked.Read(ref _lastTitleOrder)}/"
            + $"{Interlocked.Read(ref _lastP2JoinOrder)}"
            + $"\nP2 sample attempts: {Interlocked.Read(ref _p2SampleAttempts)}; "
            + $"successful P2 captures: {Interlocked.Read(ref _p2CaptureSuccesses)}"
            + $"\nP2 last sample gate: {Volatile.Read(ref _p2LastGate)}";
    }

    /// <summary>Called only with a logical seat confirmed by Players.TryCurrent, never SMAPI ScreenId.</summary>
    public void SaveLoaded(int? logicalSeat)
    {
        if (logicalSeat == 0) HostLoaded();
        else if (logicalSeat == 1) ScreenJoining(1); // Farmhands never mint host authority.
    }

    public void HostLoaded()
    {
        _cache.HostLoaded();
        MarkEvent(ref _hostLoadCount, ref _lastHostLoadOrder);
        SetP2Gate("awaiting_p2_tick");
    }

    public void ReturnedToTitle()
    {
        _cache.ReturnedToTitle();
        MarkEvent(ref _titleCount, ref _lastTitleOrder);
        SetP2Gate("title_invalidated");
    }

    public void ScreenJoining(int logicalSeat)
    {
        if (logicalSeat != 1) return; // The diagnostic cache only observes P1/P2.
        _cache.SeatUnavailable(logicalSeat);
        MarkEvent(ref _p2JoinCount, ref _lastP2JoinOrder);
        SetP2Gate("p2_joining");
    }

    public void MenuChanged(int? logicalSeat)
    {
        if (logicalSeat is not (0 or 1)) return;
        _cache.BreakScreen(logicalSeat.Value);
        if (logicalSeat == 1) SetP2Gate("p2_menu_invalidated");
    }

    /// <summary>confirmedLogicalSeat must be resolved from the active game instance on this callback.</summary>
    public void Sample(PlayerSlot seat, uint tick, int? confirmedLogicalSeat)
    {
        LastSampleFailed = false;
        _cache.Configure(_config.CollectionEnabled, _config.AllowHumanP1Collection,
            _config.HttpDisclosureEnabled);
        if (seat.Screen == 1) Interlocked.Increment(ref _p2SampleAttempts);
        if (!_config.CollectionEnabled || seat.Screen is < 0 or > 1)
        {
            if (seat.Screen == 1) SetP2Gate("collection_disabled");
            return;
        }
        if (seat.Screen != confirmedLogicalSeat)
        {
            _cache.SeatUnavailable(seat.Screen);
            if (seat.Screen == 1) SetP2Gate("screen_mismatch");
            return;
        }
        try
        {
            // Do not read Game1 until consent, role and own-screen checks have passed.
            if (seat.Screen == 0 && (!_config.AllowHumanP1Collection || seat.Role != SeatRole.Human))
            {
                _cache.SeatUnavailable(seat.Screen);
                return;
            }
            if (seat.Screen == 1 && seat.Role != SeatRole.Ai)
            {
                _cache.SeatUnavailable(seat.Screen);
                SetP2Gate("p2_role_not_ai");
                return;
            }
            if (!Context.IsWorldReady)
            {
                _cache.SeatUnavailable(seat.Screen);
                if (seat.Screen == 1) SetP2Gate("world_not_ready");
                return;
            }
            var farmer = Game1.player;
            if (farmer == null)
            {
                _cache.SeatUnavailable(seat.Screen);
                if (seat.Screen == 1) SetP2Gate("player_unavailable");
                return;
            }
            long captured = Stopwatch.GetTimestamp();
            var utc = DateTimeOffset.UtcNow;
            var menu = Game1.activeClickableMenu;
            var box = menu as DialogueBox;
            // Copy only demonstrated menu fields; semantic response keys and inventory are unsupported.
            bool question = box?.isQuestion == true;
            var labels = question ? box?.responses?.Take(DiagnosticEvidenceCache.MaxResponses + 1)
                .Select(r => r?.responseText ?? "").ToArray() : null;
            var evidence = _cache.Capture(seat.Screen, farmer, seat.Screen == 0 ? "human" : "ai", tick,
                captured, utc, menu, box != null, box?.getCurrentString(), question, labels,
                transitioning: Game1.fadeToBlack || Game1.isWarping || Game1.newDay,
                lifecycleCoverage: false);
            if (seat.Screen == 1)
            {
                if (evidence == null) SetP2Gate("cache_rejected_no_epoch_or_config");
                else
                {
                    Interlocked.Increment(ref _p2CaptureSuccesses);
                    SetP2Gate("captured");
                }
            }
        }
        catch (Exception)
        {
            // Best-effort isolation: never retain exception messages/stacks or private game data.
            LastSampleFailed = true;
            if (CaptureFailureCount < long.MaxValue) CaptureFailureCount++;
            _cache.SeatUnavailable(seat.Screen);
            if (seat.Screen == 1) SetP2Gate("sample_exception");
        }
    }
}
