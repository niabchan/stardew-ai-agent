using System.Globalization;

namespace StardewMCP.Agent;

/// <summary>Immutable metadata only; no raw evidence, game objects, identifiers or exception data.</summary>
internal sealed record DiagnosticStatus(bool CollectionEnabled, bool P1ConsentEnabled,
    string P2SamplingStatus, long CaptureCount, double? AgeSeconds, string PromptStatus,
    bool LifecycleCoverage, bool IdentityKnown)
{
    internal string Format(long captureFailureCount, bool lastSampleFailed)
    {
        static string Flag(bool value) => value ? "enabled" : "disabled";
        string age = AgeSeconds?.ToString("F3", CultureInfo.InvariantCulture) ?? "unavailable";
        return $"Sunny diagnostic status (P2 only)\nCollection: {Flag(CollectionEnabled)}\n"
            + $"P1 collection consent: {Flag(P1ConsentEnabled)} (P1 observations omitted)\n"
            + "HTTP disclosure: not implemented\n"
            + $"P2 sampling: {P2SamplingStatus}; capture count (current seat incarnation): {CaptureCount}\n"
            + $"Last capture age seconds: {age}; prompt status: {PromptStatus}\n"
            + $"Lifecycle coverage: {(LifecycleCoverage ? "verified" : "unverified")}; "
            + $"identity confidence: {(IdentityKnown ? "known" : "unknown")}\n"
            + $"CaptureFailureCount (process aggregate): {captureFailureCount}; LastSampleFailed: {lastSampleFailed}\n"
            + "guarded_dispatch=false; gift_classification=false; transfer_verification=false; checkpoint_reconciliation=false";
    }
}
