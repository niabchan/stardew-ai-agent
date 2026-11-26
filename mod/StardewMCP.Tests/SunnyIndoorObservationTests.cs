using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

public class SunnyIndoorObservationTests
{
    private static readonly SunnyIndoorScope Scope = new(2, "sunny", "cabin-A", "load-1");
    private static readonly SunnyIndoorFacts Ready = new(
        Scope, Indoors: true, Revision: 1, Fresh: true, InTransition: false,
        WorldReady: true, InteractionReady: true, FarmDay: 22, Clock: 600, MorningCue: true,
        Posture: SunnyPosture.Seated, IsSitting: true, CurrentChair: new("A", true),
        CandidateChairId: "B", CandidateChair: new(true, true), Weather: SunnyWeather.Rain,
        Tv: new(true, true));

    private static SunnyIndoorObservation Project(SunnyIndoorFacts facts) =>
        Assert.IsType<SunnyIndoorObservation>(SunnyIndoorObservation.Project(Scope, facts));

    [Fact]
    public void Projects_complete_supplied_ready_observation()
    {
        var observation = Project(Ready);

        Assert.Equal(Scope, observation.Scope);
        Assert.Equal(1L, observation.Revision);
        Assert.Equal(22, observation.FarmDay);
        Assert.Equal(600, observation.Clock);
        Assert.Equal(new SunnyIndoorChoiceFacts(true, true, true, SunnyPosture.Seated,
            new SunnyChair("A", true), "B", new SunnyAffordance(true, true), SunnyWeather.Rain,
            new SunnyAffordance(true, true)), observation.ChoiceFacts);
        Assert.True(observation.ChoiceFacts.ReadyForInteraction);
    }

    [Theory]
    [InlineData(1, "sunny", "cabin-A", "load-1")]
    [InlineData(null, "sunny", "cabin-A", "load-1")]
    [InlineData(2, "other", "cabin-A", "load-1")]
    [InlineData(2, null, "cabin-A", "load-1")]
    [InlineData(2, "sunny", "cabin-B", "load-1")]
    [InlineData(2, "sunny", null, "load-1")]
    [InlineData(2, "sunny", "cabin-A", "load-2")]
    [InlineData(2, "sunny", "cabin-A", null)]
    [InlineData(2, "sunny", "cabin-A", " ")]
    public void Rejects_wrong_or_unproven_scope(int? seat, string? player, string? scene, string? load)
    {
        var scope = new SunnyIndoorScope(seat, player, scene, load);
        var facts = Ready with { Scope = scope };
        Assert.Null(SunnyIndoorObservation.Project(Scope, facts));
    }

    [Fact]
    public void Matching_unproven_scope_is_unusable()
    {
        var scope = Scope with { LoadId = null };
        Assert.Null(SunnyIndoorObservation.Project(scope, Ready with { Scope = scope }));
    }

    [Theory]
    [InlineData(false, true, false, 1L)]
    [InlineData(null, true, false, 1L)]
    [InlineData(true, false, false, 1L)]
    [InlineData(true, null, false, 1L)]
    [InlineData(true, true, true, 1L)]
    [InlineData(true, true, null, 1L)]
    [InlineData(true, true, false, null)]
    [InlineData(true, true, false, -1L)]
    public void Rejects_unusable_samples(bool? indoors, bool? fresh, bool? transition, long? revision)
    {
        var facts = Ready with { Indoors = indoors, Fresh = fresh, InTransition = transition, Revision = revision };
        Assert.Null(SunnyIndoorObservation.Project(Scope, facts));
    }

    [Fact]
    public void Scoped_sample_can_have_only_unknown_individual_facts()
    {
        var observation = Project(new SunnyIndoorFacts(
            Scope, Indoors: true, Revision: 0, Fresh: true, InTransition: false));

        Assert.Null(observation.FarmDay);
        Assert.Null(observation.Clock);
        Assert.False(observation.ChoiceFacts.ReadyForInteraction);
        Assert.Equal(new SunnyIndoorChoiceFacts(null, null, null, SunnyPosture.Unknown,
            default, null, default, SunnyWeather.Unknown, default), observation.ChoiceFacts);
    }

    [Theory]
    [InlineData(true, null)]
    [InlineData(true, false)]
    [InlineData(false, true)]
    [InlineData(null, true)]
    public void Requires_both_readiness_signals(bool? world, bool? interaction)
    {
        var facts = Project(Ready with { WorldReady = world, InteractionReady = interaction }).ChoiceFacts;

        Assert.Equal(world, facts.WorldReady);
        Assert.Equal(interaction, facts.InteractionReady);
        Assert.False(facts.ReadyForInteraction);
    }

    [Theory]
    [InlineData((int)SunnyPosture.Unknown, false, null, null)]
    [InlineData((int)SunnyPosture.Unknown, false, false, null)]
    [InlineData((int)SunnyPosture.Unknown, true, true, "A")]
    [InlineData((int)SunnyPosture.Standing, false, null, null)]
    [InlineData((int)SunnyPosture.Standing, false, true, "A")]
    [InlineData((int)SunnyPosture.Standing, true, false, null)]
    [InlineData((int)SunnyPosture.Seated, true, true, null)]
    [InlineData((int)SunnyPosture.Seated, true, true, " ")]
    [InlineData((int)SunnyPosture.Seated, true, false, null)]
    [InlineData((int)SunnyPosture.Seated, false, true, "A")]
    public void Missing_or_conflicting_posture_evidence_stays_unknown(
        int posture, bool? sitting, bool? chairPresent, string? chairId)
    {
        var facts = Project(Ready with
        {
            Posture = (SunnyPosture)posture, IsSitting = sitting, CurrentChair = new(chairId, chairPresent)
        }).ChoiceFacts;

        Assert.Equal(SunnyPosture.Unknown, facts.Posture);
        Assert.Equal(default, facts.CurrentChair);
    }

    [Fact]
    public void Affordance_presence_and_reachability_remain_independent()
    {
        var unknownReach = Project(Ready with { CandidateChair = new(true, null), Tv = new(true, null) }).ChoiceFacts;
        var unavailable = Project(Ready with { CandidateChair = new(false, true), Tv = new(false, true) }).ChoiceFacts;
        var unknown = Project(Ready with { CandidateChair = new(null, true), Tv = new(null, true) }).ChoiceFacts;
        var unreachable = Project(Ready with { CandidateChair = new(true, false), Tv = new(true, false) }).ChoiceFacts;

        Assert.Equal("B", unknownReach.CandidateChairId);
        Assert.Equal(new SunnyAffordance(true, null), unknownReach.CandidateChair);
        Assert.Equal(new SunnyAffordance(true, null), unknownReach.Tv);
        Assert.NotEqual(Project(Ready).ChoiceFacts, unknownReach);
        Assert.Equal(new SunnyAffordance(false, null), unavailable.CandidateChair);
        Assert.Equal(new SunnyAffordance(false, null), unavailable.Tv);
        Assert.Null(unavailable.CandidateChairId);
        Assert.Equal(default, unknown.CandidateChair);
        Assert.Equal(default, unknown.Tv);
        Assert.Null(unknown.CandidateChairId);
        Assert.Equal(new SunnyAffordance(true, false), unreachable.CandidateChair);
        Assert.Equal(new SunnyAffordance(true, false), unreachable.Tv);
    }

    [Theory]
    [InlineData(null)]
    [InlineData(false)]
    public void Only_supplied_morning_evidence_projects(bool? cue)
    {
        var facts = Ready with { MorningCue = cue };
        Assert.Equal(cue, Project(facts).ChoiceFacts.MorningCue);
        Assert.Equal(cue, Project(facts with { Clock = 610 }).ChoiceFacts.MorningCue);
        Assert.Equal(cue, Project(facts with { Revision = 2 }).ChoiceFacts.MorningCue);
        Assert.Equal(cue, Project(facts with { FarmDay = 23 }).ChoiceFacts.MorningCue);
    }

    [Fact]
    public void Choice_facts_exclude_clock_revision_and_day()
    {
        var before = Project(Ready);
        var after = Project(Ready with { Clock = 610, Revision = 2 });

        Assert.NotEqual(before, after);
        Assert.Equal(before.ChoiceFacts, after.ChoiceFacts);
        Assert.Equal(before.ChoiceFacts, Project(Ready with { FarmDay = 23 }).ChoiceFacts);
    }

    [Fact]
    public void Posture_and_availability_independently_change_choice_facts()
    {
        var before = Project(Ready).ChoiceFacts;
        var standing = Project(Ready with
        {
            Posture = SunnyPosture.Standing, IsSitting = false, CurrentChair = new(null, false)
        }).ChoiceFacts;

        Assert.Equal(SunnyPosture.Standing, standing.Posture);
        Assert.Equal(new SunnyChair(null, false), standing.CurrentChair);
        Assert.NotEqual(before, standing);
        Assert.NotEqual(before, Project(Ready with { CandidateChair = new(false, null) }).ChoiceFacts);
        Assert.NotEqual(before, Project(Ready with { Tv = new(false, null) }).ChoiceFacts);
    }
}
