using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

namespace StardewMCP.Tests;

// Test-only: MemoryStream-derived fixtures, no sockets or HttpListenerRequest.
public sealed class HttpStreamIngressTests
{
    private const string P2 = "synthetic-p2-game-token";
    private const string Operator = "synthetic-operator-token";
    private const string Viewer = "synthetic-viewer-token";

    private sealed class Authority : IFakeRouteAuthority
    {
        public string IntendedInstanceId { get; set; } = "synthetic-instance-8770";
        private int boundPort = 8770;
        internal bool FailPort;
        public int BoundPort { get => FailPort ? throw new InvalidOperationException("synthetic store failure") : boundPort; set => boundPort = value; }
        public bool P1Consent => false;
        public bool DebugEnabled => false;
        public bool ViewerPublicationEnabled => false;
        public bool ViewerProjectionReady => false;
        public bool ReplayProjectionReady => false;
        public int Lookups;
        internal Action? OnResolve;
        public FakeRoutePrincipal? ResolveGameBearer(string token)
        {
            Lookups++;
            OnResolve?.Invoke();
            return token switch
            {
                P2 => new("luna", IntendedInstanceId,
                    FakeRouteGrant.P2Control | FakeRouteGrant.P2Observe),
                Operator => new("operator", IntendedInstanceId,
                    FakeRouteGrant.OperatorRawState | FakeRouteGrant.OperatorRawHistory |
                    FakeRouteGrant.OperatorRunControl | FakeRouteGrant.OperatorMetadata),
                Viewer => new("viewer", IntendedInstanceId, FakeRouteGrant.ViewerProjected),
                _ => null
            };
        }
        public bool CurrentP2Owner(FakeRoutePrincipal principal, string session, string epoch) => false;
    }

    private sealed class CountingStream : MemoryStream
    {
        internal int Calls;
        internal int ChunkSize = int.MaxValue;
        internal bool ThrowIo;
        internal bool ThrowCancel;
        internal Action? FirstRead;
        internal CountingStream(byte[] bytes) : base(bytes, writable: false) { }
        public override ValueTask<int> ReadAsync(Memory<byte> buffer,
            CancellationToken cancellationToken = default)
        {
            Calls++;
            if (Calls == 1) FirstRead?.Invoke();
            if (ThrowCancel || cancellationToken.IsCancellationRequested)
                throw new OperationCanceledException(cancellationToken);
            if (ThrowIo) throw new IOException("synthetic read failure");
            return base.ReadAsync(buffer.Slice(0, Math.Min(ChunkSize, buffer.Length)),
                cancellationToken);
        }
    }

    private static FakeHttpCapture Capture(string target = "/api/state", string method = "GET",
        string token = Operator, byte[]? body = null, int port = 8770,
        FakeHttpCaptureEvidence evidence = FakeHttpCaptureEvidence.All)
    {
        var headers = new List<KeyValuePair<string, string>> {
            new("Host", "127.0.0.1:" + port),
            new("Authorization", "Bearer " + token)
        };
        if (method == "POST")
        {
            headers.Add(new("Content-Type", "application/json"));
            headers.Add(new("Content-Length", (body?.Length ?? 2).ToString()));
        }
        return new FakeHttpCapture(method, target, "127.0.0.1:" + port,
            "127.0.0.1", port, headers, evidence);
    }

    private static FakeHttpCapture Add(FakeHttpCapture c, string key, string value) =>
        c with { RawHeaders = c.RawHeaders.Concat(new[] {
            new KeyValuePair<string, string>(key, value) }).ToList() };

    private static FakeHttpCapture Replace(FakeHttpCapture c, string key, string value) =>
        c with { RawHeaders = c.RawHeaders
            .Where(h => !h.Key.Equals(key, StringComparison.OrdinalIgnoreCase))
            .Concat(new[] { new KeyValuePair<string, string>(key, value) }).ToList() };

    private static async Task<FakeHttpIngressResult> Read(FakeHttpCapture capture,
        byte[]? bytes = null, Authority? authority = null)
    {
        using var stream = new CountingStream(bytes ?? Array.Empty<byte>());
        return await FakeHttpStreamIngress.ProcessAsync(capture, stream, authority ?? new Authority());
    }

    [Fact]
    public async Task Accepted_route_is_only_a_candidate_not_data_or_dispatch()
    {
        var auth = new Authority();
        var allowed = await Read(Capture(), authority: auth);
        Assert.Equal(200, allowed.Status);
        Assert.True(allowed.FurtherValidationCandidate);
        Assert.Equal("raw-state", allowed.RouteId);
        Assert.Equal(0, allowed.BodyBytesRead);
        Assert.Equal(1, auth.Lookups);

        var p2 = await Read(Capture(token: P2));
        Assert.Equal(403, p2.Status);
        Assert.False(p2.FurtherValidationCandidate);
        Assert.Null(p2.RouteId);
        var viewer = await Read(Capture(token: Viewer));
        Assert.Equal(403, viewer.Status);
    }

    [Fact]
    public async Task Bounded_post_reaches_route_candidate_without_executing_anything()
    {
        var bytes = Encoding.UTF8.GetBytes("{}");
        var request = Capture("/api/control", "POST", Operator, bytes);
        var result = await Read(request, bytes);
        Assert.True(result.FurtherValidationCandidate);
        Assert.Equal("run-control", result.RouteId);
        Assert.Equal(2, result.BodyBytesRead);

        var p2 = await Read(Capture("/mcp/p2", "POST", P2, bytes), bytes);
        Assert.True(p2.FurtherValidationCandidate);
        Assert.Equal("mcp-p2", p2.RouteId);
        // A real MCP parser, authenticated lease and atomic tool admission are absent.
    }

    [Fact]
    public async Task Raw_query_splits_once_without_url_normalization_or_aliases()
    {
        var good = await Read(Capture("/api/feed?after=19"));
        Assert.Equal(200, good.Status);
        Assert.Equal("raw-feed", good.RouteId);
        foreach (var raw in new[] { "/api/feed?after=%31", "/api/feed?after=1&after=2",
                 "/api/state?seat=p1", "/api%2Fstate", "/api/../state",
                 "/api/state?x=1?y=2", "http://localhost:8770/api/state",
                 "/api/state#fragment", "//api/state", "/api/state/",
                 "/api/./state", "/api/state?after=" + new string('1', 100),
                 "/api/state?reply_within=1200",
                 "/api/briefing?seat=p1", "/api/state\t", "/api/státe" })
        {
            var denied = await Read(Capture(raw));
            Assert.False(denied.FurtherValidationCandidate);
            Assert.True(denied.Status is 400 or 404);
        }
    }

    [Theory]
    [InlineData(FakeHttpCaptureEvidence.None)]
    [InlineData(FakeHttpCaptureEvidence.RawTargetPreserved)]
    [InlineData(FakeHttpCaptureEvidence.HeaderMultiplicityPreserved)]
    [InlineData(FakeHttpCaptureEvidence.PeerFromTransport)]
    [InlineData(FakeHttpCaptureEvidence.FramingVerified)]
    [InlineData(FakeHttpCaptureEvidence.ListenerInstanceVerified)]
    public async Task Any_unproven_capture_attribute_fails_before_body_read_or_credentials(
        FakeHttpCaptureEvidence evidence)
    {
        var auth = new Authority();
        using var stream = new CountingStream(Array.Empty<byte>());
        var x = await FakeHttpStreamIngress.ProcessAsync(
            Capture(evidence: evidence), stream, auth);
        Assert.Equal(400, x.Status);
        Assert.Equal(0, stream.Calls);
        Assert.Equal(0, auth.Lookups);
    }

    [Theory]
    [InlineData("Origin", "http://localhost:8770", 403)]
    [InlineData("Origin", "null", 403)]
    [InlineData("oRiGiN", "https://evil.invalid", 403)]
    [InlineData("Origin", "", 403)]
    [InlineData("Content-Length", "2", 400)]
    [InlineData("cOnTeNt-LeNgTh", "2", 400)]
    [InlineData(" Host", "127.0.0.1:8770", 400)]
    [InlineData("X-Fold", "value\r\n more", 400)]
    [InlineData("Cookie", "sid=abc", 403)]
    [InlineData("Transfer-Encoding", "chunked", 403)]
    [InlineData("Forwarded", "for=127.0.0.1", 403)]
    [InlineData("host", "127.0.0.1:8770", 400)]
    [InlineData("authorization", "Bearer other", 400)]
    [InlineData("X-Newline", "value\r\nInjected: x", 400)]
    public async Task Unsafe_native_headers_are_denied_without_body_read_or_auth(
        string header, string value, int status)
    {
        var body = Encoding.UTF8.GetBytes("{}");
        var capture = Add(Capture("/api/meta", "POST", Operator, body), header, value);
        using var stream = new CountingStream(body);
        var auth = new Authority();
        var x = await FakeHttpStreamIngress.ProcessAsync(capture, stream, auth);
        Assert.Equal(status, x.Status);
        Assert.Equal(0, stream.Calls);
        Assert.Equal(0, auth.Lookups);
    }

    [Fact]
    public async Task Wrong_port_host_peer_or_instance_never_silent_fallback()
    {
        var auth = new Authority();
        foreach (var c in new[] {
            Capture() with { RawHost = "evil.invalid:8770" },
            Capture() with { PeerAddress = "192.0.2.5" },
            Capture() with { BoundPort = 18770 },
            Replace(Capture(), "Host", "localhost:18770")
        })
        {
            using var s = new CountingStream(Array.Empty<byte>());
            var d = await FakeHttpStreamIngress.ProcessAsync(c, s, auth);
            Assert.False(d.FurtherValidationCandidate);
            Assert.Equal(0, s.Calls);
        }
        Assert.Equal(0, auth.Lookups);
        var alternate = new Authority {
            BoundPort = 18770, IntendedInstanceId = "synthetic-instance-18770"
        };
        var allowed = await Read(Capture(port: 18770), authority: alternate);
        Assert.True(allowed.FurtherValidationCandidate);
    }

    [Theory]
    [InlineData("0, 2")]
    [InlineData("+2")]
    [InlineData("-1")]
    [InlineData(" 2")]
    [InlineData("2 ")]
    [InlineData("2147483648")]
    [InlineData("999999999999999999999")]
    public async Task Ambiguous_declared_length_is_denied_before_read(string length)
    {
        var c = Replace(Capture("/api/meta", "POST"), "Content-Length", length);
        var auth = new Authority();
        using var stream = new CountingStream(Encoding.UTF8.GetBytes("{}"));
        var d = await FakeHttpStreamIngress.ProcessAsync(c, stream, auth);
        Assert.Equal(400, d.Status);
        Assert.Equal(0, stream.Calls);
        Assert.Equal(0, auth.Lookups);
    }

    [Fact]
    public async Task Missing_length_and_oversize_declared_body_shortcircuit()
    {
        var bytes = Encoding.UTF8.GetBytes("{}");
        var c = Capture("/api/meta", "POST", body: bytes);
        var absent = c with { RawHeaders = c.RawHeaders
            .Where(h => h.Key != "Content-Length").ToArray() };
        using var stream = new CountingStream(bytes);
        var missing = await FakeHttpStreamIngress.ProcessAsync(absent, stream, new Authority());
        Assert.Equal(411, missing.Status);
        Assert.Equal(0, stream.Calls);

        var oversize = Replace(c, "Content-Length",
            (FakeHttpStreamIngress.MaxBodyBytes + 1).ToString());
        var a = new Authority();
        var denial = await FakeHttpStreamIngress.ProcessAsync(oversize, stream, a);
        Assert.Equal(413, denial.Status);
        Assert.Equal(0, stream.Calls + a.Lookups);
    }

    [Fact]
    public async Task Exactly_16k_JSON_is_allowed_but_16k_plus_one_is_denied()
    {
        byte[] valid = Encoding.UTF8.GetBytes("{}" +
            new string(' ', FakeHttpStreamIngress.MaxBodyBytes - 2));
        var a = new Authority();
        var accepted = await Read(Capture("/api/meta", "POST", body: valid), valid, a);
        Assert.Equal(FakeHttpStreamIngress.MaxBodyBytes, accepted.BodyBytesRead);
        Assert.True(accepted.FurtherValidationCandidate);
        byte[] tooLong = Encoding.UTF8.GetBytes("{}" +
            new string(' ', FakeHttpStreamIngress.MaxBodyBytes - 1));
        var rejected = await Read(Capture("/api/meta", "POST", body: tooLong), tooLong);
        Assert.Equal(413, rejected.Status);
    }

    [Fact]
    public async Task Chunked_memory_stream_reads_exact_declared_length_and_probes_fake_EOF()
    {
        byte[] bytes = Encoding.UTF8.GetBytes("{\"event\":\"hello\"}");
        using var stream = new CountingStream(bytes) { ChunkSize = 1 };
        var decision = await FakeHttpStreamIngress.ProcessAsync(
            Capture("/api/meta", "POST", body: bytes), stream, new Authority());
        Assert.True(decision.FurtherValidationCandidate);
        Assert.Equal(bytes.Length, decision.BodyBytesRead);
        Assert.True(stream.Calls > bytes.Length);
    }

    [Fact]
    public async Task Premature_EOF_does_not_resolve_credential_or_dispatch()
    {
        byte[] bytes = Encoding.UTF8.GetBytes("{}");
        var declared = Replace(Capture("/api/meta", "POST", body: bytes),
            "Content-Length", "5");
        var a = new Authority();
        using var stream = new CountingStream(bytes);
        var result = await FakeHttpStreamIngress.ProcessAsync(declared, stream, a);
        Assert.Equal(400, result.Status);
        Assert.False(result.FurtherValidationCandidate);
        Assert.Equal(0, a.Lookups);
    }

    [Fact]
    public async Task Trailing_unframed_bytes_visible_in_mock_stream_fail_closed()
    {
        var bytes = Encoding.UTF8.GetBytes("{}EXTRA");
        var declared = Replace(Capture("/api/meta", "POST", body: bytes),
            "Content-Length", "2");
        var a = new Authority();
        using var stream = new CountingStream(bytes);
        var result = await FakeHttpStreamIngress.ProcessAsync(declared, stream, a);
        Assert.Equal(400, result.Status);
        Assert.False(result.FurtherValidationCandidate);
        Assert.Equal(0, a.Lookups);
    }

    [Fact]
    public async Task GET_or_DELETE_with_visible_body_is_rejected_even_without_declared_length()
    {
        foreach (string method in new[] { "GET", "DELETE" })
        {
            var capture = Capture("/api/state", method);
            var a = new Authority();
            using var stream = new CountingStream(Encoding.UTF8.GetBytes("{}"));
            var result = await FakeHttpStreamIngress.ProcessAsync(capture, stream, a);
            Assert.Equal(400, result.Status);
            Assert.False(result.FurtherValidationCandidate);
            Assert.Equal(0, a.Lookups);
        }
    }

    [Fact]
    public async Task IOException_and_cancellation_return_denial_not_throw()
    {
        var body = Encoding.UTF8.GetBytes("{}");
        using var fail = new CountingStream(body) { ThrowIo = true };
        var req = Capture("/api/meta", "POST", body: body);
        Assert.Equal(400, (await FakeHttpStreamIngress.ProcessAsync(
            req, fail, new Authority())).Status);
        using var cancelled = new CountingStream(body) { ThrowCancel = true };
        Assert.Equal(408, (await FakeHttpStreamIngress.ProcessAsync(
            req, cancelled, new Authority())).Status);
        using var alreadyCancelled = new CountingStream(body);
        using var cts = new CancellationTokenSource();
        cts.Cancel();
        Assert.Equal(408, (await FakeHttpStreamIngress.ProcessAsync(
            req, alreadyCancelled, new Authority(), cts.Token)).Status);
    }

    [Fact]
    public async Task Mutable_test_headers_are_snapshotted_before_async_read()
    {
        var source = Capture("/api/control", "POST", P2,
            Encoding.UTF8.GetBytes("{}"));
        var list = source.RawHeaders.ToList();
        source = source with { RawHeaders = list };
        using var stream = new CountingStream(Encoding.UTF8.GetBytes("{}")) {
            FirstRead = () => list[list.FindIndex(x => x.Key == "Authorization")] =
                new("Authorization", "Bearer " + Operator)
        };
        var result = await FakeHttpStreamIngress.ProcessAsync(source, stream, new Authority());
        Assert.Equal(403, result.Status); // cannot promote stale P2 to operator
        Assert.False(result.FurtherValidationCandidate);
    }

    [Fact]
    public async Task Revocation_during_fake_read_is_rechecked_before_candidate()
    {
        var a = new MutableAuthority();
        var bytes = Encoding.UTF8.GetBytes("{}");
        using var stream = new CountingStream(bytes) {
            FirstRead = () => a.Revoked = true
        };
        var result = await FakeHttpStreamIngress.ProcessAsync(
            Capture("/api/control", "POST", Operator, bytes), stream, a);
        Assert.Equal(401, result.Status);
        Assert.False(result.FurtherValidationCandidate);
    }

    // Deliberately ignores cancellation and suspends at a chosen body/EOF read.
    // The test owns release; ingress has no deadline and cannot abort this stream.
    private sealed class SuspendedStream : MemoryStream
    {
        internal readonly TaskCompletionSource<bool> Started =
            new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal readonly TaskCompletionSource<bool> Release =
            new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal int Calls;
        internal int SuspendOn = 1;
        internal SuspendedStream(byte[] bytes) : base(bytes, writable: false) { }
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer,
            CancellationToken cancellationToken = default)
        {
            if (++Calls == SuspendOn)
            {
                Started.TrySetResult(true);
                await Release.Task;
            }
            return await base.ReadAsync(buffer, CancellationToken.None);
        }
    }

    [Theory]
    [InlineData(1)]
    [InlineData(2)]
    public async Task Cancellation_ignored_by_body_or_EOF_read_never_becomes_candidate(int suspendOn)
    {
        var bytes = Encoding.UTF8.GetBytes("{}");
        using var stream = new SuspendedStream(bytes) { SuspendOn = suspendOn };
        using var cts = new CancellationTokenSource();
        var auth = new Authority();
        var pending = FakeHttpStreamIngress.ProcessAsync(
            Capture("/api/meta", "POST", body: bytes), stream, auth, cts.Token);
        try
        {
            await stream.Started.Task.WaitAsync(TimeSpan.FromSeconds(5));
            cts.Cancel();
            // Cancellation does NOT abort an ignoring read. Do not claim a time bound.
            Assert.False(pending.IsCompleted);
        }
        finally { stream.Release.TrySetResult(true); }
        var result = await pending.WaitAsync(TimeSpan.FromSeconds(5));
        Assert.Equal(408, result.Status);
        Assert.False(result.FurtherValidationCandidate);
        Assert.Null(result.RouteId);
        Assert.Equal(0, auth.Lookups);
        Assert.Equal(suspendOn, stream.Calls);
    }

    [Fact]
    public async Task Precancelled_request_does_not_call_even_an_ignoring_stream()
    {
        using var stream = new SuspendedStream(Array.Empty<byte>());
        using var cts = new CancellationTokenSource();
        cts.Cancel();
        var auth = new Authority();
        var pending = FakeHttpStreamIngress.ProcessAsync(Capture(), stream, auth, cts.Token);
        try
        {
            var result = await pending.WaitAsync(TimeSpan.FromSeconds(5));
            Assert.Equal(408, result.Status);
            Assert.False(result.FurtherValidationCandidate);
            Assert.Equal(0, stream.Calls);
            Assert.Equal(0, auth.Lookups);
        }
        finally { stream.Release.TrySetResult(true); }
    }

    [Fact]
    public async Task Header_snapshot_and_revocation_survive_a_genuinely_suspended_read()
    {
        var bytes = Encoding.UTF8.GetBytes("{}");
        var auth = new MutableAuthority();
        var source = Capture("/api/control", "POST", Operator, bytes);
        var headers = source.RawHeaders.ToList();
        using var stream = new SuspendedStream(bytes);
        var pending = FakeHttpStreamIngress.ProcessAsync(source with { RawHeaders = headers },
            stream, auth);
        try
        {
            await stream.Started.Task.WaitAsync(TimeSpan.FromSeconds(5));
            auth.Revoked = true;
            headers.Clear();
        }
        finally { stream.Release.TrySetResult(true); }
        var result = await pending.WaitAsync(TimeSpan.FromSeconds(5));
        Assert.Equal(401, result.Status);
        Assert.False(result.FurtherValidationCandidate);
        Assert.Null(result.RouteId);
    }

    [Fact]
    public async Task Zero_read_is_terminal_EOF_without_retry_or_authority_lookup()
    {
        using var stream = new CountingStream(Encoding.UTF8.GetBytes("{}")) { ChunkSize = 0 };
        var auth = new Authority();
        var result = await FakeHttpStreamIngress.ProcessAsync(
            Capture("/api/meta", "POST"), stream, auth);
        Assert.Equal(400, result.Status);
        Assert.Equal(0, result.BodyBytesRead);
        Assert.False(result.FurtherValidationCandidate);
        Assert.Equal(1, stream.Calls);
        Assert.Equal(0, auth.Lookups);
    }

    [Fact]
    public async Task Cancellation_during_authority_resolution_cannot_return_a_candidate()
    {
        using var cts = new CancellationTokenSource();
        var auth = new Authority { OnResolve = () => cts.Cancel() };
        using var stream = new CountingStream(Array.Empty<byte>());
        var result = await FakeHttpStreamIngress.ProcessAsync(Capture(), stream, auth, cts.Token);
        Assert.Equal(408, result.Status);
        Assert.False(result.FurtherValidationCandidate);
        Assert.Null(result.RouteId);
        Assert.Equal(1, auth.Lookups);
    }

    private sealed class InvalidCountStream : MemoryStream
    {
        internal int Count;
        public override ValueTask<int> ReadAsync(Memory<byte> buffer,
            CancellationToken cancellationToken = default) => new(Count);
    }

    [Theory]
    [InlineData(-1)]
    [InlineData(3)]
    [InlineData(int.MaxValue)]
    public async Task Broken_stream_count_is_denied_without_accounting_or_authority(int count)
    {
        using var stream = new InvalidCountStream { Count = count };
        var auth = new Authority();
        var result = await FakeHttpStreamIngress.ProcessAsync(
            Capture("/api/meta", "POST"), stream, auth);
        Assert.Equal(400, result.Status);
        Assert.Equal(0, result.BodyBytesRead);
        Assert.False(result.FurtherValidationCandidate);
        Assert.Equal(0, auth.Lookups);
    }

    [Fact]
    public async Task Authority_property_and_resolver_failures_are_unavailable_not_candidates()
    {
        foreach (var auth in new[] {
            new Authority { FailPort = true },
            new Authority { OnResolve = () => throw new InvalidOperationException("synthetic store failure") }
        })
        {
            using var stream = new CountingStream(Array.Empty<byte>());
            var result = await FakeHttpStreamIngress.ProcessAsync(Capture(), stream, auth);
            Assert.Equal(503, result.Status);
            Assert.False(result.FurtherValidationCandidate);
            Assert.Null(result.RouteId);
        }
    }

    [Theory]
    [InlineData("?breaks=1")]
    [InlineData("?reply_within=1200")]
    public async Task Proposed_P2_route_does_not_accept_legacy_query_controls(string query)
    {
        var bytes = Encoding.UTF8.GetBytes("{}");
        var auth = new Authority();
        var result = await Read(Capture("/mcp/p2" + query, "POST", P2, bytes), bytes, auth);
        Assert.Equal(400, result.Status);
        Assert.False(result.FurtherValidationCandidate);
        Assert.Equal(0, auth.Lookups);
    }

    private sealed class MutableAuthority : IFakeRouteAuthority
    {
        internal bool Revoked;
        public string IntendedInstanceId => "synthetic-instance-8770";
        public int BoundPort => 8770;
        public bool P1Consent => false;
        public bool DebugEnabled => false;
        public bool ViewerPublicationEnabled => false;
        public bool ViewerProjectionReady => false;
        public bool ReplayProjectionReady => false;
        public FakeRoutePrincipal? ResolveGameBearer(string token) =>
            Revoked ? null : token == Operator
                ? new FakeRoutePrincipal("operator", IntendedInstanceId, FakeRouteGrant.OperatorRunControl)
                : null;
        public bool CurrentP2Owner(FakeRoutePrincipal principal, string session, string epoch) => false;
    }
}
