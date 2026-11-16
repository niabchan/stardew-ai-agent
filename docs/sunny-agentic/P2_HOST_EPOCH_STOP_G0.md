# Sunny P2 Host epoch and STOP fence — inert C# implementation slice (G0)

**Status:** NEW dormant production-source class with game-free tests only. No installed
Mod, SMAPI, game, Controller, save, network or Luna/provider endpoint is used or
changed. It is deliberately **not invoked** from AgentHttp, McpDispatcher,
AgentRuntime, ModEntry or RunControl. Do **not** merge, deploy, enable or start a
new listener on the strength of this PR. Independent review is required.

## Verified existing code boundaries

- `AgentHttp.cs` currently creates the localhost/127.0.0.1 HttpListener,
  uses wildcard CORS, and dispatches `/mcp/p2` to McpDispatcher without a
  game credential or host-issued P2 owner. Its DELETE is an unverified 200.
- `McpDispatcher.cs` calls `seat.MarkContact()` before even method validation;
  its session ID is derived from the seat name and is not validated on requests.
  Discovery is therefore not necessarily side-effect free. This PR does NOT
  change that behavior.
- `AgentRuntime.cs` has distinct action and observation queues and coroutines.
  This PR does not attach an epoch/owner/stop check before enqueue/start/each
  game-thread step, does not drain queued work, interrupt a running coroutine,
  or prove side-effect and buffer retirement.
- `SunnyP2Preflight.cs` is an existing dormant request-shape preflight.
  It is **not** automatically atomic with owner acquisition or tool admission.
  The new host fence is not currently integrated with it.
- The separate Python `reference/sunny_transport/durable_pending.py` in
  Draft PR #72 provides an offline SQLite persisted singleton pending barrier,
  but its scope labels are caller assertions, not authenticated host evidence.

## What the new source actually does

`mod/StardewMCP/Agent/SunnyP2HostFence.cs` implements a locked,
**in-memory** host-specific fence. A *trusted C# host caller* (not an HTTP
route) supplies save-load and P1/P2 role transitions, and can issue a new
random, 32-byte-entropy P2 game bearer after a valid P1-human/P2-AI/external
brain setup. Only its SHA-256 digest is held. The host issues opaque instance,
load epoch and session IDs. It supports Control/Observe grant flags but
currently exposes no P1 read or observation route. Credential/token delivery
and trusted operator provisioning do **not** exist.

The host must explicitly arm **one** potential effectful dispatch; by default
STOP is latched. `TryQueueMutation` records a pending operation in memory;
`TryBeginOnGameThread` and `MayContinueOnGameThread` independently recheck
epoch, owner, role and STOP. An explicit `HostStop` or invalid role latches a
**terminal stop for that load epoch**, so `HostArmForOneOperation` cannot
silently undo the stop. Only a new trusted, valid host load may reset that
terminal flag; it does NOT clear any pending operation. Title, load, invalid
role or token rotation fence future steps. **Pending cannot be cleared** in this G0 class:
a positive tool acknowledgment, STOP or new save cannot authorize an action
retry, new owner, or next mutation while that operation is unresolved.

A fresh object resets these in-memory fields; all actual dispatch must use
the global durable pending barrier from PR #72 **and** a future host-owned
operation ledger before an action is sent. The API does not yet verify the
binding of tool, canonical args, queued work or actual runtime coroutine.
No real game result, save persistence, server-authenticated HTTP exchange,
credential channel, independent external STOP path, cancellation or quiescent
retirement has been established.

## Required integration boundary (future, NOT performed)

1. Independent secure host provisioning, verified loaded Mod/instance and
   authoritative epoch event at Host SaveLoaded/Title, including split-screen
   logical P2 role. Do not conflate farm day or save folder with epoch.
2. Strict HTTP preflight before **any** session-break/contact/freeze/read/queue
   effect; ensure native network peer, Host, Origin, scope, body bounds and
   credentials are actually checked. No P1 automation authorization.
3. Atomic authorization of owner, epoch, operation, tool and canonical args
   with a durable journal/commit **before** queue admission. Retain unresolved
   state across Controller/Mod/process restart and power loss uncertainty.
4. Guard **actual** AgentRuntime enqueue, start and EVERY coroutine effect step
   under the same host fence. Independently STOP/retire both queued and running
   tasks, their read/body buffers and game effects; prove quiescence before
   closing ownership. A Boolean in the fence is insufficient.
5. Authoritative outcome reconciliation: MCP `isError=false`, a read status,
   or the fact that a coroutine returned is not proof of an observed game
   effect or persisted save state. Preserve STAY and distinguish stand-only
   prerequisites from a completed selected activity.
6. Separate Luna/provider transport and secret from game credential. The
   extracted v0.3.10 AST call-site evidence in Issue #56 includes distinct
   `sunny_autonomy.GAME_URL` and `sunny_initiative.GAME_URL` origins;
   both need explicit transport injection after host security exists.
7. Independent Windows/SMAPI/HTTP.sys approval and disposable Test_ save pilot
   only after G1 gates are closed and the operator approves the exact run.

**Review/test:** `dotnet test mod/StardewMCP.Tests` compiles the *actual
new mod source file* through a direct csproj include and runs game-free
lifecycle/STOP regressions. It does not build or execute the game Mod. The
production Mod compiles source from its project by default, but the class
has no production call sites in this PR.

All 11 G1 gates remain OPEN. 50 historical live cases `not_run`.
`NO_GO_G1_START` / `NO_GO_LIVE_G2`; Draft/unmerged only.
