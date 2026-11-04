# Sunny agentic team — Phase 1 charter

> **Status:** research proposal / architecture baseline, **not** an active multi-agent execution.
> **Repo:** `niabchan/stardew-ai-agent` (fork of Duckxy's Stardew MCP).
> **Actors in game:** Guy = human P1; Sunny = AI-controlled P2; Luna = model making Sunny's choices.

## Why now?
Prior pilots validated sleeping without a mandatory journal (PR #4, merged), split-screen chat (PR #3), chair sit/stand (PR #1), and experimental gift acceptance. As the user noticed, a gift can be transferred without becoming a grounded remembered event or a spontaneous companion reaction. This will recur when Guy and Sunny share building goals/resources.

## Current boundary
- The **game-side C# SMAPI mod** and MCP/HTTP code are in this GitHub repo.
- Sunny's **P10/P11/P12/P13 Python/PowerShell controllers** have been tested from **separate local ZIPs**. They are **not currently in this GitHub repo**. In particular, do not claim a repository-only analysis has inspected the live P13 gift parser/ledger.
- Pull requests into `main` are reviewed individually. Do not change upstream Duckxy's repo.
- A successful MCP `respond` is not proof of an inventory transfer, and a world snapshot can lag a command result. Track both.
- The model should retain agency: STAY, silence, declining a gift, and proposing a different plan are legitimate choices.
- **No live actions** by research agents: do not access local saves or deployed DLLs, launch multiple controllers against a save, or send real game commands.

## Proposed research team
| Track | Domain | Required deliverable |
| --- | --- | --- |
| A1 | Interactions & game action lifecycle | Map commands, dispatch, menus, cancellation, verification, idempotency |
| A2 | Inventory, gifting & resources | Map inventory/chest/ownership changes, transfers, crafting/construction constraints |
| A3 | Perception, events & memory | Map event provenance, notification, observation, save/reload and diary |
| A4 | Companion, communication & agency | Map P1↔P2 bridge, initiative, conversational prompts, social choices and P11/P13 gap |

Each track must return: **what exists (code paths + evidence)**, **what is missing or uninspected**, **risks and tests**, **proposed contract**, **dependencies**, **questions**. Research only; design first, no code or PR implementing new behavior.

## Orchestrator responsibilities
1. Read the four reports; separate observed code facts from proposals.
2. Resolve overlaps: interaction issues an intent, inventory verifies transfer, perception publishes an evidence-backed event, companion decides whether to respond.
3. Review contracts before implementation. Keep action/observation/session identity, provenance, and eventual persistence explicit.
4. Define one vertical acceptance test and a failure-mode matrix.
5. Only after design review: split into small implementation PRs; build C# and run tests, then require operator-led in-game validation before merging.

## Proposed first cross-system scenario (not a specification yet)
Guy offers Sunny a Potato:
1. A1 confirms a specific incoming gift prompt on P2 and offers ACCEPT/DECLINE without automatically taking control of unrelated menus.
2. A4 lets Luna choose (including DECLINE). No obligatory spoken thank-you.
3. A2 verifies the actual transfer (inventory before/after and game-confirmed effect).
4. A3 records the verified event with giver/recipient/item/game session evidence and makes it available to A4's next decision.
5. A4 may speak about the item later, or remain silent. Do **not** equate speech with an objectively verified transfer.

Also test: canceled offer, missing inventory room, menu replacement, duplicate polling, request timeout, game reload, same farm day replay, night P2 dialogue blocking bedtime, gift rejected, gift acceptance without chat, Sunny giving Guy an item.

## Decision gates
- [ ] Four track reports linked and peer reviewed
- [ ] Architecture meeting notes / unresolved choices documented
- [ ] Event and action contracts proposed, reviewed, versioned
- [ ] Resource ownership and shared resource semantics checked against Stardew actual behavior
- [ ] Save/reload reconciliation and duplicate actions safety specified
- [ ] Python pilot source imported or explicitly supplied for cross-codebase analysis
- [ ] Integration test specification approved
- [ ] Only then code changes and live tests

## Research materials
- [Verified baseline](./ARCHITECTURE_BASELINE.md)
- [Four agent briefs (copy-ready for Codex Cloud tasks)](./RESEARCH_TRACKS.md)
- [Agent instructions](../../AGENTS.md)

## Important limitations
- These documents allocate **research roles**, not four continuously running agent instances.
- GitHub Issues may be unavailable if the repo's Issues feature is disabled. The briefs remain authoritative in this branch until tracking is enabled.
