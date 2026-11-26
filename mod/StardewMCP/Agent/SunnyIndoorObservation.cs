namespace StardewMCP.Agent;

internal enum SunnyPosture { Unknown, Standing, Seated }
internal enum SunnyWeather { Unknown, Sunny, Rain, Storm, Snow, Windy }

internal readonly record struct SunnyIndoorScope(int? Seat, string? PlayerId, string? SceneId, string? LoadId);

// Nullable evidence distinguishes an unknown fact from an explicit negative.
internal readonly record struct SunnyChair(string? Id, bool? Present);
internal readonly record struct SunnyAffordance(bool? Available, bool? Reachable);

internal sealed record SunnyIndoorFacts(
    SunnyIndoorScope Scope,
    bool? Indoors = null,
    long? Revision = null,
    bool? Fresh = null,
    bool? InTransition = null,
    bool? WorldReady = null,
    bool? InteractionReady = null,
    int? FarmDay = null,
    int? Clock = null,
    bool? MorningCue = null,
    SunnyPosture Posture = SunnyPosture.Unknown,
    bool? IsSitting = null,
    SunnyChair CurrentChair = default,
    string? CandidateChairId = null,
    SunnyAffordance CandidateChair = default,
    SunnyWeather Weather = SunnyWeather.Unknown,
    SunnyAffordance Tv = default);

internal sealed record SunnyIndoorChoiceFacts(
    bool? WorldReady,
    bool? InteractionReady,
    bool? MorningCue,
    SunnyPosture Posture,
    SunnyChair CurrentChair,
    string? CandidateChairId,
    SunnyAffordance CandidateChair,
    SunnyWeather Weather,
    SunnyAffordance Tv)
{
    public bool ReadyForInteraction => WorldReady == true && InteractionReady == true;
}

internal sealed record SunnyIndoorObservation(
    SunnyIndoorScope Scope, long Revision, int? FarmDay, int? Clock, SunnyIndoorChoiceFacts ChoiceFacts)
{
    /// <summary>
    /// Projects a single sample under caller-supplied scope and freshness assumptions.
    /// Runtime identity, authorization and freshness require independent evidence.
    /// Null denotes an unusable sample. A scoped sample can still have unknown facts.
    /// </summary>
    public static SunnyIndoorObservation? Project(SunnyIndoorScope expected, SunnyIndoorFacts supplied)
    {
        if (expected.Seat != 2 || !HasId(expected.PlayerId) || !HasId(expected.SceneId) ||
            !HasId(expected.LoadId) || supplied.Scope != expected || supplied.Indoors != true ||
            supplied.Revision is not long revision || revision < 0 || supplied.Fresh != true ||
            supplied.InTransition != false)
            return null;

        var (posture, currentChair) = (supplied.Posture, supplied.CurrentChair) switch
        {
            (SunnyPosture.Seated, { Present: true, Id: var id })
                when HasId(id) && supplied.IsSitting != false => (SunnyPosture.Seated, supplied.CurrentChair),
            (SunnyPosture.Standing, { Present: false, Id: null })
                when supplied.IsSitting != true => (SunnyPosture.Standing, supplied.CurrentChair),
            _ => (SunnyPosture.Unknown, default(SunnyChair))
        };

        var candidate = Normalize(supplied.CandidateChair);
        var candidateId = candidate.Available == true && HasId(supplied.CandidateChairId)
            ? supplied.CandidateChairId
            : null;

        return new SunnyIndoorObservation(expected, revision, supplied.FarmDay, supplied.Clock,
            new SunnyIndoorChoiceFacts(supplied.WorldReady, supplied.InteractionReady, supplied.MorningCue,
                posture, currentChair, candidateId, candidate, supplied.Weather, Normalize(supplied.Tv)));
    }

    private static bool HasId(string? id) => !string.IsNullOrWhiteSpace(id);

    private static SunnyAffordance Normalize(SunnyAffordance fact) =>
        new(fact.Available, fact.Available == true ? fact.Reachable : null);
}
