# Sunny P2 controller ownership and reconnection review

2026-11-07. Documentation-only design review of target branch
`docs/sunny-controller-client-compatibility` at
`3a39b83bf37ac91ca1f1b88c55f91c1d70231ae9`.
Guy is human P1; Sunny is AI P2; Luna is the external model/controller.

## Evidence and recommendation

**S — verified source fact** means inspected repository code at the commit above,
not installed DLL behavior. **D — design proposal** means a contract for later
review and implementation. **U — unknown** means external behavior not established
by this review. Nothing below implements authentication or cancellation.

Context: [client compatibility inventory](HTTP_MCP_CLIENT_COMPATIBILITY.md),
[security review](HTTP_MCP_SECURITY_REVIEW.md), and
[test-only policy fixtures](SECURITY_POLICY_FIXTURES.md). The fixtures are a
sequential, synthetic, status-only policy model. They do not establish real HTTP
parsing, concurrency, mutation cancellation, clock behavior or interoperability.

**D:** Use one authenticated controller lease for the active save incarnation,
authorizing P2 only. Bind every admitted call to its owner, lease generation and
save epoch; invalidate admission and queued work together. Separate transport
reconnection, planned context breaks, clock participation and game action outcomes.
Require exact Luna client review before enforcing the new wire contract.

## Verified source map (S)

References below are repository-relative paths; line numbers refer to the baseline
commit. Agent files are under `mod/StardewMCP/Agent/`.

| Component and evidence | Current behavior and implication |
| --- | --- |
| `AgentHttp.cs:66–129`, `306–318` (`Start`, `Handle`, `HandleMcp`) | Loopback-named prefixes with localhost fallback; task per context; wildcard ACAO. No application credential or incoming session validation. Role/split routing is not caller authorization. DELETE returns 200 without teardown. Body is read in full; JSON parse precedes `SessionBreaks.Observe`, seat-wide deadline assignment, then dispatcher. Missing/invalid `reply_within` becomes zero; signed integers have no application range bound. |
| `McpDispatcher.cs:62–118` (`Handle`, `Dispatch`) | Arrays dispatch sequentially, allowing earlier calls before a later malformed element fails. `MarkContact` occurs before method/id/params checks. No initialize prerequisite or JSON-RPC version validation. Notifications return no object; all-notification requests get empty 202. Single answered messages receive predictable `stardew-{seat}` header; batches omit it. Initialize echoes supplied protocol version or fallback, rather than selecting from a supported-version set. |
| `McpSeat.cs:19–29` | Adapts calls to `Runtime.EnqueueCall(..., observation: true)` and formats text/isError/optional structured outcomes. It supplies no credential, epoch, owner or disconnect context. |
| `Players.cs:26–84`, `183–249` (`PlayerSlot`, `Resolve`, `TryCurrent`) | Logical slots/runtimes survive role resolution. Active means a tick within two seconds. Contact sets Connected, clears TimedOut and per-day freeze release. Logical binding fails closed on ambiguity; this solves screen identity, not controller identity. Resolve changes roles without invalidating calls. |
| `SessionBreaks.cs:36–100`, `165–186` | Static per-seat bookkeeping; initialize marks Fresh and sets break opt-in, later calls reset counters on game thread. It is context-window policy, not a security session. No save-epoch key or title reset appears here. |
| `AgentRuntime.cs:14–25`, `103–130`, `214–280` | PendingCall has tool/args/flags/time/completion/outcome, no ownership or epoch. Two ConcurrentQueues have no application capacity bound. AnswerQueued completes waiting agent calls in action queue only, leaving entries for later dequeue; it does not cancel observation queue or running coroutines. Lane start checks world need, session breaks and loop guard, without a controller/epoch/role guard. |
| `AgentRuntime.cs:283–397` | Coroutine stepping can span ticks/days; an early completed reply does not itself stop a running coroutine. Interrupt covers a running non-instant action, disposes its stack and reports success through normal Finish. Finish can consume mail, annotate breaks, update stats/logs and append current-world status. This is not a general security cancellation primitive. |
| `WorldClock.cs:46–102` | Thinking depends on AI role, contact, lack of action, activity in split screen, timeout and release. World readiness, configuration, night/wakeup gates and operator hold affect freezing. Contact does not directly reset the stopwatch. Discovery today can affect clock eligibility; it is not proof that every request freezes the world. |
| `ModEntry.cs:45–63`, `95–114`, `116–159` | Listener starts at GameLaunched and remains across title/load. Title stops built-in brains and resets selected helpers. Diagnostic sampler has lifecycle invalidation, but no controller epoch/queue invalidation is wired here. SaveLoaded occurs for farmhand screens too; host resolves roles and starts brains. Runtime ticks precede host clock refresh. |

**S:** No authenticated ownership mechanism is present in these inspected paths.
**Risk inference, not demonstrated gameplay:** retained runtime queues and absent
epoch checks can allow stale work to survive lifecycle transitions. This review
did not demonstrate cross-save execution or inspect deployed state.

## Ownership and save lifecycle contract (D)

Use a process-incarnation nonce plus a monotonic host-load generation as an opaque
save epoch. Do not use farm day, save folder, farmer name or transient ScreenId:
same-day reload is a new timeline. Do not expose a private save identifier.

Maintain a coordinator with `{epoch, readiness, principal, leaseGeneration,
leaseExpiry, controllerKind, authorizedSeat=p2}`. Credentials authenticate a
principal; an unpredictable session identifier binds that principal to a lease.
Neither identifier alone grants permission. Clients sharing the same credential
and session are indistinguishable; this does not prove OS process identity.
Provisioning/storage/rotation require a separate approved design; never put secrets
in URLs, served JavaScript, logs, reports or repository configuration.

One save-scoped owner is authorized for P2; P1, debug, global controls and private
viewer data need separate grants. Built-in brains must use the same coordinator
or be excluded while an external lease exists. `Brain=none` alone is not an
ownership lock. If generalized later, independently leased seats must not bypass
the one-controller-per-save policy by acquiring another seat.

| Transition | Required result |
| --- | --- |
| Title / loading / no authoritative P2 binding | Admission closed, no gameplay lease or clock participation. Discovery may report minimal availability without acquiring control. |
| Host SaveLoaded | Invalidate old epoch before helpers/brain startup; enter loading; resolve roles and logical bindings; open acquisition only once P1 human/P2 AI and P2 readiness are established. A farmhand SaveLoaded must not rotate the global epoch again. Use authoritative host/lifecycle identity, not a guessed P2 ScreenId. |
| Initialize by authorized principal in ready epoch | Atomically acquire vacant lease and issue session. Simultaneous contenders: exactly one winner, others conflict with no owner details. Initialize alone does not mark contact. |
| Second initialize, even same credential | Conflict while live lease exists; no implicit takeover or resetting session breaks. A lost initialize response can leave a lease: explicit authenticated recovery or bounded expiry is required. |
| ReturnedToTitle, new host load, shutdown | Close admission, rotate/invalidate generation, revoke leases, purge both queues and retire active work before it can step in a later world. Clear derived contact, deadlines, breaks and cached projections. |
| Revocation/expiry, P2 role loss, binding loss, built-in/external switch | Close old lease; cancel queued calls; invalidate execution authority and clock participation. Treat inactivity as unavailable, not evidence of a new save. Require explicit reacquisition after recovery. |
| Owner DELETE | Meaningful idempotent retirement for that authenticated session; no foreign deletion. Reject further admission immediately; report running-action disposition separately. |

Serialize acquisition, invalidation and queue admission under one coordinator;
thread-safe queues alone do not make the check-and-enqueue atomic. Queue entries
carry immutable admission context. Game-thread execution rechecks epoch,
principal/grant validity, lease generation, role, binding, readiness and cancellation
before tool factory invocation or any logging/mail/break/contact effects. Invalidate
before the next coroutine step as well. An old HTTP continuation must not update
new-epoch state or return a new-world footer.

## Validation before side effects (D)

1. Apply bounded connection/request budgets and verify peer, authority/Host,
   route, method, Origin policy and unambiguous headers/query. Native P2 commands
   require authentication; loopback and absent Origin are insufficient.
2. Bound UTF-8 bytes, read time, JSON depth, batch size and response size. Require
   approved JSON media types. Reject duplicate/ambiguous security inputs; validate
   `breaks` and bounded nonnegative `reply_within` explicitly.
3. Parse and validate complete envelopes: object/nonempty supported batch,
   `jsonrpc=2.0`, method string, allowed id types/range, method-specific params,
   supported protocol version, known tool and argument schema. Inventory legitimate
   notifications; reject mutation notifications without executing them. Never echo
   an arbitrary client protocol version as a compatibility promise.
4. Validate scope, current session/epoch and whole-batch capacity before admission.
   For a supported batch, preflight every member and reserve capacity atomically;
   prohibit initialize mixed with actions. No partial admission after a malformed
   later member. Runtime outcomes remain independent, not a transaction rollback.
5. Only accepted, owner-bound tool work may apply call settings and contact at
   execution. Discovery, ping, notifications, unknown tools and rejected requests
   must not clear release/timeout, alter deadlines or arm/reset session breaks.

Keep reply deadlines per call rather than seat-wide so parallel reads cannot
rewrite action behavior. A response deadline is not an action cancellation
promise. Apply validated break settings to the owner context only; preserve the
`Session break:` marker and intentional voluntary continuation. A context break
must not release control or reset epoch. Offer an explicit owner-authorized
context reset, or deliberate DELETE/new initialize after quiescence; select the
wire form only after inspecting client behavior.

Admission and tool dispatch should accept a validated request object rather than
raw JsonElement plus a mutable slot. Denial may consume security budgets but must
not touch gameplay, protected reads, metadata, contact, break or deadline state.
Use non-sensitive errors: missing/invalid credential 401, insufficient scope 403,
owner conflict 409, retired session 404, world unavailable 503, queue/rate bound
429, malformed JSON -32700 and invalid RPC -32600 (exact HTTP mapping to be
reviewed). Preserve method-not-found -32601 and existing tool result envelopes for
accepted calls. Do not disguise auth/session failure as an ordinary game result.

## Queue cancellation and action ambiguity (D)

Give each admitted operation an opaque operation ID and states `queued → started
→ terminal`, retaining bounded owner-scoped outcome metadata. JSON-RPC request id
is correlation, not a deduplication key. Optional idempotency keys must bind the
owner/epoch/tool/argument digest; reject conflicting reuse and never replay across
epochs. No exactly-once guarantee follows from a result cache.

On lease retirement, eagerly remove stale work from **both** queues and release
capacity immediately, completing each waiter exactly once as `cancelled_before_start`.
A stale full queue must not block a fresh owner. Check cancellation atomically
with queued-to-started transition. Observation/Instant is a scheduling label, not
proof of no effects: mail, journals, contact and other bookkeeping still need guards.

For started work, disconnect, DELETE, credential revocation or expiry prevents
further authorized steps; request game-thread cooperative termination and
per-tool cleanup. Do not manipulate game objects from HTTP threads. Audit coroutine
Dispose/finally behavior: cleanup can itself change state. Use a retirement path
that avoids ordinary Finish reading a replacement world or consuming new mail.
Block replacement-owner actions until old work is quiescent; if safe cleanup is
unknown, fail closed and report operator intervention required. Invalidation
releases queued capacity immediately, but cannot promise instant safe cleanup of
running tools.

Track `cancelled_before_start`, `interrupted_partial`, `completed`, and
`outcome_unknown` separately. Once effects begin, cancellation cannot undo them.
An HTTP disconnect may be detected late or never; it is not a reliable lease
expiry signal. Cancel queued work when detected, retain ambiguous started outcome,
and use bounded lease expiry as a backstop. A delivered tool acknowledgment is
not proof of observed effect or persisted save. Never retry a mutation merely
because a request timed out, lost its response or reconnected.

Clock participation should be derived from valid ownership plus deliberate
accepted agent activity, separate from discovery and from lease keepalive. Clear
only automation-owned pause state on retirement; preserve operator hold and
human/game pauses. Specify whether status counts as activity in migration tests;
proposal: accepted tool execution does, ping/discovery does not. Preserve night
and wakeup exclusions and test stopwatch semantics explicitly.

## Safe reconnect and compatibility gates (D, U)

**D:** A network reconnect with a valid credential/session in the same epoch may
resume transport without initialize, lease takeover, counter reset or action
replay. After stale-session response, discard session and pending decisions,
reinitialize with bounded backoff only when ready, then fetch fresh P2 status.
Reconcile operation outcomes before any new mutation. If the old epoch vanished,
mark its unverified effects as abandoned/unknown rather than importing them as
current memory. P2 menus require fresh prompt identity before any response.

**U:** Current external Luna/Python/PowerShell pilot source, retries, session-header
storage, initialize timing, DELETE usage, batches, notifications, media types,
break/deadline query usage and error handling are uninspected. Historical pilot
status success does not verify this migration or the installed DLL. No claim that
Luna reconnects safely, retries only reads, or understands these errors is justified.

**D:** Preserve tool names, text/isError/structuredContent, empty 202 notification
responses and supported JSON responses. Deliberately migrate predictable session
labels, direct tools/call and no-op DELETE; do not retain them as an auth bypass.
Do not infer streaming/SSE or supported-version interoperability from the current
JSON-only dispatcher. Decide batch support/version negotiation from actual client
source and recorded synthetic contract tests before enforcement.

Viewer/OBS, replay and watchdog need separate read scopes and server-side field
projection. The native-only fixture's denial of every Origin/GET cannot govern
those clients unchanged. Cover same-origin default/custom ports, localhost versus
127.0.0.1 and explicit cross-origin/file/OBS flows. No controller secret in `?api=`.
Keep watchdog auth errors distinct from a game hang; P2 ownership must not grant
raw P1 feed, diary, paths or global run control. No silent unauthenticated fallback.

## Proposed acceptance matrix and implementation gates (D)

| Test group | Required observable invariant |
| --- | --- |
| Concurrent acquisition/admission/invalidation | One owner; no enqueue after retirement linearization; recheck before first and subsequent steps; built-in brain cannot compete. |
| Title → same-day reload → different save; guest joins | Old session rejected; exactly one epoch per host load; no guest-induced rotation; stale queues/caches/contact cannot reach new world. |
| Full action and observation queues, then DELETE/revoke/expire/load | Both queues purged, waiters terminal once, new capacity available without draining old work; running cleanup gates replacement. |
| Malformed JSON/envelope/ids/queries/batch tail, missing/foreign auth | Zero gameplay/contact/deadline/break/metadata/protected-read effects; bounded resources and controlled errors. |
| Disconnect before start, during mutation, after completion | Certain queued cancellation versus partial/unknown/completed outcomes; no automatic mutation replay. Lost initialize response has bounded recovery. |
| Released/timed-out P2, discovery/keepalive/status, night, operator hold | Explicit activity policy; no discovery freeze; stopwatch and pause ownership tested separately. |
| Exact external client and viewer adapters | Supported versions, batches, header persistence, 202, DELETE, break continuation, custom ports and grant projections verified with synthetic transport. |

First approve contracts and inspect exact external client source privately without
secrets. Then extract/test coordinator and real HTTP/runtime adapters, including
concurrent tests; the existing fake alone is insufficient. Stage authentication,
lifecycle/cancellation and client migration in reviewed implementation PRs.
Windows HTTP.sys/SMAPI behavior and game effects require a later explicitly
authorized operator acceptance pass. This report authorizes none of those actions.

## Validation performed for this report

Read all eight requested components and the three context documents plus repository
instructions. Reviewed source only; no runtime tests/builds or live HTTP/MCP calls,
credential/save access, game launch, deployment or merge. Validation is limited to
document links, source references and a documentation-only diff. GitHub source and
Draft PR operations are the only remote repository activity.
