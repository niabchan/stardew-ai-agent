using System;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

public class DiagnosticStatusTests
{
    private readonly DiagnosticEvidenceCache _cache = new(1000);
    private readonly object _farmer = new(), _menu = new();
    private EvidenceCapture Capture(int screen = 1, long tick = 1, long time = 1000,
        bool complete = true) => _cache.Capture(screen, _farmer, screen == 0 ? "human" : "ai",
            tick, time, DateTimeOffset.UnixEpoch, _menu, true, "PRIVATE_DIALOGUE",
            true, new[] { "PRIVATE_LABEL" }, complete: complete)!;
    private DiagnosticStatus Status(long now = 1100, bool consent = false) =>
        _cache.ReadStatus(true, consent, false, now);
    private void Enable(bool consent = false)
    {
        _cache.Configure(true, consent, false);
        _cache.HostLoaded();
    }

    [Fact]
    public void Disabled_and_missing_captures_do_not_create_evidence()
    {
        Assert.Equal("disabled", _cache.ReadStatus(false, false, false, 1000).P2SamplingStatus);
        Assert.Equal(0, Status().CaptureCount);
        Enable();
        Assert.Equal("unavailable", Status().P2SamplingStatus);
        Assert.Null(Status().AgeSeconds);
        Assert.Equal("unavailable", Status().PromptStatus);
    }

    [Fact]
    public void Repeated_reads_preserve_original_capture_and_identity()
    {
        Enable();
        var capture = Capture();
        var first = Status();
        Assert.Equal(first, Status());
        Assert.Equal("captured", first.P2SamplingStatus);
        Assert.Equal(1, first.CaptureCount);
        Assert.Equal(0.1, first.AgeSeconds);
        Assert.Equal("present", first.PromptStatus);
        Assert.False(first.LifecycleCoverage || first.IdentityKnown);
        Assert.Equal(0.2, Status(1200).AgeSeconds);
        Assert.Same(capture, _cache.Read("p2", 1200, capture.ClockId, 1).Capture);
        Assert.Equal(DateTimeOffset.UnixEpoch, capture.CapturedUtc);
        Assert.Equal(1000, capture.MonotonicTicks);
        Assert.Null(capture.OfferToken);
        Assert.False(capture.GuardedDispatch || capture.GiftClassification
            || capture.TransferVerification || capture.CheckpointReconciliation);
        Assert.Equal(2, Capture(tick: 2, time: 1200).Sequence);
    }

    [Theory]
    [InlineData(2001, "stale", 1.001)]
    [InlineData(999, "stale", null)]
    [InlineData(2000, "captured", 1.0)]
    public void Freshness_is_computed_without_restamping(long now, string expected, double? age)
    {
        Enable();
        var capture = Capture();
        Assert.Equal(expected, Status(now).P2SamplingStatus);
        Assert.Equal(age, Status(now).AgeSeconds);
        Assert.Same(capture, _cache.Read("p2", 1000, capture.ClockId, 1).Capture);
        if (expected == "stale")
        {
            Assert.Equal("unavailable", Status(now).PromptStatus);
            Assert.False(Status(now).IdentityKnown);
        }
    }

    [Fact]
    public void Incomplete_menu_invalidation_title_reload_and_rejoin_are_unavailable()
    {
        Enable();
        Capture(complete: false);
        Assert.Equal("unavailable", Status().PromptStatus);
        _cache.BreakScreen(1);
        Assert.Equal("unavailable", Status().P2SamplingStatus);
        var old = Capture();
        _cache.SeatUnavailable(1);
        Assert.Equal(0, Status().CaptureCount);
        var rejoined = Capture();
        Assert.True(rejoined.Scope.Incarnation > old.Scope.Incarnation);
        Assert.Equal(1, Status().CaptureCount);
        _cache.HostLoaded();
        Assert.Equal("unavailable", Status().P2SamplingStatus);
        var reload = Capture();
        Assert.NotEqual(old.Scope.LoadId, reload.Scope.LoadId);
        _cache.ReturnedToTitle();
        Assert.Equal("unavailable", Status().P2SamplingStatus);
        Assert.Null(Capture());
    }

    [Fact]
    public void P1_is_never_projected_even_with_consent_and_config_changes_hide_old_captures()
    {
        Enable();
        Assert.Null(Capture(0));
        Assert.Equal("unavailable", Status().P2SamplingStatus);
        Enable(consent: true);
        Capture(0);
        Assert.Equal(0, Status(consent: true).CaptureCount);
        var p2 = Capture();
        var status = Status(consent: true);
        Assert.True(status.P1ConsentEnabled);
        Assert.Equal(1, status.CaptureCount);
        Assert.Equal("unavailable", Status(consent: false).P2SamplingStatus);
        Assert.Equal("disabled", _cache.ReadStatus(false, true, false, 1100).P2SamplingStatus);
        Assert.Equal("unavailable", _cache.ReadStatus(true, true, true, 1100).P2SamplingStatus);
        Assert.Same(p2, _cache.Read("p2", 1100, p2.ClockId, 1).Capture);
        var output = status.Format(0, false);
        foreach (var secret in new[] { "PRIVATE_DIALOGUE", "PRIVATE_LABEL", p2.Scope.AdapterInstance,
            p2.Scope.LoadId, p2.Scope.BranchId, p2.Scope.FarmerAlias, p2.Prompt!.InstanceId })
            Assert.DoesNotContain(secret, output);
        Assert.Contains("HTTP disclosure: not implemented", output);
        Assert.DoesNotContain("PRIVATE", output);
    }
}
