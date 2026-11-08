# Sunny Phase 2D — native HTTP all-routes policy inventory (offline only)

**NOT A SECURITY FIX. NO LIVE LISTENER IS CONNECTED.** The code in this PR is a **pure, test-only** route/credential/profile classifier. It neither executes `HttpListener` nor serializes/serves a response and is NOT built into the production mod. A positive fixture decision is **only a request for further independently authorized validation**: it is not an authenticated production capability, evidence of a raw socket peer, a file-read permission, or a queue/WorldClock admission.

## Files added

- `mod/StardewMCP.Tests/FakeAllRoutesBoundary.cs` — conservative synthetic native bearer + loopback/Host/port/framing/route-matrix gate. All decision results are *hints*, with **no body or side effects**. Explicitly distinguishes P2 MCP (must still pass PR #31 real dormant preflight), raw operator-only legacy data, operator mutations, scoped health, private replay, and opt-in published viewer projections.
- `mod/StardewMCP.Tests/AllRoutesBoundaryTests.cs` — independent scopes × route/method matrix, P1/default-seat denial, native-browser/Origin/proxy/Host smuggling, raw body framing, port/instance, unknown path, C+O plus P1 consent, native watchdog isolation, replay/viewer default deny and exact debug/release-freeze constraints.
- This README — source inventory, authority matrix and genuine integration blockers.

**No changes** to `AgentHttp.cs`, `McpDispatcher.cs`, `McpSeat.cs`, `AgentRuntime.cs`, `SunnyP2Preflight.cs`, `ModEntry.cs`, `WorldClock.cs`, `Players.cs`, Python Luna scripts, installed SMAPI DLL, user saves or `main`.

## Grounded active routes at PR #22 base commit `486c6597e608f5ae6440f9f9e3adce7730637447`

The legacy `AgentHttp.cs` uses unauthenticated root listener prefixes for localhost and 127.0.0.1, wildcard `Access-Control-Allow-Origin`, no protected browser read projections and no per-route bearer grant checks. Its `Handle` starts at line 98. **These are verified observations of current source, not effects of this fixture.**

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
| `/api/debug/p2/{look,set_health,set_stamina}` POST | **A:debug-p2**, explicit target + config enabled, **then** tool/argument schema; all other debug operations denied | No debug host/P1 fallback or uncontrolled operations; actual debug effect is **not approved** by this gate. |
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
- No Transfer-Encoding/chunked and no ambiguous Content-Length. Body max 16 KiB; POST in this mock needs exact Content-Type application/json and strict UTF-8. POST bodies must be strict UTF-8 JSON objects, depth <=32, without duplicate keys anywhere or nonfinite numbers. Tool/command schemas remain **unchecked** (except a deliberately narrow `/api/release_freeze` seat shape). Candidate mutation routes require an additional real body/schema validator before doing anything.
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


## Independent Issue #38 review (2026-11-08)

Reviewed against the checked-in [approved server contract](../../docs/sunny-agentic/SERVER_AUTH_SESSION_EPOCH_CONTRACT.md),
[dormant preflight](../../mod/StardewMCP/Agent/SunnyP2Preflight.cs),
[fake atomic intake](../sunny_p2_atomic_intake/README.md), and
[PR #35 side-effect audit](../sunny_p2_server_boundary/README.md).
Severity below describes a future consumer trusting the original classifier; the fixture itself has no dispatch or response capability.

| Severity | Source-backed finding | Correction / remaining boundary |
| --- | --- | --- |
| High | Original debug matcher accepted every lowercase operation, even nonexistent `say`. [DebugApi.All](../../mod/StardewMCP/Agent/DebugApi.cs) includes `load_save`, `save`, `hang`, `capture` and world mutations: an explicit p2 path is not proof of P2-local effects. | Restrict candidates to an intentionally small source-existing subset: `look`, `set_health`, `set_stamina`. Unknown and all other operations return 404. This is not approval to run even those three: exact argument schema, own-screen targeting, role/epoch/permission checks and effect audit remain mandatory. Regressions cover unknown/global operations with debug enabled and full operator grants. |
| Medium | Original POST gate checked UTF-8 but accepted non-JSON, arrays, duplicate keys and overflowing numeric values as candidates for control/meta/debug/MCP. Downstream schemas were expressly deferred, but candidate status could falsely reassure a future caller. | Require a whole strict JSON object before credential resolution; recursively reject duplicate keys (including escaped-equivalent names), nonfinite numbers, comments, trailing commas and excess depth. Route-specific schema remains deferred. Regressions assert malformed bodies never resolve credentials or become candidates. |
| Medium | `authority.BoundPort` was read outside failure handling; binding-store failure could throw instead of returning an explicit unavailable denial. | Wrap the full synthetic evaluation in fail-closed 503 handling; regression throws from the property. This does not supply a trusted socket binding. |
| Low | Route inventory mixed existing handlers with proposed method restrictions and omitted concrete control/debug/asset fallback detail. | Exact source behavior and migration blockers below; explicit dot-segment rejection, numeric framing negatives, every single grant against every listed route, and sequential revocation/instance/publication rechecks added. |

### Complete existing handler audit

[AgentHttp.Handle](../../mod/StardewMCP/Agent/AgentHttp.cs) lines 98–220 contains all HTTP routing:

- Lines 105–112: normalized `Url.AbsolutePath.TrimEnd('/')`; any `/api/debug/` prefix goes to `SeatPrefix` and `HandleDebug` (270–302). No recognized seat prefix means **host**, not P2. Debug disabled or unknown op is 404 before method; known op with non-POST is 405. Explicit pN does not isolate effects. No application auth.
- Lines 113–131: `/mcp` aliases host, `/mcp/{id}` uses `Players.ById`; human/inactive split-screen role gate returns 404. POST dispatches; DELETE returns empty 200 with no retirement; all other methods 405. Never assume P1 is AI, or silently assign other AI seats to Sunny.
- Lines 134–164, 175–195: `/overlay`, `/replay`, root (empty after trimming), `/api/feed`, `/api/state`, `/api/briefing`, `/api/relationships`, `/api/stats`, `/api/days`, `/api/day`, `/api/memory` have **no method guard**. Their bodies may still fail downstream; these handlers are not GET-only. Feed includes raw StateJson, metadata and entries; day includes aggregate AI diaries and legacy `diary` p1 alias. Memory/relationships/stats are not automatically P2-scoped. State includes host paths, money, location and dialogue (RefreshState, 346 onward).
- `/api/control` at 165–174 forwards GET/POST/other methods to [RunControl.Handle](../../mod/StardewMCP/Agent/RunControl.cs):123 onward; unsupported methods return **400**, not 405. POST can change global pause/stop flags and queue gameplay log notes.
- `/api/release_freeze` and `/api/meta` at 196–208 are POST-only switch cases; other methods fall through to **404**. ReleaseFreeze (230–265) accepts missing seat as host, case-insensitive `all` selects all AI seats, omitted `on` means true. Metadata accepts arbitrary string dictionary entries and `event` writes gameplay log. None is protected by this fixture.
- Default is 404. There is **no generic static directory/file route**: File (335–340) serves only overlay.html or replay.html selected above. Trailing slash aliases are accepted by legacy normalization, not by the proposed classifier.

[overlay.html](../../mod/StardewMCP/assets/overlay.html):657–685 and
[replay.html](../../mod/StardewMCP/assets/replay.html):150,209–246 read raw feed/day/days; both accept an `api` query override and fall back to localhost:8770 away from port 8770. Merely granting a shell does not protect its subsequent requests or sanitize transmitted data. No viewer publication or file read occurs in this model. Future assets must use reviewed same-origin, correct-instance projected APIs with separate browser pairing; no bearer in HTML/JS/URL.

The contract also proposes `/api/companion/v1/p2/lease` and `/operations/{id}` recovery reads. These are **future-only and deliberately unlisted/404 here**, pending owner/tombstone-scoped schemas. Versioned health/safety/replay/view routes above are likewise absent from AgentHttp. No other production HTTP route was found in this handler.

### Deliberate limits and mandatory future work

The raw request is caller-supplied synthetic data: RawPath/RawQuery must be split losslessly by a trusted adapter; Host must retain multiplicity before normalization; PeerAddress is **not verified Windows socket identity**. IPv6 Host is deliberately denied until binding tests; synthetic loopback peers alone prove no identity. This model cannot test HTTP request-line/version parsing, HttpListener's header merging/rejection, socket framing, pipelining, slow bodies or resource exhaustion. Duplicate case-variant headers, folding/control characters, CL/TE, unsupported transfer codings and ambiguous lengths must be rejected by that real adapter before any route effects. Status numbers are hints: the model currently classifies path/method/query before headers/auth, so 400/404/405 precedence is not a production error-order/privacy guarantee. No Allow/WWW-Authenticate/no-store/CORS response headers are generated.

Strict JSON is not a command schema. Before RunControl, require an exact bounded action enum and property policy; before metadata, bounded approved display keys/values and no arbitrary `event` logging; before debug, approved operation-specific bounded arguments and shared-world/P1 policy; before files/reads, current credential generation, seat/day/field projection and safe path selection; before P2 calls, PR #31 envelope/tool schema followed by real atomic admission. `{}` can remain a candidate, never an executable mutation. GET/DELETE bodies are rejected; replay/view query parameters remain unapproved and rejected. Legacy `?breaks=1` / `?reply_within=1200` are deliberately incompatible until reviewed versioned client migration.

Each Check re-resolves credentials, instance, grants and publication, but neither generation nor role/epoch/consent is atomically locked to protected serialization/admission. Mutable request collections are not a trusted immutable wire snapshot. Real readers need current authorization, projection redaction and invalidation under the coordinator; R needs exact seat/day/field intersection, V explicit publication and approved sanitization. Safety requires the same C+O bearer, current owner/session/epoch and independent P1 consent; the consent-denied hint supplies **no private body**. H cannot read state or control the run. Operator subscopes do not inherit. Release-all additionally requires release-p2 and release-all, with current role/P1/shared-world validation still pending.

Preserve PR #35's **validated owner presence at acquired lease before Luna starts thinking**; accepted queue/admitted tool start is a distinct event. Denials must never cause contact, deadlines, breaks, freeze/release, log writes, publication, reads or queue actions. This fixture issues no operation ID or atomic authority. Production still needs secure native provisioning/storage, raw all-route enforcement, bounded input/concurrency, authoritative instance/host epoch/role/lease/grant generations, atomic lane admission and per-coroutine effect fences, retirement/quiescence/unknown-outcome reconciliation, P1 consent and private/public projectors, browser/OBS migration, native Luna session/epoch/recovery/long-bedtime compatibility, and isolated Windows/SMAPI acceptance. Current private pilot source and installed behavior remain uninspected. Passing game-free tests cannot satisfy those gates.

**Disposition:** suitable only as an inert test/reference addition to PR #22's Draft design branch. Keep PR #37 Draft and unmerged; no production security acceptance or deployment is implied.

### Review validation

- `dotnet test mod/StardewMCP.Tests`: **735 passed, 0 failed, 0 skipped** (.NET SDK 8.0.419, .NET 6 test target/runtime; existing SDK was added to PATH).
- `python -m pytest -q mod/tests reference/sunny_gift/tests`: **286 passed, 1 existing xfailed** (existing `.venv/bin/python`; default Python lacks pytest).
- `git diff --check` passes; only the three permitted paths changed. Relative Markdown links resolve locally. CI results must be read for the final pushed SHA; local results are not Windows/SMAPI security acceptance.
