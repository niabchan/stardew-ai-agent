# Research briefs for four coding/research agents

> These are **ready-to-paste Codex task prompts**. They do not start tasks until an operator creates them in a Codex environment connected to this repo.
> All four tasks use the same **baseline**: [`ARCHITECTURE_BASELINE.md`](./ARCHITECTURE_BASELINE.md), [team charter](./README.md), root [`AGENTS.md`](../../AGENTS.md).
> **Scope in Phase 1 = read-only code research and report**. Write reports in task workspaces or propose documentation-only PRs. No C# behavior changes, deployed mod changes, or live game calls.

## Shared completion template
Every agent returns a research report with headings:
1. **Observed code map** — exact relative file paths, relevant classes/method names and what the code demonstrably does.
2. **Boundaries / not inspected** — what depends on external P10–P13 pilot ZIPs and must not be guessed.
3. **Gaps & failure modes** — classify by severity and reproduction preconditions.
4. **Contracts proposed** — event/action inputs, outputs, ownership, persistence, idempotency.
5. **Tests** — isolated unit tests plus at least one in-game integration test requiring operator.
6. **Dependencies & questions for the other three agents**.
7. **Smallest safe first implementation PR proposal**, no code yet.

Reports must distinguish *observed facts* from *hypotheses*. Note that `main` changes after this charter may need refreshed refs.

## Agent A1 — World interaction & action lifecycle
**Role:** investigate how Sunny can act on objects, players and game menus, and verify the outcome without double-dispatching.

**Starting paths:** `AgentTools.cs`, `McpDispatcher.cs`, `AgentRuntime.cs`, `WalkController.cs`, `MenuTools.cs`, `CloseMenuTools.cs`, `Perception.cs`, `AgentHttp.cs`.

**Specific questions:**
- Enumerate action categories, preconditions, menus, pathing and state transitions. Locate `respond`, `interact`, `walk_to`, `go_to_bed`.
- Which responses acknowledge dispatch vs indicate verified game state? Where may post-action snapshots lag?
- How are `p2_menu`, P1 waiting, paused/frozen state, sleep, canceled proposal and temporary P2 action handled?
- Which actions could be unsafe to auto-retry? How can the action lifecycle expose `attempt_id`, `unknown_outcome`, `verified` without touching game state?
- What event detail should A1 send to A2/A3/A4 for **human→AI** gift proposals versus **AI→human** give?

**Minimum tests to propose:** chair sit/stand, P2 `respond` correct option and stale dialogue, timeout/no-repeat, day change after manually cleared menu, action result vs snapshot discrepancy.

**Deliverable name:** `A1_INTERACTION_RESEARCH.md`.

## Agent A2 — Inventory, gifting & shared resources
**Role:** trace every relevant source and sink for inventory items, including personal ownership and cooperative goals.

**Starting paths:** `ChestTools.cs`, `ChestLedger.cs`, `Ownership.cs`, `SocialTools.cs`, `CraftingTools.cs`, `BuildingTools.cs`, `EconomyTools.cs`, `FarmTools.cs`.

**Specific questions:**
- List personal inventory, chest, shipping, crafting, construction and gift transfer paths. Verify game-specific rules rather than assume shared ownership.
- Separate *intent to transfer*, *proposal accepted/rejected*, *actual inventory delta*, *stash retrieval*, *spent resource*.
- How does the C# `SocialTools.give` path behave for AI seats? How does vanilla human gifting differ? Where could auto-accept violate AI autonomy?
- How do quantity, item `QualifiedItemId`, stack, quality, giver, recipient, origin and transfer destination get represented?
- How could Sunny give Potato back to Guy? What happens if Guy's inventory is full or the player cancels?
- For a hypothetical bridge/construction project, identify who must physically carry/pay resources and how chest resources contribute. Do not implement imaginary in-game construction.

**Minimum tests to propose:** Daffodil accepted and verified, Potato transfer, declined or canceled offer with no change, chest item delta vs direct giving, capacity limits, resource acquisition/consumption.

**Deliverable name:** `A2_INVENTORY_RESEARCH.md`.

## Agent A3 — Perception, provenance & memory
**Role:** design a defensible observation and memory model consistent with actual game state and save/reload behavior.

**Starting paths:** `Perception.cs`, `Observation.cs`, `SightLog.cs`, `AgentLog.cs`, `JournalTools.cs`, `Briefing.cs`, `AgentHttp.cs`, `KnowledgeTools.cs`.

**Specific questions:**
- How are events observed, queued, delivered, consumed, logged, forgotten? Inventory delta evidence vs model claim?
- Recommend a minimal event schema: IDs, session/save/day, source, actor/target, item identity, state, certainty, action attempt, persistence.
- How should **actual observation log**, **Luna-authored diary/reflection**, and **working memory** be separated?
- What happens after reloading an unsaved Day 24 or restarting the Python controller in the same day? Propose branch/reconciliation semantics.
- How can a gift be remembered accurately and surfaced to the next decision without hallucinating or forcing speech?
- Which data is sensitive/local and should never enter repo or tool logs?

**Minimum tests to propose:** duplicate event suppression, stale/missing snapshot, save commit vs abandoned day, narrative contradicting inventory evidence, no diary when going to bed.

**Deliverable name:** `A3_MEMORY_RESEARCH.md`.

## Agent A4 — Companion & human ↔ AI bridge
**Role:** study Sunny's autonomy, dialogue, initiated actions, chat mailbox, friendship/companionship behavior and task collaboration.

**Starting paths:** `SocialTools.cs`, `SpeechQueue.cs`, `Brain/SeatBrain.cs`, `Brain/Prompts.cs`, `Brain/Brains.cs`, `Perception.cs`, `WorldText.cs`, `AgentHttp.cs`. Also request the **external P11 Chat Bridge/P13 gift pilot sources**, which are not in GitHub.

**Specific questions:**
- How does Guy's ordinary chat reach Sunny? What protects against duplicate echo, out-of-range talk, talking to a sleeping player, and spam?
- Map where Luna sees a gift event now versus where P13 only chooses Yes/No. Do not assume external P13 source exists in `main`.
- Define a **react-or-not** policy: may thank, ask about item, store it, defer response, or say nothing. No forced gratitude or forced acceptance.
- Support planned cooperation without assuming optimization: ask clarification, propose contribution, choose STAY/other task.
- Specify interaction contracts needed from A1 (actions), A2 (verified transfers/resources), A3 (grounded and branch-aware memories).
- Analyze model-input size, latency, language consistency and conversation cooldown tradeoffs; don't lock personality into a deterministic timer.

**Minimum tests to propose:** gift accepted with no immediate speech, optional context-aware follow-up, user chat then Luna reply, declined gift, nighttime interruption, collaborative task suggestion.

**Deliverable name:** `A4_COMPANION_RESEARCH.md`.

## Cross-agent design review agenda (after reports)
1. Round-table: **show facts and exact code evidence**, not just suggestions.
2. Agree boundaries for **action intent → game outcome → observation → memory → companion choice**.
3. Walk one accepted gift, one declined gift, one canceled gift and one unsaved replay through the proposed event diagram.
4. Validate construction/resource scenario against Stardew rules.
5. Choose minimal implementation PR ordering and integration tests. No one agent should edit the other's owned domain without a shared design change.

## How an operator can dispatch these
Create a single published **Codex Cloud environment** for `niabchan/stardew-ai-agent`. Start **four independent tasks** using the relevant prompt below. Each task should explicitly read this brief and the shared baseline. Keep each task isolated, review reports, then bring the outputs back to the Orchestrator for integration. This repository and these documents alone do not automatically create or run Codex tasks.
