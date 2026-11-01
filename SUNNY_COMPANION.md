# Sunny AI Companion — experimental fork notes

> Personal experimental fork of [Duckxy's Stardew MCP](https://github.com/duckxy166/stardew-ai-agent), not an official upstream release or a standalone Sunny distribution.

## Identity and aim

**Sunny** is an AI-controlled farmhand (P2) sharing Stardew Valley with **Guy** (human P1). We use the nickname **Luna** for the AI making Sunny's activity decisions.

Our direction is **observe → decide → act → check the outcome → continue**. The point is companionship, not mandatory optimization or a fixed number of daily actions or conversations. Early scripts used one-shot quotas and time windows to make tests interpretable; these are not intended to define Sunny's behavior.

## Project boundaries

- **[Stardew MCP](https://github.com/duckxy166/stardew-ai-agent)** by Duckxy is the underlying SMAPI mod and game/MCP/HTTP interface.
- **[This fork](https://github.com/niabchan/stardew-ai-agent)** holds game-side improvements and these notes. It shares upstream history and licensing.
- **Sunny's Python and PowerShell prototypes (P01–P09, Free Play v0.2)** are separate local experimental artifacts. They are **not included here**; cloning this repository alone does not provide the `Start-SunnyCompanion.ps1` script.
- A GitHub commit never installs the mod into the local game by itself. The test machine must compile and deploy the appropriate DLL separately.
- Don't commit API keys, personal paths, logs or save data.

## Completed chair-toggle experiment

**Original behavior:** In a test Cabin, P2 Sunny could sit on an Oak Chair at (7,4). But `walk_to(7,5)` and repeated `interact(7,4)` returned `no_path` because `interact` attempted to pathfind adjacent to the chair even while Sunny was sitting on it.

**Fix:** When P2 is already seated on the specified furniture, use the game's `StopSitting()` path and verify the seated state clears. Otherwise, keep the pre-existing interaction behavior.

**Outcome:** [PR #1](https://github.com/niabchan/stardew-ai-agent/pull/1) was merged into the **fork's `main`** on 2026-11-01 after live Day 20 verification. This did **not** change Duckxy's upstream repository.

### Day 20 gameplay observations

| Activity | Logged result |
| --- | --- |
| Walk toward Cabin (8,9) | `ok=True`; result `Arrived at (8,9)` |
| Interact with Oak Chair (7,4) | `ok=True`; Sunny sat |
| Interact with same chair again | `ok=True`; `Stood up from chair at (7,4)` |
| Luna selected weather television afterward | `ok=True`; P2 successfully watched the weather broadcast at the TV |

The TV action after standing is evidence that Sunny was able to continue another activity. A few later position snapshots differed by one tile from tool result/footer coordinates; this is not fully explained yet.

### Automated checks

- Mod **compile-only Release build** succeeded on the Windows test machine.
- Python suite: **86 passed, 7 skipped, 1 xfailed**.
- C# tests: **267 passed, 1 failed**. The remaining `BrainTests.System_prompt_fills_every_placeholder` failure is in the system-prompt test, not the chair-specific source path. It has **not yet been fixed**.
- Broader regression tests, including other chairs, remain future work. Do not overstate single-save pilot coverage.

## Next milestones

- Morning state observation (around 06:00) with proper save-reload reconciliation instead of one-shot day-based locks.
- An autonomous activity loop that checks outcomes and chooses what to do next, without fixed quotas.
- Broader world navigation, grounded object state, conversation and longer-term memory.
- Clarify tool-result versus snapshot coordinate discrepancies.

## หมายเหตุภาษาไทย

**Sunny (P2)** เป็น Farmhand ที่ AI ควบคุม ส่วน **Guy (P1)** เป็นผู้เล่นมนุษย์ และ **Luna** เป็นชื่อที่เรียก AI ผู้เลือกกิจกรรม

- โปรเจ็กต์นี้เป็น Fork ที่ใช้ **Stardew MCP ของ Duckxy** เป็นฐานและยังให้เครดิตต้นฉบับ
- **PR #1 Merge แล้วใน Fork ของเรา** หลังจาก Sunny นั่งเก้าอี้ ลุก และไปทำกิจกรรมอื่นต่อได้จริง
- **Free Play v0.2 และสคริปต์ P01–P09 ยังแยกจาก Repo** ไม่ได้ติดตั้งตามหลัง Clone
- การเล่นแบบ Autonomous Loop เต็มรูปแบบ การสังเกตตอนเช้า และความจำต่อเนื่องยังเป็นงานพัฒนา
- ยังมี C# Unit Test หนึ่งรายการที่ไม่ผ่าน ซึ่งต้องติดตามแยกจากปัญหาเก้าอี้

For upstream installation and documentation, please start with [Duckxy's Stardew MCP README](https://github.com/duckxy166/stardew-ai-agent/blob/main/README.en.md). Source code retains its [MIT License](LICENSE).
