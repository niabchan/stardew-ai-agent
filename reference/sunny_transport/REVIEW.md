# Independent offline transport review

Review date: 2026-11-07. Decision: suitable for further **test-only contract
review**, not integration, deployment or live safety acceptance.

## Provenance and scope

Input: `Sunny_P2_Offline_Transport_Contract_v0.1.zip`, beginning with
`CODEX_REVIEW_TASK.md`. Its task instructions were adopted only within the user's
request; other supplied prose was checked as evidence, not treated as authority.
The private v0.3.11 pilot ZIP was not supplied, accessed or independently tested.
The 443-test/54-subtest historical result is operator-reported and is not this
adapter's acceptance result.

Public Git refs were fetched read-only from `niabchan/stardew-ai-agent`.
Implementation base: PR #22 head `d4b6c4f0b61abfca60f4de0dd79a4adb2923d3ed`.
Some review refs contain earlier PR merges; comparisons use their actual fetched
heads, not assumptions about PR number order.

| PR / fetched head | Evidence reviewed | Contract consequence |
| --- | --- | --- |
| #19 / `8bf9178` | `HTTP_MCP_SECURITY_BOUNDARY.md`, `HTTP_MCP_SECURITY_REVIEW.md`; current AgentHttp and McpDispatcher source | No production auth/owner/epoch protection; discovery and status may affect contact. Client checks cannot repair the listener. |
| #21 / `bf2c548` | `SECURITY_POLICY_FIXTURES.md`, `FakeSecurityBoundary.cs` | Exclusive ownership, denial before effects and retired queue purging are synthetic server proposals. Its status-only fake does not implement this adapter's HTTP/JSON contract or safety route. |
| #22 / `d4b6c4f` | `HTTP_MCP_CLIENT_COMPATIBILITY.md` | Migration must preserve result shapes and explicit port choice, with separate native/controller and browser/viewer scopes. |
| #23 / `b0eb4b6` | `P2_CONTROLLER_LIFECYCLE_REVIEW.md` | Lost initialization requires recovery; revoke/reload must fence queued and running work. HTTP timeout is not cancellation. |
| #24 / `e216b18` | `BROWSER_OBS_READONLY_ACCESS_DESIGN.md` | Server filtering and human consent precede bytes; controller projection is separate from OBS/public replay. |
| #25 / `8f6ba07` | `SUNNY_V0311_HTTP_MCP_TRANSPORT_AUDIT.md` from fetched ref | Secondary evidence only for the private snapshot: direct tools/call, fixed 8770, no owner/auth/epoch, long bedtime and pre-dispatch markers. No installed-version claim. |

Production cross-checks at the base: `AgentHttp.cs:127` returns MCP DELETE 200
without owner teardown; `AgentHttp.cs:312` observes SessionBreaks before dispatch;
`McpDispatcher.cs:76` emits predictable `stardew-` session labels;
`McpDispatcher.cs:83` calls MarkContact before method validation. No production
file was modified.

## Findings and changes

1. **High: lost lease replies allowed blind reinitialization.** Reserve handshake
   state before exchange, classify lost replies as ownership-unknown, and fence
   repeated initialization. Lost DELETE also retains this fence. Invalidating
   local state is not proof of server retirement. Server recovery/expiry remains
   unspecified; no takeover or recovery shortcut was added.
2. **High: caller-controlled read classification bypassed dispatch protection.**
   Only empty-argument status is accepted as read; all other tool names require
   the guarded mutation path. This does not prove status is passive on the real
   server or implement per-tool game safety.
3. **High: mutation failures could lose uncertainty.** Every unproven HTTP denial,
   malformed return, transport exception, epoch mismatch, duplicate JSON member
   and tool-error result retains the mutation fence. There are no retries.
   Credential denial additionally disables future requests with that credential.
4. **High: claim persistence/reentrancy gaps.** Reserve locally before journal
   callbacks; commit-then-raise cannot send or permit a later action. Reject
   simultaneous/reentrant operations. Across processes and restarts, a genuinely
   durable global pending-outcome barrier remains the caller's obligation.
5. **High: P1 projection allowed incomplete or truthy private facts.** Add explicit
   proposal-only consent, strict booleans, required facts and minimal denial.
   This parser rejects unexpected bytes after receipt; only server-side filtering
   can enforce privacy. It does not implement consent provisioning or menu identity.
6. **Medium: protocol/endpoint ambiguity.** Validate token/header characters,
   case-insensitive unique headers, integer RPC correlation, duplicate/nonfinite
   JSON and bounded timeouts. Forward the proposed epoch precondition. Keep one
   explicit loopback origin, with no redirect/network implementation or fallback.

## Validation

In a local virtual environment with pytest installed, from the respective roots:

- Unmodified input ZIP: `python -m pytest -q mod/tests/test_sunny_transport_adapter.py`
  — **33 passed**.
- Reviewed prototype: same command — **84 passed**.
- Repository Python CI: `python -m pytest -q -rx mod/tests reference/sunny_gift/tests`
  — **254 passed, 1 xfailed, 0 skipped**.
- Existing expected failure:
  `test_action_tools_have_a_reason_parameter[close_menu]`; close_menu lacks the
  viewer-caption reason parameter. No unrelated fix was made.
- `dotnet test mod/StardewMCP.Tests` — **not run successfully**: `dotnet: command
  not found` (exit 127). Game-free C# CI remains unverified in this environment.
- No production mod build, game action, real MCP request, model/provider request,
  installed DLL, save, private script, key or operator-log access occurred.

The 1200-second wait is checked as a request value using immediate fake responses;
no real 20-minute wait or late game completion was exercised. Tests cannot prove
listener rejection before side effects, race-free server lease ownership, genuine
durability, cancellation, Windows networking, consent enforcement or live safety.

## Handoff

Changes contain only `reference/sunny_transport/` and
`mod/tests/test_sunny_transport_adapter.py`. Do not integrate or advertise this as
a working MCP client. Before integration: finalize server errors and authenticated
lease recovery; implement durable recovery barriers and instance identity; enforce
owner/epoch/role/consent before dispatch and coroutine steps; negotiate the complete
MCP lifecycle; then add real adapter and concurrent server tests. A supported
Windows build and disposable Test_ save acceptance need separate operator approval.

The original handoff prepared a local review branch and patch against PR #22.
That historical handoff preceded Draft PR #26; the present follow-up is authorized
to push only that PR branch and keep it Draft. Never merge automatically.

## PR #26 DELETE blocker follow-up (2026-11-07)

Adopted the review's conservative alternative: every attempted DELETE retains the
ownership fence. Successful HTTP exchange now raises `OwnershipOutcomeUnknown`
instead of authorizing another initialize. No acknowledgment schema or verifier
is invented; even a matching owner/session/epoch and quiescent-looking body is
unverified. HTTP errors, malformed callbacks and lost responses likewise cannot
clear the fence. Local invalidation cannot establish server retirement.

Added a matrix of 32 regressions covering bare 200/202/204, epoch-only, malformed,
mismatched and unknown/cleanup-required dispositions, plausible but unverified
quiescent acknowledgments, HTTP failure and lost DELETE replies, each with and
without an unresolved mutation. They check no second handshake, action or DELETE,
no extra dispatch claim, and preservation of mutation uncertainty and claims.
Existing durable-claim and mutation-uncertainty tests remain in place.

Follow-up validation:
- Offline adapter: **116 passed**.
- Repository Python CI command: **286 passed, 1 existing xfailed** (`close_menu` reason parameter).
- Game-free C# tests unavailable: `dotnet` is not installed in this runner.

No production code, network backend or server retirement implementation changed.
Recovery still requires an independently reviewed server-side protocol; neither
fake tests nor HTTP success establish legacy server safety.
