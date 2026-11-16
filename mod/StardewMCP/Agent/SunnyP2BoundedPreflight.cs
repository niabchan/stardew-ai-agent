using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Threading;
using System.Threading.Tasks;

namespace StardewMCP.Agent;

/// <summary>
/// Untrusted capture claims supplied by a FUTURE reviewed native listener adapter.
/// None of these fields, including the apparent peer, are authenticated by this
/// record. Never populate them from HTTP client-provided forwarding headers.
/// </summary>
internal sealed record SunnyP2IngressCapture(
    string Method, string RawTarget, string RawHost, string PeerAddress,
    int ListenerPort, IReadOnlyList<KeyValuePair<string, string>> Headers,
    long DeclaredBodyLength, bool HasTransferCoding);

/// <summary>
/// Candidate for further ATOMIC server-side owner/epoch/role/grant/queue checks.
/// Status 200 and a non-null preflight decision are NOT permission to execute.
/// No response body, credential, raw tool arguments or private text is exposed.
/// </summary>
internal sealed record SunnyP2IngressCheck(int Status, SunnyP2Decision? Preflight)
{
    internal static SunnyP2IngressCheck Deny(int status) => new(status, null);
    internal bool CandidateOnly => Status == 200 && Preflight?.Allowed == true;
}

/// <summary>
/// Dormant production-source bounded ingress reader plus existing SunnyP2Preflight.
/// No HttpListener, credential provisioner, game, AgentHttp, Dispatcher or Runtime
/// invokes it today. Does not send a response, MarkContact or enqueue effects.
///
/// A future listener must verify raw request-target preservation, duplicate
/// header visibility, actual OS peer/port, body framing/deadline and credential
/// ownership BEFORE using capture evidence here. C# caller-supplied metadata
/// alone cannot prove those properties.
/// </summary>
internal static class SunnyP2BoundedPreflight
{
    private const int ChunkBytes = 1024;

    internal static async Task<SunnyP2IngressCheck> CheckAsync(
        SunnyP2IngressCapture? capture, Stream? body,
        ISunnyP2PolicyAuthority? authority,
        CancellationToken cancellationToken = default)
    {
        if (capture is null || body is null || authority is null)
            return SunnyP2IngressCheck.Deny(400);

        // Snapshot metadata before the first async read. Metadata remains
        // untrusted even after copying: real HttpListener adapter not built.
        KeyValuePair<string, string>[] headers;
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            headers = capture.Headers?.ToArray() ??
                Array.Empty<KeyValuePair<string, string>>();
            if (capture.Method is not ("POST" or "DELETE") ||
                capture.RawTarget != "/mcp/p2" ||
                capture.ListenerPort is < 1 or > 65535 ||
                capture.HasTransferCoding || headers.Length is < 1 or > 64 ||
                capture.DeclaredBodyLength < 0)
                return SunnyP2IngressCheck.Deny(400);

            // Duplicate/ambiguous request headers must fail before even
            // reading body bytes. Real wire header multiplicity is UNPROVEN.
            var seen = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var pair in headers)
                if (pair.Key is null || pair.Key.Length is < 1 or > 128 ||
                    pair.Key.Any(c => !(c is >= 'a' and <= 'z' or
                                        >= 'A' and <= 'Z' or
                                        >= '0' and <= '9' or '-')) ||
                    pair.Value is null || pair.Value.Length > 4096 ||
                    pair.Value.Any(c => c < 32 || c > 126) ||
                    !seen.TryAdd(pair.Key, pair.Value))
                    return SunnyP2IngressCheck.Deny(400);

            // This early transport gate is NOT host/peer authentication.
            // It prevents a known-invalid fixture from wasting a body read.
            if (!seen.TryGetValue("Host", out var host) || host != capture.RawHost ||
                (host != "localhost:" + capture.ListenerPort.ToString(CultureInfo.InvariantCulture) &&
                 host != "127.0.0.1:" + capture.ListenerPort.ToString(CultureInfo.InvariantCulture)) ||
                !IPAddress.TryParse(capture.PeerAddress, out var peer) ||
                !IPAddress.IsLoopback(peer) ||
                seen.ContainsKey("Origin") || seen.ContainsKey("Transfer-Encoding") ||
                seen.ContainsKey("Forwarded") || seen.ContainsKey("X-Forwarded-For") ||
                seen.ContainsKey("X-Forwarded-Host") ||
                seen.ContainsKey("Cookie") || seen.ContainsKey("Proxy-Authorization") ||
                seen.ContainsKey("Expect"))
                return SunnyP2IngressCheck.Deny(403);

            if (capture.Method == "POST")
            {
                if (!seen.ContainsKey("Content-Length"))
                    return SunnyP2IngressCheck.Deny(411);
                string length = seen["Content-Length"];
                if (length.Length is < 1 or > 8 ||
                    length.Any(c => c < '0' || c > '9') ||
                    !long.TryParse(length, NumberStyles.None,
                        CultureInfo.InvariantCulture, out long actual) ||
                    actual != capture.DeclaredBodyLength)
                    return SunnyP2IngressCheck.Deny(400);
                if (capture.DeclaredBodyLength > SunnyP2Preflight.MaxBodyBytes)
                    return SunnyP2IngressCheck.Deny(413);
                if (capture.DeclaredBodyLength == 0)
                    return SunnyP2IngressCheck.Deny(400);
                if (!seen.TryGetValue("Content-Type", out var ct) ||
                    ct != "application/json")
                    return SunnyP2IngressCheck.Deny(415);
            }
            else
            {
                if (capture.DeclaredBodyLength != 0 ||
                    seen.TryGetValue("Content-Length", out var val) && val != "0")
                    return SunnyP2IngressCheck.Deny(400);
            }

            if (!body.CanRead)
                return SunnyP2IngressCheck.Deny(503);

            // Exactly N framed bytes, never ReadToEndAsync and NEVER a
            // speculative one-byte EOF probe (real HTTP streams may block).
            int total = checked((int)capture.DeclaredBodyLength);
            byte[] bytes = new byte[total];
            int read = 0;
            while (read < total)
            {
                cancellationToken.ThrowIfCancellationRequested();
                int n = await body.ReadAsync(
                    bytes.AsMemory(read, Math.Min(ChunkBytes, total - read)),
                    cancellationToken).ConfigureAwait(false);
                cancellationToken.ThrowIfCancellationRequested();
                if (n <= 0 || n > total - read)
                    return SunnyP2IngressCheck.Deny(400); // short/invalid read
                read += n;
            }
            cancellationToken.ThrowIfCancellationRequested();

            // Reuse existing strict JSON-RPC preflight. It can query an
            // injected authority, but positive preflight NEVER installs a
            // lease or authorizes/queues a tool. No mutable request effects.
            var request = new SunnyP2Request(capture.Method, "/mcp/p2",
                capture.RawHost, capture.PeerAddress, capture.ListenerPort,
                headers, bytes);
            SunnyP2Decision candidate = SunnyP2Preflight.Evaluate(request, authority);
            return candidate.Allowed
                ? new SunnyP2IngressCheck(candidate.Status, candidate)
                : SunnyP2IngressCheck.Deny(candidate.Status);
        }
        catch (OperationCanceledException)
        {
            return SunnyP2IngressCheck.Deny(408);
        }
        catch (IOException)
        {
            return SunnyP2IngressCheck.Deny(400);
        }
        catch (ObjectDisposedException)
        {
            return SunnyP2IngressCheck.Deny(503);
        }
        catch (NotSupportedException)
        {
            return SunnyP2IngressCheck.Deny(503);
        }
        catch
        {
            // Fail closed on unexpected capture/stream/policy errors.
            return SunnyP2IngressCheck.Deny(503);
        }
    }
}
