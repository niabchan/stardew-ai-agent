# Sunny P2 phase 2B — fake atomic preflight-to-admission intake

**GAME-FREE TEST HARNESS ONLY. No live HTTP listener, credentials, SMAPI, controller migration or server-side deployment.**

The previous [preflight seam](../sunny_p2_preflight/README.md) (PR #31) returns a **snapshot decision**. The prior [coordinator fixture](../sunny_p2_coordinator/README.md) (PR #29) models exclusive P2 ownership, host epochs, queues and synthetic steps. Phase 2B exercises them together under a shared **in-memory test lock** to demonstrate their proposed *ordering* and what must be rechecked before any work enters a queue.

## Files

- `mod/StardewMCP.Tests/FakeP2AtomicIntake.cs`: test-only `FakeP2AtomicIntake` implementing the already-dormant `ISunnyP2PolicyAuthority` interface with synthetic credentials and the existing `FakeP2Coordinator`.
- `mod/StardewMCP.Tests/P2AtomicIntakeTests.cs`: fake request integration and race/denial tests.
- `mod/StardewMCP.Tests/FakeP2Coordinator.cs`: adds a non-renewing `ValidateLease` test helper to check expiry without renewing on discovery.
- This README records the tested contract and missing actual integration. No production `AgentHttp`, `McpDispatcher`, `AgentRuntime`, `ModEntry`, browser or Python code is edited.

## Admission contract represented

1. The caller sends a synthetic `SunnyP2Request` with exactly one Host, an explicitly configured loopback port, native bearer, JSON-RPC 2.0 and headers. `SunnyP2Preflight.Evaluate` validates request shape and a **synthetic** authority. Unsafe route/Origin/host/role/token/session/epoch/tool/JSON returns denial **before** enqueue, contact or any game side effect.
2. **One fixture lock** surrounds preflight and reservation; the coordinator additionally holds its own lock for lease/queue decisions. Every accepted initialize is committed by `FakeP2Coordinator.Acquire`; every approved status/action must pass `FakeP2Coordinator.Enqueue` with current epoch, role, C/O grants, capacity and unresolved-effect checks.
3. A **privileged test-only** callback `betweenPhases` forces a reload, title transition, scope revocation or role change *after* a successful preflight snapshot but *before* final commit. The final checks must deny stale requests, reclaim old queue capacity and preserve unknown-outcome fences.
4. Read-only discovery/notification requires a known current owner and validates that the synthetic lease has not expired, but **must not renew** it or touch simulated gameplay.
5. Real action effects only occur later in the separate **synthetic** `Start` / `Step` sequence. A successful `IntakeReply` is **not** a tool result, durable operation record, persisted save proof or game authorization token.
6. Duplicate attempts are rejected using a `trustedAttemptId` supplied by this **test harness**, **not** the MCP request id, an untrusted HTTP header, or a durable real-world journal. Server-generated operation IDs, crash consistency and dispatch claims remain future work.
7. Fake DELETE returns `RetirementUnverified` regardless of whether the coordinator is locally quiescent. It is **not** a trustworthy HTTP 200 proof and does not loosen PR #26's client-side permanent `OwnershipOutcomeUnknown` fence. A human/test-only reconciliation is required to release unknown effects.

## What remains deliberately unimplemented

The shared lock protects only calls **made through this fake harness**, not an actual network listener. There is no real cryptographic verifier, OS credential provisioning, production authenticated principal/grant generation, host event source, actual game-thread linearization, resource-specific authorization, non-P2 route protection, bounded body streaming, true queue/coroutine cancellation, cleanup proof, operator reconciliation evidence, durable journal, private P1 consent, safe gift menu identity, OBS viewer projection or end-to-end Luna v0.3.11 migration.

The fixture's `ValidateMutationArguments` only understands a tightly bounded synthetic `say` action, not the game's `ToolContract`. Fake monotonic time and token provisioning are trusted inputs. No passing test establishes safe production HTTP admission or prevention of side effects if a future caller bypasses the coordinator. The real implementation must share one authoritative lifecycle/credential/role/queue gate, not rely on independent stale snapshots. If the future code cannot guarantee a single linearization point, fail closed and do not dispatch.

Also: the preflight seam intentionally rejects `?reply_within`, `?breaks`, some media variants and transfer encodings; the real P12 bedtime client can wait up to **1200 seconds**. A migration-compatible server/client contract and safe retirement/quiescence design are required before wiring anything to the current `AgentHttp`.

## Game-free checks

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

Run the above in PR CI; report actual output, not assumptions. New tests cover 64 concurrent initializations, 64 concurrent admissions with bounded queue, duplicate trusted claim, Host/Origin/P1/JSON denial, post-preflight role/revocation/reload/epoch changes, independent C/O grants, guest/duplicate host events, synthetic expiry, in-flight action retirement, historical unknown-effect barrier, and racing revoke/enqueue.

**Review gate:** independent Codex review of the exact PR diff before considering merge into PR #22's **Draft design branch only**. `main`, installed Stardew/Sunny, current Python controller, and live services must not be changed or exercised. Actual server-side admission/response and Windows/SMAPI tests remain separate work.


## Issue #34 independent review corrections

Reviewed candidate `6eea3d68284c57e0414771176c3bf70b3c0ece48` against the accepted
[server contract](../../docs/sunny-agentic/SERVER_AUTH_SESSION_EPOCH_CONTRACT.md),
coordinator, dormant preflight and offline Python adapter. Findings below refer to
candidate lines in `mod/StardewMCP.Tests/FakeP2AtomicIntake.cs`:

- **High (harness authority): lines 171–185.** Initialize re-resolved the token but
  did not bind the positive snapshot to the same credential generation, host epoch
  or role generation. Rebinding to another principal, same-principal replacement,
  scope remove/restore, role remove/restore, or reload plus reprovision could all
  acquire from an obsolete snapshot. Admission now compares the exact immutable
  credential object plus epoch and role generation before any commit. Replacing
  an equal-valued object still invalidates that request.
- **High (harness work fencing): lines 80–82.** Re-provisioning an existing token
  for another principal left the old principal's coordinator grants and work live.
  Replacement now revokes the former principal, purges queued work and fences
  started work; quiescence and historical unknown effects remain separate gates.
- **Medium (fixture consistency): lines 90–101.** Token-local grant records could
  disagree with the coordinator's principal-scoped grants across aliases. The
  coordinator still denied unauthorized queue admissions, but preflight could use
  stale scope claims and a revoked alias could remain recognized. This fixture
  now explicitly uses principal-wide scope updates and whole-principal revocation
  (all aliases), including on token replacement. This is conservative synthetic
  policy, not a specification of production multi-credential rotation.

Seven targeted new cases failed against the original intake source (five stale
initialize cases, rebinding work fencing and alias revocation); all pass after
correction. Additional regressions cover same-principal 64-way initialize, active
lease non-renewal and 1200-tick running-action pinning, old claims across role/epoch
changes, queue purging with unknown partial effects, denied preflight never reaching
the interleaving callback, and concurrent admission against revoke/load/title/role/
credential replacement. Integer reply statuses remain fixture assertions only.

Lock review: the coordinator is private and never escapes the intake. Every
intake lifecycle, grant, admission, start and step method takes the intake gate
before entering coordinator methods; the coordinator does not call back into the
intake. The privileged interleaving callback runs reentrantly under that gate.
Direct coordinator tests exercise a separate fixture. Exposing this coordinator,
adding reverse lock acquisition, or using a separately mutable credential store
would invalidate this argument. The future runtime needs one authoritative commit
boundary and immutable request/authentication inputs; this harness is no proof of
such an implementation.

`ValidateLease` advances synthetic time and can retire an expired idle owner; it
is not pure, does not renew either 60-tick provisional or 180-tick active expiry,
and does not retire a running action at the idle deadline. No real timer, credential
TTL, 1200-second HTTP response, lost-response journal or authenticated DELETE proof
is modeled. Status is the sole observation tool (C+O); only bounded synthetic
`say` is admitted as a mutation. No private-state payload, diary, contact counter,
logging or OBS projection exists here, so zero fake steps cannot prove absence of
real contact/log/disclosure effects. Raw HTTP parsing/framing and real credential
expiry remain adapter/runtime work. Current installed Luna compatibility remains
uninspected.

After these corrections this harness is suitable only for review into PR #22's
still-Draft design branch, with PR #33 kept Draft. Real authenticated atomic server
admission, durable reconciliation, platform tests and deployment remain unimplemented.

Local review validation (2026-11-08):

- `DOTNET_ROOT=/workspace/.dotnet DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages /workspace/.dotnet/dotnet test mod/StardewMCP.Tests --no-restore`:
  **593 passed, 0 failed, 0 skipped**, including 42 atomic-intake cases (19 added).
- `work/venv/bin/python -m pytest -q mod/tests reference/sunny_gift/tests`:
  **286 passed, 1 existing xfailed**, no failures.
- `git diff --check`: passed. Only the four authorized paths changed.
- The SDK was already installed outside PATH; pytest was installed into a local
  scratch virtual environment. Initial bare `dotnet` and system-Python pytest
  commands were unavailable; the commands above are the completed runs.
- Seven targeted regression cases against the original intake: **7 failed** as
  expected; restored corrected source and reran the complete C# suite successfully.
  No live HTTP/MCP, Stardew launch, production build, deployment or merge executed.
