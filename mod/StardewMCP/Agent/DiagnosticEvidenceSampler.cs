using System;
using System.Diagnostics;
using System.Linq;
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
    // Explicit local reads only. Do not Configure, Sample, or access any Game1/Players fields here.
    internal string ReadStatus() => _cache.ReadStatus(_config.CollectionEnabled,
        _config.AllowHumanP1Collection, _config.HttpDisclosureEnabled, Stopwatch.GetTimestamp())
        .Format(CaptureFailureCount, LastSampleFailed);
    public void SaveLoaded()
    {
        if (Context.ScreenId == 0) HostLoaded();
        else ScreenJoining(); // Farmhand callbacks never mint host authority.
    }
    public void HostLoaded() => _cache.HostLoaded();
    public void ReturnedToTitle() => _cache.ReturnedToTitle();
    public void ScreenJoining() => _cache.SeatUnavailable(Context.ScreenId);
    public void MenuChanged() => _cache.BreakScreen(Context.ScreenId);
    public void Sample(PlayerSlot seat, uint tick)
    {
        LastSampleFailed = false;
        _cache.Configure(_config.CollectionEnabled, _config.AllowHumanP1Collection,
            _config.HttpDisclosureEnabled);
        if (!_config.CollectionEnabled || seat.Screen is < 0 or > 1) return;
        if (seat.Screen != Context.ScreenId)
        { _cache.SeatUnavailable(seat.Screen); return; }
        try
        {
            // Check role and human consent before touching Game1 fields. Never resolve/change roles here.
            if ((seat.Screen == 0 && (!_config.AllowHumanP1Collection || seat.Role != SeatRole.Human))
                || (seat.Screen == 1 && seat.Role != SeatRole.Ai) || !Context.IsWorldReady
                || Game1.player == null)
            { _cache.SeatUnavailable(seat.Screen); return; }
            long captured = Stopwatch.GetTimestamp();
            var utc = DateTimeOffset.UtcNow;
            var menu = Game1.activeClickableMenu;
            var box = menu as DialogueBox;
            // Copy only demonstrated menu fields; semantic response keys and inventory are unsupported.
            bool question = box?.isQuestion == true;
            var labels = question ? box?.responses?.Take(DiagnosticEvidenceCache.MaxResponses + 1)
                .Select(r => r?.responseText ?? "").ToArray() : null;
            _cache.Capture(seat.Screen, Game1.player, seat.Screen == 0 ? "human" : "ai", tick,
                captured, utc, menu, box != null, box?.getCurrentString(), question, labels,
                transitioning: Game1.fadeToBlack || Game1.isWarping || Game1.newDay,
                lifecycleCoverage: false);
        }
        catch (Exception)
        {
            // Best-effort isolation: never retain exception messages/stacks or private game data.
            LastSampleFailed = true;
            if (CaptureFailureCount < long.MaxValue) CaptureFailureCount++;
            _cache.SeatUnavailable(seat.Screen);
        }
    }
}

