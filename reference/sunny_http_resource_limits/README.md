# Sunny Phase 2G — Transport Resource Limits & Abort Contract (G0 offline design)

**PROPOSAL ONLY · NOT RATIFIED · NO WINDOWS TEST OR LISTENER · NOT AUTHORIZATION TO START G1**

This phase proposes numerical transport limits and an abort/cleanup state contract for a **future approved disposable Windows HTTP testbed**. It has not started HTTP.sys, used `HttpListener`, built the mod, launched Stardew or touched the installed Luna pilot. An approval of the **documents/tests** is **not approval of the numbers** or permission to test a port.

The authoritative preceding [Phase 2F 50-case plan](../../docs/sunny-agentic/WINDOWS_HTTP_TRANSPORT_ACCEPTANCE.md) remains G0; [cases.json](../sunny_windows_http_acceptance/cases.json) still has **50 `not_run` cases (37 G1 transport / 13 G2 runtime; 17 blockers)**.

## Files

- [proposed_limits.json](proposed_limits.json): named, machine-checkable **unratified** numeric candidates and explicit unresolved approval inputs.
- [offline_ledger.py](offline_ledger.py): pure Python **synthetic state machine** for reservation, first-byte/handler/body deadlines, retained in-flight capacity after timeout, abort claims, observed completion and safe buffer ownership prior to release.
- [test_sunny_http_resource_limits.py](../../mod/tests/test_sunny_http_resource_limits.py): deterministic offline regressions; no time.sleep, OS calls, sockets, threads, subprocesses, real credentials, runtime output or game.
- This README: exact model/non-model boundary, proposed numerical values, fail/stop conditions, Windows G1 and game G2 requirements.

## Numerical candidate profile — not a recommendation to deploy

| Limit | Proposed initial value | Source / review question |
| --- | ---: | --- |
| Request body cap | **16 KiB** | Carries forward prior proposed server limit |
| Response cap | **256 KiB** | Carries forward prior proposed server limit; actual output/streaming bounded separately |
| Body-reading budget | **5,000 ms** | Prior proposed body limit; still subordinate to whole-ingress deadline |
| **Total ingress from trusted first byte/connection** | **8,000 ms** | **New candidate**, includes pre-handler slow headers, HTTP.sys queue wait and body; cannot start at `GetContextAsync` |
| Header first-byte→complete | **2,000 ms** | **New candidate**; the fake can observe late arrival at handler but **cannot enforce a pre-handler OS clock** |
| Abort + completion + cleanup grace | **2,000 ms** | **New candidate**, not permission to release a stuck read after two seconds |
| Global in-flight requests, **including timed-out but undrained** | **32** | Prior proposed concurrent limit; capacity must not be reused on HTTP 408 alone |
| General request capacity | **28** | **New candidate**: leave 4 reserved for separate authenticated recovery/health work, not an authorization shortcut |
| Recovery/health reserved capacity | **4** | **New candidate** and subject to separate identity/route authorization |
| Per authenticated principal in-flight | **8** | Prior proposed limit; **does not apply to pre-auth connections** until verified |
| Unresolved transport aborts before stop-new-admission | **4** | **New candidate**; fail closed, do not open new work while cleanup ownership uncertain |
| Synthetic backlog limit | **16** | **New candidate**, impossible to enforce on HTTP.sys pre-handler without separately approved platform evidence |

The prior server contract also proposes **10 requests/s burst 20 per principal**, and P2 pending queue limits. Those are **NOT implemented by this fixture**; they remain additional runtime gates and do not replace unauthenticated connection controls. Numbers above are deliberately a candidate profile for review and measurement, not endorsed Windows safety parameters. No review of this PR ratifies them. Future G1 requires independent numerical signoff, chosen transport abort primitive and verified pre-handler timing enforcement **before any socket opens**.

## Exact time model and zero-trust provenance

- `t_first`: trusted monotonic connection/first-byte timestamp **must come from an independently verified platform source**, not a model argument or a client header. The pure fixture receives a synthetic integer and `provenance_verified=True`, which does **not** authenticate anything.
- `t_handler`: when the test/handler sees the context (after HTTP.sys header processing). `t_handler >= t_first + header_budget` yields `late_headers_unenforced` in the model; this is **detection after delay**, not proof that kernel/queue occupancy was bounded. A missing trusted anchor triggers `unverifiable_prehandler_time` and halts new admissions.
- `t_body`: start of body reading; expiry is `min(t_first + total, t_body + body_budget)`. A slow sender cannot reset those deadlines by providing one byte per fragment.
- `t_done`: only an independently observed **read-task completion, terminal transport quiescence and safe buffer release** can free the in-flight slot. A 408 response, cancelled token, closed response or attempted abort does **not** prove this.
- Request response waiting (ordinary proposed **95s**, P12 bedtime **1200s**) includes queue wait, game execution limit (ordinary proposed **360s**, P12 bedtime **1200s**) begins on valid tool start, and P2 owner-presence thinking freeze is distinct from transport ingress. None of these longer budgets may extend `t_first` ingress limits.

The fake ledger stores **application-visible** tickets only. It has **no real HTTP.sys queue, TCP socket, connection accounting, OS-enforced header clock, response stream, actual request task or auth authority**. Claims of `read_completion_observed=True`, `transport_quiescent=True` and `buffers_safely_released=True` are supplied by tests. In the real adapter they require evidence from the transport and owned buffer/task lifecycle. A passing fake assert cannot establish that `HttpListenerRequest` exposes those fields.

## Abort / teardown state contract

```text
UNKNOWN / pre-handler (no trusted evidence) → NO-GO, never admitted
PROVEN t_first + admitted capacity → ACTIVE (synthetic only)
  ├─ full body delivered before min(total/body deadline) → ELIGIBLE FOR NEXT POLICY CHECK
  │      (not authenticated, no queue/game authority)
  └─ deadline or body/read failure → ABORT PENDING (capacity remains HELD)
        ├─ request-specific abort independently proven
        │     → read observed complete + transport quiescent + buffer safe
        │     → RELEASED capacity (never resurrect candidate)
        ├─ whole-listener abort required → STOP new admission; count collateral work
        ├─ unverified abort or unread pending task → HELD, no safe reuse
        └─ cleanup exceeds fixed grace / unresolved cap reached → NO-GO / stop
```

The fake is **not** a real interruptor: `abort_requested(scope="request")` merely records a caller-provided *claim*. Actual G1 tests must verify the OS abort primitive and scope. If abort requires destroying the whole listener, shutdown must be bounded and collateral accepted requests recorded, not silently called success. If a read hangs beyond the grace, the correct result is **FAIL/BLOCK and capacity quarantine**, not reusing the buffer or accepting more work. Quarantine is not a workaround for indefinitely leaked reads.

The `recovery` lane in the fixture is **just a finite reserved counter**, **not** a C/O/A/H authorization or authenticated status endpoint. A malicious caller cannot select a real recovery lane without independent route and identity gates. The fake accepts any synthetic principal solely to exercise arithmetic. True untrusted pre-auth backlog saturation needs a separately reviewed OS/transport control and cannot be solved by 8-per-principal quotas after credential lookup.

## Offline model tests vs actual requirements

The Python tests exercise missing/untrusted `t_first`, slow headers, too-late body, whole-ingress deadline unchanged by chunks, 5s subordinate body deadline, no early slot release on timeout, required completion/quiescence/buffer acknowledgment, limits and recovery reserve, max unresolved cleanup, late read completion never reacquiring a candidate, and conservative whole-listener-abort stop. All counters are synthetic and the effect counter must stay zero.

**Known simplification:** the fixture does not model actual concurrent races, incomplete HTTP headers before delivery, kernel backlog admission, nuanced mid-header idle timing, raw Host/CL/TE parsing, response backpressure, timeout callback concurrency, real sockets, ownership of pooled .NET buffers or crash recovery. The fake state machine must never be called by `AgentHttp`; it is a design reference to challenge, not production logic.

## G1 review questions that remain hard blockers

1. Can Windows HTTP.sys expose a **trusted monotonic connection/first-byte anchor** that captures slow headers **before `GetContextAsync`**, or provide independently documented enforceable equivalent limits without OS-wide mutations? If not, **G1 is blocked**; the model's post-handler `late_headers_unenforced` does not fix it.
2. What exact request-specific transport-owned **abort primitive** causes a hung `HttpListenerRequest.InputStream.ReadAsync` to actually finish, and what objects does it affect? Does closing the response or context abort the read, or only the whole listener? **Measure under separate approval; no unproven assumption.**
3. Can the selected API bound open connections, pre-auth headers, HTTP.sys queue length and pending reads at proposed values? Record impact on the disposable instance and proof that accepted recovery/health and other lanes don't starve.
4. How are completion, exact buffer ownership, late callbacks, exception observation, transport shutdown and resource release proven? A timer that returns 408 but leaves a task alive fails.
5. Do the selected numerical values make sense on an isolated Windows test process? Review CPU/memory, UI/game-thread isolation, useful success latency, P12/WorldClock freeze and absence of collateral real gameplay effects. Ratify independently; this repository never auto-upgrades `approval_state`.

**Explicit G0→G1 STOP:** no launch, no port selection, no Windows URLACL/firewall change, no synthetic packet sending until the separate operator-approved G1 setup and reviewed quantitative/abort contract exist. **G1→G2 STOP:** protecting only `/mcp/p2` while legacy raw API/control/debug remains open is not acceptable. Real P1 consent, sessions/epoch, durable partial/unknown outcomes, separate native Luna migration and Windows/SMAPI acceptance remain G2.

Review only the four paths in this PR; any tests validating these conditions are **offline structural/model tests**, not an actual HTTP listener test.

## Independent Issue #44 audit corrections

At author head `ba02341564bed8bb1d17ad166bacffae763a25a0`:

- **High — stale lifecycle acknowledgments:** completion/quiescence claims accepted before a read or abort could later free capacity. Claims are now accepted only after body completion or abort-pending, and invalidated on each abort transition. Cleanup events require monotonic event times. They remain synthetic claims, never verified Windows evidence.
- **High — stale time and delayed expiry:** eligibility accepted rollback timestamps; admission did not process existing expired work; delayed callbacks restarted cleanup grace. A ledger-wide integer monotonic event clock now processes deadlines at every timed event. `abort_due_ms` is the effective minimum deadline; `abort_requested_ms` records only an actual synthetic request event. Equality expires both ingress and cleanup. Late safe cleanup can release capacity but cannot clear a latched stop.
- **High — listener collateral and missing cancellation:** whole-listener abort only stopped admission, leaving other tickets active. It now transitions all held active tickets to abort-pending and invalidates earlier claims. Explicit synthetic `cancel` covers cancellation/read failure/response-close without releasing capacity or requalifying late work.
- **Medium — profile overclaim:** numeric floats/bools and Windows/runtime evidence flags could pass profile loading. Positive integer candidates and false evidence flags are now required. No numeric value is ratified by these checks.

All event times, principal names, recovery lanes and proof flags are fixture inputs. Sequential synthetic events cannot authenticate their producer, prove real abort effectiveness, or exercise races. Ticket IDs are permanent tombstones within this ledger; no reuse/ABA or automatic restart is supported. A halted instance stays halted even after all slots drain; restart requires external lifecycle review, not a counter reaching zero. Retaining tombstones is an intentional finite-test simplification, not a production memory policy.

The body deadline starts when reading actually begins, while waiting to start remains bounded by total ingress. A successful body remains only a held candidate until another policy check, never an admitted game action. This fixture does not model a response wait; future runtime accounting must transfer ownership without losing the global/per-principal reservation across the 95s/1200s response wait. The 8s ingress candidate must not become a response or execution timeout. Neither successful-body release nor any abort event proves operation retirement.

No reservation arithmetic bounds pre-auth/kernel occupancy or grants fairness. Four recovery counters cannot guarantee service under saturated unauthenticated connections, principal rotation, or listener-wide teardown. Header detection at handler delivery includes queue delay and may conservatively reject promptly completed headers; it cannot distinguish that delay or establish enforcement. Trusted first-byte provenance, pre-handler bounds, authenticated lane selection, abort effectiveness/scope, buffer ownership and bounded shutdown remain independently approved G1 evidence requirements. All-route security and actual game/response lifetimes remain G2 requirements.
