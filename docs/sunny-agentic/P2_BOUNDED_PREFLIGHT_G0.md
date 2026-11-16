# G0 Sunny P2 bounded body / strict preflight bridge — dormant Mod source

**Status: OFFLINE ONLY, NO PRODUCTION CALLER.** This is a deliberately narrow
G0 step in the [Issue #76](https://github.com/niabchan/stardew-ai-agent/issues/76)
host integration lane, stacked on independently reviewed Draft PR #74.
No changes to `AgentHttp`, `McpDispatcher`, `AgentRuntime`, `ModEntry`, ports,
network listeners, installed Controller or user Mod.

## Why another source file is needed

Existing `AgentHttp.HandleMcp:306–315` reads a full request with
`StreamReader.ReadToEndAsync()` before mutating `SessionBreaks.Observe` and
`seat.ReplyWithinSeconds`, then invokes a dispatcher that calls
`seat.MarkContact()` before validation. Existing `SunnyP2Preflight.cs` is
already a strict game-free request-shape classifier but receives an **already
buffered** `byte[] Body`. The older `FakeHttpStreamIngress` in
`StardewMCP.Tests` tests bounds with synthetic streams, but its implementation
is **test-only**.

`mod/StardewMCP/Agent/SunnyP2BoundedPreflight.cs` is an inert **actual
Mod-source** byte-budget reader for a *future* trusted native capture. It
reads exactly declared body length (0–16 KiB, with nonempty POST), never uses
unbounded `ReadToEndAsync` or an unsafe extra EOF probe, snapshots headers
before an asynchronous read, rejects duplicate/invalid security headers,
malformed/ambiguous raw route targets and mismatched Content-Length *before
reading*, and then delegates to existing `SunnyP2Preflight.Evaluate`.
Only `/mcp/p2` POST and DELETE are considered in this source. DELETE
may only become a **retirement candidate**—never a proven quiescent retirement.

The result `SunnyP2IngressCheck.CandidateOnly` means a provisional shape and
policy answer. It is **not permission to enqueue a tool, mark contact, start
session breaks, freeze the game, send a success response, acquire/release a
lease, or disclose data**. Any status code here is an inert classification
only; caller must still independently recheck credentials, role, host epoch,
owner lease, tool/arguments and pending-op journal atomically at admission
and at the eventual game-thread start/step.

## Strong caveats

- **No real HttpListener adapter**: `SunnyP2IngressCapture` fields are
  caller-provided assertions. A future reviewed adapter MUST prove Windows
  HTTP.sys preserves the raw request target and header multiplicity, supplies
  real peer address and bound listener port rather than forwarding headers,
  and checks body framing and host authority. A fake localhost string is
  **not** server authentication, and `Capture` itself does not prove any
  such provenance.
- **No deadline / cancellation guarantee**: `ReadAsync` observes a caller
  cancellation token and returns a denial if it fires; a stream that ignores
  cancellation may block indefinitely. A future listener must enforce
  independent connection/read/dispatch budgets, real cancellation/abort and
  resource/queue limits. This G0 code does not contact any socket.
- **No extra EOF probe**: true HTTP framing is outside the body budget
  helper. Reading a speculative byte after declared Content-Length can block
  or be unrelated to this request. Uncertain framing MUST be denied by the
  upstream native adapter.
- **No listener security/credentials**: the injected `ISunnyP2PolicyAuthority`
  in tests is fake. A positive `SunnyP2Preflight.Evaluate` is *not* a real
  atomic authorization, host identity or independent STOP. There is no P1
  access authorization or P1 private data projection here.
- **No actual STOP**: the new source is never called by `AgentHttp` or
  `AgentRuntime`. The reviewed `SunnyP2HostFence` in PR #74 is also dormant;
  a Boolean STOP gate does not retire two runtime queues, running
  coroutines, partial game effects or their buffers.
- **No durable host journal/effect reconciliation**: the SQLite pending
  ledger of reviewed PR #72 is offline Python storage, not yet bound to
  this C# ingress. A tool ACK or returned `TaskCompletionSource` cannot
  release pending uncertainty or authorize retry.
- **No provider-key alias**: game bearer, if ever provisioned, must be
  independent of the Luna/model API key. The extracted private v0.3.10
  Controller callsite inventory still awaits guarded full migration.

## G0 tests, not Windows/game proof

`mod/StardewMCP.Tests/SunnyP2BoundedPreflightTests.cs` compiles the **actual
Mod-source** file through `StardewMCP.Tests.csproj` and tests synthetic
MemoryStream and injected authority behavior: positive *candidate-only*
initialize/mutation/DELETE; no premature credentials on invalid raw
target, host/peer, duplicate/unsafe headers or oversize/missing lengths;
partial reads, missing bytes, no unsafe EOF probe, cancellation/IO errors,
old owner denial and malformed JSON delegated to the existing strict
preflight. Tests never bind `HttpListener`, open sockets or touch SMAPI,
Controller, Luna, installed DLLs or saves.

**G1 stays NO_GO:** 11 gates OPEN, 50 historical live cases `not_run`,
`NO_GO_G1_START / NO_GO_LIVE_G2`. Independent review required before
integration. Keep this PR Draft/unmerged.
