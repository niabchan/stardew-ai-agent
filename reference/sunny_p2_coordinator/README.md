# Sunny P2 coordinator — phase 1 fake-only concurrency acceptance

**Status: game-free test fixture, not an installed security or controller implementation.**

This phase adds only two C# files under `mod/StardewMCP.Tests/`:
- `FakeP2Coordinator.cs` — locked, synthetic P2 ownership/epoch/work-state model
- `P2CoordinatorOfflineTests.cs` — deterministic admission, concurrency and lifecycle tests

The fixture is deliberately **not linked into `StardewMCP` or `AgentHttp`**. It does not receive HTTP, parse authenticated tokens, supply an OS credential provider, touch games/saves, enqueue real `AgentRuntime` work, run an actual coroutine, manipulate freeze status or call OpenAI. None of its synthetic session IDs or host epochs are production-ready. It is a future-contract acceptance model for [the approved design](../../docs/sunny-agentic/SERVER_AUTH_SESSION_EPOCH_CONTRACT.md), not a substitute for the existing, differently scoped `FakeSecurityBoundary`.

## Modeled invariants

- One exclusive Sunny **P2** controller per host epoch, including concurrent initializations; no global restriction on other upstream AI seats
- Admission requires explicit human P1, AI P2 and external-brain-disabled role resolution; unknown role/brain state fails closed
- Independent C (control) and O (observe) grant checks; losing O cancels only P2 observation work while preserving C, whereas losing C retires the owner
- One synthetic host-load epoch for each distinct host transition; repeated callbacks sharing the same test-only host-transition key and delayed/guest SaveLoaded do not rotate it. Returning to title closes the gate
- Both pending action and pending observation lanes are bounded; retirement frees their capacity immediately, with queued work marked `cancelled_before_start`
- A started operation is separately fenced before every synthetic step. New owners cannot acquire until its quiescence has been confirmed; old-work partial and unknown outcomes remain distinguishable
- Prior uncertain effects create a **global pending-outcome barrier** for subsequent mutations, including after host reload. Observations can continue for reconciliation. Clearing the barrier is an explicit trusted test-harness operation, never a timeout or DELETE side effect
- A lost initialize response cannot lead to an automatic takeover; fake provisional expiry cannot bypass started work
- No read, admin denial or discovery path is treated as a gameplay contact, and no fake tool success establishes a persisted save effect

## Important unimplemented obligations and non-equivalences

This *fixture* uses `lock` to serialize its in-process state and a caller-supplied **fake monotonic timestamp**. It does **not** establish actual game-thread atomicity, cross-process claims, restart durability, random IDs, host-versus-guest source events, real role binding, valid consent, exact P1 safety projection, security headers, authentic session/lease recovery, detached real queues, safe coroutine disposal, bounded pinned execution budgets or verified no-op HTTP DELETE retirement. Those are separately gated in PR #28. The fake action `Step` merely increments a counter; it is not a real tool effect.

The toy `ReconcileFromOperator`/`Quiesce` methods are **trusted harness hooks**, **not** deployable endpoints or proof of real evidence-based recovery. A future real implementation must keep unresolved mutation provenance and never invent a safe outcome based solely on this fixture.

The synthetic owner may be re-acquired after timeout **only with no running work**. For the intentionally simplified long-running-action model, an action is pinned until `Finish`/`Quiesce`; real 1200-second bedtime execution and cleanup deadlines remain an implementation gate. This model does not validate any actual Windows/SMAPI request.

## Validation

From repository root:

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

CI must run both game-free suites for the new branch. No game runtime, Mod build, live API, secrets, operator files or private ZIP required. Passing fake tests proves only this local model is internally consistent, **not** that the current unauthenticated listener is safe or that the installed v0.3.11 controller can connect.

## Next integration gate

Independently review the fake state model, particularly race windows, queued/started distinction, O-scope withdrawal, synthetic expiry, unknown-effect barriers and role/epoch lifecycle. A future, **separate** PR must integrate an explicit C# coordinator into real `AgentHttp`, `McpDispatcher` and `AgentRuntime` with server-side preflight, both-queue/coroutine guards, token provisioner and real HTTP negative tests before any Windows/game/production rollout. Until then, leave `main` and installed Sunny untouched.

## Independent review for Issue #30 — 2026-11-07

Reviewed candidate `c9178f49ca13ca0823153be152f11259f05e1cbe` against
PR #28's server contract and the PR #19/#21/#22/#23/#24/#25/#26 design,
fixture and transport context. Findings below concern this **offline model**;
severity describes the consequence if its flawed expectations were carried into
an implementation. All corrections stay in the three files of this PR.

| Severity | Finding at reviewed candidate | Minimal correction and regression |
| --- | --- | --- |
| High | `FakeP2Coordinator.cs:216` `Step` and `:232` `Finish` ignored the global unresolved barrier. O withdrawal followed by unknown observation quiescence could create a barrier while an action was already running, yet that action could still mutate and report completion. | Recheck the barrier before action steps and completion. `Unresolved_barrier_blocks_already_running_mutation_steps_and_completion` preserves the earlier effect count and rejects both later paths. |
| High | `FakeP2Coordinator.cs:100` and `:162` reused identical epoch/session/generation tuples in a new coordinator instance. Structural record equality let a stale handle act as the new owner after identical setup. | Give each fixture an incarnation nonce in its synthetic epoch. `New_fixture_instance_rejects_old_session_even_with_identical_setup` checks stale enqueue and release denial without disturbing the fresh owner. This nonce is not a credential or production cryptographic identity. |
| High | `FakeP2Coordinator.cs:89` `HostLoaded` retained prior-epoch grants, allowing control reacquisition after role resolution without trusted reprovisioning, contrary to the approved epoch contract. | Clear epoch grants on true host load/title; retain them on duplicate current-transition callbacks. Add explicit trusted grant setup in reload tests and `True_reload_does_not_reuse_prior_epoch_grants`. |
| Medium | `FakeP2Coordinator.cs:98`/`:111` retained the last callback key across title, so reopening with that key silently left admission closed and no active epoch. | Reset title callback state and deduplicate only in a ready host lifecycle. `Title_then_reused_host_key_is_a_new_load_and_requires_fresh_grants` checks a new epoch, fresh grants and reacquisition. |
| Medium | `FakeP2Coordinator.cs:148`/`:172` accepted negative/regressing time; deadline overflow could occur after assigning an owner or inserting work. | Validate ticks in `[0, long.MaxValue - 180]` before mutation, maintain a nondecreasing harness clock, and treat omitted/zero time as the current tick. Invalid-clock regressions check no partial owner, queue or history; a regression test checks renewal cannot move backward. Fake ticks remain trusted harness inputs, never client-selected server time. |
| Medium | `FakeP2Coordinator.cs:232` did not provide the specified 180-tick idle period after long-running action completion; the existing bedtime test instead expected immediate takeover. | Make `Finish` clock-aware and renew the idle window. The bedtime test now asserts conflict until tick 429 and acquisition at 430 following completion at 250. Indefinite execution pin remains a documented fixture simplification. |

### Coverage and remaining gates

- The 64-way test asserts exactly one accepted owner and 63 conflicts; the
  same-principal assertion now uses the actual winning principal. Old owners
  cannot release a successor, and role/brain generation changes cancel queued
  work and require explicit acquisition. This models only P2; there are no other
  seats here to establish real upstream multi-seat compatibility.
- C-only/O-only denials and O withdrawal are independent from C retirement.
  C-only reads cannot destroy a C owner. No P1 safety projection, consent record,
  private data serialization or public OBS grant is modeled. These tests cannot
  establish consent or privacy enforcement.
- Four barrier-synchronized races cover revoke, reload, role change and release
  against dequeue/start or a subsequent synthetic nested step, in both lanes.
  They allow an effect before invalidation wins, then assert no further step,
  completion or count increase after it. Running work requires quiescence and
  unknown outcomes remain unresolved; repeated quiescence cannot clear them.
  These are repeated calls to the fake `Step`, not actual nested IEnumerator,
  Dispose/finally, delayed callbacks, logging, mail or world effects.
- Expiry with a running observation and full action/observation queues checks
  immediate capacity reclamation, no stale observation step, blocked acquisition
  before quiescence, then fresh capacity and stale-owner rejection. Running
  actions remain pinned through timeout in this model, while revoke/load/role/
  release still fence them. Real execution and cleanup budgets are unimplemented.
- Duplicate current host callback keys preserve ownership; guests are no-ops;
  a distinct same-save/day/time load rotates epoch and invalidates grants. Title
  and new-instance stale handles are now tested. Synthetic keys are trusted test
  labels, **not validated SMAPI identities**. A delayed key from an older transition
  may conservatively rotate again; real authoritative lifecycle deduplication is
  still an integration gate.
- `Quiesce`, `SetGrants` and `ReconcileFromOperator` are privileged harness calls.
  Foreign lease step/finish/release cannot retire live work, and reconciliation
  cannot remove running ownership. There is no client route to these hooks in
  this fixture, but also no authentication test for them: a future service must
  independently authorize recovery and bind evidence to operation/old epoch.
- Lost initialize, lost reply and unknown mutation remain separate concerns.
  The fixture does not simulate authenticated retirement responses or implement
  client recovery. PR #26's unknown-ownership and durable unknown-mutation fences
  remain unchanged: no bare DELETE, expiry, new object or epoch observation is
  permission for a client to retry or reinitialize automatically. Fixture history
  is in-memory and unbounded; it does not prove durable restart recovery or
  production resource bounds. Only pending lane capacity is bounded here.

### Actual validation and disposition

Before correction, the six new failing regression cases produced
`Failed: 6, Passed: 16, Skipped: 0, Total: 22` on the reviewed fixture.
After correction and the additional race tests, local execution with the existing
.NET SDK 8.0.419 (net6.0 test target) and pytest 9.2.0 produced:

```text
DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages /workspace/.dotnet/dotnet test mod/StardewMCP.Tests --no-restore
Passed!  - Failed: 0, Passed: 475, Skipped: 0, Total: 475

.venv/bin/python -m pytest -q mod/tests reference/sunny_gift/tests
286 passed, 1 xfailed in 10.68s
```

The existing Python expected failure is unchanged. The first unconfigured .NET
invocation could not write its home sentinel; using the pre-existing workspace
.NET home resolved that without installing anything. No full mod build was run.

**Disposition:** suitable only for consideration as a test/reference addition to
PR #22's design branch after these corrections. Keep PR #29 **Draft**. This is no
approval of production integration, live HTTP/game safety, rollout or merge.
Actual listener authorization, consent projection, game-thread linearization,
bounded execution/cleanup, authentic host events, durable recovery and the current
external client remain separate review gates. No production source, installed
mod, save, private operator material, live service, browser or OBS was used.
