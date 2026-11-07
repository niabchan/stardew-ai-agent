# Sunny P2 preflight policy seam — phase 2A (dormant source)

**Status: proposed, inert C# source and game-free tests. NOT a working secure listener.**

## Exact scope

- `mod/StardewMCP/Agent/SunnyP2Preflight.cs` — a dependency-free C# request-shape policy with pluggable **fake** credential, owner/session/epoch and tool argument authority. It is present in the mod source tree, so the normal C# project includes the class, **but no current code calls it**. In particular, `AgentHttp` still runs the legacy permissive listener. Do not assume the application is hardened.
- `mod/StardewMCP.Tests/SunnyP2PreflightTests.cs` — xUnit fake-auth and raw HTTP/MCP request-shape tests with no game or network.
- `mod/StardewMCP.Tests/StardewMCP.Tests.csproj` — explicitly compiles the new pure policy source into the game-free test assembly.
- This README records omissions, especially the crucial time-of-check/time-of-use distinction.

No changes to `AgentHttp.cs`, `McpDispatcher.cs`, `AgentRuntime.cs`, `ModEntry.cs`, roles, installed DLL, Lua/Luna Python controller, `main`, saves or real credentials. The new dormant source alone **does not stop unauthenticated requests**, including legacy `/api/state` and `/api/control`.

## Future P2-only preflight contract represented here

- Only canonical `/mcp/p2`, explicit configured loopback Host/peer, method POST or DELETE. `/mcp` and all other seats/routes are rejected. IPv6 host binding remains intentionally unapproved until Windows HTTP.sys testing.
- Reject any native Origin, duplicate/case-variant headers, invalid ASCII header values, absent/invalid game bearer, missing/mismatched session and host epoch. A synthetic authority is responsible for credential verification, independent C/O scopes, human P1/AI P2/external brain role readiness and current owner tuple; **the class does not provision/authenticate a real credential**.
- Fail closed on unparsed query strings (including legacy `?breaks` and `?reply_within`), invalid configured ports, bounded 16 KiB request, JSON depth, duplicate JSON object keys, finite numbers, strict JSON-RPC 2.0 shape and safe IDs. Query compatibility requires a separate parser/schema approval before integration. Reject all batches and unknown methods. Require exact initialize version `2025-06-18` with no session headers. Distinguish optional initialized notification and harmless discovery from tool admission.
- Empty-argument `status` requires both P2 Control and Observe. Other tools require explicit injected argument validation and Control. Unknown tools should be denied by a production schema validator; **never inject an allow-all callback**.
- A DELETE only passes policy admission for a matching owner; it **does not** retire the lease or certify quiescence. This must not weaken PR #26's permanent ownership-uncertain fence after unverified DELETE.
- The returned `SunnyP2Decision` is **not an authorization capability**: server integration must atomically recheck grant/role/owner/epoch, queue budget and tool schema under the coordinator on enqueue, then again at each game-thread step. Preflight never calls `MarkContact` or schedules anything.
- Only an accepted tool request is `MayMarkContact` eligible. Even this marker is not permission to mark a real seat without successful atomic admission and accepted tool *start*.

## Explicit limitations and gaps

**Do not wire the seam to AgentHttp yet.** Live legacy routes still use wildcard CORS, an unverified read-body limit, old JSON-RPC dispatch, response deadlines and contact before real policy validation. This phase intentionally does not add partial HTTP enforcement that would disconnect the existing Luna P10–P13 pilot.

Before a real listener integration, implement and independently test: native trusted verifier/provisioner and revocation, session issuance/retirement/tombstone and live epoch coordinator, role-generation and exclusive P2 ownership, strict request parsing at raw HTTP boundary (including duplicate Host, Transfer-Encoding, URL decoding and request-body read limits), exact tool schema from ToolContract, queue admission/fencing including observation lane, long-running coroutine cancellation, Windows HttpListener/HTTP.sys origin/peer validation, private P1 consent/status response projection, browser/OBS scopes, and full MCP response/version compatibility. A non-P2 route policy must also block legacy unprotected APIs before enforcement; adding a secure P2 path beside an insecure backdoor is insufficient.

The fake authority is invoked from the request parser; an application must not mistake its test implementation for a trusted principal. Exceptions from credential/schema provider fail closed with generic 503. No credential or raw body appears in `SunnyP2Decision`. Invalid requests do not change game state; synthetic verification counters in tests are not gameplay contacts. Concurrent revocation can still occur **after** a positive result; that is why the final coordinator must be the admission authority.

## Game-free verification

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

These commands must run in CI on this Draft PR. No Windows/SMAPI build, live HTTP/MCP, model usage, private records or saves should be accessed. Passing tests demonstrates parsing and rejection under synthetic assumptions only, **not** real listener authorization or race safety.

This slice is separate from [the server auth/epoch design](../../docs/sunny-agentic/SERVER_AUTH_SESSION_EPOCH_CONTRACT.md), [the offline Python client](../sunny_transport/README.md) and [the P2 coordinator fake](../sunny_p2_coordinator/README.md). Any merge should target PR #22's **Draft design branch only**, never main. Keep the actual listener change in a later, reviewed PR.

## Issue #32 independent review (2026-11-07)

Material findings fixed in this dormant seam (severity describes future integration
risk; none changes the currently exposed listener):

- **High: raw authority/framing ambiguity.** A valid `request.Host` previously
  coexisted with a conflicting single `Host` header, and Content-Length and
  Transfer-Encoding were ignored. Require one raw Host matching the explicit
  authority, validate any Content-Length against the bounded byte body, and
  reject all transfer codings in this phase. Duplicate headers remain rejected
  before credential lookup. This is not an HTTP request-smuggling defense for
  HTTP.sys: only a reviewed raw adapter can establish what bytes were consumed.
- **Medium: optional protocol header was ignored.** A contradictory
  `MCP-Protocol-Version` now fails closed instead of bypassing negotiation.
  Omission remains compatible with PR #26.
- **Medium: deferred UTF-8 decoding.** JsonDocument syntax parsing alone does not
  establish valid UTF-8 in every unused string. Validate the entire bounded byte
  body with a throwing UTF-8 decoder before JSON parsing, including unused nested
  values. Regressions also cover escaped duplicate keys, depth and safe-ID limits.
- **Medium: malformed authority principal.** Reject an empty/whitespace principal
  ID rather than letting an implementation accidentally match an anonymous owner.

### Adapter contract and compatibility gates

The future adapter must supply the configured port (never derive it from Host),
actual socket peer (never forwarded headers), exact raw authority in both Host
and the uncollapsed header list, canonical raw path and raw query separately.
Never feed only `Url.AbsolutePath`, decoded/trimmed paths or a dictionary that
already combined duplicates. Preserve case-variant duplicates, including Host,
Origin, Content-Length and Transfer-Encoding. If HTTP.sys cannot expose ambiguity,
prove its rejection at that boundary before integration. Bound body reads before
allocation (16 KiB, deadline 5s), verify length/end-of-body, and reject transfer
coding before dispatch. Reject ambiguous requests and close their connections;
do not reuse keepalive connections with unread bytes. Connection and concurrency
budgets, slow-body defense and pipelined requests are not implemented here.

Exact `application/json` and the supplied v0.3.11 pilot's
`Accept: application/json, text/event-stream` list work; PR #26's JSON-only Accept
also works. Media parameters, Accept quality negotiation and chunked requests
remain unsupported by this narrow profile and require a reviewed migration,
not silent normalization. The pilot itself still needs bearer/session/epoch and
initialize migration; its legacy query options remain rejected.

`SunnyP2Decision.Status == 200` means policy admission only, not a wire response.
The future response layer must turn admitted initialized notifications into empty
202, echo the admitted epoch, use no-store/no wildcard CORS, issue a lease only
after atomic acquisition, and never treat admitted DELETE as retirement proof.
The current bool session authority cannot distinguish foreign/unknown (404),
retired (410) and stale-current-owner (409) states from the approved contract;
its generic 409 is a deliberate lossy seam, not the final wire error taxonomy.
No positive decision proves cryptographic credential verification, session
issuance, retirement, cancellation or quiescence. PR #26's indefinite ownership
and mutation-unknown fences must remain intact.

C and O are independent: status requires both, mutation requires C plus an
approved schema. Neither authorizes P1 automation, raw status/diary/OBS data or
the separate consent-aware P1 safety projection. Every non-status tool is
conservatively classified as mutation; real ToolContract validation must deny
unknown tools, extra fields and cross-seat/resource injection. The fake say-only
validator is not a production schema registry.

The existing reload-between-preflight-and-enqueue regression demonstrates a
stale positive decision, not general race safety. A real coordinator must
atomically recheck credential revocation, C/O grants, owner/session/instance/epoch,
role generation, tool arguments and queue capacity before contact, deadline,
freeze or insertion, and check relevant predicates before every coroutine step
and observation disclosure. Fake counters are not gameplay effects.

### Compilation and disposition

The SDK's default source inclusion compiles this namespace's unused records and
class into the net6.0 mod; the test project explicitly links the same file into
its own assembly without referencing the game project. The language, records,
System.Text.Json and namespace match the current project. Game-free compilation
does not verify SMAPI/Windows integration; no mod build or installed DLL change
is part of this review. No caller references this class.

Keeping the source dormant here is acceptable **only as an inert source+test
addition to PR #22's Draft branch**. Before integration, prefer a separate
game-free shared policy library with typed admission/response boundaries so the
mod, raw-adapter tests and coordinator use one compiled contract. That structural
change is outside these four files and does not justify connecting this seam now.
Legacy endpoints remain exposed as documented above.

Review source anchors: raw header/framing/version gates
[SunnyP2Preflight.cs:52](../../mod/StardewMCP/Agent/SunnyP2Preflight.cs#L52),
principal check [line 76](../../mod/StardewMCP/Agent/SunnyP2Preflight.cs#L76),
UTF-8 check [line 106](../../mod/StardewMCP/Agent/SunnyP2Preflight.cs#L106);
revocation snapshot regressions
[SunnyP2PreflightTests.cs:335](../../mod/StardewMCP.Tests/SunnyP2PreflightTests.cs#L335).
The existing role/scope, stale-session and reload regressions remain in that file.

Local verification: game-free C# suite **551 passed, 0 failed, 0 skipped**;
Python `mod/tests reference/sunny_gift/tests` **286 passed, 1 existing xfailed**;
`git diff --check` passed. The first C# invocation could not write the default
CLI home; rerunning with the existing writable /workspace CLI home and NuGet
cache passed. No dependencies, mod binaries or game were installed/launched.
These results cover synthetic contracts only.
