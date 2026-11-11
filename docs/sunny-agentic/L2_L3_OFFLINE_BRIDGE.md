# G0: L3 daytime intentions -> L2 fake-world action and verification

**Synthetic integration ONLY.** No actual Luna, Python pilot, Mod DLL, Stardew/SMAPI, SteamLibrary file, credential, port or HTTP. These tests add no live capability. Branch is stacked **on Draft PR #60, which is stacked on Draft PR #58**, not on `main`.

## Purpose

Previously, Draft PR #58 demonstrated **L2**: a fake `MOVE_TO_CHAIR` can be prepared, dispatched to synthetic P2, and verified; a subsequent `STAY` makes no dispatch. Draft PR #60 independently proposed **L3** contextual activity candidates on fake observations (STAY, chair, TV, P1 speech). The two were **not connected**.

This small adapter, `reference/sunny_l2_l3_bridge.py`, now composes the two **without altering either underlying PR**. It reads the L2 fake observation, constructs a minimal L3 scene from **only known fake facts**, presents available proposals to an injected *scripted* interest callback, and passes a chosen, snapshot-pinned `STAY` or `MOVE_TO_CHAIR` back to the unchanged L2 fake controller. The L2 checker must independently reobserve the same fake snapshot before dispatch.

Example: one toy world revision offers `STAY` and `MOVE_TO_CHAIR`; a test interest chooses `MOVE_TO_CHAIR`. The fake action is reserved before dispatch, updates P2 toy tile and revision, and returns `VERIFIED_FAKE`. The second observation offers only `STAY`, which another scripted decision chooses without a second dispatch. Thus proposal, choice, action, fake effect, verification, and new choice are joined in one **fake** demonstration.

## Important limits and explicit non-capabilities

- `WATCH_WEATHER_TV` and `SPEAK_TO_P1` exist as **L3 proposal concepts**, not as executable L2 fake actions. This adapter **does not** offer them, because the L2 fake world did not expose those actions. There is no mapping to Mod `watch_tv` or `interact` yet.
- `APPROACH_P1` and `FIND_P1` are **not implemented**. The human P1 may be busy, sleeping or elsewhere; there is no trusted availability or P1 locator observation. The future idea in Issue #57 (Sunny can approach, change her mind, wait or cancel) requires separately specified, bounded pathing and reobservation.
- The L2 `sunny_tile` is a fake position and **does not prove chair seated status**. The adapter explicitly does not infer seating from it; `p2_seated=False` is a dummy non-evidence field, and the L2 offered-action set still suppresses repeat move when at the target tile.
- Fake weather is `unknown`, fake TV reachability is `False`, and fake P1-awake/distance are `False/None`: do not fabricate values to authorize interactions. No P1 raw diary, chat, feed or inventory is projected.
- A fake chooser callback is **not Luna**. The code does not implement curiosity, natural dialogue, memories, real environment perception or autonomous intentions.
- The executor's result `VERIFIED_FAKE` is the **same in-memory fake world effect** as the L2 tests; **not independent game evidence**.
- A missing reply, stale observation, owner/epoch mismatch or pending effect prevents blind retry. The marker persists only in the **same in-memory fake world**; **not** across process termination, new world creation, crash or Windows game reload. This is not a durable journal.
- L3 requires a new observed revision to make a new proposal; a `STAY` without changed observation pauses. There is no fixed time, action quota, or automatic timer.
- Identifying one extracted controller reference candidate (`Sunny_P10_P11_P12_P13_Gift_Offers_v0.3.10`) and on-disk Mod DLL AssemblyVersion 0.4.0.0 in Issue #56 **did not establish that they ran together**. This bridge does not pretend otherwise.

## Acceptance in the game-free test runner

`python -m pytest -q mod/tests/test_sunny_l2_l3_bridge.py`

Eleven test cases cover integration of two independent decisions, STAY pause, unsupported TV and P1 approach/speech proposals blocked, lost reply, same-world controller recreation, owner/epoch and P1/P2 role mismatch, snapshot change between proposal and execution, unknown private P1 content exclusion and chooser error. Keep the existing PR #58 and #60 tests unchanged and green.

## Real integration gates

Read-only inspect **exact extracted v0.3.10 P11 chooser action schema** and corresponding safe Mod dispatcher. Do not infer executable action support from substring searches. No live P2 test or change to SteamLibrary is allowed yet: Issue #59's independent PR #58 review is open, G1 resource/auth/privacy/independent-stop preflight gates remain open, G1/G2 verification not run. `NO_GO_G1_START`, `NO_GO_LIVE_G2`; do not merge, deploy, call Luna or launch game as part of this PR.


## Exact v0.3.10 P11 offer IDs (operator supplied source lines 219–268, 402–405)

The local, **extracted** `scripts/sunny_freeplay.py` was inspected read-only by the operator (SHA-256 `F049A9502E073A487C473B962D8FD0A53968FD4C15E80B25F9547A23A5E6F156`). These are **source facts, not proof of runtime-loaded controller**:

| Observed controller option | Source condition to offer | Real source target | Integration meaning |
| --- | --- | --- | --- |
| `F0 stay` | unconditional in `options_for` | **none**, no MCP dispatch | First-class no-action choice |
| `F1 chair` | exactly one observed chair, one target tile | `interact(x,y,reason)` | **Seat-toggle interaction**, not the L2 toy's `MOVE_TO_CHAIR`; seated status requires independent verification |
| `F2 tv_weather` / `F3 tv_fortune` | `objects['tvs']` is nonempty | `watch_tv(channel=weather/fortune, reason)` | Two separate channel intents |
| `F4 speak` | `nearby_guy(state)` is true | `say(text)`, 1–150 characters | Proximity only; busy/consent **not** established. Do not automatically add `@Guy` |
| `M1`–`M8 move` | up to eight `open_tiles(grid, origin, state)` | `walk_to(x,y,reason)` | **Clear Cabin tiles**, not arbitrary movement anywhere or a generic approach to P1 |

`choose_luna` submits exactly the listed options plus a bounded context: farm day, game time/weather, Sunny's tile, nearby-Guy boolean, up to six temperament traits and six recent activities. It requests one strict function call with fields `option_id` and `text`, `parallel_tool_calls=False` and no fixed mandatory conversation or game-clock schedule (operator-supplied lines 237–266). This **shows a source design for model autonomy**, but actual model acceptance, correct reply parsing, operational permissions and tool outcomes are not yet proven. The functions behind `nearby_guy`, `open_tiles`, exact response parsing and the P10/P12 loop remain to be reviewed if integration requires them.

`reference/sunny_p11_option_contract.py` provides **inert, static grammar checks** for these IDs and a `P11Plan` displaying which MCP-shaped tool call *would* be needed. Its `CONTRACT_ONLY` verdict **must never be treated as execution approval**; it does not use `Request`, a token, the real Luna client, actual `status/look`, the local Windows scripts or the Mod. It deliberately refuses unoffered IDs, forged ID/action pairings and arbitrary target coords from a chooser, and adds a conservative **proposal-only** speech restriction on `@` because the current Mod's `say` tool description says `@name` may interrupt the recipient. This latter restriction is **stricter than** the extracted P11's known 1–150 character validation, not a claim of current P11 runtime behavior. Only the already-existing `STAY` and toy `MOVE_TO_CHAIR` are dispatched by the isolated L2/L3 fake bridge; no P11 tool call is dispatched by this contract.

**Critical distinction:** We have no evidence that P11's `chair` action is equivalent to L2 `MOVE_TO_CHAIR`. Nor does `F4` authorize searching for/approaching P1 when `nearby_guy` is false, and it has no explicit busy-state or cancellation during approach. The future social feature remains design-only in Issue #57.

**New game-free checks:** `python -m pytest -q mod/tests/test_sunny_p11_option_contract.py`. These test only the published, operator-reported v0.3.10 source grammar as copied into the static reference module. Exact source snippets are neither a complete executable script nor a proof of current binary/controller behavior.



## Extracted v0.3.10 source: model reply and pre-dispatch check (operator lines 269–293, 390–422)

A narrower read-only excerpt of the **extracted P11** script clarifies the boundary between model choice and game action:

- \`choose_luna\` lines 269–275 use a 90-second HTTP request timeout and **do not automatically retry** a model HTTP error, lost response, or other uncertain model result. This is *model-call failure handling*, **not** evidence that a game tool has been invoked or that a possible game action is reconciled.
- Lines 276–293 require a response object with \`status=="completed"\`, exactly one function-call item named \`choose_sunny_freeplay\`, JSON-encoded arguments containing exactly the two string fields \`option_id\` and \`text\`, and an \`option_id\` present in the **offered options**. Speech must be 1–150 characters, trimmed, and contain none of CR/LF/TAB/\`<>{}\`/backslash; non-speech actions require an empty \`text\`.
- Lines 390–406 journal the model's selected activity, return from \`stay\` **without game dispatch**, or translate the chosen activity to a tool name and parameters. A failed model response is journalled as \`model_uncertain\`.
- Lines 409–422 **re-read** game state before dispatch, check \`state_gate\` and whether P2's tile still matches the previous observation, cancel if the gate or position changed, and perform an additional wake-specific check. The excerpt **ends while entering the special step precondition check**: it does **not** establish all of the subsequent step/seat/owner/dispatch or post-effect handling.

**New G0-only contract tests:** \`inspect_p11_model_reply\` was added to \`reference/sunny_p11_option_contract.py\` with synthetic Responses-style envelopes and deterministic tests in \`mod/tests/test_sunny_p11_option_contract.py\`. It validates the same function-call **shape**, then returns an **inert** \`P11Plan\` (never an executable command). Additional restrictive policy blocks \`@\` in P1-directed speech because GitHub Mod source indicates \`@name\` can interrupt the human recipient. **This extra rule is not claimed to exist in the extracted historical Controller.** Missing/rejected/uncertain model data does not trigger any game dispatch in this G0 reference code.

**Remaining unknown:** exact \`mcp_call\` response parsing (P11 starts at line 296), the pre-dispatch step/stand checks beyond line 422, and how the historical controller independently confirms a post-action effect. A text match, JSON-RPC acknowledgement, \`isError=false\`, or \`structuredContent.ok=true\` is not enough for actual verified sitting/movement/TV/communication. **Neither the installed DLL SHA nor the GitHub source establishes the real run environment.**

Do not merge/deploy or run Windows/Luna/SMAPI as a result of these passing toy checks; independent review Issue #59 and all G1/G2 entry gates remain open.


## Extracted P11 v0.3.10: MCP reply and cautious chair exit (operator lines 296–335, 420–485)

**Source observation (not installed-version/runtime evidence):**
- Historical \`mcp_call\` allows only \`walk_to\`, \`interact\`, \`watch_tv\` and \`say\`; exact argument-key sets are checked. Coordinates are Python \`int\` in [0, 199], TV channels only \`weather\`/\`fortune\`, and speech length 1–150 characters. It creates a fixed JSON-RPC request ID **20013**, sends one \`tools/call\` to the P2 endpoint and uses a **95-second timeout**. On network/HTTP/malformed-reply exceptions, it raises an **uncertain / no automatic retry** error.
- Its response decoder (lines 314–319) computes \`ok\` from **absence of top-level \`error\` and \`result.isError\`**, and copies \`structuredContent.reason\` and the first 500 characters of concatenated text. It **does not check \`structuredContent.ok\`, \`structuredContent.partial\`, the JSON-RPC \`id\`, or proof of actual game state change**. A success-shaped acknowledgement must not be equated with a completed action. The server's documented structured content can report \`ok=true\` *and* \`partial=true\`.
- The \`act=='step'\` branch **recomputes options** from a fresh room inspection at lines 420–428 and cancels an option no longer present without dispatch. For \`move\` or TV selections when chair posture evidence says \`likely_seated\`, lines 429–454 perform a separate *stand* prerequisite using \`interact\`, with one request, no blind retry on uncertainty and a textual \`Stood up from chair at (x,y)\` check.
- Lines 455–481 then attempt to **observe** chair exit; if the observation is unavailable or the intended destination is no longer supported, they **complete the stand-only prerequisite and hold the next activity for re-evaluation**, rather than blindly dispatching it. Lines 482–485 begin one final state gate before the original activity, but the supplied excerpt stops there: we have **not** verified how this last gate or the final post-dispatch outcome is handled.

**Actual seam to improve eventually:** P11 already has useful model-choice validation, rechecks, and cautious sit/stand handling. Preserve these. A future properly secured controller should inspect both \`isError\` and \`structuredContent.ok/partial/reason\`, require matching authenticated owner/epoch/attempt, and observe independent P2 game effects before labeling the action successful. Even a matching fixed request ID is **not** an idempotency marker or proof of which attempt produced the reply.

**New *inert* G0 tests:** \`reference/sunny_p11_reply_contract.py\` and \`mod/tests/test_sunny_p11_reply_contract.py\`. The parser accepts only simulated JSON-RPC response objects; it never sends a request or dispatches anything. A fully coherent response is called \`ACK_REOBSERVE\` (**not** \`VERIFIED\`), while inconsistent flags, partial outcomes, untrusted/missing IDs, declared failures or malformed results are \`UNKNOWN_*\` and cannot authorize blind retries. For chair exit, matching stand text provides only \`STAND_REOBSERVE\`, **not actual seated-state proof**. This parser is a proposed conservative policy for eventual review, not a claim that the historical v0.3.10 code already behaves that way.

All G1/G2 no-go gates and draft/independent review requirements remain unchanged; nothing in these tests connects to the user's installed game or authorizes a runtime change.


## Final P11 v0.3.10 section inspected: line 486–541, not a verified-action loop

Operator's read-only excerpts of extracted \`sunny_freeplay.py\` show:
- Lines 486–495: after a stand prerequisite, the script checks a final fresh game-state gate and P2 position again; if the world changed, it records \`stood_only\` and does not send the originally selected activity. If posture is \`uncertain\` or \`snapshot_pending\`, it cancels without a blind chair toggle.
- Lines 497–504: it records \`dispatch\` **before** invoking a game tool. Any uncertain MCP call records \`unknown\` and returns without an automatic retry.
- Lines 505–515: after an MCP response, it calls \`read_state\` and records the current P2 coordinate and the reply's \`ok/reason/text\`. **It does not itself compare target against actual position, establish P2 seating state, verify the TV channel, or verify P1 received speech.** It explicitly prints instructions for the human operator to verify walking or chair sitting **visually**. A journal \`ok=true\` at this stage is the **tool-reply flag**, not an independently verified game effect. This file is a *one-shot* \`perform\` command; continuous scheduling may belong to the separate uninspected \`sunny_loop.py\`.
- Lines 518–541 show the CLI wrapper and exception handling. Read-state exceptions after dispatch may be caught at the outer CLI layer and stop, but that does **not** provide durable reconciliation or proof of which game effect occurred. No claims about subsequent autonomous-loop retries are warranted from this file alone.

### Focused G0 follow-up: evidence-gated *next* choice

\`reference/sunny_p11_post_action.py\` and \`mod/tests/test_sunny_p11_post_action.py\` are **synthetic only**. A fake, explicitly P2-only scene includes save/day/epoch/owner/roles/revision/tile, and the pure policy receives an inert P11 plan and fake MCP reply assessment from the earlier tests.

- A coherent MCP acknowledgement is **only** \`ACK_REOBSERVE\`; if a **new fake snapshot** has unchanged identity and shows an exact selected move target reached, the result is called \`FAKE_MOVE_OBSERVED\`, with permission **only to offer another fake choice**. It is **not independent game causation, actual seat authorization or a real effect verification**. An unchanged/wrong target, unknown result, partial result, failed tool or changed save/epoch/owner/seat roles does not permit re-planning.
- A chair \`interact\` or TV/speech acknowledgement plus changed P2 coordinates **does not** establish sitting, program playback or P1 receipt. These remain \`DEFER_*\` until a separately trusted, specific evidence source exists. This is an intentionally conservative *proposal for future review*, not a claim that the historical v0.3.10 controller already pauses those activities.
- \`STAY\` remains no-dispatch and waits for changed observation before another choice. An unresolved result never triggers an automatic effectful retry.
- \`FakeP2Snapshot\` fields are **caller-supplied in tests**, not authenticated or independent of any tool that caused a game action. The missing server-verified P2 postconditions, durable attempt ID, independent STOP and G1 gates remain **unimplemented**. Even 100% green G0 tests cannot prove the real gameplay loop is safe.

No changes to the operator's local v0.3.10 script, DLL, SteamLibrary, game save, API, or the earlier stacked Draft PRs. No run authorization or merge.
