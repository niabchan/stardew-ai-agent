# Instructions for coding agents working on the Sunny fork

Read [Sunny companion notes](SUNNY_COMPANION.md) and [Phase 1 research charter](docs/sunny-agentic/README.md) before proposing changes. This fork is based on Duckxy's Stardew MCP. **Do not modify upstream** or assume GitHub branch changes deploy to the local game.

## Project facts / boundaries
- Guy is **human P1**, Sunny is **AI-controlled P2**; Luna is the model name used in the Sunny pilot.
- Game-side code is a C# SMAPI mod under `mod/StardewMCP`. The separate Sunny P10–P13 Python/PowerShell pilot ZIPs are **not in this GitHub repo**; mark any assumed logic there *uninspected* until exact source is supplied.
- The core loop objective is **perceive → reflect/decide → act (or STAY) → verify → continue**. Speech is optional and model agency matters; do not enforce thanks, acceptance, optimization, or one-action-per-day quotas.
- Distinguish **intent**, **dispatch**, **tool acknowledgment**, **observed game effect**, **persisted save**, and **model-authored narrative**.
- Same farm day after save reload can represent an abandoned timeline. Avoid stale locks, hallucinated memories, duplicate gift responses or game actions.
- One controller per save. MCP actions may have asynchronous or delayed outcomes; never blindly retry on timeout.
- The P2 menu may contain a gift choice or an unrelated/canceled dialogue. Never press Yes/No on an unverified prompt or dismiss an unrelated menu.
- No API keys, private paths, save data, personal identifiers, logs, or secrets in GitHub commits.

## Phase 1 mode (current milestone)
**Research only.** Agents A1–A4 must inspect source, identify verified facts and unknowns, propose contracts/tests, then return reports. Do not implement behavior or merge PRs as part of research. Follow [track briefs](docs/sunny-agentic/RESEARCH_TRACKS.md).

## Future implementation gates (after design approval)
- Keep PRs small, limited in ownership and explicit in contract changes.
- Preserve split-screen and local MCP semantics; no unauthorized live game calls.
- Run relevant automated tests and record full commands/results and any baseline failures. Do not claim passing builds or gameplay without having run them.
- Human operator validates actions on a `Test_` save before risky behavior merges.
- Use exact code references; keep speculative work clearly labeled.

## Cross-agent code ownership for design, not an exclusive lock
- A1: interactions/tools/action life cycle.
- A2: inventory/ownership/gifts/shared resources.
- A3: perception/events/memory/save branches.
- A4: companion/social bridge/initiative/decision context.
Any shared API (especially `SocialTools`, `Perception`, `AgentHttp`) requires cross-agent review before implementation.
