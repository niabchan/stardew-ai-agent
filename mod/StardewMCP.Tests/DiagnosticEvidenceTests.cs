using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

public class DiagnosticEvidenceTests
{
    private readonly DiagnosticEvidenceCache _cache = new(1000);
    private readonly object _farmer = new(), _menu = new();
    private static readonly DateTimeOffset Utc = DateTimeOffset.Parse("2026-11-05T00:00:00Z");
    private EvidenceCapture Sample(long tick = 1, string text = "Synthetic question", string[]? labels = null,
        int screen = 1, object? farmer = null, object? menu = null, bool coverage = true,
        bool complete = true, bool transition = false, long? time = null) =>
        _cache.Capture(screen, farmer ?? _farmer, screen == 0 ? "human" : "ai", tick,
            time ?? tick * 10, Utc, menu ?? _menu, true, text, true, labels ?? new[] { "Yes", "No" },
            complete, transition, coverage)!;
    private void Start(bool p1 = false)
    {
        _cache.Configure(true, p1, false);
        _cache.HostLoaded();
    }
    private EvidenceRead Read(EvidenceCapture c, long? now = null, string? seat = null) =>
        _cache.Read(seat ?? c.Scope.Seat, now ?? c.MonotonicTicks, c.ClockId, 1);

    [Fact]
    public void Default_disabled_and_independent_P1_consent_and_roles()
    {
        var config = new DiagnosticObservationConfig();
        Assert.False(config.CollectionEnabled || config.AllowHumanP1Collection || config.HttpDisclosureEnabled);
        Assert.Null(Sample());
        _cache.Configure(false, true, true);
        _cache.HostLoaded();
        Assert.Null(Sample()); // HTTP flag never enables collection.
        Start();
        Assert.Null(Sample(screen: 0));
        Assert.Null(_cache.Capture(0, _farmer, "ai", 1, 1, Utc, null, false, null, false, null));
        Assert.Null(_cache.Capture(1, _farmer, "human", 1, 1, Utc, null, false, null, false, null));
        Assert.Null(_cache.Capture(2, _farmer, "ai", 1, 1, Utc, null, false, null, false, null));
        Assert.NotNull(Sample());
    }

    [Fact]
    public void Continuous_prompt_preserves_instance_and_changes_revision_for_order_and_text()
    {
        Start();
        var first = Sample();
        var next = Sample(2);
        Assert.Equal(first.Prompt!.InstanceId, next.Prompt!.InstanceId);
        Assert.Equal(1, next.Prompt.Revision);
        Assert.True(next.IdentityKnown);
        var reordered = Sample(3, labels: new[] { "No", "Yes" });
        Assert.Equal(2, reordered.Prompt!.Revision);
        var changed = Sample(4, text: "Other", labels: new[] { "No", "Yes" });
        Assert.Equal(3, changed.Prompt!.Revision);
        Assert.Null(changed.OfferToken);
        Assert.False(changed.GuardedDispatch || changed.GiftClassification || changed.TransferVerification
            || changed.CheckpointReconciliation || changed.ResponseKeys || changed.InventorySupported);
    }

    [Theory]
    [InlineData("event")]
    [InlineData("replacement")]
    [InlineData("gap")]
    [InlineData("stall")]
    [InlineData("partial")]
    [InlineData("coverage")]
    [InlineData("transition")]
    public void Uncertainty_and_recovery_never_revive_old_identity(string fault)
    {
        Start();
        var before = Sample();
        long tick = 2;
        if (fault == "event") _cache.BreakScreen(1);
        if (fault == "gap") tick = 3;
        var gap = Sample(tick, menu: fault == "replacement" ? new object() : _menu,
            coverage: fault != "coverage", complete: fault != "partial", transition: fault == "transition",
            time: fault == "stall" ? 2000 : null);
        Assert.NotEqual(before.Prompt!.InstanceId, gap.Prompt!.InstanceId);
        var recovered = Sample(tick + 1, time: fault == "stall" ? 2010 : null);
        Assert.NotEqual(before.Prompt.InstanceId, recovered.Prompt!.InstanceId);
        if (fault is "coverage" or "partial" or "transition" or "gap" or "stall")
            Assert.NotEqual(gap.Prompt.InstanceId, recovered.Prompt.InstanceId);
        Assert.Null(recovered.OfferToken);
        Assert.True(recovered.Sequence > before.Sequence);
    }

    [Fact]
    public void Live_unverified_coverage_never_claims_identity()
    {
        Start();
        var a = Sample(coverage: false);
        var b = Sample(2, coverage: false);
        Assert.False(a.IdentityKnown || b.IdentityKnown);
        Assert.NotEqual(a.Prompt!.InstanceId, b.Prompt!.InstanceId);
        Assert.Equal("lifecycle_unverified", b.UnavailableReason);
    }

    [Fact]
    public void Load_title_seat_loss_farmer_replacement_and_late_P2_do_not_share_identity()
    {
        _cache.Configure(true, true, false);
        Assert.Null(Sample()); // P2 before host authority is quarantined.
        _cache.HostLoaded();
        var p1 = Sample(screen: 0);
        var p2 = Sample();
        Assert.Equal(p1.Scope.LoadId, p2.Scope.LoadId);
        Assert.NotEqual(p1.Scope.FarmerAlias, p2.Scope.FarmerAlias);
        _cache.SeatUnavailable(1);
        Assert.Null(Read(p2).Capture);
        var rejoin = Sample(2);
        Assert.True(rejoin.Scope.Incarnation > p2.Scope.Incarnation);
        var other = Sample(3, farmer: new object());
        Assert.True(other.Scope.Incarnation > rejoin.Scope.Incarnation);
        _cache.HostLoaded();
        Assert.Null(Read(p1).Capture);
        var reload = Sample(4);
        Assert.NotEqual(p2.Scope.LoadId, reload.Scope.LoadId);
        Assert.NotEqual(p2.Scope.BranchId, reload.Scope.BranchId);
        Assert.Null(reload.Scope.SaveId);
        Assert.Null(reload.Scope.ParentCheckpointId);
        _cache.ReturnedToTitle();
        Assert.Null(Read(reload).Capture);
        Assert.Null(Sample(5));
    }

    [Fact]
    public void Cached_reads_never_restamp_and_host_capture_does_not_refresh_P2()
    {
        Start(true);
        var p2 = Sample();
        Sample(200, screen: 0);
        Assert.Same(p2, Read(p2).Capture);
        Assert.Same(p2, Read(p2).Capture);
        Assert.Null(Read(p2, now: 2000).Capture);
        Assert.Null(Read(p2, now: 0).Capture);
        Assert.Null(_cache.Read("p2", 10, "wrong_clock", 1).Capture);
        Assert.Null(_cache.Read("p2", 10, p2.ClockId, double.NaN).Capture);
        Assert.Null(_cache.Read("p2", 10, p2.ClockId, -1).Capture);
        Assert.Equal(Utc, p2.CapturedUtc);
        Assert.Equal(10, p2.MonotonicTicks);
        Assert.Null(_cache.Read("all", 10, p2.ClockId, 1).Capture);
    }

    [Fact]
    public void Copy_bounds_are_incomplete_and_responses_are_immutable()
    {
        Start();
        var labels = new[] { "A", "B" };
        var c = Sample(labels: labels);
        labels[0] = "changed";
        Assert.Equal("A", c.Prompt!.Responses[0].Label);
        Assert.Throws<NotSupportedException>(() => ((IList<EvidenceResponse>)c.Prompt.Responses)[0] = new(0, "changed"));
        var huge = Sample(2, text: new string('x', 3000), labels: Enumerable.Repeat(new string('y', 300), 100).ToArray());
        Assert.False(huge.Complete || huge.IdentityKnown);
        Assert.Equal("unavailable", huge.PromptStatus);
        Assert.Equal(2048, huge.Prompt!.Question.Length);
        Assert.Equal(16, huge.Prompt.Responses.Count);
        Assert.All(huge.Prompt.Responses, r => Assert.Equal(256, r.Label.Length));
    }

    [Fact]
    public void Absence_and_unsupported_menu_and_unavailable_are_distinct()
    {
        Start();
        var absent = _cache.Capture(1, _farmer, "ai", 1, 1, Utc, null, false, null, false, null)!;
        Assert.Equal("absent", absent.PromptStatus);
        var unsupported = _cache.Capture(1, _farmer, "ai", 2, 2, Utc, _menu, false, null, false, null)!;
        Assert.Equal("unsupported", unsupported.PromptStatus);
        var incomplete = _cache.Capture(1, _farmer, "ai", 3, 3, Utc, _menu, true, null, true, null)!;
        Assert.Equal("unavailable", incomplete.PromptStatus);
        _cache.SeatUnavailable(1);
        Assert.Equal("unavailable", Read(incomplete).Status);
    }

    [Theory]
    [InlineData(1, 20)]
    [InlineData(0, 20)]
    [InlineData(2, 9)]
    public void Out_of_order_input_retires_cache_instead_of_restoring_old_capture(long tick, long time)
    {
        Start();
        var old = Sample();
        Assert.Throws<InvalidOperationException>(() => Sample(tick, time: time));
        Assert.Null(Read(old).Capture);
    }

    [Fact]
    public void Disable_consent_revocation_and_disclosure_changes_clear_captures()
    {
        Start(true);
        var old = Sample(screen: 0);
        _cache.Configure(true, false, false);
        Assert.Null(Read(old).Capture);
        var p2 = Sample();
        _cache.Configure(true, false, true);
        Assert.Null(Read(p2).Capture);
        var next = Sample(2);
        _cache.Configure(false, false, true);
        Assert.Equal("disabled", Read(next).Status);
        _cache.Configure(true, false, true);
        Assert.Null(Read(next).Capture);
    }

    [Fact]
    public async Task Readers_observe_whole_immutable_capture_and_title_invalidates_atomically()
    {
        Start();
        var first = Sample();
        var readers = Enumerable.Range(0, 8).Select(_ => Task.Run(() => {
            for (int n = 0; n < 100; n++) {
                var r = Read(first, now: 1000);
                if (r.Capture is { } c) Assert.Equal(c.Tick * 10, c.MonotonicTicks);
            }
        })).ToArray();
        for (int i = 2; i < 100; i++) Sample(i);
        _cache.ReturnedToTitle();
        await Task.WhenAll(readers);
        Assert.Null(Read(first).Capture);
    }
}
