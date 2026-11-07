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
