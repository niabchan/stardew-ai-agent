# Sunny Phase 2 — logical P2 identity across SMAPI screen rejoin (draft PR #18)

## Evidence and fault

Operator logs in PR #17 show Sunny joining P2 after successive title-to-load cycles, while
SMAPI assigns new physical screen IDs (1, then 2, then 3). The old
`Players.Current => Slots[Math.Clamp(Context.ScreenId, 0, Seats - 1)]` coupled that
transient identifier to stable P1..P4 agent runtimes. With two active seats, a new screen
ID of 2 or 3 can select P3/P4 instead of Sunny. Diagnostic sampling also erroneously
required `seat.Screen == Context.ScreenId`.

## Intended repair

- Determine the **logical seat** from the currently selected `Game1.game1` instance's
  `instancePlayerOneIndex`, cross-checked with its position in the active GameRunner
  instance list. The game-thread binding rejects missing, stale, mismatched, off or
  out-of-config instances. Screen 0 may only bind P1; any other physical ID may only
  bind a verified guest. It never clamps/modulos the SMAPI screen ID.
- Use that binding in UpdateTicked and the SaveLoaded/MenuChanged diagnostic
  invalidation paths; keep P2 as logical index 1 in SplitScreen.GuestTick, timers,
  agent runtime and diagnostic capture. An ambiguous screen gets **no dispatch**.
- The diagnostic observer remains opt-in, read-only, P2-only on status and without
  gameplay, model calls or HTTP evidence disclosure. Consent, role gates and host
  epoch remain unchanged.

## Regression boundaries

Game-free tests simulate physical IDs 1→2→3→12 while the logical P2 stays at index 1,
plus P1/guest confusion, mismatch, missing authority, no P3/P4 access with two active
players, and no P1 raw content in status. Python source checks guard wiring.
These tests **do not validate actual GameRunner/SMAPI callback context**.

## Operator-only validation (not yet done)

1. Review this Draft PR, run its CI tests, and build with a supported local installation
   without automatic deployment.
2. Back up the **test** save and installed mod. With P1 human, P2 AI, Brain=none,
   compare `sunny_observe_status` on first load, return-to-title, and two same-process
   reloads (do not save).
3. Verify P2 sample/capture counters resume, and verify a harmless P2-only command
   works after reload; P1 remains manual. Stop if identity, consent, control or menus
   diverge from expectations.
4. Avoid overwriting original DLL/save and do not merge to main without operator review.

The repair is proposed, not proven live. PR #17 stays diagnostic-only Draft.
