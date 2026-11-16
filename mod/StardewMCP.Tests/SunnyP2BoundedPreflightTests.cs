using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

/// <summary>Inert game-free Mod-source bridge tests. No HttpListener/socket or game.</summary>
public class SunnyP2BoundedPreflightTests
{
    private const string Bearer = "synthetic-local-p2-token";
    private const string InitJson =
        "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\"," +
        "\"params\":{\"protocolVersion\":\"2025-06-18\"}}";
    private const string ToolJson =
        "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\"," +
        "\"params\":{\"name\":\"say\",\"arguments\":{\"text\":\"hello\"}}}";

    private sealed class Authority : ISunnyP2PolicyAuthority
    {
        public int Resolutions;
        public int Sessions;
        public int Validations;
        public bool Current = true;
        public bool Ready = true;
        public bool ThrowOnResolve;

        public SunnyP2Principal? ResolveGameCredential(string token)
        {
            Resolutions++;
            if (ThrowOnResolve) throw new IOException("synthetic authority unavailable");
            return token == Bearer ? new("synthetic-p2", "p2", true, true) : null;
        }

        public bool HumanP1AiP2ExternalBrainReady => Ready;

        public bool IsCurrentOwnerSession(string principal, string session, string epoch)
        {
            Sessions++;
            return Current && principal == "synthetic-p2" &&
                   session == "synthetic-session-1" && epoch == "synthetic-epoch-1";
        }

        public bool ValidateMutationArguments(string tool, System.Text.Json.JsonElement args)
        {
            Validations++;
            return tool == "say" && args.ValueKind == System.Text.Json.JsonValueKind.Object &&
                   args.TryGetProperty("text", out var text) &&
                   text.ValueKind == System.Text.Json.JsonValueKind.String;
        }
    }

    private sealed class ReadCounter : MemoryStream
    {
        internal int Reads;
        internal int MaxChunk = int.MaxValue;
        internal bool FailIo;
        internal bool Cancel;
        internal bool RejectRead;
        internal ReadCounter(byte[] b) : base(b, writable: false) { }

        public override ValueTask<int> ReadAsync(Memory<byte> buffer,
            CancellationToken cancellationToken = default)
        {
            Reads++;
            if (RejectRead) throw new InvalidOperationException("unexpected read");
            if (FailIo) throw new IOException("synthetic read failure");
            if (Cancel || cancellationToken.IsCancellationRequested)
                throw new OperationCanceledException(cancellationToken);
            return base.ReadAsync(buffer.Slice(0, Math.Min(MaxChunk, buffer.Length)),
                                  cancellationToken);
        }
    }

    private static SunnyP2IngressCapture Capture(byte[]? bytes = null, string method = "POST",
        string target = "/mcp/p2", bool withSession = false)
    {
        var headers = new List<KeyValuePair<string, string>> {
            new("Host", "127.0.0.1:18770"),
            new("Authorization", "Bearer " + Bearer)
        };
        if (method == "POST")
        {
            headers.Add(new("Content-Type", "application/json"));
            headers.Add(new("Content-Length", (bytes?.Length ?? 0).ToString()));
        }
        if (withSession)
        {
            headers.Add(new("Mcp-Session-Id", "synthetic-session-1"));
            headers.Add(new("X-Sunny-Save-Epoch", "synthetic-epoch-1"));
        }
        return new(method, target, "127.0.0.1:18770", "127.0.0.1",
                   18770, headers, bytes?.Length ?? 0, false);
    }

    private static SunnyP2IngressCapture Add(SunnyP2IngressCapture c,
        string k, string v) => c with {
            Headers = c.Headers.Concat(new[] {
                new KeyValuePair<string, string>(k, v) }).ToArray()
        };

    private static SunnyP2IngressCapture Remove(SunnyP2IngressCapture c,
        string key) => c with { Headers = c.Headers.Where(h =>
            !h.Key.Equals(key, StringComparison.OrdinalIgnoreCase)).ToArray() };

    private static async Task<(SunnyP2IngressCheck Check, ReadCounter Stream,
        Authority Authority)> Run(byte[] bytes, SunnyP2IngressCapture? capture = null,
        Authority? authority = null)
    {
        var a = authority ?? new Authority();
        var input = new ReadCounter(bytes);
        var result = await SunnyP2BoundedPreflight.CheckAsync(
            capture ?? Capture(bytes), input, a);
        return (result, input, a);
    }

    [Fact]
    public async Task Initialize_is_only_a_candidate_not_owner_acquisition()
    {
        var bytes = Encoding.UTF8.GetBytes(InitJson);
        var (result, input, authority) = await Run(bytes);
        Assert.True(result.CandidateOnly);
        Assert.Equal(200, result.Status);
        Assert.Equal(SunnyP2Operation.Initialize, result.Preflight!.Operation);
        Assert.Equal(1, authority.Resolutions);
        Assert.Equal(0, authority.Sessions);
        Assert.Equal(0, authority.Validations);
        Assert.Equal(1, input.Reads);
    }

    [Fact]
    public async Task Correct_shape_mutation_is_only_preflight_not_a_dispatch()
    {
        var bytes = Encoding.UTF8.GetBytes(ToolJson);
        var (result, input, authority) = await Run(bytes, Capture(bytes, withSession: true));
        Assert.True(result.CandidateOnly);
        Assert.Equal(SunnyP2Operation.Mutation, result.Preflight!.Operation);
        Assert.Equal(1, authority.Validations);
        Assert.True(input.Reads > 0);
        // A fake authority can grant this status without host-owned epoch/STOP.
        // No real authorization or AgentRuntime queue exists in this test.
    }

    [Theory]
    [InlineData("/mcp")]
    [InlineData("/mcp/p1")]
    [InlineData("/mcp/p2/")]
    [InlineData("/mcp/p2?x=1")]
    [InlineData("/mcp%2Fp2")]
    [InlineData("/mcp/../mcp/p2")]
    [InlineData("//mcp/p2")]
    public async Task Wrong_raw_target_never_reads_body_or_resolves_token(string target)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(InitJson);
        var (res, input, auth) = await Run(bytes, Capture(bytes, target: target));
        Assert.False(res.CandidateOnly);
        Assert.Equal(0, input.Reads);
        Assert.Equal(0, auth.Resolutions);
    }

    [Fact]
    public async Task Invalid_host_peer_or_port_fails_before_body_read()
    {
        byte[] bytes = Encoding.UTF8.GetBytes(InitJson);
        foreach (var bad in new[] {
            Capture(bytes) with { RawHost = "evil.invalid:18770" },
            Capture(bytes) with { PeerAddress = "192.0.2.9" },
            Capture(bytes) with { ListenerPort = 8770 },
            Capture(bytes) with { RawHost = "localhost:18770" },
        })
        {
            var (res, input, auth) = await Run(bytes, bad);
            Assert.Equal(403, res.Status);
            Assert.Equal(0, input.Reads);
            Assert.Equal(0, auth.Resolutions);
        }
    }

    [Theory]
    [InlineData("Origin", "null")]
    [InlineData("Origin", "https://evil.invalid")]
    [InlineData("Transfer-Encoding", "chunked")]
    [InlineData("Cookie", "sid=x")]
    [InlineData("Forwarded", "for=127.0.0.1")]
    [InlineData("X-Forwarded-For", "127.0.0.1")]
    public async Task Unsafe_http_headers_fail_before_body_and_auth(string header, string value)
    {
        var b = Encoding.UTF8.GetBytes(InitJson);
        var (res, s, a) = await Run(b, Add(Capture(b), header, value));
        Assert.Equal(403, res.Status);
        Assert.Equal(0, s.Reads);
        Assert.Equal(0, a.Resolutions);
    }

    [Theory]
    [InlineData("host", "127.0.0.1:18770")]
    [InlineData("Authorization", "Bearer anything")]
    [InlineData("content-length", "99")]
    [InlineData("X-Header", "a\r\nb")]
    public async Task Duplicate_or_nonascii_headers_fail_before_stream(string key, string value)
    {
        var b = Encoding.UTF8.GetBytes(InitJson);
        var (res, s, a) = await Run(b, Add(Capture(b), key, value));
        Assert.Equal(400, res.Status);
        Assert.Equal(0, s.Reads);
        Assert.Equal(0, a.Resolutions);
    }

    [Fact]
    public async Task Missing_and_wrong_lengths_and_oversize_never_read_or_authenticate()
    {
        var b = Encoding.UTF8.GetBytes(InitJson);
        var c = Capture(b);
        var tooLarge = new byte[SunnyP2Preflight.MaxBodyBytes + 1];
        var inputs = new[] {
            (Remove(c, "Content-Length"), 411),
            (c with { DeclaredBodyLength = -1 }, 400),
            (c with { DeclaredBodyLength = b.Length + 1 }, 400),
            (Add(Remove(c, "Content-Length"), "Content-Length", "1x"), 400),
            (Capture(tooLarge), 413),
            (c with { HasTransferCoding = true }, 400)
        };
        foreach (var (bad, expected) in inputs)
        {
            var (res, s, auth) = await Run(b, bad);
            Assert.Equal(expected, res.Status);
            Assert.Equal(0, s.Reads);
            Assert.Equal(0, auth.Resolutions);
        }
    }

    [Fact]
    public async Task Early_end_of_body_blocks_preflight_and_credential_lookup()
    {
        var bytes = Encoding.UTF8.GetBytes(InitJson);
        var declared = Capture(bytes);
        using var stream = new ReadCounter(bytes.AsSpan(0, bytes.Length - 1).ToArray());
        var auth = new Authority();
        var result = await SunnyP2BoundedPreflight.CheckAsync(declared, stream, auth);
        Assert.Equal(400, result.Status);
        Assert.Null(result.Preflight);
        Assert.Equal(0, auth.Resolutions);
    }

    [Fact]
    public async Task Reads_exact_declared_body_in_small_chunks_without_unbounded_eof_probe()
    {
        var bytes = Encoding.UTF8.GetBytes(InitJson + "TRAILING-NOT-FRAMED");
        var declared = Capture(Encoding.UTF8.GetBytes(InitJson));
        using var stream = new ReadCounter(bytes) { MaxChunk = 1 };
        var auth = new Authority();
        var result = await SunnyP2BoundedPreflight.CheckAsync(declared, stream, auth);
        Assert.True(result.CandidateOnly);
        Assert.Equal(InitJson.Length, stream.Position);
        Assert.Equal(InitJson.Length, stream.Reads);
        // The extra bytes are untrusted/framing-dependent, not silently approved.
        // Future native adapter MUST prove OS framing; don't read beyond declared N.
    }

    [Fact]
    public async Task Wrong_or_stale_owner_is_denied_by_preflight_before_candidate()
    {
        var bytes = Encoding.UTF8.GetBytes(ToolJson);
        var authority = new Authority { Current = false };
        var (res, s, a) = await Run(bytes, Capture(bytes, withSession: true), authority);
        Assert.Equal(409, res.Status);
        Assert.False(res.CandidateOnly);
        Assert.Equal(0, a.Validations);
        Assert.Equal(1, a.Sessions);
        Assert.True(s.Reads > 0);
    }

    [Fact]
    public async Task No_lease_headers_means_no_effectful_candidate()
    {
        var bytes = Encoding.UTF8.GetBytes(ToolJson);
        var (res, stream, auth) = await Run(bytes);
        Assert.Equal(409, res.Status);
        Assert.False(res.CandidateOnly);
        Assert.Equal(0, auth.Validations);
        Assert.True(stream.Reads > 0);
    }

    [Fact]
    public async Task Delete_is_only_a_retirement_candidate_and_never_a_retirement()
    {
        var cap = Capture(Array.Empty<byte>(), method: "DELETE", withSession: true);
        var (res, input, auth) = await Run(Array.Empty<byte>(), cap);
        Assert.True(res.CandidateOnly);
        Assert.Equal(SunnyP2Operation.Retire, res.Preflight!.Operation);
        Assert.Equal(0, input.Reads);
        Assert.Equal(1, auth.Sessions);
        // This MUST NOT be mapped to legacy AgentHttp DELETE == 200 no-op.
    }

    [Fact]
    public async Task Cancelled_or_faulty_stream_never_reaches_policy()
    {
        var b = Encoding.UTF8.GetBytes(InitJson);
        var cap = Capture(b);
        var a = new Authority();
        using var cancelled = new ReadCounter(b) { Cancel = true };
        var x = await SunnyP2BoundedPreflight.CheckAsync(cap, cancelled, a);
        Assert.Equal(408, x.Status);
        Assert.Equal(0, a.Resolutions);
        using var io = new ReadCounter(b) { FailIo = true };
        var y = await SunnyP2BoundedPreflight.CheckAsync(cap, io, a);
        Assert.Equal(400, y.Status);
        Assert.Equal(0, a.Resolutions);
        using var cts = new CancellationTokenSource();
        cts.Cancel();
        using var never = new ReadCounter(b) { RejectRead = true };
        var z = await SunnyP2BoundedPreflight.CheckAsync(cap, never, a, cts.Token);
        Assert.Equal(408, z.Status);
        Assert.Equal(0, never.Reads);
    }

    [Fact]
    public async Task Authority_exception_fails_closed_without_candidate()
    {
        var b = Encoding.UTF8.GetBytes(InitJson);
        var (res, _, a) = await Run(b, Capture(b), new Authority { ThrowOnResolve = true });
        Assert.Equal(503, res.Status);
        Assert.False(res.CandidateOnly);
        Assert.Equal(1, a.Resolutions);
    }

    [Fact]
    public async Task Malformed_json_fails_at_existing_strict_preflight()
    {
        var b = Encoding.UTF8.GetBytes("{\"jsonrpc\":\"2.0\",\"id\":1,");
        var (res, s, a) = await Run(b);
        Assert.Equal(400, res.Status);
        Assert.False(res.CandidateOnly);
        Assert.True(s.Reads > 0);
        Assert.Equal(1, a.Resolutions);
    }
}
