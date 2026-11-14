# Sunny P0 — single Game URL / two-Mod-tree routing handoff (G0, design only)

> **Status:** 2026-11-14 static evidence reconciliation and proposed offline migration, **not** a code fix, completed source-level trace of every v0.3.10 import, installed runtime attestation, game readiness, or G1/G2 approval. This document is a one-file Draft PR stacked on PR #22's transport-compatibility branch. No external Controller files, DLLs, configs, Windows scripts, HTTP endpoints, API/model keys, logs or saves were accessed or changed by this PR.

## What we can and cannot conclude

| Evidence | Directly established | Must **not** infer |
| --- | --- | --- |
| Operator's read-only candidate v0.3.10 files | `scripts/sunny_loop.py` SHA-256 `2A53976CB1D8AAB3AEAF9D7D9DA723F3438D9E8F24C51F194A38D22E579EDEFE`; `scripts/sunny_freeplay.py` SHA-256 `F049A9502E073A487C473B962D8FD0A53968FD4C15E80B25F9547A23A5E6F156`; `Start-SunnyCompanion.ps1` SHA-256 `3CB509AADBA7DD2563E02648E167C0770D1EBB1A0E7AB69775C606D247A0E655` | Which process or scripts were *actually loaded in the latest session* or that every file equals v0.3.11 |
| Operator's read-only port search in extracted v0.3.10 | `sunny_autonomy.py` and `sunny_initiative.py` contain a literal `127.0.0.1:8770`; `sunny_freeplay.py` and `sunny_loop.py` did not contain a *direct* `localhost:PORT` or `127.0.0.1:PORT` literal | Blank literal matches do **not** mean URL-free code: the operator-supplied `sunny_loop.py` excerpts refer to `freeplay.core.GAME_URL`; Python imports can hide the source URL. The complete exact v0.3.10 import/override graph remains uninspected |
| Operator's previous SMAPI invocation | The **game executable** was previously launched using a `--mods-path` argument selecting a separate `sunny-smoke-test/Mods` root | That SMAPI successfully loaded a particular DLL in its last run; this command is not the separate Sunny PowerShell/Python controller |
| Custom smoke-test Mod at rest | `StardewMCP.dll` SHA-256 `15C206AFE8B88715DCA6BFFC74EA9CC5A8B1173E0F516C8AC1B7B39FFE2A3EBC`, assembly `0.4.0.0`, manifest `0.4.0`, and adjacent config `HttpPort=18770` (operator read-only output) | That the game actually bound/opened 18770, that a real HTTP response came from this DLL, or that its source is equivalent to the GitHub repo checkout |
| Ordinary game-directory Mods at rest | Different `StardewMCP.dll` SHA-256 `51718B9620BF32BCEFB7F586F6BE3518187313874AAED1A5556AD38986495213`, assembly `0.4.0.0`, manifest `0.3.0` | That either binary is newer, safer or the one loaded; assembly-version equality does not establish byte or behavioral identity |
| GitHub C# source on PR #22 | `ModConfig.cs:81` defaults `HttpPort=8770`; `AgentHttp.cs:63–79` opens HTTP prefixes for `localhost:{port}` and `127.0.0.1:{port}` and may fall back to a `localhost` prefix if an `HttpListenerException` occurs | That a **runtime-loaded** DLL uses this exact C# source or that effective port is always the default |
| Source-audited **v0.3.11** ZIP | `SUNNY_V0311_HTTP_MCP_TRANSPORT_AUDIT.md` reports the main PowerShell wrapper has **no** `GameUrl/HttpPort` argument; Python core/shared URL is hardcoded to 8770, separate helper callers use this URL; calls include `GET /api/state`, `GET /api/feed`, `POST /mcp/p2` | This is **not** a full source audit of v0.3.10, even when file names match |
| Historical P10–P11 package README and operator history | `Start-SunnyCompanion.ps1` is a foreground wrapper for the P10/P11 loop; `sunny_loop.py` is the scheduling Controller; `sunny_freeplay.py` implements P11 decisions; `-Start`, `-Status`, `-Stop` and manual commands are documented | That every P12/P13 script or current launcher call forwards a common URL |

**Finding:** a **static configuration mismatch candidate** (Controller Python hints at 8770, smoke-test Mod config at 18770) is now directly supported. It is **not** evidence of a particular live failure or that changing the port alone would make the legacy unauthenticated MCP transport safe. The earlier default-Mod manifest `0.3.0` and the custom smoke-test manifest `0.4.0` refer to different files at rest, not a proven chronological upgrade path.

## Controller-to-game flow and audit checkpoints

```text
SMAPI game host [historical invocation]
  --mods-path = custom sunny-smoke-test/Mods
  -> StardewMCP config.json : HttpPort = 18770 [at-rest only]
  -> AgentHttp listener [bound port unknown without a running game]

Start-SunnyCompanion.ps1 [separate historical controller entrypoint]
  -> sunny_loop.py [P10/P11/P12/P13 scheduling, documented/source excerpts]
       + P10: state/ready and morning status; read URL origin: CHECK EXACT v0.3.10
       + P11: sunny_freeplay.py -> imported core.GAME_URL / P2 tools: CHECK
       + P12: sunny_bedtime.py -> game transport helper: CHECK
       + P13: sunny_gifts.py -> game transport helper: CHECK
  manual -Step/-Chair/-Move/-Wake and status: CHECK EACH OPTION
  -> future single, explicit Game URL [NOT IMPLEMENTED]
        -> authenticated, verified target P2 only [NOT IMPLEMENTED]
```

**Read-only code audit before patching actual Controller:** In the **exact SHA-matched v0.3.10 extraction**, inspect the `param` block and Python invocation branches of `Start-SunnyCompanion.ps1`, imports and `GAME_URL` assignments in `sunny_autonomy.py`, `sunny_initiative.py`, `sunny_memory.py`, `sunny_freeplay.py`, `sunny_loop.py`, `sunny_gifts.py`, `sunny_bedtime.py` and any called `sunny_indoor.py`/other pilot scripts. Record **module, function, URL-origin expression, call type (read vs mutation), CLI/override path and retry policy**. Check manual modes and `-Status` separately; never infer all P10–P13 behaviors from two literal port matches. Inspect by source only, without starting processes, making network requests or publishing the private package.

## Proposed future Game URL contract (DRAFT, not applied)

1. **One deliberate configuration per Controller startup.** The selected native loopback target must be supplied explicitly at launch, e.g. proposed `-GameUrl http://127.0.0.1:18770`, or from a user-approved private config with an equally explicit displayed target; fail closed if absent or conflicting. Do **not** silently default to 8770, infer the correct running process by port probing, select whichever port responds first, or copy the target from unrelated OBS/browser config. This example is **not an instruction to run it against the current Mod**.
2. **Strict validation before all network or model activity:** require an absolute `http` origin with an **explicit port 1–65535**, and a host of **exactly `127.0.0.1` or `localhost`** for the current Windows HTTP listener contract; accept at most an optional trailing `/`. Reject userinfo, username/password, non-loopback addresses, host suffixes, IPv6 unless independently supported/tested, DNS aliases, paths, query, fragment, Unicode ambiguities, whitespace/control characters and conflicting flags/config. Never downgrade or auto-switch `127.0.0.1` to `localhost` or another port after failure; the host's fallback bind behavior means an operator may need to explicitly choose `localhost` after validating that specific listener. This URL is not a secret; credentials are separate.
3. **Dependency injection into all call paths:** PowerShell passes a single validated origin through Python `--game-url` or another explicit process-safe configuration object. The loop constructs exactly one game transport client; P10, P11, P12, P13 and manual action handlers all consume the same client/verified target. Replace direct `core.GAME_URL`, imported aliases and handwritten per-module `urllib` URLs **only after** auditing their exact caller semantics. No module may restore an implicit `:8770` fallback. `-Status` and local `-Stop` must remain usable without live-game contact and must not reveal secrets; real host-independent STOP is a separate G1 requirement.
4. **Target identity is not port identity.** Even if URL is reachable, require a future authenticated native session and **server-authoritative** game instance/save-load epoch, P2 owner lease, P1 human/P2 AI role and expected save binding *before* enqueueing an effectful P2 action. Preserve host/game-thread epoch fencing and real STOP/queue retirement. A client-provided save name, manifest version, HTTP response or matching localhost port cannot authenticate the intended game. Never control P1.
5. **Credentials and data isolation.** OpenAI/Luna API keys are **not** game-MCP credentials. Future P2 native grant must be provisioned separately and never placed in URL, command line, PowerShell history, logs, GitHub, JSONL, screenshots or exported notes. Only minimal consent-aware P1 safety signals may reach the companion; no raw P1 diary/dialogue or viewer-wide feed. Status-only probes also need authorization in the future transport.
6. **Unknown is not a retry.** A wrong port, refused connection, timeout, 401/403, stale owner/epoch, changed save, lost response, mismatch between dispatch and result, or action still in flight must not become a second mutation. Read-only contacts can have separately bounded retries after permission/auth checks; action retries require authoritative host operation reconciliation, not just a new URL, journal last-row or `ok=True`. Bedtime may outlast ordinary short request deadlines.

### Offline acceptance cases for a later *code* PR

| Scenario in a fake transport | Expected decision |
| --- | --- |
| Explicit 18770 target, fake host identity/authorization valid | Requests across P10–P13 use **the exact same target**; ability to proceed still depends on full per-action checks |
| 8770 is reachable but expected 18770 instance, or vice versa | **Reject wrong instance**; do not use a responding unrelated host |
| 18770 unavailable or 127.0.0.1 unreachable but localhost might bind | Report unavailable and **do not silently switch** |
| Missing GameUrl, default 8770 left in a helper, malformed URL, LAN URL, userinfo, query or URL path | **Reject before side effects** |
| Same save name but a new host epoch/owner, or two separate game instances | Reject stale owner/epoch; never identify solely by save name or port |
| P11/P12/P13 mutation dispatched then HTTP reply lost | Persist pending/unknown; **no auto-repeat**, no false success |
| P12 standing prerequisite ACK but no independent real effect | Reobserve/fence; not proof of original activity or next-day transition |
| P13 gift/response prompts changed before game-thread dispatch | Reject stale prompt without commanding P1 |
| `-Stop` while a long P12 task is queued/running | Stop requests may be observed locally but only future independently verified host STOP proves actual retirement; unresolved remains quarantined |
| `-Status` / local `-Stop` without available game port | Remain usable as bounded local operations; do not require model calls or release unresolved mutations |
| Read request returns untrusted P1 dialogue or private full feed | Reject or server-project least-privilege P2 data; no viewer or P1 leakage |

These are **future acceptance criteria**, not tests added or passed in this documentation PR. The test harness must never make live HTTP calls or launch a game/model.

## Concrete next implementation boundary and stop conditions

**Next readiness work:** verify the exact v0.3.10 caller-import graph read-only in a private, approved local workspace; identify the Mod binary's source correspondence without assuming AssemblyVersion matches; choose the host-side authenticated instance/epoch handshake. Then separately review a **minimal client transport adapter** and G0 tests with injected fake HTTP, *before* changing the installed script or enabling a new Mod listener. Keep the Mod/server security owner/lease work separate from the client parameter migration until compatible and independently tested.

**Cannot claim yet:** that a historical Sunny action failed due to port mismatch, that a specific DLL was actually loaded, a running instance is on 18770, or that a configuration fix alone permits gameplay. Do not instruct the operator to flip the installed Mod to 8770, expose ports, launch `-Start`, bypass security/auth, rerun unknown mutations, deploy DLLs, or merge this design PR to `main`.

**Gate status:** all eleven G1 gates remain OPEN, fifty historical live cases `not_run`, Phase 2G limits unratified. `NO_GO_G1_START` / `NO_GO_LIVE_G2`. All existing PRs stay Draft/unmerged. The user's real goal remains a flexible observed P1-human/P2-Sunny gameplay loop, not test-count growth or a forced daily schedule.
