# A4 — Companion, communication & agency research

Research only, 2026-11-04. Repository `niabchan/stardew-ai-agent`; target `docs/sunny-agentic-architecture-phase1`; inspected baseline `11c4aa2fe12a2500d9ff9ad26e09437b40d93f92`. Guy is human P1, Sunny is AI P2, and Luna names the external pilot's decision model. No gameplay code, live game actions, deployed DLLs, saves or private logs were accessed or changed.

**Fact** means inspected repository behavior. **Hypothesis** means a possible failure requiring reproduction. **Proposal** means a future contract/test, not implemented protection. Historical operator observations in the baseline are attributed evidence, not tests performed here. References below are relative paths at the pinned baseline; refresh before implementation.

Read `AGENTS.md`, `SUNNY_COMPANION.md`, and all documents present in `docs/sunny-agentic/`: charter, baseline, research tracks and the local untracked A1 report (left untouched). Reviewed the complete research diffs from [PR #6 / A1](https://github.com/niabchan/stardew-ai-agent/pull/6), head `cb99879e612a22b071201bc11c82d1cc90d6b01a`; [PR #7 / A2](https://github.com/niabchan/stardew-ai-agent/pull/7), head `180638791d747237a77f4537a9d4e5dee9d07877`; and [PR #8 / A3](https://github.com/niabchan/stardew-ai-agent/pull/8), head `6dc8b9916641fea006f1d4d0f86d7cff06089156`. All three were open drafts. Their proposed contracts are dependencies, not merged features.

## 1. Observed code map

### Guy's chat → Sunny's next decision

| Source / method | Fact and limit |
| --- | --- |
| `mod/StardewMCP/Agent/SocialTools.cs:41`, `Apply`; `:56`, `ReceiveHumanChat_Postfix` | Harmony postfix on `ChatBox.receiveChatMessage` relays only world-ready, screen-0 human, ordinary `chatKind=0` local self-echo from the current farmer and current chat box. Blank input is ignored. This screens out other screens' multiplayer echoes; it is not a durable message-ID deduplicator. Slash commands are outside the intended ordinary-chat route. |
| `SocialTools.cs:56`; `Agent/Players.cs:116`, `ScreenState.Sees` | Human chat listeners are active AI seats whose cached screen sees the speaker: same unique map and viewport contains standing pixel. This is viewport eligibility, not a fixed chat radius. No explicit sleeping, quiet-mode or conversation-consent check exists in these predicates. Cached state can lag. |
| `SocialTools.cs:166–195`, `Clean`, `Clip`, `Deliver`, `TakeMail` | Newlines become spaces; text clipped to 240 UTF-16 code units. Per-seat in-memory inbox retains 30, drops oldest, then drains all and displays last 20 with omission count. It has no durable cursor, message identity, acknowledgment or replay. Repeated identical human messages are not suppressed by this path. |
| `Agent/Perception.cs:230`, `OnSay`; `Mentions` | Stores last heard text as a claim. Case-insensitive bounded `@name` or `@p2` triggers a short-only mention notice for an eligible listener. Ordinary unmentioned chat enters mail without this interrupt trigger. No mention-specific spam cooldown is present. |
| `Agent/AgentRuntime.cs:363`, `Lane.Finish`; `Agent/ToolDef.cs`, `Mail`; `Perception.TakeMail` at 195 | Eligible tool completion appends consumed mail when `Tool.Mail` and reply not already completed. Perception drains its own queue, prints only non-null details (last 12), then social mail. Mail is consumed before proof of client/model receipt. Short-only events need interrupt-result text or separate social mail for their meaning. |
| `Agent/Brain/SeatBrain.cs:117`, `PlayDay`; `:300`, `RunTool` | Built-in loop awaits runtime tool results, adds them as tool messages, then asks the model again. That is a concrete next-decision route for delivered mail. There is no direct chat-push-to-model call here; a model request already in flight does not receive newly queued mail through this code. External Luna prompt assembly is uninspected. |

Thus the observed built-in route is **human local chat echo → visibility-filtered social inbox → optional mention event/safe interruption → eligible tool result → conversation tool message → next model call**. Loss, truncation and delayed completion can break delivery. Chat receipt proves that text was said, not that the content is true or that Sunny agreed to obey it.

### Sunny speaking, initiating and giving

| Source / method | Fact and limit |
| --- | --- |
| `SocialTools.cs:113`, `All`; `:241`, `Say` | `say`, `emote`, `give` are instant. Say cleans/clips text; computes visible AI and human listeners; queues bubble/chat for speaker plus listener screens; delivers AI inbox text and perception mentions; logs listener IDs. Human Guy can hear Sunny here even though `give` cannot target him. The response's “Heard by” means eligibility at enqueue, not human attention or acknowledgment. |
| `SocialTools.cs:200`, `Tick`; `:267`, `ShowChat`; `SpeechQueue.cs`, `Add/Advance/Showing` | Speech appears serially per unique location; different places can show concurrently. Duration uses text length and `ChatSeconds`; queue clock does not advance while paused. Screen targets are captured when speech is enqueued. `Shown` prevents redrawing the same queued line into one screen's chat repeatedly. No semantic-repeat filter, TTL, queue capacity or per-speaker rate limit exists in `SpeechQueue`. |
| `SocialTools.cs:151–164`, `OtherAis/Target`; `:287`, `Give`; `:200`, `Tick` | Give targets active other AI seats only, not human Guy. It checks nearby location, stack/quality quantity and synced capacity, removes sender items and queues delivery. Recipient tick inserts or creates debris, then issues generic `gift` notification in either case. There is no recipient choice in this AI-queue route. Sender reply is earlier than recipient delivery. This independently corroborates A1/A2. |
| `Agent/AgentTools.cs`, `Interact/Respond`; `Agent/WorldText.cs:67`, `MenuState` | Held-item interaction is only a candidate human-gift affordance pending game validation. Respond uses current dialogue/index; WorldText shows text and numbered options without stable prompt token. Neither establishes a verified Guy→Sunny receipt or a supported Sunny→Guy transaction. A1/A2 own those mechanics. |

Sunny can already choose to call `say` without incoming chat, approach someone through movement, emote, or select available activity tools. There is no inspected dedicated cooperative-goal negotiation protocol. Do not advertise `give(to=Guy)` or change Guy's role to work around its AI-only selector. Agreed chest deposit/retrieval is a possible indirect contribution, with two separately verified movements, not direct delivery at deposit time.

### Activities, events and model-authored memory

| Source / method | Fact and limit |
| --- | --- |
| `Agent/Brain/Brains.cs`, `StartAll/OtherPlayers/Tools` | Starts built-in brains for configured AI seats with provider settings, shares tool definitions, identifies human versus AI companions in system input. This manages built-in instances, not a lease excluding external controllers. |
| `SeatBrain.cs:79`, `Run`; `:117`, `PlayDay` | Builds a system prompt per day, obtains briefing, asks the model and executes requested tools sequentially. Text outside tools is logged as `think`, not sent through `say`. No-tool responses get nudged; `++idle > 3` releases on the fourth consecutive no-tool response until day changes. Daily token budget also releases until day change. There is no explicit semantic STAY decision handled here. A wait/rest tool is not equivalent to a durable voluntary STAY policy. |
| `SeatBrain.cs:217`, `BuildSystem`; `Brain/Prompts.cs:44`, `System`; `:78`, `Tail`; `:113`, `Handoff` | Reads authored self/people/lessons/plan/notes. Lessons/notes are limited to last 60 lines. Handoff carries last thought, Today plan and last three clipped results, then asks status/look. The system string is not rebuilt at this handoff in PlayDay. Newly received event evidence may fall out of context while an authored thought remains. |
| `Brain/Prompts.cs:87`, `Morning`; `:107`, `Nudge`; `mod/StardewMCP/assets/system_prompt.md` | Prompts encourage work, mandatory thought and journal, efficiency and dealing with menus. Template falsely still says sleep refuses without journal; it also generalizes separate wallets and giving to players. These are prompt claims, not current executable rules. Prompt pressure can conflict with silence/STAY and A2's actual resource/target semantics. |
| `Agent/Perception.cs:186`, `Notify`; `:263`, `Tick`; `:288`, `SamplePlayers` | Bounded 20-event queues, six-tick sampling, arrival/weather/crow cooldowns. `Others` selects AI seats, so AI arrival/doing/claims sampling is not a general human-Guy perception bridge. Human chat bridge is a separate path. Cooldowns suppress presentation noise, not duplicate actions or verified events. |
| `Perception.cs:417`, `SafeToStop`; `:484`, `TryInterrupt` | Stops selected tools only at safe points; avoids swings, ordinary menus, warp/fade/event; does not interrupt bedtime walk for events. Cancelable sleep-ready state can be interrupted by queued events, including mentions. Both-AI-to-bed arrival suppression is narrower than a human sleeping/quiet-hours policy. Interrupted normal result is lost; observe partial progress before choosing again. |
| `Perception.cs:449`, `ReplyInTime`; `Agent/AgentHttp.cs:346`, `RefreshState` | Sleep reply may complete while sleep coroutine continues. Cached API state includes per-seat action/brain, but host top-level dialogue is not P2 prompt content. Heartbeat is not fresh P2 inventory/prompt evidence. Polling and elapsed time alone cannot authorize another action. |
| `Agent/JournalTools.cs:66`, `Journal`; `Agent/AgentLog.cs`, memory writers | Journal stores model-authored text with format/length checks, not evidence verification. Self/people are subjective reflections; naming notes “facts” does not make them factual. A3's evidence/reflection/working-memory separation is necessary. No journal or utterance is necessary to establish an observed transfer. |

Existing `SpeechQueueTests` cover order, paused clock and independent places; they do not validate human echo filtering, social consent, gift transfer, multilingual rendering or the external pilot.

## 2. Boundaries / not inspected

- **External P10–P13 Python/PowerShell pilots are absent and uninspected.** A repository filename search found no P10–P13 ZIP/controller source. The baseline reports P11 speech/STAY and P13 Luna ACCEPT followed by P2 response and operator-confirmed receipt. This does not reveal what prompt Luna saw, whether P13 only returned Yes/No, whether receipt reached the next decision, or how retry/ledger/restart works.
- **Source request for follow-up:** supply exact P11 Chat Bridge and P13 gift pilot source, entry scripts, prompt templates, parser/option mapping, model request assembly, state/ledger storage, controller ownership, retry and restart code, with versions/hashes. Include P10/P12 dependencies if imported. Redact secrets and private paths; no saves or private logs needed in GitHub. This is an implementation/research dependency, not a reason to invent their behavior or block this repository report.
- No deployed config/model, game/SMAPI implementation assemblies, vanilla gift menu/capacity behavior, actual chat latency, Thai rendering, game saves or live integration inspected. C# wrappers and historical pilots do not certify runtime behavior.
- Generic upstream runners are not proof of the Sunny P11/P13 controller. Findings about `SeatBrain` apply to the built-in loop only; the actual active controller is unknown.

## 3. Gaps & failure modes

Severity is design priority. Preconditions below describe proposed reproductions, not newly reproduced incidents.

| Priority / evidence | Preconditions and failure | Required direction |
| --- | --- | --- |
| Critical; fact + hypothesis | Gift prompt canceled/replaced during model latency; index response or broad menu cleanup reaches unrelated content. | A1 execution-time prompt guards on every mutation route; no default Yes/No or generic cancellation dismissal. |
| Critical; fact + hypothesis | Lost reply or competing built-in/external controller; repeated gift/action follows unseen outcome. | A1 shared lease/attempt reconciliation, never retry from missing mail. |
| High; fact | Generic AI `gift` notification also describes debris; authored diary or human claim says receipt. | A2 causal verification and A3 canonical event; prose never upgrades certainty. |
| High; fact + hypothesis | Mail drains before lost response, queue overflows, handoff truncates evidence, or no eligible tool finishes. | Replayable A3 projection and explicit gaps, independent of transient chat/diary. |
| High; fact + hypothesis | Ordinary nearby chat or repeated mentions reaches sleeping/working Sunny; safe sleep interrupt cancels rest. | Separate delivery from interruption; quiet/sleep suppression and safe points, no compulsory social response. |
| High; fact + hypothesis | Unsaved same-day reload retains authored gift story, plans or old decision. | Branch-aware A3 eligibility; invalidate old prompt/decision and dependent factual claims. Local persistence is not saved game truth. |
| High; fact + hypothesis | Goal proposal assumes consent, null owner means communal, or chest deposit becomes Guy receipt/build completion. | A2 possession/permission/executor/wallet evidence, A4 voluntary agreement, independent completion checks. |
| Medium; fact + hypothesis | No-tool STAY receives nudges or releases for whole day; efficiency/journal prompts encourage unwanted action. | Explicit resumable STAY semantics and prompt review after approval; preserve refusal and alternative activities. |
| Medium; fact + hypothesis | Repeated model speech accumulates per-map queue, delayed line shown to original listener set. | Bounded presentation queue, freshness/listener recheck and repetition handling; enqueue is not attention. |
| Medium; fact + hypothesis | UTF-16 clipping cuts surrogate/combining sequence; English tool labels become inconsistent Thai references. | Unicode-aware presentation and stable structured IDs; inspect real model output before judging language quality. |

## 4. Contracts proposed

All contracts below are **proposals requiring joint review**. A4 owns voluntary choices and conversational state, not transfer truth, game permissions or save commitment.

### Ownership and grounded next-decision delivery

Adopt A1's separate execution/effect/reply states and exact prompt tokens; A2's typed variants, actual quantities and causal TransferEvidence; A3's canonical event ID/revision, branch/checkpoint eligibility, correction and cursor protocol. Prefer separate `gift_choice_resolved` and verified `item_transfer_observed` over overloaded `gift_accepted`. Event naming remains joint design work.

Proposed `CompanionContext v1` contains:

- `context_id`, schema version, seat, save/load/branch, active controller lease, capture/freshness references, projection version and source cursor range.
- Current action/attempt including reply-completed versus still-running, safe-interrupt eligibility, menu/prompt token and exact observed choice mapping; unresolved outcomes remain explicit.
- Bounded current-branch events with ID/revision, verification scope, source/evidence refs, participant/item/quantity/disposition, observed time, save-commit state and corrections. Unknown fields remain null. Historical receipt and current possession are separate predicates.
- Chat with stable source message ID/sequence, sender, time, visibility evidence, thread/turn relation and delivery status; content labeled human/model-authored claim. Reflections separately labeled with authorship, branch and cited events, never mixed into verified facts.
- Voluntary goals/agreements, current alternatives, relevant inventory/capabilities and permissions; quiet preferences, recent topics, unresolved proposals and reaction decisions.

Proposed delivery sequence:

1. A1 observes a specific P2 offer; Luna may accept/decline/defer/STAY independently of speech. A1 dispatches only a fresh matching decision. A2 verifies actual outcome; A3 records event/revision once.
2. Before the next model decision, A4 consumes A3's branch-aware projection and stores its ingestion cursor locally. Ingestion acknowledgment is not proof of model understanding, speech or game save. A3 replay can repeat delivery without creating a new offer or reaction.
3. Assemble an immutable context snapshot for each model request. Record included event IDs/revisions and resulting decision ID locally. Event arriving during a model call goes into the next snapshot; cancellation of that request does not roll back game actions. Before executing a response, recheck lease, branch, prompt/action state and newer corrections. Superseded unsafe decisions are rejected, not silently remapped.
4. Maintain independent states for `context_ingested`, `decision_requested`, `decision_recorded`, reaction intent/attempt and observed dispatch. A3 cursor is not a “thank-you done” bit. Crash between speech dispatch and record produces unknown; do not automatically repeat it.
5. Corrections invalidate dependent factual projection/queued intents, retain original reflection as authored history, and can prompt optional clarification. On abandoned branch, exclude its events and factual reflections/goal progress from current decisions; retain audit locally. Saved ancestors need checkpoint proof, current possession reobservation. Controller-only restart reattaches to authoritative epoch and reconciles unknown attempts; day/item/name is never a dedup key.

Synthetic example: verified E1 says Guy transferred one observed Potato variant to Sunny, inventory receipt verified but save unconfirmed. The next context includes E1 even if Sunny says nothing and writes no journal. Luna can continue TV, store the item, ask about it later or choose another task. If delivery is only acknowledged/unknown, context must not say “Guy gave me a Potato.” After unsaved reload, E1 cannot reappear as current memory or trigger a thank-you; a new equal gift is a distinct event. Later consumption changes current holdings without erasing valid historical receipt.

### React-or-not and STAY

Proposed `CompanionDecision v1`: decision/context/branch/lease IDs, cited event/message revisions, independent activity choice and social choice, optional offer/goal/prompt ref, proposed action intent(s), private rationale and revalidation requirements. Allowed activity choices include continue, STAY, rest, another activity, ask clarification, cooperate, defer and refuse. Social choice includes silence, later follow-up, brief say, emote or proposal. No activity requires speech; silence is an explicit valid completion of a social decision.

For a live gift offer, acceptance, decline, deferral/no response and STAY remain choices. Deferral does not mean cancellation or safe indefinite menu blocking; surface the unresolved offer and bedtime conflict without silently deciding for Sunny. For a verified receipt, gratitude, item question, storage, later reference or silence are all valid; accepting does not create reciprocal debt. Decline need not carry an apology. A correction or uncertain receipt may justify asking, but never compels it. A4 must not press Yes/No or dismiss an unrelated menu to clear a social backlog.

STAY should release world-time hold while preserving a resumable decision state, with model-selected reconsideration conditions/time and quiet-event eligibility; it must not be converted into work, mandatory talk, sleep or “finished for the entire day.” A requested pause has different semantics from rest and sleep. Resource/latency ceilings may stop computation transparently, but must not masquerade as Luna's preference. Refusal is not an error for a repair loop to overcome. These semantics need an approved controller adapter; they are not an existing STAY tool.

### Initiative and voluntary cooperation

Sunny may initiate a topic, offer an available item or suggest working together without waiting for a command. Eligibility uses fresh facts, a supported action route, recipient availability and conversational preferences; it does not rank farm optimization above companionship. A model proposal is not permission to transfer/spend or acceptance by Guy.

Proposed `CooperationProposal v1`: proposal/revision and branch IDs, proposer/participants, concrete goal/affordance, proposed contributions and executor, resource/container/wallet evidence, permission scope, independent participant decisions, cancellation/expiry/reconsideration condition and progress evidence refs. Distinguish proposed, clarified, voluntarily agreed, deferred/declined/withdrawn and verified progress/completion. An agreement does not reserve items mechanically; recheck before each effect. Silence from Guy means pending, never consent. Sunny can withdraw, refuse, STAY or counter-propose; Guy can too. Goal text is untrusted conversational data, not tool authorization.

Example: Sunny can ask whether Guy wants a Potato, or offer to collect materials for a named Robin catalog project. Until human gifting is validated, do not dispatch fictional `give_to_human`; explain the unsupported route or propose an agreed chest deposit. Deposit, Guy retrieval and project spending are distinct. Do not claim an indistinguishable Potato is the exact one previously gifted. For construction, clarify which project/bridge, actual executor, money scope and carried materials per A2; neither a chat agreement nor chest stock proves build eligibility. No irreversible project selection follows from a vague shared goal.

### Conversation, interruption, latency and language

- Separate factual retention, presentation, and interrupt priority. Quiet events remain available at a natural next decision; urgent game hazards and positively identified consent prompts use A1's safe routing. Social @mention does not automatically justify waking a sleeper. At night/quiet mode, defer ordinary chat/proposals; surface identified blocking prompt without auto-answer or unrelated dismissal. Operator intervention may remain necessary.
- Track event/message/thread identity and last topic/response meaning. Replayed event does not open another gratitude turn. A declined proposal is not re-offered until materially changed circumstances or a new invitation; independent later gifts remain distinct. One unresolved proposal should not trigger repeated “are you there?” messages. Model may choose a relevant follow-up without arbitrary once-per-day limits.
- Use tunable transport bounds, per-thread backoff and queue expiry to prevent floods, plus semantic/contextual novelty judgment. Rate ceilings protect delivery capacity; they do not schedule personality, require greetings or force silence for a deterministic interval. Expose omitted/gapped messages and preserve source evidence in A3, not an unbounded model prompt.
- Budget prompt tokens by priority: epoch/unsafe unresolved attempt, current prompt/corrections, recent addressed chat and relevant verified events, then optional reflections/older topics. Keep stable IDs and uncertainty outside lossy summaries. Page older evidence on demand; truncation cannot erase action dedup state. Handoff must rebuild grounded context rather than carrying only last thought/results.
- Measure event-to-context and context-to-choice latency plus queue age, model token use and safe-point delay. Batch quiet events at natural boundaries; avoid model calls on every poll. Frozen-world thinking can still delay the human; running-world thinking costs game time. Provider retry backoff is not permission to replay an action or leave a stale prompt decision executable.
- Use configured interaction language (Thai when configured), preserving proper names and stable item/response IDs separately from localized labels. Never infer choice meaning from English Yes/No alone. UTF-16 slicing/20-character bubbles need Unicode/grapheme and Thai wrapping tests; model language consistency is a separate quality question. Retain raw evidence locally and redacted synthetic fixtures in repo; do not publish chat, farmer identifiers, API keys or save paths.

## 5. Tests

### Validation actually performed

Read-only source/report inspection and documentation checks only. No C# build, behavior suite, model call or live integration executed by A4. A1's recorded game-free test results are attributed to A1; existing SpeechQueue test source was read, not rerun. All behavioral tests below are proposed, unimplemented and unrun. Publication checks must confirm only this report differs from the target.

### Proposed isolated unit / contract fixtures

| Seam | Assertions |
| --- | --- |
| Human chat adapter | One P1 self-echo yields one message; other-screen echo, slash/nonordinary/system, wrong source/chatbox, blank/out-of-view/wrong-map rejected. Equal genuine new messages have distinct IDs. Cached/missing visibility explicitly handled. |
| Context/reaction reducer | Verified receipt reaches next decision with silence/no journal; ack, debris, human claim and reflection never become inventory receipt. Duplicate cursor/revision gives no extra reaction; correction/unknown remains visible. |
| Model-call race | Event during inference appears next context; stale prompt, new load, correction or lost lease rejects old intent. Unknown speech/action dispatch is reconciled without replay after crash. |
| Agency adapter | Accept+silence, decline, defer, STAY, refusal, alternate task all valid; no gratitude/reciprocity quota. STAY releases hold and can reconsider on new eligible event without all-day abandonment or nudge-to-work. |
| Conversation scheduler | Repeated polling/topic/mention cannot flood; quiet events survive without interruption; sleeper not woken for routine social text; new genuine question can bypass presentation backoff appropriately. Refusal not classified as failed action. |
| Cooperation reducer | Propose/clarify/agree/decline/withdraw separately per participant; silence not consent; no contribution from missing permission/unsupported human route. Chest deposit not receipt, agreement not reservation or building completion. |
| Branch/handoff | Unsaved equal-day replay excludes abandoned E1 and related reflections/intents; new E2 eligible. Controller restart preserves current epoch and unresolved attempts. Context truncation keeps uncertainty/corrections/IDs and explicit gaps. |
| Presentation/language | Bounded queue and stale listener/expired line handling; pause does not consume display time. Thai combining marks, surrogate pairs, mixed names and localized option order remain intact; language preference never rewrites canonical IDs. |

### Proposed operator integration sequence — all unrun

Only after design approval, explicit operator authorization, one controller, backed-up `Test_` save and recorded source/DLL/config/controller hashes locally. Research agents send no game calls. Use synthetic/redacted published evidence.

1. **Chat and reply:** Guy sends ordinary nearby chat and a distinct @Sunny message. Observe exactly one mailbox input per real message and next model context; let Luna choose reply/silence. If reply chosen, observe bubble/chat on intended screens once. Repeat out of viewport/map, with echoes and burst traffic. “Heard by” is not proof Guy read it.
2. **Gift accepted silently:** Guy offers Daffodil then Potato with known variants/count. Capture exact P2 offer/choices; Luna freely chooses. In an accepted+silent run, A1 responds once, A2 verifies causal receipt, A3 publishes one event and next decision includes it with no journal/chat requirement. Optional later item-specific question or thanks is allowed, never required. Choice coverage uses synthetic fixtures if Luna does not choose the requested branch naturally.
3. **Decline/cancel/latency:** exercise freely chosen decline, Guy cancellation, unrelated replacement and delayed model response. Require zero stale clicks and no invented receipt; incomplete evidence stays unknown. Operator identifies blocking cancellation text separately; no generic cleanup. Lost-reply harness never resends blindly.
4. **Nighttime:** Guy in bed, Sunny working/resting/sleep-ready; send routine chat/mentions. Verify proposed quiet policy defers conversation and preserves events without waking or spamming; current source may fail. Positively identified blocking menus are handled only through scoped choice/operator action. Bedtime without diary and actual save checkpoint are checked independently.
5. **Sunny initiative:** allow Luna to offer an item or propose cooperation without a preceding command. First confirm current give-to-human restriction without bypassing Guy's role; operator separately validates candidate vanilla route before relying on it. Guy may decline or ignore. For agreed stash route measure deposit/retrieval separately; do not label deposit completed gift.
6. **Voluntary shared goal:** clarify a supported project, executor, permission, wallet and materials. Sunny can gather, defer, refuse, STAY or suggest TV/another activity; no reward/test failure for declining. Any actual spend/build needs separate operator authorization and A2 verification; a conversation-only goal test requires no construction.
7. **Reload/restart/handoff:** after verified receipt and optional reflection, abandon unsaved same-day branch; old memory/reaction excluded, new equal gift distinct. Separately load confirmed checkpoint and restart only exact supplied external controller; replay context without duplicate action or thanks. Force bounded handoff with synthetic context and ensure correction/unknown state survives.

## 6. Dependencies & questions for the other three agents

- **A1 / PR #6:** agree guarded prompt/attempt and reply-vs-running contracts; include close/sleep/watchdog mutation routes. Can social event delivery be separated from interruption without allowing stale actions? Which safe point resumes STAY and which exact vanilla affordance can target human Guy? Refusal/silence must not be retried as failure. Lease must cover built-in and external controllers.
- **A2 / PR #7:** adopt receipt-versus-choice and AI queue/debris distinctions. Supply actual variant/quantity/current possession and causal evidence; no inference from generic gift text. Agree supported human offer/stash route, participant permission and executor costs. How should agreed chest contribution coexist with legacy theft language without making null ownership communal?
- **A3 / PR #8:** adopt sole publication, event/revision/cursor, corrections and abandoned-branch exclusion. Define bounded context delivery/replay and decision inclusion records independently of speech. Which optional subjective preferences may survive branch abandonment without carrying factual gift memories? Default: archive old reflections, exclude their factual assertions until reviewed; do not silently erase authorship or promote it to evidence.
- **External-source dependency:** exact P11/P13 sources requested above are needed to map Luna's actual incoming context, choice grammar/STAY, gift parser, chat echo filtering, restart and model latency. Until supplied, repository-side adapter design only; no cross-codebase refactor claims.
- **Joint unresolved choices:** message/event/decision schema versions, quiet/urgent policy, acceptable context and latency budgets, speech queue expiry/revalidation, human-route validation and checkpoint authority. Shared `SocialTools`, `Perception`, `AgentHttp` and controller wiring require cross-track review. This report completes review input, not mutual approval of all contracts.

## 7. Smallest safe first implementation PR proposal

**After architecture approval only:** add an unwired, game-free companion context/decision reducer with synthetic A1/A2/A3 fixtures. Scope: evidence-versus-reflection projection, event/revision replay, independent silence/activity choice including STAY/refusal, stale decision rejection and minimal voluntary proposal state. Test accepted-with-silence, unknown receipt, corrected/abandoned event, duplicate delivery and cooperation decline. No live tools, model API, prompt rewrite, persistence migration, personality timer or gameplay hook; explicitly no active protection claimed.

Then review additive context/cursor and controller adapters only after actual P11/P13 source inspection; separately review prompt consistency and quiet/interruption behavior. A1 guarded dispatch and A2/A3 evidence/epoch contracts must be available before integration. Operator-led tests precede behavior merges. This research changes documentation only and authorizes no implementation or merge.
