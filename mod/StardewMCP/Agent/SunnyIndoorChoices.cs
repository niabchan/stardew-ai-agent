using System;
using System.Collections.Generic;

namespace StardewMCP.Agent;

internal enum PendingDisposition { Unknown = 0, Unresolved, NoUnresolvedWork }
internal enum RoundStatus { Unavailable, HeldByStay, Open }
internal enum IndoorIntent { Stay, Sit, Stand }

internal sealed record IndoorHistory(SunnyIndoorScope Scope, long? LastAcceptedRevision, StayAnchor? Stay);
internal sealed record StayAnchor(long Revision, SunnyIndoorChoiceFacts Facts);
internal sealed record IndoorRound(RoundStatus Status, IndoorOfferBatch? Batch);
internal sealed record IndoorOfferBatch(SunnyIndoorScope Scope, long Revision, IReadOnlyList<IndoorIntention> Intentions);
internal sealed record IndoorIntention(IndoorIntent Intent, string? ChairId);

internal static class SunnyIndoorChoices
{
    /// <summary>
    /// Describes intentions for a supplied projection. The caller supplies a current sample
    /// and ensures each revision identifies one immutable sample within its scope.
    /// Pending disposition comes from the caller's independent evidence.
    /// The caller records voluntary STAY choices and retires an anchor after its round reopens.
    /// </summary>
    public static IndoorRound Evaluate(
        SunnyIndoorObservation? current,
        IndoorHistory? history,
        PendingDisposition pending = PendingDisposition.Unknown)
    {
        if (current is null || history is null || current.Scope != history.Scope ||
            current.Revision < 0 || history.LastAcceptedRevision is < 0 ||
            current.Revision < history.LastAcceptedRevision)
            return new(RoundStatus.Unavailable, null);

        var facts = current.ChoiceFacts;
        if (history.Stay is { } anchor)
        {
            if (anchor.Revision < 0 || history.LastAcceptedRevision is not long cursor ||
                cursor < anchor.Revision)
                return new(RoundStatus.Unavailable, null);

            if (facts == anchor.Facts)
                return new(RoundStatus.HeldByStay, null);

            if (current.Revision == anchor.Revision)
                return new(RoundStatus.Unavailable, null);
        }

        var intentions = new List<IndoorIntention> { new(IndoorIntent.Stay, null) };
        if (facts.ReadyForInteraction && pending == PendingDisposition.NoUnresolvedWork)
        {
            if (facts.Posture == SunnyPosture.Standing &&
                facts.CurrentChair is { Present: false, Id: null } &&
                !string.IsNullOrWhiteSpace(facts.CandidateChairId) &&
                facts.CandidateChair is { Available: true, Reachable: true })
                intentions.Add(new(IndoorIntent.Sit, facts.CandidateChairId));

            if (facts.Posture == SunnyPosture.Seated &&
                facts.CurrentChair is { Present: true, Id: var chairId } &&
                !string.IsNullOrWhiteSpace(chairId))
                intentions.Add(new(IndoorIntent.Stand, chairId));
        }

        return new(RoundStatus.Open, new(current.Scope, current.Revision, intentions.AsReadOnly()));
    }
}
