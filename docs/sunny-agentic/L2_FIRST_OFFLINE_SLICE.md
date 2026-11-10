# Sunny Issue #56 — L2 minimal gameplay loop, first offline vertical slice

**G0 / GAME-FREE ONLY — not a Luna/model test, not Stardew/SMAPI, not a security implementation, not G1/G2 approval.**

This intentionally small slice demonstrates a useful behavior boundary: **status → observe → choose (including STAY) → dispatch once → verify actual P2 change → choose again**. It is independent of [Issue #55 Kestrel research](https://github.com/niabchan/stardew-ai-agent/issues/55) and does not change the live Mod, controller, game, save, `main`, or current Draft PR #22 other than this proposed stacked Draft PR.

## Version / route / permission gap table (source audit, not current installation verification)

| Source and evidence | Real historical route / capability | Observed in source audit | Still missing before real Sunny play |
| --- | --- | --- | --- |
| [v0.3.11 private archive audit](PILOT_AUDIT_V0311.md) | External P10/P11/P12/P13 Python and PowerShell | Archive SHA-256 `662924ad5ca981b16425ca342bcabb3945a9867d10087ab969d3ea3c5a9521fb` was reviewed read-only | **Current installed controller and DLL hashes/versions UNKNOWN.** Archive equality does not prove installed version |
| [v0.3.11 transport audit](SUNNY_V0311_HTTP_MCP_TRANSPORT_AUDIT.md) | `POST /mcp/p2` `tools/call` | Legacy direct call; no game MCP bearer, initialize or stored security session; JSON result parsing | Separate game credential, true P2 owner+session, save epoch, failure/unknown outcome classification and compatibility |
| [v0.3.11 transport audit](SUNNY_V0311_HTTP_MCP_TRANSPORT_AUDIT.md) | `GET /api/state`, `GET /api/feed`, some `GET /api/day` | Unauthenticated aggregate reads in supplied archive; a client-side filter cannot enforce privacy | Least-privilege authenticated P2 observations, explicit consent-aware **minimal P1 safety** projection; no raw P1 diary/chat or full feed to a viewer |
| [v0.3.11 transport audit](SUNNY_V0311_HTTP_MCP_TRANSPORT_AUDIT.md) | Game URL | Historical main P10–P13 controller uses hardcoded `127.0.0.1:8770`; custom isolated game port had used `18770` | Explicit validated loopback URL, wrong-instance rejection and no insecure fallback |
| [v0.3.11 archive audit](PILOT_AUDIT_V0311.md) | P11 Luna chooser | Offered `stay/move/chair/TV/speak` in audited snapshot; L2 fireplace not offered | Verify **current** chooser schema and affordances before claiming Luna could select fireplace; [Issue #57](https://github.com/niabchan/stardew-ai-agent/issues/57) tracks capability catalog |
| [Client compatibility inventory](HTTP_MCP_CLIENT_COMPATIBILITY.md) | Operator `/api/control`, browser OBS overlay/replay | Distinct native/operator/browser behavior; legacy viewers can read unscoped data | P1 stays human-controlled; separate read-only viewer and operator grants; never let P2 dispatch to P1 |
| [Existing transport contract](../../reference/sunny_transport/README.md) and Phase 2 G0 docs | Future P2 transport | Offline/fake-only policy and lease/epoch proposals exist | Current Windows HTTP boundary, independent stop, real credentials, server-verified task/buffer retirement, Luna client migration, G2 gameplay checks |

**Do not interpret the gaps above as fixed in the live server.** The repo currently has a dormant preflight seam, models and docs, not production enforcement.

## What this offline slice does

The minimal **synthetic** fake world has P1 role = human and P2 role = AI, an illustrative owner, a load epoch, a revision, Sunny's tile and two candidate intentions: `STAY`, `MOVE_TO_CHAIR`. Its `observe()` exposes **no raw P1 private data**. A **scripted test chooser** stands in for Luna; there is **no provider call** or inference, no real MCP, no actual auth and no actual map/pathing.

**Review correction (G0-only):** The revised fake loop reserves a pending attempt **before dispatch** in the in-memory `FakeGame`. A replacement `OfflineController` using that *same live fake world object* sees the unresolved marker and cannot blindly re-dispatch; an unknown/exception/ACK-without-evidence keeps the marker. It also pins the expected synthetic epoch at controller construction, rather than silently adopting an unseen reload. Only an explicitly fake pre-effect denial or verified synthetic completion clears the marker. **This is not durable across a real process crash or new `FakeGame` instance**. Real recovery requires a separately reviewed persistent per-operation journal, server-verified owner/epoch and reconciliation; there is no such production implementation here.

The post-action `observe()` reads from **the same in-memory synthetic world that applied the action**, not an independent Stardew/SMAPI state source. `VERIFIED_FAKE` asserts only that the toy model's expected tile changed, **not an independently authenticated effect, actual chair seating, or causation in a live save**. There is no real concurrency, credential, trusted raw transport or game clock in this example.

Two consecutive decisions in the normal case:

1. `status/observe`: P2 is ready, at (3,11); MOVE_TO_CHAIR is offered.
2. `choose`: deterministic fake chooser requests MOVE_TO_CHAIR. Fake pinned epoch/owner/role/revision checks and the shared in-memory pre-dispatch marker precede one P2 effect.
3. `verify`: *subsequent same-fake-world post-observation* shows P2 at (7,4), so verdict = `VERIFIED_FAKE` (not actual game success).
4. Next `status/observe`: the state has changed. Chooser independently picks `STAY`; no second dispatch.

Ambiguous case: a fake action mutates the P2 position but loses its response. The controller returns `UNKNOWN`, **latches safe halt** and never reissues the action. An ACK without observable state change also remains `UNKNOWN`; API acknowledgement alone is not game success. Stale epoch/revision, foreign owner or wrong seat role are rejected before the fake effect; missing post-observation, exception, or an ambiguous result retains the pending marker. A `MARRY_NPC` or `FIREPLACE_TOGGLE` request is not offered in this L2 slice and cannot be dispatched.

Implementation: [test-only fake world and controller](../../reference/sunny_gameplay_slice.py), [bounded pytest scenarios](../../mod/tests/test_sunny_gameplay_slice.py). They deliberately do **not** map to the real `AgentHttp`, `McpDispatcher` or external Python pilot.

## Acceptance and strict verdict

| Check | Expected evidence | Scope |
| --- | --- | --- |
| Two consecutive choices including STAY | `VERIFIED_FAKE → STAY`, two scripted decisions, one P2 fake dispatch | Game-free test only |
| Unknown mutation result | `UNKNOWN → BLOCKED_UNRESOLVED`, including new controller object using same fake world, no second dispatch | Game-free test only |
| Rejection before effects | Wrong P1/P2 role, owner, pinned same-save load epoch, changed revision, unprepared or unoffered choice | Game-free test only |
| Private data isolation in fake observation | P1 raw diary/chat absent from fake observation fields | Fake schema only, not a real viewer test |
| Current installed controller / Windows / Luna / SMAPI | **UNKNOWN / NOT TESTED** | Must remain blocked |

Offline command from repository root: `python -m pytest -q mod/tests/test_sunny_gameplay_slice.py`. Pass is **only** a synthetic contract pass. Do not mark Issue #56 or G1/G2 as fully complete before independent review, actual installed-version inventory, client migration, real all-route auth/privacy/epoch implementation and later separately authorized isolated game acceptance.

## Remaining operator-local version inventory (not performed)

GitHub can establish the pinned v0.3.11 archive's historical source properties, **but cannot read which Mod DLL, launcher or Python scripts are currently installed on the user's Windows computer**. A future explicitly operator-run **read-only local** check should obtain only version/hash metadata for the installed `StardewMCP.dll`, current Sunny P10/P11/P12/P13 PowerShell launcher and relevant Python modules; compare those to the reviewed archive or mark them as separately modified. Determine the configured game URL and whether the current chooser actually offers fireplace, **without starting a process, sending an HTTP request, reading credentials or committing local paths/saves/logs to GitHub**. Hash matching alone does not prove running behavior.

Do not claim `CURRENT_VERSION_VERIFIED` until these read-only machine-local details have actually been reviewed. Do not ask for or expose full private game logs, keys or dialogue. This information can inform a later migration plan; it is not a prerequisite for the present **toy-only** unit tests.

## What is deliberately NOT part of the first vertical slice

Actual Luna selection, fireplace discovery, sitting animation, night routine, travel outside, gifts, inventory transfers, payments, NPC romance/marriage, OBS and diary are not validated here. Fireplace and wider game capabilities belong to [Issue #57](https://github.com/niabchan/stardew-ai-agent/issues/57); bedtime is the *next possible L3 game behavior*, only after this small L2 contract is independently reviewed.

**No port, socket, OS changes, game launch, saved state, installed DLL, secret, production runtime modification, external API call or `main` merge is authorized.** All 11 G1 entry prerequisites stay OPEN, original 50 cases stay `not_run`; `NO_GO_G1_START`, `NO_GO_LIVE_G2`.
