using System;
using System.Collections.Generic;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

public class SunnyIndoorChoicesTests
{
    private const PendingDisposition Clear = PendingDisposition.NoUnresolvedWork;
    private static readonly SunnyIndoorScope Scope = new(2, "sunny", "cabin", "load-1");
    private static readonly IndoorHistory Initial = new(Scope, null, null);
    private static readonly SunnyIndoorFacts Standing = new(
        Scope, Indoors: true, Revision: 10, Fresh: true, InTransition: false,
        WorldReady: true, InteractionReady: true, FarmDay: 1, Clock: 600, MorningCue: true,
        Posture: SunnyPosture.Standing, IsSitting: false, CurrentChair: new(null, false),
        CandidateChairId: "A", CandidateChair: new(true, true), Weather: SunnyWeather.Rain,
        Tv: new(false, true));
    private static readonly SunnyIndoorFacts Seated = Standing with
    {
        Posture = SunnyPosture.Seated, IsSitting = true, CurrentChair = new("A", true),
        CandidateChairId = "B", CandidateChair = new(false, null)
    };

    [Fact]
    public void Voluntary_stay_holds_until_change_and_the_caller_can_retire_or_replace_it()
    {
        var first = Project(Standing);
        var batch = AssertOpen(first, SunnyIndoorChoices.Evaluate(first, Initial, Clear), new(IndoorIntent.Sit, "A"));
        Assert.Throws<NotSupportedException>(() =>
            ((IList<IndoorIntention>)batch.Intentions)[0] = new(IndoorIntent.Stand, "A"));

        var paused = RecordStay(first);
        AssertNoBatch(RoundStatus.HeldByStay, SunnyIndoorChoices.Evaluate(first, paused, Clear));

        var equivalent = Project(Standing with
        {
            Revision = 11, FarmDay = 2, Clock = 900, MorningCue = false, Tv = new(true, false)
        });
        Assert.NotEqual(first.Tv, equivalent.Tv);
        AssertNoBatch(RoundStatus.HeldByStay, SunnyIndoorChoices.Evaluate(equivalent, paused, Clear));

        var changed = Project(Standing with { Revision = 12, CandidateChairId = "B" });
        AssertOpen(changed, SunnyIndoorChoices.Evaluate(changed, paused with { LastAcceptedRevision = 11 }, Clear),
            new(IndoorIntent.Sit, "B"));

        var repeated = Project(Standing with { Revision = 13, CandidateChairId = "B" });
        AssertNoBatch(RoundStatus.HeldByStay, SunnyIndoorChoices.Evaluate(repeated, RecordStay(changed), Clear));

        var returned = Project(Standing with { Revision = 13 });
        var retired = new IndoorHistory(Scope, changed.Revision, null);
        AssertOpen(returned, SunnyIndoorChoices.Evaluate(returned, retired, Clear), new(IndoorIntent.Sit, "A"));
    }

    [Theory]
    [InlineData(false, true, true, false)]
    [InlineData(null, true, true, null)]
    public void Equivalent_raw_readiness_preserves_stay(
        bool? worldBefore, bool? interactionBefore, bool? worldAfter, bool? interactionAfter)
    {
        var first = Project(Standing with { WorldReady = worldBefore, InteractionReady = interactionBefore });
        var later = Project(Standing with { Revision = 11, WorldReady = worldAfter, InteractionReady = interactionAfter });

        AssertOpen(first, SunnyIndoorChoices.Evaluate(first, Initial, Clear));
        AssertNoBatch(RoundStatus.HeldByStay, SunnyIndoorChoices.Evaluate(later, RecordStay(first), Clear));
    }

    [Theory]
    [InlineData((int)SunnyWeather.Sunny, false, true, true)]
    [InlineData((int)SunnyWeather.Rain, true, true, true)]
    [InlineData((int)SunnyWeather.Rain, false, false, false)]
    public void Weather_tv_and_readiness_can_each_reopen(
        int weather, bool tvAvailable, bool ready, bool offersSit)
    {
        var first = Project(Standing);
        var later = Project(Standing with
        {
            Revision = 11, Weather = (SunnyWeather)weather, Tv = new(tvAvailable, true), WorldReady = ready
        });
        var round = SunnyIndoorChoices.Evaluate(later, RecordStay(first), Clear);

        if (offersSit)
            AssertOpen(later, round, new(IndoorIntent.Sit, "A"));
        else
            AssertOpen(later, round);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Pending_is_caller_supplied_and_posture_changes_do_not_clear_it(bool unresolved)
    {
        var pending = unresolved ? PendingDisposition.Unresolved : PendingDisposition.Unknown;
        var seated = Project(Seated);
        var standing = Project(Standing with { Revision = 11, CandidateChairId = "B" });
        var history = new IndoorHistory(Scope, seated.Revision, null);

        AssertOpen(seated, SunnyIndoorChoices.Evaluate(seated, Initial, pending));
        AssertOpen(standing, SunnyIndoorChoices.Evaluate(standing, history, pending));
        AssertOpen(standing, SunnyIndoorChoices.Evaluate(standing, history));
        AssertOpen(standing, SunnyIndoorChoices.Evaluate(standing, history, Clear), new(IndoorIntent.Sit, "B"));
        AssertOpen(seated, SunnyIndoorChoices.Evaluate(seated, Initial, Clear), new(IndoorIntent.Stand, "A"));

        var equivalent = standing with { Revision = 12 };
        AssertNoBatch(RoundStatus.HeldByStay, SunnyIndoorChoices.Evaluate(equivalent, RecordStay(standing), Clear));
    }

    [Theory]
    [InlineData(null, true, true)]
    [InlineData(" ", true, true)]
    [InlineData("A", false, true)]
    [InlineData("A", null, true)]
    [InlineData("A", true, false)]
    [InlineData("A", true, null)]
    public void Sit_requires_identified_available_and_reachable_chair(string? id, bool? available, bool? reachable)
    {
        var current = Project(Standing with { CandidateChairId = id, CandidateChair = new(available, reachable) });
        AssertOpen(current, SunnyIndoorChoices.Evaluate(current, Initial, Clear));
    }

    [Fact]
    public void Unknown_or_incompatible_posture_leaves_only_stay()
    {
        var samples = new[]
        {
            Standing with { Posture = SunnyPosture.Unknown },
            Standing with { IsSitting = true },
            Standing with { CurrentChair = new("A", true) },
            Seated with { CurrentChair = new(null, true) },
            Seated with { CurrentChair = new(" ", true) },
            Seated with { CurrentChair = new("A", null) },
            Seated with { IsSitting = false }
        };

        foreach (var sample in samples)
        {
            var current = Project(sample);
            AssertOpen(current, SunnyIndoorChoices.Evaluate(current, Initial, Clear));
        }
    }

    [Fact]
    public void Unusable_projections_leave_caller_history_available_for_a_later_sample()
    {
        var first = Project(Standing);
        AssertOpen(first, SunnyIndoorChoices.Evaluate(first, Initial, Clear), new(IndoorIntent.Sit, "A"));
        var paused = RecordStay(first);
        var next = Standing with { Revision = 11 };
        var unusable = new[]
        {
            next with { Fresh = false },
            next with { InTransition = true },
            next with { Indoors = false }
        };

        foreach (var sample in unusable)
        {
            var current = SunnyIndoorObservation.Project(Scope, sample);
            Assert.Null(current);
            AssertNoBatch(RoundStatus.Unavailable, SunnyIndoorChoices.Evaluate(current, paused, PendingDisposition.Unresolved));
        }

        AssertNoBatch(RoundStatus.HeldByStay,
            SunnyIndoorChoices.Evaluate(Project(next), paused, PendingDisposition.Unresolved));
    }

    [Fact]
    public void Missing_history_and_invalid_ordering_fail_closed()
    {
        var current = Project(Standing);
        var paused = RecordStay(current);
        var anchor = paused.Stay!;
        var invalid = new IndoorHistory?[]
        {
            null,
            Initial with { LastAcceptedRevision = -1 },
            Initial with { LastAcceptedRevision = 11 },
            paused with { LastAcceptedRevision = null },
            paused with { LastAcceptedRevision = 9 },
            paused with { Stay = anchor with { Revision = -1 } },
            paused with { Stay = anchor with { Revision = 11 } },
            paused with { Stay = anchor with { Facts = anchor.Facts with { Weather = SunnyWeather.Storm } } }
        };

        foreach (var history in invalid)
            AssertNoBatch(RoundStatus.Unavailable, SunnyIndoorChoices.Evaluate(current, history, Clear));

        AssertNoBatch(RoundStatus.Unavailable, SunnyIndoorChoices.Evaluate(current with { Revision = -1 }, Initial, Clear));
        AssertOpen(current, SunnyIndoorChoices.Evaluate(current, Initial with { LastAcceptedRevision = 10 }, Clear),
            new(IndoorIntent.Sit, "A"));
    }

    [Theory]
    [InlineData("other", "cabin", "load-1")]
    [InlineData("sunny", "other", "load-1")]
    [InlineData("sunny", "cabin", "load-2")]
    public void Changed_scope_requires_its_own_history(string player, string scene, string load)
    {
        var scope = new SunnyIndoorScope(2, player, scene, load);
        var current = Project(Standing with { Scope = scope, Revision = 11 });
        var paused = RecordStay(Project(Standing));

        AssertNoBatch(RoundStatus.Unavailable, SunnyIndoorChoices.Evaluate(current, paused, Clear));
        AssertOpen(current, SunnyIndoorChoices.Evaluate(current, new(scope, null, null), Clear),
            new(IndoorIntent.Sit, "A"));
    }

    private static SunnyIndoorObservation Project(SunnyIndoorFacts sample) =>
        Assert.IsType<SunnyIndoorObservation>(SunnyIndoorObservation.Project(sample.Scope, sample));

    private static IndoorHistory RecordStay(SunnyIndoorObservation current) =>
        new(current.Scope, current.Revision, new(current.Revision, current.ChoiceFacts));

    private static IndoorOfferBatch AssertOpen(
        SunnyIndoorObservation current, IndoorRound round, IndoorIntention? posture = null)
    {
        Assert.Equal(RoundStatus.Open, round.Status);
        var batch = Assert.IsType<IndoorOfferBatch>(round.Batch);
        Assert.Equal(current.Scope, batch.Scope);
        Assert.Equal(current.Revision, batch.Revision);
        var stay = new IndoorIntention(IndoorIntent.Stay, null);
        Assert.Equal(posture is null ? new[] { stay } : new[] { stay, posture }, batch.Intentions);
        return batch;
    }

    private static void AssertNoBatch(RoundStatus status, IndoorRound round)
    {
        Assert.Equal(status, round.Status);
        Assert.Null(round.Batch);
    }
}
