# Sunny Phase 2H — G1 Readiness Review

**G0 DOCUMENT REVIEW ONLY · Decision: NO-GO · not yet approved to begin G1**

This is a readiness review for **whether to authorize a future, disposable Windows HTTP.sys/HttpListener experiment**. It is **not a Windows acceptance**, an operator approval, a live listener implementation, a deployment decision or permission to change `main`. No sockets, OS configuration, game, installed Sunny/Luna controller, real credentials, player saves, private logs or G1 traffic were used.

Reviewed source baseline: Draft PR #22 at `752db4a7d5fda301947287862f480cc221aafffc`, after independent Phase 2G [resource and abort model](../../reference/sunny_http_resource_limits/README.md) review. The [Phase 2F transport plan](WINDOWS_HTTP_TRANSPORT_ACCEPTANCE.md) remains authoritative for the **50 `not_run` cases**: **37 future G1 isolated transport cases** and **13 separate G2 security/privacy/Sunny–Luna cases**, with **17 highlighted priority blockers across both stages**. None is signed off.

The machine-readable [entry gates](../../reference/sunny_g1_readiness/gates.json) contain **11 open prerequisites**. Their offline [validator](../../reference/sunny_g1_readiness/evaluate.py) and [pytest](../../mod/tests/test_sunny_g1_readiness.py) deliberately have **no route to emitting GO**. Passing static validation means documents agree about being unapproved, not that Windows has been tested.

## Decision snapshot

| Question | Current result | Rationale |
| --- | --- | --- |
| Is G0 plan content structurally checkable? | **Yes (offline scope only)** | Case inventory, PR #22 source references and Phase 2G numerical *candidates* can be cross-checked |
| May the user or assistant start an actual G1 disposable listener now? | **NO-GO** | No separately approved test executable, network/port setup, numeric limits, or verified abort/provenance approach |
| Have all 37 G1 Windows cases passed? | **not_run** | Not a G1 *entry* prerequisite; G1's future job is to measure these cases, once starting it is separately authorized |
| Can a G1 test certify Sunny/Luna security or P1 consent? | **No** | The 13 G2 cases are distinct; real all-route auth, game ownership and migration remain outside isolated HTTP transport |
| Is production HTTP security enabled by PR #22? | **No** | Existing `AgentHttp`/runtime code remains the legacy implementation; reference fixtures do not replace real enforcement |

**Important distinction:** G1 entry requires an approved **safe experiment design**; it cannot require already-passing G1 Windows results, which would be circular. G1 completion would require independently examined results of all 37 G1 transport cases, including all applicable G1 blocker cases. G2 completion separately requires real runtime tests; no G1 evidence counts as G2 proof.

## Eleven open prerequisites before G1 can START

All rows are **Open**. The IDs correspond to [gates.json](../../reference/sunny_g1_readiness/gates.json), where each row links relevant, **unexecuted G1 case IDs**.

| Gate | Required *before* G1 execution | What is missing today |
| --- | --- | --- |
| **G1E-01 — Isolation** | Peer-reviewed disposable loopback-only server/client design and complete rollback without touching live Sunny | No reviewed, authorized test executable and teardown |
| **G1E-02 — Raw provenance** | Proposed trusted observation layers for transmitted bytes, HTTP.sys decisions and actual listener-exposed fields, marking missing fields `unobservable` | Raw target/Host/header multiplicity fidelity cannot be inferred from `RawUrl` or mock flags |
| **G1E-03 — First byte** | Credible way to observe/limit pre-handler **first byte**, slow headers and kernel queue wait, including hard stop if unavailable | `GetContextAsync` is too late to start a total ingress clock |
| **G1E-04 — Pre-auth capacity** | Reviewed strategy to bound open connections, pre-auth headers and HTTP.sys backlog without unapproved OS-wide changes | Offline 32-slot ledger begins only after handler delivery |
| **G1E-05 — Actual abort** | Identified request-scoped vs whole-listener abort operation and safe failure/stop handling | `CancellationToken`, 408 or response close do not prove read termination |
| **G1E-06 — Cleanup** | Evidence plan for read-task completion, transport quiescence, buffer ownership/quarantine, late callbacks and bounded shutdown | Synthetic booleans are not actual Windows evidence |
| **G1E-07 — Numbers** | Independently ratified *experiment-only* numerical/resource limits | Phase 2G values remain `proposed_not_ratified`; `g1_approval=false` |
| **G1E-08 — Safe probes** | Reviewed synthetic raw-wire fixtures, validity/denial expectations, finite traffic rate, separated pipelining and malformed framing | No approved executable fixtures or capture/response-trace protocol |
| **G1E-09 — Approval** | **Separate explicit** user/operator approval for program, disposable port, traffic cap, safe stop and rollback | This Draft PR is not permission to select a port or send packets |
| **G1E-10 — Privacy** | Scrubbed evidence format, strict no-personal-data policy and defined handler/protected-effect counters | No reviewed Windows capture procedure; never record secrets/P1 diaries |
| **G1E-11 — Verdicts** | Approved case-by-case evidence ledger and independent outcome classifier distinguishing OS vs adapter denial, acceptable candidate, failure and unknown | No signed G1 acceptance owner/process; no Windows outcomes exist |

These are **entry design/authorization gaps**. For example, exact Windows raw-field observability and actual abort effectiveness remain things to prove **during G1** if the proposed experiment can safely test them; failure to design a safe way to test them keeps G1 start NO-GO. A `not_run` row is never silently promoted to failure or success.

## Proposed Phase 2G numbers: candidates only, NOT ratified

The JSON profile currently suggests **8,000 ms total ingress** from a trustworthy first byte/connection anchor; **2,000 ms header budget**, **5,000 ms body read budget**, **2,000 ms abort+cleanup grace**, **16 KiB request body** and **256 KiB response**. Resource candidates are **32 global held requests**, split **28 general + 4 reserved recovery**, **8 per authenticated principal**, **4 unresolved aborts before stop**, and backlog **16**. These are neither Windows guarantees nor accepted defaults.

The 95-second ordinary response wait and 1200-second P12 bedtime response/action budgets belong to separate runtime clocks, **not** to the 8-second HTTP ingress window. A timeout/abort must never release a held slot until actual completion and safe ownership are proven. Even after simulated cleanup, a latched safety halt cannot automatically clear itself.

G1 must **not start** until the numerical limits, any required OS-enforced equivalent protections, the abort primitive/scope, and rollback constraints are independently reviewed and explicitly authorized. For timeout/cancellation, a hung read that ignores cancellation remains **NO-GO** even if a timer returns 408.

## Evidence needed *during* an approved G1 (not already available)

Once separately authorized, an isolated test could collect case-specific sanitized raw byte fixtures + actual sent lengths, destination/bound process, transmitted-request IDs, Windows API-observable fields, OS rejection vs handler arrival, protected-effect counts (all zero for denials), response status/headers including interim `100 Continue`, and monotonic timeline for first byte → header queue → read → abort → observed completion → buffer release → teardown.

If required original-wire attributes are impossible to observe/guarantee through `HttpListenerRequest`, the result is **BLOCK / redesign the transport**, not inferred proof from client bytes or a claimed `Evidence.All`. An OS 400 can prove refusal with reliable layer attribution, but not that application header parsing was correct. A valid pipelined second request must be treated as a separate request, not confused with malformed trailing bytes. No real listener probe is executed in this PR.

## Stop/rollback contract before any future G1 authorization

A separate future approval must name the test binary/build, a **new disposable loopback port** not used by Sunny, valid test fixture IDs, rate/concurrency/body caps, the decision-maker and observed shutdown requirements. Deny by default if the executable requests elevated access, URLACL/firewall/system-wide changes, unknown listeners or unbounded stress. Abort on any unexpected protected candidate, private response, uncertain raw provenance, unbounded pending read, resource/cleanup overrun or unsafe teardown. Keep unknowns blocked; don't label them passed because the process exited or the client saw a timeout.

The test fixture must not reach the existing mod's port or any running service, change Stardew saves, use provider API credentials, expose P1 conversation/diary data, install a DLL or edit machine configuration. An isolated process cannot certify the actual game. Current `main`, Luna Controller and installed Sunny must remain unchanged.

## What this review recommends next — while staying offline

Complete a **reviewable G1 experiment specification** (not executable traffic yet): provide a small source-level interface sketch for raw transport observations and abort ownership; decide how to get a trusted pre-handler clock/connection bound; identify Windows API unknowns; propose a safe synthetic fixture catalog, data-minimization schema, and fallback transport decision if `HttpListener` cannot supply original-wire facts. Independently review proposed 8/2/5/2-second and 32-request limits for feasibility before any permission request.

Then return to the user for **new explicit G1 approval** of a concrete disposable test setup. The start gate requires separate explicit user/operator approval, not merely a continuation of current G0 document work. Approval cannot be inferred from this conversation's permission to continue G0 document work. Even a successful future G1 cannot activate the G2 authenticated server while raw legacy APIs remain unprotected.

**Current final finding: NO-GO. The plan is useful, but G1 is not yet approved to begin.**
