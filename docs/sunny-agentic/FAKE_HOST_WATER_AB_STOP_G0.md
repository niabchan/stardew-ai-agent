# Sunny G0 — Synthetic P2 A/B WATER callback + STOP interleavings

**Scope:** test-only, game-free, offline **model** for Issue #76; no runtime Mod integration, no injected native WATER call, no Steam/SMAPI/Harmony, network, file, provider or save access. This is not a real Host-owned authorization service, IPC protocol, physical STOP or causal game-effect receipt.

## Provenance and positioning

- Stacked on Draft PR #60 (daytime-intents fake-world proposal) and, through it, Draft PR #58 (fake observation/choice/effect). Both are G0-only and Draft/unmerged.
- Source: `reference/sunny_host_stop_fake.py`.
- Synthetic regression tests: `mod/tests/test_sunny_host_stop_fake.py`.
- Only three *new* files are proposed in this Draft PR. Existing Mod/Agent runtime files, tests and fake L2/L3 source are not modified.
- Criteria: Issue #76 Host operation contract and STOP erratum, especially [R1-A/B](https://github.com/niabchan/stardew-ai-agent/issues/76#issuecomment-6947297633) and the Native WATER callback source-only verdict. This is not a claim to implement those contracts.

## Defined toy model

The synthetic fake host has one actor `P2`, one literal action `WATER`, a synthetically frozen `FakeWaterOperation` record whose fields are validated as exact built-in strings, tuple and integers (not merely objects comparing equal to literals), a fixed fake owner/epoch and at most one unresolved operation. It deliberately models only a *sequentially chosen event order*. There are no threads, locks, independent STOP channel, authoritative Host OS process, persistence, source/game binaries or side effects beyond a Python `fake_wet` flag and event list.

1. `reserve(op)`: create one unresolved marker and pre-reserve **callback B lineage** *before* A starts; B reservation does **not** permit B entry by itself.
2. `enter_a(op)`: one synthetic region A entry only while not stopped; duplicate A cannot enter.
3. `run_a_with_callback(op, callback)`: the injected fake callback may call `enter_b(op)` while A is entered but has **not** finished. B must have the same immutable operation and pre-reserved lineage. This depicts possible early/reentrant callback ordering without dispatching native game methods.
4. `enter_b(op)` and `finish_b(op)`: one B entry and one synthetic effect. If STOP latches **before** B entry, entry is denied. If B entered **before** STOP, a modelled effect may complete **after** the latch; the test **must not** falsely promise immediate physical cancellation.
5. `latch_stop()`: monotone, idempotent in this *same in-memory fake object*. STOP prevents any new A, B or operation reservations but cannot retract a B already entered. No independent watchdog, delivery/observation latency or physical preemption exists.
6. `confirm_fake_observation(op)`: an **internal fake confirmation** is possible only if both regions finished and `fake_wet` is true **and** the synthetic `FakeEffectEvidence` record matches that exact operation ID, original load epoch, owner and tile while the Host still reports that same epoch/owner. A callback from an already-entered B may finish after the load changes, but that *old-epoch receipt cannot clear the unresolved old operation*. Otherwise unresolved remains. Lost/ambiguous receipts **never** clear pending. A fake epoch change **also latches terminal STOP**, even when no operation is pending; it does not rearm new-epoch operations or clear pending/seen IDs. The synthetic B/finish calls accept only the **same reserved in-memory operation object** (not an equal-but-unissued clone); this models a host-owned handle, **not** real authentication. A resolved operation ID is not replayable.

**Important boundaries:** B lineage pre-reservation is not a *real* atomic ticket. Calls chosen by a deterministic test **cannot prove** a race-safe STOP-vs-region-entry total order, physical STOP latency, effect callback ownership/cleanup, any actual game refills/wetting, private recipient-specific egress or durable persistence after process restart. The fake `fake_wet` value is not a real-game state receipt. Fake epoch rotation is not a real SaveLoaded observation. Authentication, untrusted client messages, grant delivery and actual source coverage are **not represented**.

## Scenarios currently tested (synthetic only)

- Pre-A reserved B lineage, reentrant callback, B before A denial, duplicate B denial, a single fake-effect marker.
- STOP before operation reservation; STOP between reservation/A; STOP after A before B.
- B entry wins before STOP, then residual fake effect *after* STOP; no rearm.
- Lost receipt keeps pending even after simulated mutation; no new operation ID bypass.
- Fake epoch rotation terminally revokes old authority (even with no pending), denies stale A/B without clearing pending; an already-entered B may produce an old-epoch fake effect, but cannot clear the old pending based on that receipt. STOP stays latched.
- Wrong operation and equal-but-unissued clone, mutable equality-compatible aliases for P2 seat/WATER action, wrong P1 seat, disallowed action, invalid tile, stale owner/epoch.
- Callback exception leaves unresolved; no silent retry.
- Fake observation cannot resolve until A/B completion and receipt operation/epoch/owner/tile match; forged or mismatched synthetic evidence cannot prove completion; one effect cannot occur before A.

Local isolated smoke tests in a temporary Python workspace: **15 passed on the prior reviewed HEAD**, before R1's additional three regressions; **18 tests are now present** in this patch. Latest-head CI must be verified separately and must not be inferred from the old green run and request independent code review; do not re-label game G1/G2 cases as passed.

## Review criteria and explicit blockers

Before any promotion (including another G0 design iteration), independent reviewer should challenge: forged/mutable operation identity, callback lineage consumption, STOP vs A/B entry ordering, residual entry after latch, duplicate/replay, lost receipt, epoch rotation, completion/unknown, accidental target file/network access, and cross-PR scope. No synthetic assertions may be interpreted as a verified Host implementation.

**Frozen:** Native WATER `BLOCK/DENY`, all **11 G1E gates OPEN**, all **50 G1/G2 cases `not_run`**, `NO_GO_G1_START / NO_GO_LIVE_G2`. No runtime patches, production source wiring, user file reading or game execution in this slice.

## R1 correction after independent FIX_REQUIRED

The independent [Issue #76 review](https://github.com/niabchan/stardew-ai-agent/issues/76#issuecomment-7014787657) identified two material defects in the prior HEAD: an old B effect after `rotate_epoch()` could clear old pending with a receipt lacking load identity; and mutable equality-compatible `seat`/`action` objects passed primitive literal checks. R1 adds `FakeEffectEvidence(operation_id, epoch, owner, tile)` and an exact current-epoch/owner check before toy reconciliation, plus exact built-in-string validation and three focused regressions. The same-load STOP-after-B-entry residual still remains intentionally permitted; no physical STOP or authenticated source claim follows.
