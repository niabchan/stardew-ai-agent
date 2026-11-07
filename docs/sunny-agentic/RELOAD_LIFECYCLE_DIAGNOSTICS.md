# Sunny Phase 2 — Reload lifecycle diagnostics (draft PR)

## Why this exists

A real split-screen smoke test established that the opt-in, P2-only diagnostic sampler
captures thousands of fresh observations when a save is loaded after starting SMAPI.
Returning to the title invalidates the latest P2 evidence as expected. On a subsequent
load **inside the same game process**, P2 was visibly present, but the local status
still reported `unavailable` and `capture count: 0` without a captured exception.
Exiting the application, restarting SMAPI and loading the same test save restored
fresh, increasing P2 capture counts. A prior observation of P2 external-console
control becoming unresponsive after an in-process reload may be related, **but has
not been demonstrated to share a cause**.

This PR adds *diagnostics, not a reload fix*. Do not use it as evidence that reloading
without restarting is supported yet.

## Implementation

The manually invoked `sunny_observe_status` console command appends **metadata
only** about the game process's observation callbacks, including:

- Number of host `SaveLoaded`, title return and P2 `SaveLoaded` events (process
  counters), and their most recent ordinal order (not wall-clock times).
- Number of P2 `Sample` invocations and successful P2 cache captures (process
  counters; separate from the current incarnation's capture sequence).
- Most recent P2 gate, chosen from a fixed allowlist:
  `not_observed`, `awaiting_p2_tick`, `p2_joining`,
  `p2_menu_invalidated`, `title_invalidated`, `collection_disabled`,
  `screen_mismatch`, `p2_role_not_ai`, `world_not_ready`,
  `player_unavailable`, `cache_rejected_no_epoch_or_config`,
  `sample_exception`, `captured`.

These counters are diagnostic breadcrumbs, not formal evidence of gameplay or
prompt identity. Notably, `cache_rejected_no_epoch_or_config` is intentionally
ambiguous: it cannot by itself prove a missing host epoch. Event ordinal comparison
and P2 attempt counts help narrow that diagnosis. A P2 tick count of zero after
a host load suggests missing callback delivery *or a different instance/screen
binding*; additional game logs are required to distinguish those cases.

The status command remains a **passive read**. It does not invoke the game, fetch
player references, inspect raw dialogue, scan saves, change roles, configure sampling,
create new epochs, or repair anything.

## Safety boundaries

- Existing `DiagnosticObservation.CollectionEnabled` remains opt-in and default false.
- `AllowHumanP1Collection` remains independent, default false; **P1 samples are never
  included in the status report**, even if an operator separately consents to P1
  collection. The new counters and gate are P2-specific.
- No farmer names, paths, load IDs, branch IDs, farmer aliases, menu content,
  messages, exceptions, item lists or secret values are included.
- `HttpDisclosureEnabled` remains reserved and ineffective. No new route, HTTP
  read or controller/tool path is added. Existing legacy HTTP security limitations
  remain unchanged.
- No game/input/SMAPI behavior is changed intentionally, no additional per-screen
  tick is scheduled, no automatic action is triggered. `guarded_dispatch`,
  `gift_classification`, `transfer_verification`, and
  `checkpoint_reconciliation` remain false.
- No save, installed mod or API key is touched. Do not merge to `main` or deploy
  without separate review and an operator-owned backed-up test save.

## Proposed live reproduction (after isolated tests, full mod build and review)

1. Use an explicitly backed-up **test** save, with P1 human, P2 AI, Brain=none.
2. Start game and load the save. Confirm P2 appears; read `sunny_observe_status`.
3. Return to title without saving. Read the same status; P2 evidence should be
   unavailable. Do **not** assume every title callback fires exactly once.
4. Load the same test save **within the same process**. Read status twice with
   the P2 viewport visible and game running. Record only the text-only diagnostic
   output. If unavailable, compare event orders, attempt counts and last gate.
5. Exit without saving; optionally restart the game to confirm that first-load
   observation still functions. Stop on crashes, unexpected control or role changes.

Avoid using P1 private dialogue or inventories to create test prompts.

## Interpretation examples

- `P2 sample attempts` unchanged across the reload and `awaiting_p2_tick`:
  no P2 `Sample` was observed since the last gate update. Check split-screen
  callback/screen bindings before modifying cache logic.
- Attempts increasing with `world_not_ready`: P2 callbacks exist but the game
  does not report a ready world at the time sampled.
- Attempts increasing with `p2_role_not_ai`: check role resolution on reload.
- Attempts increasing with `cache_rejected_no_epoch_or_config`: compare the
  last host/title event order, then inspect host epoch setup.
- `title_invalidated` following a later host load (event order): investigate
  delayed or duplicate title callbacks.
- `captured`: latest P2 sample succeeded; this does not establish prompt
  lifecycle coverage, identity confidence, or controller responsiveness.

## Validation status

Game-free C# tests added for the event order and capture gate on a synthetic
`host load → P2 join → title → load → P2 join` sequence, plus role/world/player
readiness and mismatch branches. These use the existing shim project, not real
Stardew/SMAPI event delivery. Run:

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

Actual full-mod compilation and repeatable game reproduction still require an
operator's supported Stardew/SMAPI installation. No live validation or successful
test run is claimed merely because the code is in this branch.

## Next decision

Use the new event/attempt/gate evidence to identify the first broken invariant,
then propose the smallest guarded reload repair in a separate reviewed PR with
regression tests. Do not automatically clear/recreate host authority or drive P2
based solely on a local status read.
