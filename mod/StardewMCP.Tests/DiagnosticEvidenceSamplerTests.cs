using System;
using System.Diagnostics;
using System.Reflection;
using StardewMCP.Agent;
using StardewModdingAPI;
using StardewValley;
using StardewValley.Menus;
using Xunit;

namespace StardewMCP.Tests;

public class DiagnosticEvidenceSamplerTests
{
    public DiagnosticEvidenceSamplerTests()
    {
        Game1.ThrowOnPlayerRead = Game1.fadeToBlack = Game1.isWarping = Game1.newDay = false;
    }

    private static DiagnosticEvidenceCache Cache(DiagnosticEvidenceSampler sampler) =>
        (DiagnosticEvidenceCache)typeof(DiagnosticEvidenceSampler).GetField("_cache", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(sampler)!;
    private static EvidenceCapture? Latest(DiagnosticEvidenceSampler sampler, int screen)
    {
        var states = (Array)typeof(DiagnosticEvidenceCache).GetField("_seats", BindingFlags.NonPublic | BindingFlags.Instance)!
            .GetValue(Cache(sampler))!;
        var state = states.GetValue(screen)!;
        return (EvidenceCapture?)state.GetType().GetField("Latest")!.GetValue(state);
    }

    [Fact]
    public void Real_bridge_uses_own_screen_only_and_never_changes_roles_or_bookkeeping()
    {
        var config = new DiagnosticObservationConfig { CollectionEnabled = true, AllowHumanP1Collection = true };
        var sampler = new DiagnosticEvidenceSampler(config);
        sampler.HostLoaded();
        var p1 = new PlayerSlot { Screen = 0, Role = SeatRole.Human, Connected = true, TimedOut = true, Released = true };
        var p2 = new PlayerSlot { Screen = 1, Role = SeatRole.Ai };
        Context.IsWorldReady = true;
        Context.ScreenId = 0;
        Game1.player = new object();
        Game1.activeClickableMenu = new DialogueBox { Text = "P1 private", isQuestion = true,
            responses = new[] { new FakeResponse { responseText = "P1 label" } } };
        sampler.Sample(p1, 1);
        var first = Latest(sampler, 0)!;
        Context.ScreenId = 1;
        Game1.player = new object();
        Game1.activeClickableMenu = new DialogueBox { Text = "P2 synthetic", isQuestion = false };
        sampler.Sample(p2, 1);
        var second = Latest(sampler, 1)!;
        Assert.Equal("P1 private", first.Prompt!.Question);
        Assert.Equal("P2 synthetic", second.Prompt!.Question);
        Assert.Equal(first.Scope.LoadId, second.Scope.LoadId);
        Assert.False(first.LifecycleCoverage || second.IdentityKnown);
        Assert.True(p1.Connected && p1.TimedOut && p1.Released);
        Assert.Equal(3, p1.MailCount);
        Assert.Equal(SeatRole.Human, p1.Role);
        Assert.False(p2.Connected || p2.TimedOut || p2.Released);
        Game1.fadeToBlack = true;
        sampler.Sample(p2, 2);
        Assert.True(Latest(sampler, 1)!.Transitioning);
        Game1.fadeToBlack = false;
        sampler.ScreenJoining();
        Assert.Null(Latest(sampler, 1));
        sampler.Sample(p2, 3);
        sampler.MenuChanged();
        Assert.Null(Cache(sampler).Read("p2", Stopwatch.GetTimestamp(), second.ClockId, 1).Capture);
        sampler.ReturnedToTitle();
        Assert.Null(Cache(sampler).Read("p1", Stopwatch.GetTimestamp(), first.ClockId, 1).Capture);
    }

    [Fact]
    public void Disabled_unconsented_and_wrong_role_screens_do_not_read_game_fields()
    {
        var config = new DiagnosticObservationConfig();
        var sampler = new DiagnosticEvidenceSampler(config);
        var seat = new PlayerSlot { Screen = 0, Role = SeatRole.Human };
        Context.IsWorldReady = true;
        Context.ScreenId = 0;
        Game1.Reads = 0;
        sampler.Sample(seat, 1);
        config.CollectionEnabled = true;
        sampler.Sample(seat, 2);
        config.AllowHumanP1Collection = true;
        seat.Role = SeatRole.Ai;
        sampler.Sample(seat, 3);
        seat.Role = SeatRole.Human;
        Context.ScreenId = 1; // A wrong screen must not fall back to the current Game1 player.
        sampler.Sample(seat, 4);
        Assert.Equal(0, Game1.Reads);
    }
    [Fact]
    public void SaveLoaded_dispatch_keeps_P2_join_in_host_epoch_and_quarantines_early_join()
    {
        var sampler = new DiagnosticEvidenceSampler(new() { CollectionEnabled = true, AllowHumanP1Collection = true });
        Context.IsWorldReady = true;
        Context.ScreenId = 1;
        Game1.player = new object();
        Game1.activeClickableMenu = null;
        var p2 = new PlayerSlot { Screen = 1, Role = SeatRole.Ai };
        sampler.SaveLoaded();
        sampler.Sample(p2, 1);
        Assert.Null(Latest(sampler, 1));
        Context.ScreenId = 0;
        sampler.SaveLoaded();
        var p1 = new PlayerSlot { Screen = 0, Role = SeatRole.Human };
        sampler.Sample(p1, 2);
        var host = Latest(sampler, 0)!;
        Context.ScreenId = 1;
        sampler.Sample(p2, 2);
        var joined = Latest(sampler, 1)!;
        sampler.SaveLoaded();
        Assert.Null(Latest(sampler, 1));
        Assert.Same(host, Latest(sampler, 0));
        sampler.Sample(p2, 3);
        Assert.Equal(host.Scope.LoadId, Latest(sampler, 1)!.Scope.LoadId);
        Assert.True(Latest(sampler, 1)!.Scope.Incarnation > joined.Scope.Incarnation);
        Context.ScreenId = 0;
        sampler.SaveLoaded();
        Assert.Null(Latest(sampler, 0));
        Assert.Null(Latest(sampler, 1));
        sampler.Sample(p1, 4);
        Assert.NotEqual(host.Scope.LoadId, Latest(sampler, 0)!.Scope.LoadId);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Capture_failure_is_counted_without_retaining_details_and_recovery_retires_identity(bool playerRead)
    {
        var sampler = new DiagnosticEvidenceSampler(new() { CollectionEnabled = true });
        Context.IsWorldReady = true;
        Context.ScreenId = 1;
        sampler.SaveLoaded(); // Still requires host authority.
        sampler.HostLoaded();
        var seat = new PlayerSlot { Screen = 1, Role = SeatRole.Ai };
        var menu = new DialogueBox { Text = "synthetic", isQuestion = false };
        Game1.player = new object();
        Game1.activeClickableMenu = menu;
        sampler.Sample(seat, 1);
        var before = Latest(sampler, 1)!;
        if (playerRead) Game1.ThrowOnPlayerRead = true;
        else menu.ThrowOnRead = true;
        sampler.Sample(seat, 2);
        Assert.True(sampler.LastSampleFailed);
        Assert.Equal(1, sampler.CaptureFailureCount);
        Assert.Null(Latest(sampler, 1));
        sampler.Sample(seat, 3);
        Assert.Equal(2, sampler.CaptureFailureCount);
        Game1.ThrowOnPlayerRead = menu.ThrowOnRead = false;
        Context.IsWorldReady = false;
        sampler.Sample(seat, 4);
        Assert.False(sampler.LastSampleFailed); // Normal unavailable is distinct from failure.
        Assert.Equal(2, sampler.CaptureFailureCount);
        Context.IsWorldReady = true;
        sampler.Sample(seat, 5);
        var after = Latest(sampler, 1)!;
        Assert.NotEqual(before.Prompt!.InstanceId, after.Prompt!.InstanceId);
        Assert.False(sampler.LastSampleFailed);
        Assert.Equal(2, sampler.CaptureFailureCount);
        Assert.False(seat.Connected || seat.TimedOut || seat.Released);
        Assert.Equal(3, seat.MailCount);
    }

}
