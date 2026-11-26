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
        Assert.True(observation.MorningCue);
        Assert.True(observation.WorldReady);
        Assert.True(observation.InteractionReady);
        Assert.Equal(new SunnyAffordance(true, true), observation.Tv);
        Assert.Equal(new SunnyIndoorChoiceFacts(SunnyReadiness.Ready, SunnyPosture.Seated,
            new SunnyChair("A", true), "B", new SunnyAffordance(true, true), SunnyWeather.Rain,
            SunnyTvAvailability.Available), observation.ChoiceFacts);
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
        Assert.Null(observation.MorningCue);
        Assert.Null(observation.WorldReady);
        Assert.Null(observation.InteractionReady);
        Assert.Equal(default, observation.Tv);
        Assert.False(observation.ChoiceFacts.ReadyForInteraction);
        Assert.Equal(new SunnyIndoorChoiceFacts(SunnyReadiness.Unknown, SunnyPosture.Unknown,
            default, null, default, SunnyWeather.Unknown, default), observation.ChoiceFacts);
    }

    [Theory]
    [InlineData(true, true, (int)SunnyReadiness.Ready)]
    [InlineData(true, false, (int)SunnyReadiness.NotReady)]
    [InlineData(true, null, (int)SunnyReadiness.Unknown)]
    [InlineData(false, true, (int)SunnyReadiness.NotReady)]
    [InlineData(false, false, (int)SunnyReadiness.NotReady)]
    [InlineData(false, null, (int)SunnyReadiness.NotReady)]
    [InlineData(null, true, (int)SunnyReadiness.Unknown)]
    [InlineData(null, false, (int)SunnyReadiness.NotReady)]
    [InlineData(null, null, (int)SunnyReadiness.Unknown)]
    public void Projects_readiness_with_false_dominance(bool? world, bool? interaction, int expected)
    {
        var observation = Project(Ready with { WorldReady = world, InteractionReady = interaction });

        Assert.Equal(world, observation.WorldReady);
        Assert.Equal(interaction, observation.InteractionReady);
        Assert.Equal((SunnyReadiness)expected, observation.ChoiceFacts.Readiness);
        Assert.Equal(expected == (int)SunnyReadiness.Ready, observation.ChoiceFacts.ReadyForInteraction);
    }

    [Theory]
    [InlineData(true, true, (int)SunnyTvAvailability.Available)]
    [InlineData(true, false, (int)SunnyTvAvailability.Unavailable)]
    [InlineData(true, null, (int)SunnyTvAvailability.Unknown)]
    [InlineData(false, true, (int)SunnyTvAvailability.Unavailable)]
    [InlineData(false, false, (int)SunnyTvAvailability.Unavailable)]
    [InlineData(false, null, (int)SunnyTvAvailability.Unavailable)]
    [InlineData(null, true, (int)SunnyTvAvailability.Unknown)]
    [InlineData(null, false, (int)SunnyTvAvailability.Unavailable)]
    [InlineData(null, null, (int)SunnyTvAvailability.Unknown)]
    public void Projects_tv_availability_with_false_dominance(bool? available, bool? reachable, int expected)
    {
        var observation = Project(Ready with { Tv = new(available, reachable) });

        Assert.Equal(new SunnyAffordance(available, reachable), observation.Tv);
        Assert.Equal((SunnyTvAvailability)expected, observation.ChoiceFacts.TvAvailability);
    }

    [Fact]
    public void Readiness_evidence_obeys_normalized_choice_equality()
    {
        var blocked = Project(Ready with { WorldReady = false, InteractionReady = null });
        var stillBlocked = Project(Ready with { WorldReady = false });
        var unknown = Project(Ready with { WorldReady = null });

        Assert.NotEqual(blocked, stillBlocked);
        Assert.Equal(blocked.ChoiceFacts, stillBlocked.ChoiceFacts);
        Assert.NotEqual(blocked.ChoiceFacts, unknown.ChoiceFacts);
        Assert.NotEqual(unknown.ChoiceFacts, Project(Ready).ChoiceFacts);
        Assert.NotEqual(blocked.ChoiceFacts, Project(Ready).ChoiceFacts);
    }

    [Fact]
    public void Tv_evidence_obeys_normalized_choice_equality()
    {
        var unavailable = Project(Ready with { Tv = new(false, true) });
        var unreachable = Project(Ready with { Tv = new(true, false) });
        var unknownAvailabilityButUnreachable = Project(Ready with { Tv = new(null, false) });
        var unknown = Project(Ready with { Tv = new(null, null) });

        Assert.NotEqual(unavailable, unreachable);
        Assert.Equal(unavailable.ChoiceFacts, unreachable.ChoiceFacts);
        Assert.Equal(unavailable.ChoiceFacts, unknownAvailabilityButUnreachable.ChoiceFacts);
        Assert.NotEqual(unknown.ChoiceFacts, unknownAvailabilityButUnreachable.ChoiceFacts);
        Assert.NotEqual(unknown.ChoiceFacts, Project(Ready).ChoiceFacts);
        Assert.NotEqual(unavailable.ChoiceFacts, Project(Ready).ChoiceFacts);
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
    public void Candidate_chair_retains_existing_affordance_semantics()
    {
        var unknownReach = Project(Ready with { CandidateChair = new(true, null) }).ChoiceFacts;
        var unavailable = Project(Ready with { CandidateChair = new(false, true) }).ChoiceFacts;
        var unknown = Project(Ready with { CandidateChair = new(null, true) }).ChoiceFacts;
        var unreachable = Project(Ready with { CandidateChair = new(true, false) }).ChoiceFacts;

        Assert.Equal("B", unknownReach.CandidateChairId);
        Assert.Equal(new SunnyAffordance(true, null), unknownReach.CandidateChair);
        Assert.NotEqual(Project(Ready).ChoiceFacts, unknownReach);
        Assert.Equal(new SunnyAffordance(false, null), unavailable.CandidateChair);
        Assert.Null(unavailable.CandidateChairId);
        Assert.Equal(default, unknown.CandidateChair);
        Assert.Null(unknown.CandidateChairId);
        Assert.Equal(new SunnyAffordance(true, false), unreachable.CandidateChair);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" ")]
    public void Missing_or_blank_candidate_id_remains_distinct_from_a_usable_target(string? id)
    {
        var observation = Project(Ready with { CandidateChairId = id });
        var usableTarget = Project(Ready).ChoiceFacts;

        Assert.Null(observation.ChoiceFacts.CandidateChairId);
        Assert.Equal("B", usableTarget.CandidateChairId);
        Assert.Equal(new SunnyAffordance(true, true), observation.ChoiceFacts.CandidateChair);
        Assert.NotEqual(usableTarget, observation.ChoiceFacts);
    }

    [Theory]
    [InlineData(true, false)]
    [InlineData(true, null)]
    [InlineData(false, true)]
    [InlineData(false, null)]
    [InlineData(null, true)]
    [InlineData(null, false)]
    public void Morning_cue_changes_observation_without_changing_choices(bool? before, bool? after)
    {
        var previous = Project(Ready with { MorningCue = before });
        var current = Project(Ready with { MorningCue = after });

        Assert.Equal(before, previous.MorningCue);
        Assert.Equal(after, current.MorningCue);
        Assert.NotEqual(previous, current);
        Assert.Equal(previous.ChoiceFacts, current.ChoiceFacts);
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    [InlineData(null)]
    public void Only_supplied_morning_evidence_projects(bool? cue)
    {
        var facts = Ready with { MorningCue = cue };
        Assert.Equal(cue, Project(facts).MorningCue);
        Assert.Equal(cue, Project(facts with { Clock = 610 }).MorningCue);
        Assert.Equal(cue, Project(facts with { Revision = 2 }).MorningCue);
        Assert.Equal(cue, Project(facts with { FarmDay = 23 }).MorningCue);
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
