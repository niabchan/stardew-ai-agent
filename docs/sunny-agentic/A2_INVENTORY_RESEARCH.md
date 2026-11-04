# A2 — Inventory, gifts & shared resources research

Research only, 2026-11-04. Repository `niabchan/stardew-ai-agent`, target `docs/sunny-agentic-architecture-phase1`, inspected commit `11c4aa2fe12a2500d9ff9ad26e09437b40d93f92`. Guy is human P1; Sunny is AI P2. No gameplay code, deployed mod, save, controller or live game action was changed or accessed.

**Fact** denotes inspected source behavior; **Hypothesis** denotes a possible consequence requiring reproduction; **Proposal** denotes a future contract/test. Calls into Stardew APIs establish what this wrapper requests, not a verified audit of the game's internals. Operator pilot outcomes in the baseline remain historical evidence.

Read `AGENTS.md`, `SUNNY_COMPANION.md`, `docs/sunny-agentic/README.md`, `ARCHITECTURE_BASELINE.md` and `RESEARCH_TRACKS.md`. Reviewed [PR #6](https://github.com/niabchan/stardew-ai-agent/pull/6), A1 report head `cb99879e612a22b071201bc11c82d1cc90d6b01a`; the PR was open/draft with no discussion comments returned at inspection. A1 is a dependency proposal, not merged implementation.

## 1. Observed code map

Paths are relative to the repository root; line references use the inspected commit. This maps the requested resource paths and nearby exceptions, not every specialized tool in the game.

| Path / class or method | Fact and evidence limit |
| --- | --- |
| `mod/StardewMCP/Agent/AgentTools.cs:30`, `P`; `:490`, `FindItem/FindIn`; `:509`, `Snapshot/Diff` | `P` is the current screen's `Game1.player`. Lookup chooses exact display/internal name, else first partial match; it does not accept a dedicated stable-ID selector. Generic deltas aggregate by DisplayName, collapsing qualities and distinct IDs with the same label. |
| `Agent/WorldText.cs:111`, `Inventory` | Text lists slots, names, stacks, category and quality; this display is not a structured QualifiedItemId/provenance snapshot. Slot is a current position, not durable item identity. |
| `Agent/SocialTools.cs:151–164`, `OtherAis/Target`; `:287`, `Give` | Targets only active other AI-role seats by seat/name. Human P1 Guy is excluded. A tool description saying “another player” is broader than its implementation. `give` is instant and has no recipient decision prompt. |
| `Agent/SocialTools.cs:287`, `Give`; `:200`, `Tick` | Selects non-tool stack by name, groups sender holdings by QualifiedItemId and Quality, checks requested count, same map and distance ≤4.5 tiles, and synced recipient capacity. Copies `held.getOne()`, removes sender quantity, enqueues item plus giver label. Reply/log precede delivery. Receiver tick calls `addItemToInventoryBool`, otherwise creates debris, then emits `Perception.Notify(...,"gift",...)` even for debris. The queue is static in-memory, not a durable transfer journal. |
| `Agent/ChestTools.cs`, `ChestTool`; `:207`, `ChestWork`; `:299`, `PlanMoves` | Opens via `Interact`, moves via `MenuTools.Take/Put`, closes a menu it opened. List/store/take/all; named items or everything; optional quality/quantity. Store-everything excludes tools, seeds and cooked dishes. Outer move accounting uses QualifiedItemId + quality pack totals; it permits partial completion. Inner selection still uses name/quality. If the target opens a non-chest menu, the error path calls broad `CloseMenu`; this needs A1's unrelated-menu review. |
| `Agent/MenuTools.cs:218`, `Take`; `:258`, `Put` | Clicks whole stacks or individual items, re-fetching menus after clicks; capacity and highlight checks. Generic moved-count feedback uses display-name totals. Shipping take-back is a special last-item path. No stable expected-chest token binds subsequent clicks to the originally observed container. |
| `Agent/ChestLedger.cs:42`, `Tick`; `:62`, `Contents`; `:76`, `Record`; `:132`, `Load` | Per-screen chest menu open/close snapshots; computes net differences by QualifiedItemId + quality. Records closing seat as actor. Persisted `Change` retains label/count/location/tile/seat/owner/day/time, but discards ID and quality as separate fields and has no event/load/attempt ID. Appends local `chests.jsonl`; keeps latest 300 changes. Loading is keyed by log file path. This is a bounded net-change history, not a complete causal inventory ledger or save-commit record. |
| `Agent/ChestLedger.cs`, `Report/OthersChanged/MorningText` | Farm, FarmHouse, Greenhouse and farm-building interiors are scanned for placed player chests; report shows up to 15 stacks per chest plus recent changes. This is not a global all-location resource registry. |
| `Agent/Ownership.cs:34`, `SeatOf`; `:42`, `OwnerOf`; `ClaimCrop`, `GrabFromChest_Prefix/Harvest_Postfix` | Object owner is mapped through an AI-role seat by farmer name; human-owned object may return null. Null does not establish communal ownership. Crop owner is seat ID in soil modData. Taking/harvesting is allowed; cross-owner AI actions can log “theft.” Chest hook runs before actual grab with capacity precheck, so this notice alone is not proof of final quantity moved. These labels are not permission enforcement. |
| `Agent/CraftingTools.cs:57`, `Craft` | Known recipe; 1–99 crafts; checks inventory ingredients and output capacity, calls `consumeIngredients(null)`, inserts output and updates recipe counters. No chest collection passed. Batch may stop after some crafts; number of crafts differs from output quantity. Addition return value is not used as a postcondition. Recipe ingredient keys may be category IDs, not individual item IDs. |
| `Agent/CookingTools.cs:44`, `CookKitchen`; `CookFridges`; `:94`, `Cook` | Cooking uses pack plus current kitchen's fridge/mini-fridges; passes fridge inventories to ingredient consumption, pack first. This is a specific exception to pack-only crafting, not general shared-chest crafting. Fridge consumption need not open a chest menu and text fridge counts aggregate by name. |
| `Agent/BuildingTools.cs:89–128`, `MatchesId/CountItem/TakeItems/Shortfall`; `:167`, `Build` | Counts/removes from calling farmer's `P.Items`, checks `P.Money`. No chest search or another farmer's pack. Materials match qualified ID or `(O)` prefix; qualities are pooled for spending. Catalog reads Robin building data/conditions, excludes building upgrades; requires Robin shop gate and valid footprint. |
| `Agent/BuildingTools.cs:227`, `TryBuildStructure`; `:346`, `UpgradeHouse` | Reflects into game buildStructure with calling farmer; successful call is followed by remaining money/material charge based on before/after counts. Returned errors say “Nothing was charged,” but wrapper does not prove rollback after an exception. House upgrade invokes `upgrade_Yes`; if neither upgrade nor resources changed, directly sets timer and deducts hard-coded cost. Scheduled construction/upgrade is not completed building or saved persistence. |
| `Agent/EconomyTools.cs:30`, `Pay`; `CheckWallets` | Shared wallet refuses pay; separate wallets debit caller and credit selected recipient. Reuses AI-only `SocialTools.Target`, so pay also cannot address human Guy here. Build/buy use current farmer's money; actual wallet mode controls whether that balance is pooled. Do not assume separate wallets from configuration advice. |
| `Agent/AgentTools.cs:1084`, `Buy`; `:1165`, `Ship`; `:1195`, `Eat/EatSlot` | Buy uses ShopMenu currency/trade checks and purchase function; held output/remainder may become debris. Ship walks to bin, removes selected quantity and adds copied stack to `farm.getShippingBin(P)`; estimated value is not an observed overnight payout. Take-back supports last shipped item. Eating delegates to game animation. Money, recipes, physical items and debris are distinct sinks/results. |
| `Agent/AgentTools.cs`, `Plant/Harvest/UseTool/Interact`; `Agent/FarmTools.cs:467`, `HarvestAll`; `:803`, `PlantTool` | Planting spends seeds and claims crop ownership; harvest/tool actions request vanilla effects and report inventory changes. Farm macros batch existing primitives and can stop partway. Cleared terrain or harvested crop does not by itself prove every dropped resource entered Sunny's pack. |
| `Agent/CraftingTools.cs`, `Place`; `Agent/AgentTools.cs:746`, `Interact`; `Agent/CloseMenuTools.cs`, `ClaimBeforeClose/ClaimGrabMenu` | Place uses game placement then checks decreased ID total; held-item interaction can load/use/gift through game action path. Closing one-shot grab/letter menus can claim items (chest source excluded). Inventory changes therefore have sources beyond explicit give/chest calls. |

### Guy → Sunny: incoming vanilla proposal

**Fact:** baseline P13 reports Daffodil and Potato accepted by Luna and operator-confirmed in Sunny's pack. Actual P13 parser/ledger is external and uninspected. Repository `AgentTools.Respond` acts on the current dialogue and option index, without verifying giver, item or transfer. There is no audited incoming vanilla gift transaction adapter in these paths.

**Proposal:** keep offer observed, model choice, response dispatched, proposal resolution and item receipt separate. Capture exact P2 prompt/response mapping, Guy and Sunny observations, item ID/quality/count, attempt and fresh observation references. Accept is not receipt; prompt disappearance is not rejection. Declined/canceled offers need resolution evidence and no unexplained transfer, rather than simply a missing positive delta. `Guy canceled the request.` is a cancellation message, not a fresh offer or default decline. Unrelated menus remain untouched.

### Sunny → Guy: returning a Potato

**Fact:** `give(to="p1" or "Guy")` fails target selection while Guy is human. Do not change Guy to AI to bypass this boundary. Existing generic `interact(x,y,holding="Potato")` selects the held item, walks adjacent and calls `Game1.tryToCheckAt`; source comments acknowledge possible gifting. It has no farmer-ID target, gift-specific eligibility/consent/result verifier, quantity or quality selector. Therefore it is only a **candidate vanilla affordance**, not a verified direct-return recipe. Game assemblies/menu semantics were not inspected; whether this exact call initiates the correct human offer must be established on a Test_ save. Do not invent a `give_to_human` tool.

**Proposal:** A1 first verifies supported farmer targeting and prompt lifecycle. If vanilla offers are available, Sunny chooses whether to offer; Guy chooses accept/decline, with cancellation/timeout/full-pack outcomes kept distinct. A2 requires Sunny decrement and Guy increment for the same item variant and known quantity, tied to that offer. Full inventory must not be claimed to reject or drop automatically without testing vanilla behavior. AI-only `Give` debris fallback does not establish human-gift rules.

A supported indirect alternative is Sunny storing Potato in a mutually agreed chest, then Guy manually retrieving it. That is two resource movements, not completed direct gifting at deposit time. Full chest/pack or cancellation may leave partial progress. Chest-owner labels neither grant consent nor verify Guy's receipt. Do not call this “gave Potato back” until recipient evidence supports it; indistinguishable stacks may make exact historical origin unknowable.

### Shared chests, project materials and construction

**Fact:** access, recorded owner, social agreement and actual inventory location are different. There is no inspected communal/reserved-project flag or hard resource reservation. Existing “theft” wording may conflict with agreed cooperation, while human ownership may be shown as null. A report must not translate null into “free to take.” ChestLedger sees net contents during menu sessions; cooking, direct mutations, net-zero put/take and changes outside observed sessions need separate evidence. Assigning all net change to the closing seat can misattribute external changes; that is a **hypothesis** to reproduce, not proof that concurrent chest access is permitted by vanilla locks.

**Proposal scenario:** Guy and Sunny agree on an actual Robin catalog building. Choose an executor and wallet mode; record materials by actual container and consent. Sunny may gather, store or withdraw resources, decline the plan, or do something else. For this wrapper's build, the executor must carry required materials and have access to required money. Materials in Guy's pack or a chest do not satisfy Sunny's `Shortfall`. Withdraw first, re-observe pack, then separately authorize/dispatch build once. A project reservation is advisory until enforced by an approved implementation; recheck immediately before spending. Shared wallet spending affects the same pool; separate wallet funds are not automatically communal and current pay cannot send to Guy.

“Build a bridge” needs a named affordance. `BuildingTools` is Robin's catalog, not arbitrary infrastructure. `Agent/JojaTools.cs`, `JojaRoute` catalog, lists Quarry Bridge Repair at 25,000g; `JojaBuyProject` checks membership/project state/location/money, clicks the form, observes payment and learns mail flags, with completion expected later. This is a specific gold project, not a wood/stone construction abstraction. Beach bridge/Community Center paths and game implementation were not audited. Never select a bridge route, cost, membership change or permanent world effect from a hypothetical goal alone. Verify the requested bridge, actual prerequisites and eventual world state before implementation.

## 2. Boundaries / not inspected

- External P10–P13 Python/PowerShell ZIPs, actual P13 recognition/option mapping, controller locks, retry and persistence code: not supplied or inspected.
- Stardew/SMAPI implementation assemblies, installed versions/config, vanilla human gift classes/capacity/cancel behavior, chest locking and exact construction API side effects: unverified. No live saves, DLLs, private logs or deployed paths accessed.
- Specialized fishing, animal, mining, bundle/donation and other late-game sources/sinks were not exhaustively audited. The core registry and nearby farming/cooking/Joja paths identify why a universal inventory ledger needs a broader later audit.
- A1 report was reviewed, with key inventory claims independently checked above; its baseline test results are attributed to A1, not rerun by A2. A3/A4 reports were not available for review.

## 3. Gaps & failure modes

Severity is design priority, not a newly reproduced incident.

| Priority / evidence | Preconditions and failure | Required handling |
| --- | --- | --- |
| Critical; fact + hypothesis | Lost reply after respond/give/ship/build; blind retry can repeat effects. No A2 transaction ID/dedup at these mutation points. | A1 attempt reconciliation; unknown outcome blocks automatic replay. |
| Critical; fact | Incoming prompt replaced/canceled before index-based response; model intent can reach unrelated dialogue. | Execution-time A1 prompt guard; no default acceptance or dismissal. |
| High; fact + hypothesis | AI give removes sender before receiver tick; process failure may lose pending item; changed capacity may cause debris. | Distinguish queued/inventory/debris; test interrupted delivery and game API partial-add semantics before claiming conservation. |
| High; fact | “gift” perception notification also fires when item fell at feet. | Do not upgrade notification to recipient inventory receipt. |
| High; fact | Label totals merge variants; chest persisted changes lose structured IDs/quality. | Typed snapshots and preserved evidence; ambiguous remains unknown. |
| High; hypothesis | Other acquisition/consumption overlaps gift window; equal net pack deltas suggest false attribution. | Causal transaction evidence or controlled window; track intervening mutations. |
| High; fact + hypothesis | Chest/reload history appends outside game save; same-folder unsaved reload may retain abandoned history. | A3 branch reconciliation; a written JSONL record is not save commitment. |
| High; fact | Null human ownership, advisory theft labels, no reservations; project planner treats chest contents as freely spendable. | Explicit agreement/permissions, executor/container mapping and fresh affordability check. |
| High; hypothesis | Reflected build call throws after partial world/payment effect; error text is treated as guaranteed no charge. | Observe money/materials/buildings before retry; no inferred rollback. |
| Medium; fact | Partial craft/chest/farm batches and shipping estimate reported as goal completion. | Per-item actual quantity and project ordered/underway/completed states. |
| Medium; fact + hypothesis | Menu changes to another chest during multi-click macro. Type checks alone may allow wrong-container movement. | A1 expected container identity/revision and no-click refusal on mismatch. |

## 4. Contracts proposed

Everything in this section is a **Proposal**, not an existing schema or runtime guarantee.

### Evidence and item identity

`InventoryObservation v1`: opaque observation ID, save ID, load session ID, branch ID, seat/farmer reference, container reference, capture sequence/game tick/day/time, freshness/completeness, and entries `{qualified_item_id, quality, quantity, slot, stack_signature, display_label}`. Labels are for display; unknown IDs are null, never guessed from language. `stack_signature` covers relevant stackability metadata where available; ID + quality alone may not distinguish flavored/modded items. Slot/signature does not imply a globally persistent item UUID. Preserve actual consumed/output variants even where recipe costs pool qualities/categories.

Containers distinguish personal inventory, chest/fridge, shipping, pending delivery, held menu item, debris and world object. Chest reference includes location/tile plus observed instance/revision; moved/replaced chests invalidate stale references. Log identity locally without publishing real farmer IDs, save paths or private data. Snapshots on two screens are not assumed atomic; include their separate freshness and intervening mutations.

### Transfer and spending records

`TransferIntent v1`: A1 attempt identity, controller lease, save/load/branch, actor, intended recipient, route (`vanilla_offer`, `ai_queue`, `stash`), item selector/quantity, exact source/destination, expected prompt/container revision, and choice provenance. A4 owns voluntary intent/consent context; it is not proof of ownership or effect.

`TransferEvidence v1`: same identities, offer/response observations, tool acknowledgment, source/target before/after references, typed deltas, queue/debris evidence, actual moved quantity and disposition, causal attribution and reason. States must distinguish `offered`, `response_dispatched`, `accepted_choice`, `declined`, `canceled`, `queued`, `inventory_received`, `stash_deposited`, `stash_withdrawn`, `debris_created`, `partial`, `unknown_outcome`, `contradicted`. Prefer independent resolution/execution/delivery fields over a single linear enum: a choice can be accepted with delivery still unknown.

A confirmed inventory transfer requires matching source loss and destination gain of the actual variant/quantity plus causality (transaction/game evidence or controlled observations excluding intervening changes). Matched net deltas alone establish correlation. Missing observation remains unknown. Sender loss alone cannot establish recipient; recipient gain alone cannot identify giver. Zero net change is not proof no transient transfer occurred. Debris is not recipient inventory receipt. Stash retrieval is not automatically a gift or preservation of original giver provenance.

`ResourceSpend v1`: executor, actual wallet mode/scope, materials/currency before/after, input recipe/catalog version and cost, exact project/recipe ID, output/world evidence and actual quantities. Track acquired → available → advisory reserved → carried → spent separately; build ordered → underway → completed separately. Craft, cooking, shipping and spending are conversions/sinks with their own equations, not item transfers requiring identical output. Shipping payment and save commitment are later observations.

### Ownership, publication, idempotency and persistence

- A1 owns dispatch attempts, execution/prompt/container validation and timeout state. A2 owns resource evidence and verification predicates. A3 alone publishes/deduplicates grounded resource events and manages durable local storage/save branches. A4 receives the grounded context and independently decides reaction or silence. No competing “gift_accepted” producers.
- Key evidence by save/load/branch + attempt/offer + observed transition + item/container identity; repeated polling returns the same evidence. Multiple partial movements stay distinct. Do not deduplicate unrelated equal items by day/name/count. A3 assigns canonical event IDs; duplicate publication must not cause another action.
- Preserve source evidence and superseding reconciliation rather than silently rewriting history. Restart after ambiguous dispatch never replays spending. Queue persistence cannot promise exactly-once effects across a crash without game reconciliation.
- Save/reload creates a fresh load epoch; unsaved abandoned-branch evidence is not current possession or a definite retained memory. Local JSONL persistence is not game save persistence. A3 supplies explicit save-checkpoint evidence; until then `save_commit_state=unconfirmed`.
- Keep personal ownership, access capability, permission agreement, project allocation and provenance separate. Gathering for a goal does not obligate contributing it; no auto-accept, mandatory thanks or enforced optimization.

## 5. Tests

### Validation actually performed

Read-only source inspection and documentation review at the pinned baseline; no automated gameplay tests, C# build or live integration tests executed by A2. Existing `mod/StardewMCP.Tests/StardewMCP.Tests.csproj` links selected game-free sources; it does not link ChestTools/ChestLedger/Ownership/SocialTools/CraftingTools/BuildingTools as live game handlers. A1's reported test passes do not establish these transfers. Report publication validation should confirm a single added Markdown file against the target and no gameplay diff.

### Proposed isolated unit/contract tests — not implemented or run

| Seam | Required assertions |
| --- | --- |
| Typed snapshot/delta reducer | Stack split/merge preserves totals; quality/ID/name collisions remain distinct; metadata mismatches stay ambiguous; stale/incomplete/out-of-order snapshots do not become negative evidence. |
| Transfer verifier | Ack/accepted option/notification alone cannot confirm receipt; matching but causally ambiguous deltas remain unknown; source-only, recipient-only, debris and partial quantities have separate outcomes. |
| Offer/attempt adapter with A1 | Duplicate/concurrent attempt dispatches once; canceled/replaced/localized prompt and wrong seat/container cause zero clicks; delayed result reconciles same attempt, never a new transfer. |
| Chest evidence reducer | Deposit and withdrawal are separate; +1 then -1 net zero does not prove no activity; non-menu fridge consumption is explicitly outside menu-ledger coverage; reopened/replaced chest uses a new revision. |
| Resource planner | Chest stock does not satisfy pack-only build/craft; cooking includes only supported fridge sources; category recipes and multi-output crafts retain actual consumed/produced variants; advisory reservation cannot guarantee availability. |
| Wallet/project verifier | Shared vs separate scope, human target unsupported, payment vs project completion, reflected-call partial failure and missing final observation all classified correctly. |
| A3 replay fixtures | Duplicate event suppressed; unsaved same-day reload abandons evidence; local log restart cannot imply saved item; equal new gifts on same day remain separate. |
| A4 choice fixtures | Acceptance with silence, decline, defer/STAY and alternative cooperation remain valid; narrative cannot promote unknown transfer to confirmed. |

### Proposed operator integration tests — all unrun

Use a backed-up `Test_` save, one controller and recorded source/DLL/config version locally. Operator performs human actions; research agents do not send game calls. Capture per-screen before/after typed evidence, prompt transitions and intervening changes; publish only synthetic/redacted fixtures.

1. **Daffodil Guy→Sunny:** identify actual ID/quality/count in game, exact P2 offer and choices. Luna freely chooses; for ACCEPT verify Guy decrement/Sunny increment and one grounded event; no immediate speech required. Repeat with Potato and a split stack/quality variant. Do not assume option 0 is universally ACCEPT.
2. **Decline/cancel/replacement:** record both inventories, decline a valid offer; separately cancel before decision and replace with unrelated dialogue. Assert no attributed transfer and zero stale clicks. Positively identify cancellation text; do not auto-dismiss it. If observations are incomplete, expected result is unknown rather than invented nontransfer.
3. **Sunny→Guy Potato:** first confirm `give` rejects human P1 without mutation. Separately have operator validate whether the exact held-item interaction can initiate vanilla offer to Guy. Test Guy accept, decline, cancel, full inventory and stack room without empty slots; record actual behavior rather than borrowing AI-queue semantics. Unsupported interaction is a valid finding, not a reason to add code in research.
4. **Stash vs gift:** Sunny deposits a measured Potato quantity in agreed chest, Guy manually retrieves later. Check both legs/container revisions, no direct-gift event at deposit, full chest/recipient pack, interrupted macro and replacement menu. Confirm human owner is not inferred communal from null.
5. **AI queue (separate fixture with another AI seat):** verify sender removal, delayed recipient insertion and capacity-change debris; observe possible partial-add behavior. Controlled interrupted-process test only with operator preparation/backups; do not infer crash recovery from a normal pass.
6. **Acquire/consume:** gather materials and verify pack receipt versus uncollected debris. With materials only in chest, verify craft/build affordability remains insufficient. Withdraw and recheck; craft known recipe, record exact consumption/output and partial-batch/capacity behavior. Cook from fridge without chest menu and verify ledger coverage gap separately.
7. **Actual construction:** select catalog project, explicit executor and wallet mode; validate shop/footprint/missing-material gates. Measure pack and balance before/after one order, inspect building/timer, then completion and save/reload. Separately test shared and separate wallet scope; do not spend on a hypothetical bridge or irreversible membership change as incidental setup.
8. **Timeout/reload:** controlled lost response after a mutation, no blind resend; reconcile source/destination/world evidence. Save and reload, then separately abandon unsaved same-day timeline. A3 must mark correct branch/commit without stale gift, spend or project replay. Bedtime after operator clearing of exact cancellation message is A1's joint lifecycle test.

## 6. Dependencies & questions for the other three agents

- **A1 / PR #6:** agree on the exact prompt/attempt envelope, guarded dispatch and expected container token. Supply actor/recipient/item offer evidence plus sender-removal/queue/insertion/debris transitions, not generic gift text. Independently confirmed AI-only target restriction and delayed queue behavior. A1's fresh observation/execution distinction is required before A2 can trust a post-action snapshot. Include all broad cleanup routes (CloseMenu, chest error path, sleep/watchdogs), since a respond-only guard is insufficient. Validate human farmer targeting for held-item interaction before promising Potato return. A1's proposed pure attempt reducer can precede wiring, but must consume A2 verification fixtures; it must not label acknowledgment “transfer verified.”
- **A3:** define load/branch/save checkpoints, local retention, canonical event IDs and causal evidence storage. Review ChestLedger same-path reload and bounded label-only history; do not migrate it as authoritative inventory history. What direct screen evidence is available for human P1 without controlling P1? Who reconciles queued gifts and abandoned observations after reload?
- **A4:** obtain exact external P13/P11 sources before cross-controller claims. Present known/unknown item and actual route to Luna; separate willingness to contribute from possession, permission and capacity. How should agreed shared-chest use coexist with current theft wording? Returning an item, declining and silence remain voluntary choices.
- **Joint unresolved decisions:** authoritative vanilla offer classifier and quantity rules; required evidence when both inventories cannot be observed atomically; metadata identity; whether advisory project reservations are useful; naming of accepted-choice versus received events. Shared SocialTools/Perception/AgentHttp changes need cross-track review before implementation. No approval or implementation is implied by this report.

## 7. Smallest safe first implementation PR proposal

**After design approval only:** add an unwired game-free typed inventory-delta/transfer-verification reducer plus synthetic fixtures for variants, partial outcomes, source-only evidence, debris, causal ambiguity, stale snapshots and branch invalidation. Agree schema/ownership with A1/A3/A4 first. Keep scope in a new pure module and tests; no gameplay hooks, prompt clicking, chest permission changes, persistence migration or external pilot import.

Then propose additive per-screen typed observation adapters and evidence hooks in separate reviewed PRs; only afterward consider guarded vanilla offers, queued-delivery reconciliation or resource planning. Operator Test_ integration gates precede risky behavior merges. This research PR changes documentation only and must remain unmerged as part of this task.
