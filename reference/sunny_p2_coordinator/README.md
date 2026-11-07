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
- One synthetic host-load epoch for each host reload; delayed/guest SaveLoaded never rotates it. Returning to title closes the gate
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
