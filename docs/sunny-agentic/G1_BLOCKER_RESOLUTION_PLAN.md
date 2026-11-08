# Sunny Phase 2J — G1 Blocker Resolution Plan

**G0 planning only · G1 start decision: NO-GO · no transport selected or authorized**

This is a **work-sequencing and evidence-to-close plan**, not another Windows acceptance test or permission to start G1. Its source is Draft PR #22 at `e0710b4d87f14ae411b7d4067896ba5ca3648b3c`, including the Phase 2H [11-entry-gate readiness review](G1_READINESS_REVIEW.md) and Phase 2I [disposable experiment specification](G1_EXPERIMENT_SPECIFICATION.md). The [machine-readable resolution plan](../../reference/sunny_g1_resolution/plan.json) is the single source for order, evidence, dependencies and gate status.

**Current finding:** all **11 entry gates remain open**, proposed Phase 2G resource limits remain **unratified**, and G1 execution remains **NO-GO**. The Phase 2F manifest still has **50 cases all `not_run`**: 37 G1 transport cases and 13 independent G2 Sunny/Luna cases; 17 have blocker priority. A completed G0 PR or passing Python/C# CI does **not** close any entry gate, authenticate approval or demonstrate Windows transport behavior.

## The decision we are actually trying to make

Before attempting a disposable Windows experiment, decide whether a **safe, testable HTTP API approach exists**. Do not blindly assume `HttpListener` exposes raw original Host/request-target/header multiplicity, lets application code observe or enforce the first-byte/header/queue clock **before `GetContextAsync`**, or provides a reliable request-scoped abort that completes an uncooperative body read. These are platform questions, not properties proved by `FakeHttpCaptureEvidence.All`.

The immediate next task is **P1, a targeted source-grounded transport feasibility memo**, not a runnable server. The memo should compare the proposed test-only `HttpListener` approach against a separately reviewed alternative **only if required raw evidence, prehandler bounds or safe abort cannot be justified**. Record unknowns honestly; source documentation may demonstrate possible methods but does **not** replace future empirical G1 evidence. A NO-GO transport-choice outcome is productive: it prevents sunk time building an unsafe proof-of-concept.

## Four ordered work packets

| Packet | Entry gates | Offline deliverable and decision | May it open a socket? |
| --- | --- | --- | --- |
| **P1 — Transport feasibility** | G1E-03, G1E-04, G1E-02 | Compare prehandler first-byte/header/queue measurement, preauth capacity control, raw Host/target/peer/multiplicity evidence. Choose a *reviewable approach* or document a blocking API limitation. | **No** |
| **P2 — Stop and isolation** | G1E-05, G1E-06, G1E-01 | Source/interface design for abort scope, true completion and buffer quarantine, independent stop under saturation, test executable and process/endpoint inventory. | **No** |
| **P3 — Finite experiment review** | G1E-10, G1E-07, G1E-08, G1E-11 | Redaction policy, independently ratified *experiment-only* numerical limits, vetted finite synthetic fixtures, per-case verdict/evidence process. | **No** |
| **P4 — Specific user/operator approval** | G1E-09 | New, explicit consent for **exact approved source/build, isolated port, traffic limits, stop owner and rollback** after the other ten gates are resolved. | **Only after new authorization, not from this PR** |

Start G1E-05/G1E-06 independent-stop and cleanup design **in parallel with P1**, before finalizing any transport choice. Packet sequence is review priority, not a serial safety delay. Final transport choice requires reviewed G1E-02..06 methods, and G1E-01 testbed closure depends on all five. P1/P2 may iterate proposals offline without requiring each other's closed gate or measured G1 results. Any unknown **required safety property** is BLOCK/NO-GO; only safely bounded measurement questions may await G1.

Packets order review effort; individual gate dependencies are authoritative in [plan.json](../../reference/sunny_g1_resolution/plan.json). Independent review is **required**: an authored artifact is not automatically an accepted method and is never Windows-proven implementation. P3 can prepare a numerical decision package offline; do not change the Phase 2G `proposed_not_ratified` values or claim signoff in this PR.

### Priority 1: decide API feasibility before building another harness

The P1 memo must provide a source/line or API-doc reference and verdict **Supported by reviewed design / Unknown / Unsafe or incompatible**, plus a fallback for:

1. **G1E-03:** locate a genuinely authoritative monotonic connection/first-byte source, covering slow headers and HTTP.sys queue wait, or an independently enforceable equivalent. A stopwatch starting at handler delivery only detects lateness.
2. **G1E-04:** account for unauthenticated connections, partial headers, queued kernel contexts and body reads before a principal exists. The Phase 2G **32 global / 8 per-principal** post-handler counters alone cannot enforce these.
3. **G1E-02:** identify how client-sent bytes, HTTP.sys decisions and `HttpListenerRequest`-exposed values would be distinguished. If mandatory original-wire fields are unobservable, record a **blocked API decision** instead of manufacturing raw-data provenance.

**Exit for P1 review:** a reviewer can identify what the future isolated experiment could safely measure, what could be bounded *before* application delivery, and what unknowns must be measured during approved G1; otherwise remain NO-GO and revisit API choice. This does **not** require all 37 G1 Windows cases to have passed before starting them.

### Priority 2: independent emergency stop before any endpoint

The P2 memo/design must independently specify a finite abort and escalation path available even if all HTTP listener, recovery, queue and evidence-writer workers are saturated. It needs an **operator-owned external stop**, named stop authority, finite total stop/cleanup deadlines, request-vs-listener abort scope, collateral request invalidation, read-task completion observation, buffer ownership/quarantine and a *manual* rollback and new restart approval. Never release capacity on `408`, cancellation-token signal, response close or process exit alone. There is **no automatic** resource release, safety-halt reset or restart without independently observed completion and new approval. A hung read or unobservable teardown is **BLOCK**, not success.

Only then should a **disposable source-level test executable design** and bounded process/endpoint inventory be reviewed (G1E-01); no port selection, binding or software installation is approved here. `ENV-02` wrong-instance tests default to offline mismatch; any second endpoint must be explicitly approved and newly disposable.

### Priority 3: obtain finite specifications with independent signoff

P3 must produce evidence/data-minimization requirements; genuine **experiment-only numeric approval**, not silent conversion of [Phase 2G proposals](../../reference/sunny_http_resource_limits/proposed_limits.json); reviewed concept-to-sendable-fixture source for all 37 G1 cases including subvariants; and per-request evidence/GO/FAIL/BLOCK criteria. Untrusted client-write completion is not HTTP.sys reception. Require a distinct attribution per request and connection sequence for pipelined/keep-alive traffic, plus correlated clock-domain evidence when times are compared. A 200/400/408 client response alone is not proof.

All source and outputs must remain synthetic and sanitized: no production bearer, provider key, P1 dialogue, diary, user save/logs, installed Sunny port, user identity or Windows-wide configuration changes.

### Priority 4: new specific decision (G1E-09)

Only **after** an independent reviewer accepts P1–P3 gate evidence may a separate operator approval request name the exact executable source/build SHA, proposed disposable loopback endpoint(s), explicit synthetic fixtures/rates/body/response/concurrency limits, time window, independent stop owner/path and recovery plan. The user agreeing to **continue G0 design work** is **not** approval to start G1. This plan provides no form, token or flag that authorizes it.

## How we mark a blocker resolved

An entry gate transitions from **open** only after a separately reviewed artifact directly supports its [entry_closure_evidence](../../reference/sunny_g1_resolution/plan.json) and links its exact existing Phase 2H G1 IDs. Missing evidence, a merely drafted document, a fake success flag, green CI or platform assumptions do not count. Any change to transport, build, limits, fixture variants, evidence schema or stop design invalidates affected downstream reviews and any prior scope-specific consent; re-review before a new operator decision. Revised numerical limits also require reconciliation of the existing Phase 2F/2I case expectations in a separate authorized change. CI and scripts cannot promote this decision. Reviewer and decision record must be provided in a **future reviewed change**, not invented in this baseline.

`G1E-09` is special: no amount of document completion can stand in for new explicit operator permission. Even when all 11 G1 start prerequisites are eventually reviewed and authorized, **37 actual Windows measurements belong to G1 exit**, and **13 Sunny/Luna/P1 privacy/security cases belong to separate G2**.

The [offline regression checks](../../mod/tests/test_sunny_g1_blocker_resolution.py) keep the current NO-GO baseline, source links, exact gate set, valid dependency order, distinct evidence requirements, 50 `not_run` status, no approval and unratified profile honest. These tests **do not** certify code or prove transport limits.

## Next reviewed deliverable and explicit limits

**Next small PR after this resolution-plan review:** source-grounded **P1 transport feasibility memo**, focused on G1E-03, G1E-04 and G1E-02. Keep the first feasibility decision small; if a required OS-level control is unsupported or unknown, identify a safer alternative *on paper* and stop instead of opening a port to see what happens. Independent Codex review may correct this plan before merging it into PR #22's Draft design branch.

**No runtime changes in Phase 2J.** Do not touch actual `AgentHttp`, `McpDispatcher`, `AgentRuntime`, native Luna controller, installed DLL, game/save, Windows network policies, `main` or existing services. No Windows G1 or game G2 actions are authorized. PR #22, #19 and #10 remain Draft, and the current installed Sunny remains the prior version.

## Issue #50 independent audit and closure evidence

- **High — missing feasibility barrier:** G1E-01 previously depended only on stop/cleanup, allowing testbed design closure before raw-wire, prehandler timing and preauth capacity reviews. It now requires G1E-02..06. Fixture closure also requires G1E-10 privacy review, rather than leaving data minimization until outcome review. Independent stop/cleanup begins alongside P1; a transport choice cannot be finalized before its safety method review. No dependency cycle exists.
- **Medium — consent ordering ambiguity:** G1E-08 previously requested an already approved endpoint while G1E-09 depended on G1E-08. Fixtures now use proposed endpoint parameters conditional on later consent. Candidate 16KiB boundary variants follow experiment-specific numeric ratification, rather than fixing an unratified limit. G1E-11 accepts proposed verdict thresholds, not measured outcomes. G1E-02 cannot waive mandatory provenance by merely blocking security claims.
- **Medium — offline false positives:** packet membership could be changed consistently in both entries and packets; any allowed mode or loosely prefixed owner could be substituted; 37 duplicated experiment IDs could satisfy a count check. Regressions now pin each packet distribution, mode/owner and exact experiment-to-source case identity, and mutate these failure modes. Text-length/keyword checks remain documentation checks, not semantic or Windows certification.

Every entry requires an independent reviewer identity, versioned artifact/source references, method and limitation verdict, explicit fallback and decision record in a future reviewed change. The current null evidence/approval records remain null.

| Rank / gate | Evidence needed to close entry design review |
| --- | --- |
| 1 / G1E-03 | Source-backed first-byte/connection monotonic anchor or enforceable equivalent before handler, including slow headers/queue time and clock correlation. |
| 2 / G1E-04 | Source-backed finite preauth connection/header/kernel queue controls, overload behavior and isolation without machine-wide edits. |
| 3 / G1E-02 | Per-field client / HTTP.sys / listener observation matrix for original target, Host, duplicates, peer and denial stage; mandatory unobservable fields BLOCK the experiment. |
| 4 / G1E-05 | External operator stop outside listener/recovery/evidence workers, named authority, finite escalation and request/listener collateral invalidation. |
| 5 / G1E-06 | Completion observation, held-resource ownership, late callback/buffer quarantine, latched halt, bounded teardown and manual rollback/restart approval. |
| 6 / G1E-01 | Transport and safety reviews plus disposable executable/source identity, proposed process/endpoint inventory and non-invasive isolation/rollback design. |
| 7 / G1E-10 | Vetted allowlist/redaction schema and negative leak fixtures: zero P1, diary, provider secrets or real user/game material. |
| 8 / G1E-07 | Independent experiment-specific numerical decision covering total/header/body/cleanup/response-write time, request/response bytes, preauth caps, backlog, held/recovery/per-principal concurrency and stop budgets. |
| 9 / G1E-08 | Vetted synthetic source and all 37 case/subvariant mappings, ratified-boundary probes, bounded traffic, pipelining attribution and proposed endpoints; no service discovery or prior operator consent required. |
| 10 / G1E-11 | Reviewed per-case GO/FAIL/BLOCK thresholds and evidence charter with unknown=BLOCK, denial provenance, independent outcome reviewer and rollback. |
| 11 / G1E-09 | New explicit operator decision after the other ten reviews, naming exact source/build, endpoint inventory, fixtures/rates/limits/duration, external stop owner and rollback. |

The smallest next G0-only task is a source-grounded P1 feasibility matrix for G1E-03/04/02, with a parallel G1E-05/06 safety interface sketch. Cite exact API/version/source and ownership/control scope for each required property; compare an alternative offline where necessary. An independently accepted feasible method with finite safety bounds can close a design gate in a future reviewed change. An unknown mandatory control cannot. No executable listener, port selection or empirical probe belongs in that task. Operator consent remains a separate later decision; actual enforcement, fidelity and cleanup effectiveness require future authorized Windows G1 measurements. Real all-route authorization, lease/epoch, privacy, Sunny/Luna migration and gameplay remain G2.

Offline validation for this correction: Python **637 passed, 1 existing xfailed** (including 46 resolution-plan checks); C# game-free **787 passed, 0 failed/skipped** via an in-process xUnit runner outside the repository to avoid a VSTest TCP listener. Only the three Issue #50 paths changed. These results supply no Windows, G1 or G2 evidence; all 50 acceptance cases remain `not_run`.
