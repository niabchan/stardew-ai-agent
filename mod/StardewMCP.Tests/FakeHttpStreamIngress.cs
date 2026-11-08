using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace StardewMCP.Tests;

// PHASE 2E: PURE TEST-HARNESS HTTP-INGRESS MODEL, NOT A TRUSTED HttpListener ADAPTER.
// Every evidence bit below is SUPPLIED BY A TEST. A real HttpListenerRequest has not
// proved that its normalized Url/Headers preserve raw-target and header multiplicity.
[Flags]
internal enum FakeHttpCaptureEvidence
{
    None = 0,
    RawTargetPreserved = 1,
    HeaderMultiplicityPreserved = 2,
    PeerFromTransport = 4,
    FramingVerified = 8,
    ListenerInstanceVerified = 16,
    All = RawTargetPreserved | HeaderMultiplicityPreserved | PeerFromTransport |
          FramingVerified | ListenerInstanceVerified
}

internal sealed record FakeHttpCapture(
    string Method,
    string RawRequestTarget,
    string RawHost,
    string PeerAddress,
    int BoundPort,
    IReadOnlyList<KeyValuePair<string, string>> RawHeaders,
    FakeHttpCaptureEvidence Evidence);

// This is NOT a wire response and NEVER includes a bearer, private body or raw URL.
internal sealed record FakeHttpIngressResult(int Status, bool FurtherValidationCandidate,
    string? RouteId, int BodyBytesRead)
{
    internal static FakeHttpIngressResult Deny(int status, int bytes = 0) =>
        new(status, false, null, bytes);
}

/// <summary>
/// Inert byte-stream harness exercising bounded POST reads and a conservative
/// mapping to the PR #37 all-routes candidate classifier. There are NO sockets,
/// HttpListener calls, credential issuance, game access, queue admission or output
/// serialization. Success does not imply true raw-wire provenance or authorization.
/// </summary>
internal static class FakeHttpStreamIngress
{
    internal const int MaxBodyBytes = 16 * 1024;
    private const int ChunkSize = 1024;

    internal static async Task<FakeHttpIngressResult> ProcessAsync(FakeHttpCapture? capture,
        Stream? input, IFakeRouteAuthority? authority, CancellationToken cancellationToken = default)
    {
        if (capture is null || input is null || authority is null)
            return FakeHttpIngressResult.Deny(400);

        // Snapshot the potentially mutable collection before any await. This alone
        // cannot prove the host/peer/header data was authenticated at the OS boundary.
        KeyValuePair<string, string>[] headers;
        try
        {
            headers = capture.RawHeaders?.ToArray() ?? Array.Empty<KeyValuePair<string, string>>();
            if (capture.Evidence != FakeHttpCaptureEvidence.All ||
                capture.BoundPort is < 1 or > 65535 ||
                capture.Method is not ("GET" or "POST" or "DELETE") ||
                string.IsNullOrEmpty(capture.RawRequestTarget) ||
                string.IsNullOrEmpty(capture.RawHost) ||
                string.IsNullOrEmpty(capture.PeerAddress) ||
                headers.Length is < 1 or > 64)
                return FakeHttpIngressResult.Deny(400);

            // Split ONLY a test-provided RAW request target. Uri.AbsolutePath,
            // UriBuilder, decoded paths and guessed Host values are not acceptable.
            string target = capture.RawRequestTarget;
            if (target.Length > 260 || target.IndexOf('#') >= 0 ||
                !target.StartsWith("/", StringComparison.Ordinal) ||
                target.Any(c => c < 33 || c > 126))
                return FakeHttpIngressResult.Deny(400);
            int question = target.IndexOf('?');
            string path = question < 0 ? target : target.Substring(0, question);
            string query = question < 0 ? "" : target.Substring(question);
            if (path.Length == 0 || query.Count(c => c == '?') > 1)
                return FakeHttpIngressResult.Deny(400);

            // This early gate runs before reading the stream or asking a credential
            // store anything. It is NOT an alternative to the full route classifier.
            var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var pair in headers)
            {
                if (string.IsNullOrWhiteSpace(pair.Key) || pair.Key.Length > 128 ||
                    pair.Key.Any(c => !AsciiHeaderName(c)) ||
                    pair.Value is null || pair.Value.Length > 4096 ||
                    pair.Value.Any(c => c < 32 || c > 126) ||
                    !values.TryAdd(pair.Key, pair.Value))
                    return FakeHttpIngressResult.Deny(400);
            }
            foreach (var forbidden in new[] { "Origin", "Cookie", "Transfer-Encoding",
                         "Forwarded", "X-Forwarded-Host", "X-Forwarded-For",
                         "Proxy-Authorization", "Expect" })
                if (values.ContainsKey(forbidden)) return FakeHttpIngressResult.Deny(403);

            string expectedPort = capture.BoundPort.ToString(CultureInfo.InvariantCulture);
            if (!values.TryGetValue("Host", out string? host) ||
                host != capture.RawHost ||
                (host != "127.0.0.1:" + expectedPort &&
                 host != "localhost:" + expectedPort) ||
                !IPAddress.TryParse(capture.PeerAddress, out var peer) ||
                !IPAddress.IsLoopback(peer))
                return FakeHttpIngressResult.Deny(403);

            if (!values.TryGetValue("Authorization", out string? auth) ||
                !auth.StartsWith("Bearer ", StringComparison.Ordinal) ||
                auth.Length <= 7 || auth.Length > 263 ||
                auth.Substring(7).Any(c => c < '!' || c > '~'))
                return FakeHttpIngressResult.Deny(401);

            if (capture.Method == "POST" &&
                (!values.TryGetValue("Content-Type", out string? media) ||
                 media != "application/json"))
                return FakeHttpIngressResult.Deny(415);

            int length = 0;
            if (values.TryGetValue("Content-Length", out string? contentLength))
            {
                if (contentLength.Length is < 1 or > 8 ||
                    contentLength.Any(c => c < '0' || c > '9') ||
                    !int.TryParse(contentLength, NumberStyles.None,
                        CultureInfo.InvariantCulture, out length))
                    return FakeHttpIngressResult.Deny(400);
                if (length > MaxBodyBytes) return FakeHttpIngressResult.Deny(413);
            }
            else if (capture.Method == "POST")
                return FakeHttpIngressResult.Deny(411);

            if (capture.Method != "POST" && length != 0)
                return FakeHttpIngressResult.Deny(400);
            if (capture.Method == "POST" && length == 0)
                return FakeHttpIngressResult.Deny(400);
            if (!input.CanRead) return FakeHttpIngressResult.Deny(503);

            // No unbounded StreamReader.ReadToEndAsync; request body has a fixed
            // maximum. A simulated EOF after expected bytes is checked below.
            byte[] body = new byte[length];
            int read = 0;
            while (read < length)
            {
                int n = await input.ReadAsync(body.AsMemory(read, Math.Min(ChunkSize, length - read)),
                    cancellationToken).ConfigureAwait(false);
                if (n <= 0) return FakeHttpIngressResult.Deny(400, read); // early EOF
                read += n;
            }

            // This ONLY detects extra bytes in an in-memory fixture. In a real
            // HttpListener input stream, request framing may hide trailing/pipelined
            // wire bytes and a one-byte probe may block. Do NOT copy this EOF
            // probe into production without a proven framing API and deadline.
            byte[] extra = new byte[1];
            int trailing = await input.ReadAsync(extra.AsMemory(0, 1),
                cancellationToken).ConfigureAwait(false);
            if (trailing != 0) return FakeHttpIngressResult.Deny(400, read + trailing);

            // The full route policy is AFTER the bounded read and still has to
            // check all route/grant/session/projection requirements independently.
            var request = new FakeRouteRequest(capture.Method, path, query,
                capture.RawHost, capture.PeerAddress, capture.BoundPort, headers, body);
            FakeRouteDecision outcome = FakeAllRoutesBoundary.Check(request, authority);
            return new(outcome.Status, outcome.CandidateForFurtherValidation,
                outcome.CandidateForFurtherValidation ? outcome.RouteId : null, read);
        }
        catch (OperationCanceledException)
        {
            return FakeHttpIngressResult.Deny(408);
        }
        catch (IOException)
        {
            return FakeHttpIngressResult.Deny(400);
        }
        catch
        {
            return FakeHttpIngressResult.Deny(503);
        }
    }

    private static bool AsciiHeaderName(char c) =>
        c is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '-';
}
