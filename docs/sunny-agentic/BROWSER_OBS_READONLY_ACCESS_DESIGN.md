# Sunny browser, OBS and read-only access design

> 2026-11-07 · Documentation proposal, source review only. Baseline:
> `3a39b83bf37ac91ca1f1b88c55f91c1d70231ae9` on
> `docs/sunny-controller-client-compatibility`. No runtime enforcement is implemented.
> Guy is human P1; Sunny is AI P2. No live Sunny API, credentials, saves, game,
> OBS or external controller was accessed or run for this review.

This extends [the client inventory](HTTP_MCP_CLIENT_COMPATIBILITY.md),
[security review](HTTP_MCP_SECURITY_REVIEW.md) and
[test-only policy](SECURITY_POLICY_FIXTURES.md). **S** below means checked-in
source; **D** means proposed contract; **U** means unverified external behavior.
The native-only fixture's rejection of every Origin and GET is not a browser policy.

## Source findings and compatibility consequences (S)

The following files were inspected at the baseline; source links identify the
functions rather than implying deployed DLL equivalence.

| Evidence | Actual contract | Consequence |
| --- | --- | --- |
| [AgentHttp.cs](../../mod/StardewMCP/Agent/AgentHttp.cs), `Start`, `Handle` | Configured port; localhost and 127.0.0.1 prefixes, with localhost-only fallback. All responses receive wildcard ACAO. No application authentication or Origin/Host/peer authorization. | Loopback binding and CORS are not caller identity. Windows prefix/ACL/IPv6 behavior needs separate validation. |
| [overlay.html](../../mod/StardewMCP/assets/overlay.html), `API`, `fetchFeed`, `stripPoll`, `stripItem` | Unauthenticated feed polling every 400 ms. `player=p2` filters after downloading all seats. Strips show think, diary and journal `args.self`; names come from all-seat state. | A P2 strip is not a P2 privacy boundary; private self/diary text is currently broadcast-capable. Cosmetic text cleanup is not redaction. |
| Overlay `showDayCard`, `fetchDay` | Full overlay also requests previous `/api/day?n=N` for summaries. | Removing diary access requires a sanitized summary adapter, not simply breaking this request. Strip and full-overlay requirements differ. |
| [replay.html](../../mod/StardewMCP/assets/replay.html), `API`, `initLang`, `loadDays`, `show`, `render` | Fetches feed with huge `after` for language, names/model; days index; day entries plus diaries. Seat checkboxes filter locally. Diary panel uses legacy `day.diary` (P1), despite server returning `diaries`. | Huge `after` suppresses entries, not state/meta. Replay must not inherit a viewer grant; legacy P1 diary alias must not survive P2-only projection. |
| Both assets, `API` | `?api=` overrides base; otherwise same-origin only if `location.port === "8770"`, else `http://localhost:8770`. Fetches do not add auth headers or request cross-origin credentials. | At 18770 they ordinarily read 8770, including a different instance. File/static-host use depends on cross-origin access. |
| AgentHttp `Handle`, [AgentLog.cs](../../mod/StardewMCP/Agent/AgentLog.cs), `FeedAfter`, `ReadMemory` | State contains host resources, dialogue speaker/question metadata, paths and seats; feed embeds complete StateJson, arbitrary meta and entries. Day includes raw logs, P1 diary alias and every AI diary. Memory includes lessons/plan/notes/self/people. | Seat filtering alone cannot sanitize nested data, shared-event text or arbitrary tool arguments/results. Read-only does not mean public. |
| AgentHttp `RefreshState` | Heartbeat increments with game-thread snapshots (~4/s), even before world ready. HTTP can continue serving a stale snapshot when game thread blocks. | HTTP 200 is not game liveness. Heartbeat must retain freshness semantics without exposing the full snapshot. |
| AgentHttp `HandleMcp`, [McpDispatcher.cs](../../mod/StardewMCP/Agent/McpDispatcher.cs), `Dispatch` | MCP supports single/batch JSON-RPC, 202 notifications, predictable session label; traffic marks contact, affects freeze eligibility. Handler changes break bookkeeping and reply deadline before dispatch. | Read clients must never call MCP just for liveness; auth and validation must precede all contact/deadline/session effects. |
| [api.md](../api.md), [configuration.md](../configuration.md) | Advertised GET reads mostly have no method guard in actual handler; control has GET flags/POST actions. HttpPort defaults 8770; debug defaults off; provider ApiKey is plaintext configuration. | Explicit future GET/HEAD/POST/OPTIONS contracts are migration changes. Provider keys are not HTTP grants. Never copy them into browser assets. |
| [recording.md](../recording.md), [howto-record-day.md](../howto-record-day.md) | OBS URL browser strips at localhost:8770; WebSocket 4455 password via OBS_WS_PASSWORD; external automation uses state/control/meta/release/debug, LogDir checks and exports. How-to recommends 127.0.0.1 for native calls. | OBS WebSocket credentials are a separate authority. Scripts and their header/cookie/retry capabilities are U: `runner/` is absent. Documentation is not execution evidence. |

## Recommended boundary and grants (D)

Use a native authenticated P2 controller plus a separate browser-facing read
surface. Prefer a small local broker for OBS, serving its assets and sanitized
feed at the same origin. Keep private replay and operator sessions on a separate
origin/process boundary from the credential-free OBS surface. A port is routing,
not authorization; different ports also do not isolate cookies.

| Principal | Allowed contract | Denied by default |
| --- | --- | --- |
| P2 controller | Native `/mcp/p2` with explicit approved tool set; scoped P2 observation/briefing and own memory only if separately granted | `/mcp` alias, P1/P3/P4, aggregate reads, operator control, debug, arbitrary logs, watchdog/operator credentials |
| Operator | Separate authenticated control grant: POST control; explicit seat release, with `all` separately authorized; validated metadata keys. Narrow setup-status grant for ready/screens/wallet and path checks only when required | Implicit private-log access or P2 lease takeover; debug requires separate temporary grant and EnableDebugApi |
| Watchdog/recorder | GET minimal health projection; recorder can read frozen/day for recording decisions | MCP/contact, paths, diary, resources, controls, restart authority through HTTP |
| Viewer/OBS | GET approved seat's published display feed, display configuration and sanitized day summary | Raw state/feed/day/memory, private diary/self/people, control/meta writes, debug, other seats and private replay |
| Private replay reader | GET explicitly allowed seats/days, projected day index/logs/diaries, minimal replay display configuration | Mutations, arbitrary seats, unapproved P1 dialogue/data, memory unless independently granted |

These are independent scopes, not a role hierarchy. Operator may explicitly hold
several grants, but possession of control alone must not disclose diaries. Native
watchdog credentials must not share P2 ownership. Health reads must have no freeze,
contact, session-break or reply-deadline effects. One exclusive P2 owner lease per
save epoch must exclude built-in/external overlap, reject concurrent initialization,
and retire queued work on revoke/title/reload; recheck role/epoch/grant at execution.
Do not blindly retry ambiguous actions or treat a diary as proof of game effects.

### Server projection contract

Use additive, versioned adapters (illustrative names `/api/view/v1/*`,
`/api/health/v1`, `/api/replay/v1/*`), leaving raw legacy routes unavailable to
restricted grants. Never authorize a generic proxy pass-through to `/api/*`.

- Viewer configuration: UI language, approved display name/seat/color and public
  model label only. Feed: opaque stream epoch/cursor, freshness, day/time and
  allowlisted display events `{id, seat, kind, displayText}`. Default publication
  excludes thoughts, diary, journal/self, arguments and results; thoughts require
  explicit opt-in publication. Never automatically publish private journal text.
- Full-overlay summary: approved day/counts and optional consented resource totals;
  do not retrieve raw previous-day logs to compute it in the browser. Remove or
  replace unsupported private panels; show unavailable rather than fetching raw data.
- Health: instance/epoch identifiers without save identity, monotonic heartbeat,
  snapshot age, ready, frozen, paused, stopNow, eventUp/festival and optional
  recording day/time. State clearly when a snapshot is stale, including not-ready
  shape. An independent monotonic age clock must keep advancing if game ticks stop.
  Keep private LogDir/saveFolder checks in operator setup, ideally returning a
  comparison boolean rather than paths. Auth failure is not a hung-game signal.
- Replay: derive available days from authorized material, filter entries before
  serialization, return only authorized `diaries[seat]`; remove P1 `diary` alias for
  P2-only readers. Use a minimal config endpoint instead of raw feed initialization.
  Apply independent projections to memory, stats, relationships and briefing;
  textual briefing providers and shared/system events need explicit content policy.
- Intersect requested seats/fields with grant scope on the server; reject invalid
  or out-of-scope requests. No `all`/missing-seat fallback to host. Allowlist nested
  schemas and text sources, not just top-level key removal. Unknown fields stay
  private. P2-tagged text may mention Guy: seat tags do not imply publication consent.
- Filter before counts, caching, cursor generation and serialization. Scope cursors
  to epoch/grant and use projection-local sequencing so hidden activity is not
  inferred from sequence gaps. Bound response size, retention, polling and catch-up;
  cursor reset must not mix saves or replay an abandoned same-day timeline.
- Private responses: `Cache-Control: no-store`, no shared cache, no sensitive errors,
  logs or referrers; discard UI state on logout/revoke/epoch. Published viewer text
  is public to local viewers and cannot be made secret again after capture in OBS.

## Browser transport and origin rules (D)

Default API URLs must be relative to the page origin at **every** configured port.
Use one canonical loopback hostname consistently; localhost and 127.0.0.1 are
different origins, and 8770 and 18770 are different origins. Test both ports as
alternative configurations, not an assumed proxy pair. Never silently fall back
from 18770 to 8770. Existing `?api=` may temporarily select the same approved origin
without userinfo; reject external/arbitrary origins. Prefer removing that override
from protected pages. File URLs (`Origin: null`) and generic hosted static pages
are unsupported by default; serve them through the approved broker instead.

Validate actual peer and exact configured Host/authority before routing (including
IPv6 handling and fallback-prefix behavior). Bind loopback explicitly; reject
unexpected hosts/DNS-rebinding authorities. Browser sessions do not make arbitrary
local web pages trusted. Separate native paths, which deny any Origin, from browser
paths with exact-origin policy. Missing Origin on safe navigation/GET is normal;
require appropriate session or intentionally public viewer projection anyway.
Reject null/multiple/malformed/untrusted Origin on protected requests; do not infer
native identity merely because Origin is absent.

Same-origin reads need no CORS headers. Remove wildcard ACAO from protected routes.
If cross-origin use is approved later, allow only configured scheme/host/port,
return that exact ACAO plus `Vary: Origin`, allow credentials only when required,
and narrowly handle OPTIONS methods/headers without effects. Explicitly expose
MCP session headers only for an approved browser MCP design (not recommended here).
CORS only controls browser response access; it does not prevent submission. Reject
hostile/simple text/plain or form POSTs before effects, require JSON and a validated
session-bound anti-CSRF header on browser mutations. Check exact Origin for those
mutations, with an explicitly tested fallback for browsers omitting it. SameSite
cookies alone are insufficient, especially across same-site loopback ports.
Bound bodies/batches/queues/rates; denial must precede contact and other side effects.

## Viable provisioning options (D)

| Option | Benefit | Cost / disposition |
| --- | --- | --- |
| Integrated same-origin session | Browser automatically sends HttpOnly cookie; no bearer in JS or URL; fewer services | Requires trusted login/bootstrap, CSRF controls and tested local HTTPS. OBS cookie profile/login persistence U. Viable for private replay/operator browser. |
| Local read-only broker, recommended for OBS | Browser URL has no secret; broker holds only upstream viewer grant and serves sanitized assets/data same-origin | Extra service and independent review. Credential-free local projection is readable by other local clients and must be deliberately publishable. Must not expose private replay/operator sessions on this surface. Backend legacy listener still needs enforcement; proxy alone cannot secure a directly reachable unauthenticated backend. |
| Protected static export | No live backend credential; convenient approved replay artifact | Private data remains in artifact; OS ACLs, retention and consent required. No live feed; publish only separately reviewed redacted exports. |
| Direct bearer in browser JS or token URL | Easy fetch/OBS wiring | Reject: assets, history, logs, scene exports and browser tools leak secrets. Query/fragment, localStorage and embedded Authorization literals are not provisioning. |

Generate distinct random, revocable native grants through a local operator-owned
provisioner; bind scope, owner, expiry and intended service. Store under OS-protected
storage/ACLs and deliver through protected IPC or a restricted file handle. Native
clients obtain credentials through that channel and send Authorization headers;
never in command-line arguments, URLs, prompts, logs or scripts committed to Git.
The broker receives only its viewer grant, not P2/operator/provider/OBS passwords.
A local same-user malicious process remains outside strong isolation guarantees.

For private browser access, use an operator-approved local pairing flow: credential
entered through a protected native UI or HTTPS form POST, verified server-side,
then issue a short-lived opaque HttpOnly, SameSite=Strict, host-only Secure cookie
under tested local HTTPS. No secret is emitted into page JS, HTML or URLs. JS may
receive a non-authorizing anti-CSRF nonce; it never receives the authentication
credential. Do not assume Secure cookies work for every plain-HTTP loopback/OBS
version. Use distinct hostnames and separate session stores for private services;
cookies are not port-scoped, so Path/port differences alone are insufficient.
Disable query-based pairing and cross-origin redirects; redact auth headers and
pairing bodies. Revoke/rotate sessions server-side and test restart/expiry behavior.
Until OBS can be safely paired and persisted, use only the deliberately published
broker projection. Do not weaken private replay authentication to accommodate OBS.

## Proposed acceptance tests and release gates (not executed)

Use synthetic data/credentials and fake clocks first. These extend, rather than
claim coverage from, the current sequential FakeSecurityBoundary fixture.

| Gate | Test and required result | Evidence still required |
| --- | --- | --- |
| Ports / instance | Browser page at each of localhost and 127.0.0.1, ports 8770 and 18770; two synthetic servers with distinct markers. Each page reads only its own marker. Test root replay and explicit api override, no listener at 8770, stale cursor and reconnect. | Browser harness against projected adapters; Windows prefix fallback separately |
| Least privilege | Cross-product of five grants and every route/method, including aliases, trailing slashes, default/missing seats and debug enabled. Wrong/expired/revoked grant yields no private bytes or protected side effects. | Real AgentHttp integration, not fake-only policy |
| Field privacy | Canary P1 path/dialogue, other-seat memory, P2 self/diary, journal args, meta/event text and future unknown fields. Viewer payload, counts, errors and cursors disclose none; P2-only replay never returns P1 alias. | Serialized-response assertions, including nested/text content and summaries |
| Origin / CSRF | Hostile site simple POST/form, null/multiple Origin, forged Host, non-loopback peer, cross-port cookies, unapproved api override and denied preflight. No reads or effects; approved same-origin reads work. | Browser + actual HTTP parser/Windows tests; CORS response omission alone is insufficient |
| Provisioning | Pair, expire, revoke, rotate and restart; inspect synthetic URLs/scene export/history/assets/logs/JS/storage. No authentication secret appears. Cookies HttpOnly/host-only/Secure and correct scope. Broker cannot use viewer grant for commands. | Local HTTPS/browser validation; OBS pairing/profile behavior U |
| Health | Fake snapshot freezes while HTTP still responds; snapshot age rises and heartbeat stalls. Legitimate pause, stop, event/festival and not-ready do not trigger restart. 401/403 becomes auth error; 429 backs off; connection failure differs from game stall. | Actual watchdog source and authorized rehearsal U; this review authorizes no restart |
| P2 ownership | Second owner, native/browser mix, built-in overlap, revoked owner, full retired queue, title/load and same-day new epoch. No stale work/contact; fresh owner can initialize; no P1 dispatch. Preserve 202/JSON-RPC/result compatibility deliberately. | Concurrent runtime tests and exact Luna client source U |
| UI / OBS | Denied/expired/stale feed clears prior private text and shows a neutral unavailable state; no automatic controller login or raw-route fallback. Verify transparent 1920×360 strip, polling budget, reload/cache/shutdown settings. | Exact OBS/CEF version on Windows U; mock proves appearance only |
| Recording / private replay | Synthetic day rollover and frozen state preserve recorder semantics; replay config/day index/diaries obey grants. OBS WS password remains separate, never enters mod/browser config. | Exact external recorder/runner/exporter source and operator acceptance U |

No acceptance row above is reported passing. This documentation-only change was
checked with `git diff --check` and a one-file diff review; no runtime tests/build
were needed or run. Existing documents describe rehearsals but do not verify the
current OBS, Luna, runner or watchdog. Actual external sources must be inspected
privately before finalizing headers, sessions, retry and polling limits.

Implement in separately authorized stages: approve schemas/publication policy and
provisioning; add synthetic browser/real-adapter tests; add same-origin and read
adapters; then enforce grants across the legacy listener with explicit client
migration. Fail closed rather than exposing a hidden no-auth fallback. Full mod
build/deployment and any backed-up Test_ save rehearsal require separate operator
authorization. This report authorizes no live action, deployment or merge.
