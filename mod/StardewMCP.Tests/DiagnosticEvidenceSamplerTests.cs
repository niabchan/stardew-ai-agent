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
}
