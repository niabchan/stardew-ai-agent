# Sunny G1 Windows transport — exact-run approval card (G0 design only)

**STATUS: UNAPPROVED / NOT EXECUTED / NO LISTENER / NO TRANSPORT SELECTED.**
**`NO_GO_G1_START / NO_GO_LIVE_G2` remains binding.**

This is a **fillable decision-and-approval annex**, not a second experiment specification,
a runnable harness or authorization. It relies on these existing, authoritative
source artifacts rather than replacing them:

- [G1 experiment specification](G1_EXPERIMENT_SPECIFICATION.md), which describes
  pre-authorization design and the three evidence layers.
- [Windows HTTP transport acceptance plan](WINDOWS_HTTP_TRANSPORT_ACCEPTANCE.md),
  including the independently reviewed Microsoft API crosswalk in Draft PR #79.
- [50-case manifest](../../reference/sunny_windows_http_acceptance/cases.json):
  **37 future Windows G1 cases, 13 separate G2 cases, all 50 `not_run`**.
- [G1 experiment plan](../../reference/sunny_g1_experiment/experiment_plan.json):
  conceptual per-case fixtures, not sendable raw traffic.
- [Empty evidence template](../../reference/sunny_g1_experiment/evidence_template.json):
  intentionally no observations or approval.
- [11-gate resolution plan](../../reference/sunny_g1_resolution/plan.json)
  and [readiness review](G1_READINESS_REVIEW.md).
- [Reviewed transport choices and STOP uncertainties](G1_KESTREL_DECISION_DESIGN.md).
- [Unratified numeric candidates](../../reference/sunny_http_resource_limits/proposed_limits.json).

This document specifies **what must be filled, sourced and independently reviewed**
before a user can be asked to approve a *particular, one-time* non-game Windows
experiment. It does not supply or infer any of the missing authorization. The
source branch is stacked on PR #79's independently accepted document head
`f4a51e3e36256596bfaa293173fd6a6f6824b0d2`. Nothing here is evidence
that Windows behavior or a real installed StardewMCP Mod was observed.

## 1. Exact-run identity — every unresolved field blocks execution

| Item | Current value | Required source/owner before approval |
| --- | --- | --- |
| Selected candidate | **NONE** — `HttpListener` / ASP.NET Core HTTP.sys / Kestrel not chosen | Independently reviewed field-by-field evidence methods; one candidate per run |
| Run purpose and case subset | **UNSET** | Exact existing Phase 2F case IDs and variants; dependencies and expected denial/observation only |
| Windows test host | **UNSET** | Operator-authorized machine/OS build and .NET runtime; no assumptions about the user's installed PC |
| Disposable server implementation | **NOT WRITTEN / NOT REVIEWED** | Named repository ref, reviewed source, build steps, SHA-256 of exact binary and dependency inventory |
| Disposable synthetic client | **NOT WRITTEN / NOT REVIEWED** | Separate source/binary SHA-256; controlled fixture manifest and write limits |
| Independent stop/controller process | **NOT WRITTEN / NOT REVIEWED** | External owner/process and observable, independently operable stop mechanism; not listener HTTP, queue slots or logger |
| Evidence writer | **NOT WRITTEN / NOT REVIEWED** | Sanitized-only fields, source attribution, fail-closed writer failure and no private logs |
| OS process/endpoint inventory | **UNSET** | Exact approved process aliases, bindings, expected child processes, no wildcard binding |
| Primary IPv4 loopback port | **UNSELECTED / UNAPPROVED** | Explicit unused value chosen and approved before bind; must not reuse Sunny's current or previous port |
| Optional second disposable endpoint | **NONE APPROVED** | Separate explicit approval; otherwise ENV-02 uses offline mismatch fixture |
| Approved synthetic test window | **UNSET** | UTC date/start/end or a single bounded operator-controlled run; no automatic recurrence |
| Independent stop owner and fallback | **UNASSIGNED** | Named role, access independent from test listener, finite escalation path and rollback authority |
| Execution limits, rates and concurrency | **UNRATIFIED** | Stage-specific finite numerical profile, reviewed before any listener/port binding |
| Final operator approval | **NONE** | New unambiguous consent for the *exact* code, endpoint, scope, stop, rollback and test window |
| Independent approval/review reference | **NONE** | Links to completed G1E-01..08,10,11 reviews and separate G1E-09 operator decision |

**No scanning for a free port.** Before approval, validate a candidate port
only against a local, operator-authorized inventory or another reviewed
non-intrusive method; do not probe or touch existing services. If an endpoint
is unexpectedly bound, **STOP**, do not auto-select a fallback. A generated
binary, GitHub CI run or prior G0 review is not consent to start it.

## 2. Minimal proposed non-game testbed (diagram is not running architecture)

```text
[Approved finite synthetic client]     [Independent STOP owner / control]
             |                                     |
             | localhost, approved unused port     | out-of-band halt
             v                                     v
[Disposable isolated Windows listener] <- HALT [independent supervisor]
             |
       [capture/deny-only handler]
             |
       [sanitized evidence writer]
```

The listener must implement **zero** Stardew/SMAPI/Luna/Controller imports,
save-file access, P1 data, AI model calls, API-key lookup, game mutation,
world clock, Debug API or installed-Host IPC. It may emit only inert synthetic
candidate counters, fixed denial codes and sanitized test observations.
No route may pass a real game command. Do not bind `0.0.0.0`, `+`, `*`,
LAN or IPv6 without **new separate approval**; no wildcard CORS, browsers,
OBS, redirects or real bearer secrets. The normal game must not be running
as a test dependency.

The test source must keep **server, client, supervisor and evidence-writer
lifecycles** explicit, not hide child processes, timers or network calls
in installers/tests. The supervisor's control path cannot depend on an
HTTP route of the listener being tested, its admission locks, worker pool,
reserved recovery slots or the evidence writer. A process-exit fallback
may be proposed only after its exact scope and effects are independently
reviewed and approved; it is never per-request cleanup evidence.

## 3. Candidate decision before code, with hard negative branches

- **HttpListener / HTTP.sys:** `RawUrl`, `Headers` and exposed endpoints are
  not original-wire guarantees. Configured `HeaderWait` does not set a
  short limit for the **first request on each connection**. If no reviewed
  independent mechanism can establish/enforce pre-handler admission and
  absolute timing, preserve **BLOCK / reject this candidate**, rather
  than relying on handler-entry clocks or inferred header multiplicity.
- **ASP.NET Core HTTP.sys:** HTTP.sys queue/header/body timing APIs require
  the same scrutiny for first-request exceptions, resource ceilings,
  preserved raw authority/CL-TE evidence and collateral abort. It does
  not inherit HttpListener acceptance or provide all wire fields by name.
- **Kestrel:** `IHttpRequestFeature.RawTarget` is *not* an authorization
  primitive or full parser-rejected wire record. Header names and values
  may be represented after parsing. `RequestHeadersTimeout` is not enforced
  under an attached debugger; upgraded connections leave the ordinary
  concurrency cap, and `MaxRequestBodySize` does not apply to upgrades.
  Both ordinary and upgraded connection caps default to unlimited. If used,
  independently ratify both caps or explicitly reject upgrades; require
  pre-handler timing, queue/backlog and abort/cleanup evidence. Kestrel
  does **not** automatically satisfy HttpListener-targeted Phase 2F cases;
  review **case-by-case substitutions** without changing original statuses.
- **Custom raw HTTP/TCP parser:** do not treat custom parsing as an easy
  bypass. New parsing, smuggling, header normalization, resource ownership
  and abort hazards require a new security design and approval; not
  provisionally selected here.

No candidate may be picked just to make the experiment start. Each
**required** property needs an independently reviewable method; if original
wire semantics are fundamentally inaccessible, the candidate is blocked
unless the protocol/policy is independently redesigned to reject such
ambiguity *before* any protected effect. Platform documentation is not
measured evidence for the current Windows installation.

## 4. Proposed experiment-only numeric review sheet — NOT ratified

These figures are inherited from
`reference/sunny_http_resource_limits/proposed_limits.json` **as proposals
only**. They are neither proven enforceable nor approved values. The
independent reviewer must accept/revise them with an explicit rationale and
prove how each is enforced **before handler entry where needed**.

| Proposed budget | Candidate | Independent evidence still required |
| --- | ---: | --- |
| Total first-byte → completed ingress | 8,000 ms | Non-resetting monotonic anchor, including headers, kernel queue and body |
| Header first-byte → completed | 2,000 ms | Actual pre-handler enforcement (NOT merely HttpListener configured HeaderWait) |
| Body read | 5,000 ms | Absolute budget and owned abort on non-cooperating reads |
| Abort + cleanup grace | 2,000 ms | Actual task/read/write completion, buffer ownership and bounded escalation |
| Request body | 16,384 bytes | Transport framing proof before fixed-size allocation and read |
| Response | 262,144 bytes | Bound response bytes and completion/abort |
| Global in-flight, incl. unresolved | 32 | All connections/reads/callbacks, no hidden kernel/upgrade bypass |
| General / reserved recovery slots | 28 / 4 | No bypass of total cap, stop must work if all slots full |
| Per authenticated synthetic principal | 8 | Inert test identities only; no real credential |
| Unresolved aborted requests | 4 | Exceeding count halts testing; no premature capacity reuse |
| Backlog | 16 | OS/server bound, not merely app queue |
| Per-fixture send count/rate | **UNSET** | Explicit finite count, pacing and total run ceiling required before approval |
| Response write, full test-window and emergency escalation deadline | **UNSET** | Finite non-resetting values and independent controls required |

If any of the above clock, occupancy or abort controls cannot be enforced
without system-wide URLACL, firewall, kernel settings, admin rights or
an unapproved transport change, **NO-GO**. The 95-second ordinary response
budget and P12's 1200-second bedtime execution are **not** permission to
extend the ingress clock or to touch the game.

## 5. Synthetic probes, three-source proof and attribution

The existing `reference/sunny_g1_experiment/experiment_plan.json` defines
one conceptual plan for each of the **37 Windows cases**. A separate,
independently reviewed implementation must supply the exact *finite*
sendable bytes, sequence, SHA-256 and variants, without modifying that
G0 plan or the 50-case statuses. For a first authorized Windows run,
use only a *specified, approved subset* (for example ENV-01/03 and a
single RAW-01 instrumentation check); do not claim all 37 passed from
that pilot. Any raw malformed-header/CL-TE/slow-header/abort probe is
**NOT pre-approved** by this document. It may be permitted only after
the specific negative-risk fixture, process isolation and stop budget
are independently reviewed and expressly approved.

Each future request/variant record must preserve:

1. **Client-written:** fixture ID + exact synthetic bytes hash, attempted
   and confirmed client-write lengths, destination alias, connection and
   request sequence aliases, interim responses and sanitized final response.
   A client write does **not** prove delivery to the server.
2. **HTTP.sys / selected server pre-handler:** only *directly observed*
   rejection/acceptance stage, first-byte/connection source, kernel queue
   occupancy, header/body/CL-TE transformation, or **`unobservable`**.
   The server must not backfill this from client fixtures.
3. **Listener after parsing:** `RawUrl` or `RawTarget` *as exposed*,
   parsed URL, headers/values *as exposed*, actual endpoint fields and
   handler-entry timestamp. No inferred duplicate original lines.
4. **Effects and ownership:** sanitized handler/auth/candidate/contact/
   queue/private-field counters (denied traffic must all remain zero),
   thread/task/read/write aliases, held/aborted collateral work, stop
   state, buffer owner/quarantine and observed cleanup. A 200/408 or
   `CandidateOnly` is never an effect/retirement receipt.
5. **Time-domain mapping:** one source for monotonic elapsed timing,
   with cross-process calibration and explicit uncertainty. Client and
   server unsynchronized timestamps are **not** a common wall clock.

Use the pre-existing
`reference/sunny_g1_experiment/evidence_template.json` for structure.
Do not fill its current empty values or change `status=not_run` before
a separately approved run; create a separately dated and independently
reviewed sanitized record afterward. No user names, machine paths,
keys, Authorization/Cookie values, user speech, P1 dialogue, save data
or real game logs may be uploaded as evidence.

## 6. Independent STOP, quarantine, teardown and rollback acceptance

**Before any traffic**, independently review the exact process/task/handle
inventory and mechanically verifiable stop sequence. Required stages:

1. Operator/supervisor **latches terminal HALT** independent of the
   listener; stop *new* synthetic sends and all new test candidates.
   Once latched, no request, cleanup callback or timing reset may rearm.
2. Invalidate queued/pre-commit and collateral candidates across all
   accepted synthetic connections (including bodies complete but awaiting
   any candidate decision). Maintain a named owner for every task,
   stream, response write, buffer and connection.
3. Use an independently approved, transport-owned request/connection
   abort method with explicit **scope**. If only whole-listener abort is
   possible, stop every candidate and record collateral effects.
4. Observe read/write **task terminal completion**, callbacks finished,
   connection/listener teardown and owned buffer status. Until these are
   established, preserve unresolved/quarantined ownership and do not
   count freed slots or reuse those buffers. A cancellation signal,
   `HttpListener.Abort`, process kill or HTTP 408 alone is not proof of
   individual request cleanup.
5. If the immutable stop/escalation deadline expires or the evidence
   writer freezes, escalate through the separate operator-owned path.
   Preserve `UNRESOLVED_QUARANTINED` when quiescence is unknown; never
   turn a timeout into `PASS`.
6. Perform operator-reviewed rollback: dispose authorized test resources,
   inspect only approved disposable processes/endpoint inventory, retain
   sanitized evidence, and record `CLOSED_NO_RESTART`. **No automatic
   retry, listener restart, port fallback or second test run.**

The stop mechanism must remain operable if every request, read,
recovery slot or evidence-writing queue is saturated. Its exact
escalation path/time and owner are **UNSET** in this G0 card. Until
reviewed and assigned, **do not run even an ostensibly harmless
positive probe**.

## 7. G1E approvals and truthful readiness

These eleven entries are drawn from
`reference/sunny_g1_resolution/plan.json`. **All remain OPEN.** A
source-review document does not itself close any entry; each needs
separate evidence, a reviewer decision and an owner.

| Gate | Required independent result before an approved G1 start |
| --- | --- |
| G1E-02 | Trusted target/Host/security-header multiplicity and peer rejection evidence method, with explicit `unobservable` alternatives |
| G1E-03 | Pre-handler connection/first-byte/queue timing or enforceable equivalent |
| G1E-04 | Pre-auth header, socket and HTTP.sys/server queue saturation bounds |
| G1E-05 | Exact independent STOP owner, abort scope, collateral invalidation and finite escalation |
| G1E-06 | Observed read/write/task completion, buffer ownership and quarantine rules |
| G1E-01 | Reviewed disposable app/build/process/endpoint inventory and rollback |
| G1E-10 | Data minimization/redaction and evidence-writer failure controls |
| G1E-07 | Independently ratified numeric limits and enforcement mapping |
| G1E-08 | Finite sendable synthetic fixtures, count/rate/variant and case mapping |
| G1E-11 | Per-case evidence-verdict charter: `BLOCK` on unknown, independent review |
| G1E-09 | **New, explicit operator approval** for the exact one-time run after all other prerequisites |

**Decision template (do not prefill):**

```text
Selected transport:                      UNSET
Approved code review / exact binary SHA: NONE
Windows host and runtime versions:       UNSET
Primary approved process/endpoint/port:  NONE
Second endpoint approved?:               NO
Exact Phase 2F case IDs and variants:    NONE
Synthetic fixture SHA / max count/rate:  NONE
Absolute clock source / limits:          UNRATIFIED
Trusted raw-wire / prehandler evidence:  UNPROVEN
Independent STOP owner/path/escalation:  UNASSIGNED
Owned abort, buffers, task completion:   UNPROVEN
Rollback / no-restart method:            UNREVIEWED
All G1E-01..08,10,11 independently met?: NO
New explicit operator consent (G1E-09): NONE
Approval reference and run window:       NONE
RESULT: NO_GO_G1_START
```

A user saying “continue the design” or an independent G0 review of this
document is **not** the G1E-09 authorization. Do not ask for that
authorization until the other ten G1 entry prerequisites have been
independently reviewed. If any mandatory provenance or cleanup method
is impossible, document a **transport BLOCK** and revisit the candidate;
do not paper over the gap by weakening the requirement.

## 8. Completion boundaries

- **G0 exit for this Run Card:** source correctness, compatibility with
  the existing 37/13 plan, fail-closed values, links and offline checks
  independently reviewed. This is a *planning* acceptance only.
- **G1 entry:** all eleven G1E gates independently resolved, exact test
  and numeric constraints ratified, then a new explicit operator
  approval; only then a narrowly scoped disposable Windows loopback
  run with synthetic bytes may begin.
- **G1 exit:** observed, dated, separately reviewed platform evidence
  for each of the 37 applicable transport cases. A pilot subset cannot
  close the other cases. Unobserved mandatory fields are **BLOCK**, not
  a presumed success. Kestrel cannot inherit HTTP.sys outcomes by
  analogy without reviewed case-by-case adaptation.
- **G2:** independently authorized production all-route credentials,
  P1 human privacy/consent, host-issued epoch/P2 lease, atomic tool/args
  admission, dual-lane coroutine STOP/retirement, durable host journal,
  authoritative effect reconciliation and Luna/bedtime compatibility.
  None can be inferred from a G1 non-game transport run.

**Immutable current status:** all **11 G1 entry gates OPEN**; all
**50 cases `not_run`** (37 G1 + 13 G2); no Windows listener, no game,
no SMAPI, no installed Controller, no provider key, no transport choice,
no user approval for a test, and no change to `main`. Keep this proposal
Draft/unmerged.
