# Sunny Phase 2D — native HTTP all-routes policy inventory (offline only)

**NOT A SECURITY FIX. NO LIVE LISTENER IS CONNECTED.** The code in this PR is a **pure, test-only** route/credential/profile classifier. It neither executes `HttpListener` nor serializes/serves a response and is NOT built into the production mod. A positive fixture decision is **only a request for further independently authorized validation**: it is not an authenticated production capability, evidence of a raw socket peer, a file-read permission, or a queue/WorldClock admission.

## Files added

- `mod/StardewMCP.Tests/FakeAllRoutesBoundary.cs` — conservative synthetic native bearer + loopback/Host/port/framing/route-matrix gate. All decision results are *hints*, with **no body or side effects**. Explicitly distinguishes P2 MCP (must still pass PR #31 real dormant preflight), raw operator-only legacy data, operator mutations, scoped health, private replay, and opt-in published viewer projections.
- `mod/StardewMCP.Tests/AllRoutesBoundaryTests.cs` — independent scopes × route/method matrix, P1/default-seat denial, native-browser/Origin/proxy/Host smuggling, raw body framing, port/instance, unknown path, C+O plus P1 consent, native watchdog isolation, replay/viewer default deny and exact debug/release-freeze constraints.
- This README — source inventory, authority matrix and genuine integration blockers.

**No changes** to `AgentHttp.cs`, `McpDispatcher.cs`, `McpSeat.cs`, `AgentRuntime.cs`, `SunnyP2Preflight.cs`, `ModEntry.cs`, `WorldClock.cs`, `Players.cs`, Python Luna scripts, installed SMAPI DLL, user saves or `main`.

## Grounded active routes at PR #22 base commit `486c6597e608f5ae6440f9f9e3adce7730637447`

The legacy `AgentHttp.cs` uses an unauthenticated catch-all listener, wildcard `Access-Control-Allow-Origin`, no protected browser read projections and no per-route bearer grant checks. Its `Handle` starts at line 98. **These are verified observations of current source, not effects of this fixture.**

| Existing handler | Required synthetic next-step grant / profile | Why normal P2, H, R or V cannot receive raw legacy output |
| --- | --- | --- |
| `/mcp/p2` POST, DELETE | Native P2 **C** control; **delegate** to PR #31 preflight then atomic session/queue/epoch coordinator | C is not authority over P1 or arbitrary raw reads. Legacy DELETE 200 is **not** verified retirement. POST can be initialize; method/JSON/grant/tool details still unchecked by this fixture. |
| `/mcp`, `/mcp/p1`, `/mcp/p3` and other seats | Deny this **Sunny-specific** route profile | Never fallback to host/P1. Other upstream AI seats need their own separate authority profile, not P2 ownership. |
| `/api/state` | **A:raw-state**, exceptional private operator read | Legacy raw state exposes host information and all-seat data. Never use it as P2's safety read or watchdog health. |
| `/api/feed`, `/api/days`, `/api/day`, `/api/memory` | **A:raw-history** | Raw feed/day/memory may contain diaries, reasoning, IDs, logs and P1 material. No viewer or native P2 fallback. |
| `/api/briefing`, `/api/relationships`, `/api/stats` | **A:private-read**, with explicit `?seat=p2` on briefing | Existing briefing may select the wrong/default seat when unspecified. Never grant P1 raw information through a generic O scope. |
| `/api/control` GET or POST | **A:run-control**, requires real command-schema validation on POST | Cannot be controlled by watchdog, ordinary P2, replay or viewer credentials. |
| `/api/release_freeze` POST | **A:release-p2** plus independently **A:release-all** for `seat=all` | This fixture enforces exact JSON `seat=p2` or `seat=all` (and bool `on`) before classifying. P1/other-seat/default implicit release refused. Actual operator freeze and P1 role semantics remain runtime obligations. |
| `/api/meta` POST | **A:metadata** + future body schema | No general controller metadata-write right. |
| `/api/debug/p2/{op}` POST | **A:debug-p2**, explicit target + config enabled, **then** tool/argument schema | No debug host/P1 fallback or uncontrolled operations; actual debug effect is **not approved** by this gate. |
| `/`, `/overlay`, `/replay` GET | **A:private-shell** and separately vetted private assets | No direct published viewer/OBS shell in this slice; legacy HTML may load unprotected API URLs. |
| Other legacy path/method | Deny 404/405 | Unknown paths never imply a default route or raw endpoint. |

The original handler also responds on methods not intentionally limited in its `switch`; this table describes the **proposed stricter methods**, not what the legacy server actually enforces. User consent and exact P1/private projections remain mandatory before live viewer features.

## Proposed-only endpoints (NOT present in today's AgentHttp)

| Future route | Only synthetic candidate with | Still required before a response could exist |
| --- | --- | --- |
| `GET /api/companion/v1/p2/safety` | Same P2 bearer with **C+O**, current owner/session/epoch, separate P1 consent | Consent false is `ConsentDeniedProjectionOnly` **not** permission to emit private fields; the final server design requires an exact minimal denial payload. No fake safety data is constructed here. |
| `GET /api/health/v1` | **H** watchdog-only | Safe aggregate liveness projector with no raw state, diaries, paths or operator controls. |
| `GET /api/replay/v1/{config,days,day,memory}` | **R** private replay and explicitly ready projector | Seat/day/field intersection, projected data, no P1 raw fallback or implicit file read. |
| `GET /api/view/v1/{config,feed,summary}` | **V** distinct viewer bearer, explicit publication AND approved sanitized projector | Default **unpublished**. No viewer shell, diary, personal thoughts, P1 text or raw feed API. OBS/browser-cookie pairing and CSRF must be designed separately. |

C, O, A subscopes, H, R and V have **no implicit inheritance**. There is no P1 automation grant, and P2 exclusivity does not change other upstream seats. The game bearer here is synthetic and **not** the OpenAI provider key.

## Mock boundary constraints and request attributes

- Exact **raw path** / case, loopback peer address, raw Host header matching the configured port, and per-listener **intended instance ID**. A token from port 18770 is not usable on the instance bound to 8770; hostname/port fallback is not permitted. The fake expects the **full, unnormalized raw request target**; real `HttpListenerRequest.Url.AbsolutePath` is normalized and cannot substitute for it without review.
- Exactly one each security header (case-insensitive duplicate rejected), no `Origin` (including empty/null/same-origin), Cookie or forwarded-peer/proxy headers in **this native bearer-only pilot profile**. No browser form/CSRF bypass. Browser pairing is not implemented; **real UI/OBS use remains gated**.
- No Transfer-Encoding/chunked and no ambiguous Content-Length. Body max 16 KiB; POST in this mock needs exact Content-Type application/json and strict UTF-8. Body JSON and tool schemas are **not fully parsed** (except a deliberately narrow `/api/release_freeze` seat shape). Candidate mutation routes require an additional real body/schema validator before doing anything.
- Query grammar is narrowed for raw operator reads: `?after=digits`, `?n=digits`, and **required** `?seat=p2` for briefing. Any encoded query/duplicate/legacy P2 `?breaks`/`?reply_within` is rejected **until a reviewed compatibility migration**. No URI normalization, auto-redirects or default seat.
- A user-provided HTTP token, `trustedAttemptId`, session header or fake authorization callback does **not** acquire game admission. The class doesn't issue sessions, check owner for MCP initialize/DELETE, write a dispatch journal, cancel pending game calls, fence nested coroutine steps, validate P1 consent against the actual game, or calculate real HTTP response deadlines.

**This policy is a deny/route candidate map for later deep validation, not a protocol wire implementation.** Real Auth must recheck credential generation + role + host epoch atomically with protected reads or queue admission. Auth failure may only affect sanitized security counters; it may not alter `MarkContact`, `SessionBreaks`, `ReplyWithinSeconds`, `RunControl`, logging, freeze, or P1/game state. Protected responses must be no-store; scoped content must be projected and redacted before serialization.

## Migration blockers and next isolated gate

The legacy listener remains an unauthenticated side door unless **every route** is coherently gated. In particular, merely enabling PR #31's dormant P2 policy would not secure `/api/control`, debug or raw private reads. A future separate PR should review an actual Windows `HttpListener` **raw target/Host/framing adapter** using isolated loopback tests, exact error handling, bounded asynchronous input/connection work, and browser/OBS behavior, not the user's running game.

Before any live enforcement: provision real separate native credentials and OS ACL storage, secure per-route A/H/R/V independent identities, server-owned P2 role/epoch/lease/queue and immutable operation journal, verified retirement/quiescence with partial/unknown effect handling, consent-aware P1 projection and contact/freeze semantics, protected non-P2 routes, versioned native Luna/P12 migration, and Windows/SMAPI manual operator acceptance. No retrofit code in this PR claims to satisfy these.

## CI and independent review gates

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

Run the existing game-free suites in GitHub CI, then get an independent Codex review focusing on paths, raw Host/Origin, denied effects, method/query/body scope matrix, owner/port authorization, freeze control, viewer publication and P1 privacy. All tests use synthetic credentials and no live HTTP/MCP, OpenAI, attached private ZIP, SMAPI or game saves. Keep PR **Draft** and **unmerged until reviewed**, targeting PR #22's Draft branch only. No `main` change.
