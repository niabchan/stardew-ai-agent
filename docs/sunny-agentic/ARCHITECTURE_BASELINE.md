# Architecture baseline — Sunny (read-only inspection)

**Source:** `niabchan/stardew-ai-agent` `main` reviewed 2026-11-04, beginning at merge commit `4bae8d2`. File links below are entry points, **not** proof that all internals or external Python pilots have been audited.

## Runtime topology (observed)
- **Game-side:** SMAPI mod under [`mod/StardewMCP/`](../../mod/StardewMCP/) hooks Stardew Valley. Relevant sources include [`Agent/AgentTools.cs`](../../mod/StardewMCP/Agent/AgentTools.cs), [`Agent/McpDispatcher.cs`](../../mod/StardewMCP/Agent/McpDispatcher.cs), [`Agent/AgentHttp.cs`](../../mod/StardewMCP/Agent/AgentHttp.cs), [`Agent/Players.cs`](../../mod/StardewMCP/Agent/Players.cs), [`Agent/AgentRuntime.cs`](../../mod/StardewMCP/Agent/AgentRuntime.cs).
- **Seat control:** P1 human Guy, P2 AI Sunny; HTTP MCP supports seat-scoped `/mcp/p2` as documented in `AgentHttp.cs`. `/api/state` is a game-state snapshot, not an event-sourcing ledger.
- **Model orchestration:** Game-side [`Brain/SeatBrain.cs`](../../mod/StardewMCP/Agent/Brain/SeatBrain.cs), [`Brain/Prompts.cs`](../../mod/StardewMCP/Agent/Brain/Prompts.cs) and [`Brain/Brains.cs`](../../mod/StardewMCP/Agent/Brain/Brains.cs) exist; the distinct external Sunny P10–P13 Python/PowerShell loop uses Luna to choose actions for pilots and is **not committed** here. Distinguish these two control paths during research.
- **Prototypes:** Prior experimental P10 wake → P11 Cabin → P12 bedtime → P13 incoming-gift dialogue ran as local ZIP-based scripts. **Uninspected in this repository.** Study provided ZIP/source before designing refactors across C# and Python.

## Existing relevant C# components
| Area | Starting evidence | Research question |
| --- | --- | --- |
| General actions/menus | [AgentTools](../../mod/StardewMCP/Agent/AgentTools.cs), [MenuTools](../../mod/StardewMCP/Agent/MenuTools.cs), [CloseMenuTools](../../mod/StardewMCP/Agent/CloseMenuTools.cs), [WalkController](../../mod/StardewMCP/Agent/WalkController.cs) | Which return values verify state, which only acknowledge command execution? What is safe to retry? |
| P2 observation/interruptions | [Perception](../../mod/StardewMCP/Agent/Perception.cs), [Observation](../../mod/StardewMCP/Agent/Observation.cs), [WorldText](../../mod/StardewMCP/Agent/WorldText.cs) | How are events created/queued/consumed, and which are lost on restart? |
| Gifts/social/chat | [SocialTools](../../mod/StardewMCP/Agent/SocialTools.cs), [SocialTools P1 chat bridge PR #3](https://github.com/niabchan/stardew-ai-agent/pull/3) | AI-side `give` and human→AI in-game proposal have different semantics; how to unify without auto-accept? |
| Inventory/chests | [ChestTools](../../mod/StardewMCP/Agent/ChestTools.cs), [ChestLedger](../../mod/StardewMCP/Agent/ChestLedger.cs), [Ownership](../../mod/StardewMCP/Agent/Ownership.cs) | ChestLedger detects menu-open/close inventory deltas; what changes occur outside this path? How are item identities verified? |
| Diary/log/state | [AgentLog](../../mod/StardewMCP/Agent/AgentLog.cs), [JournalTools](../../mod/StardewMCP/Agent/JournalTools.cs), [AgentHttp](../../mod/StardewMCP/Agent/AgentHttp.cs) | Separate factual observation log, model-authored diary, and uncommitted after reload. |
| Sleep/change of day | [Bedtime](../../mod/StardewMCP/Agent/Bedtime.cs), [AgentTools](../../mod/StardewMCP/Agent/AgentTools.cs), [PR #4](https://github.com/niabchan/stardew-ai-agent/pull/4) | Journal now optional for bedtime; P2 menus can still block; how to handle completion/cancellation safely? |
| Companion decision | [Brain/Prompts](../../mod/StardewMCP/Agent/Brain/Prompts.cs), [SpeechQueue](../../mod/StardewMCP/Agent/SpeechQueue.cs), [SocialTools](../../mod/StardewMCP/Agent/SocialTools.cs) | What gets into the next Luna decision, and when does an incoming gift change context? |

## Confirmed pilot evidence from operator gameplay (not automatically checked by repo CI)
- **P12:** A configured bedtime led to confirmed farm day transitions 22→23 and 23→24 without a required diary; on Day 23 a lingering P2 dialogue needed manual dismissal first.
- **P13:** Incoming Daffodil and Potato offers were recognized, Luna chose ACCEPT, `respond(option=0)` was sent to P2, and the operator confirmed both items reached Sunny's inventory. The P13 parser and loop are external ZIP-based Python, not yet reviewed here.
- **P13 failure path:** After declining a canceled gift, a leftover `Guy canceled the request.` dialogue blocked sleep until it was dismissed. Do not describe this as an end-to-end unattended pass.
- **P11:** Successful chair interaction, TV, speaking, STAY, and morning wake were observed. A few post-action snapshots disagreed with endpoint coordinates; verify actual state before asserting position.

## Proposed contracts — design ideas, NOT implemented
An event model might carry:
```json
{
  "schema_version": 1,
  "event_id": "example-uuid-or-stable-game-event-id",
  "save_id": "opaque-save-identity",
  "session_id": "load-instance-id",
  "farm_day": 24,
  "event_type": "item_transfer",
  "actor_seat": "p1",
  "target_seat": "p2",
  "item_id": "(O)18",
  "quantity": 1,
  "source_kind": "game_inventory_delta",
  "verification": "confirmed",
  "action_attempt_id": "optional-id",
  "persisted_after_save": false
}
```
**This is a discussion seed, not a settled schema.** Verify the actual item ID in game before adopting this example; keep displayed labels separate from stable IDs. Event IDs must be idempotent; action intent, dispatch, observed result, save commitment, and stale/reload branch status must not be conflated.

Suggested lifecycle: **intent → eligibility checks → dispatch (once) → observation → verified outcome (or uncertain/failure) → optional memory/reflection → persistence/branch reconciliation**. The model may react or remain silent independently of transfer verification.

## Cross-track design decisions required
1. **Event ownership:** Which subsystem is sole producer of `gift_accepted`? Distinguish response accepted from inventory verified.
2. **Clock and snapshot:** game clock vs wall clock; stale `/api/state` snapshot; menu transition sequencing; timeout cannot imply action never happened.
3. **Save/reload:** same farm day loaded again must not resurrect stale action locks or create contradictory “definite memories”; journal is optional.
4. **Resource model:** personal inventory, chest inventory, shared farm resources, building/crafting checks, who spends what; validate Stardew's game rules.
5. **Agency:** receiving a gift should not force speech; a project goal should not force cooperation; world actions need explicit game/tool affordances.
6. **Operational safety:** one controller per save; use a `Test_` save for integration tests; no secrets or user file paths in commits.

## Initial acceptance-test outline
With a controlled save, offer a Daffodil from Guy to Sunny:
- Confirm exact P2 dialogue before action and both Yes/No choices;
- Let Luna accept or decline without a hard-coded preference;
- Confirm actual transfer **if** accepted; verify nontransfer if declined;
- Record provenance with one event, deliver it to the next decision, no obligatory response;
- After game save, reload and verify what memory is legitimately retained;
- Repeat with canceled offer and bedtime-blocking message; never auto-dismiss unrelated menus.

## Status
Phase 1 research is open. No implementation PR is authorized by this baseline alone.
