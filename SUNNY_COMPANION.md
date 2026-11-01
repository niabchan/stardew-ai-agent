# Sunny AI Companion — experimental fork notes

> Work in progress. This is a personal development fork of [Duckxy's Stardew MCP](https://github.com/duckxy166/stardew-ai-agent), not a separate finished mod or an official upstream release.

## What is Sunny?

**Sunny** is an AI-controlled farmhand (P2) intended to share a Stardew Valley farm with a human player (P1, in-game name **Guy**). The objective is an AI *companion*, not just an optimized farming bot: Sunny can observe the world, decide on personal activities, interact with game objects, and sometimes converse with the human player.

The longer-term design is **observe → decide → act → check the result → continue**, with room for the AI to remain idle, change plans, or respond to events. Fixed quotas for talking to Guy or performing activities have **not** been established. Existing one-shot supervised scripts were early testing controls, not rules for Sunny's personality or daily life.

## How this fork relates to the project

- **Upstream Stardew MCP (Duckxy)** provides split-screen seats, game actions, observation, and an MCP/HTTP interface.
- **This fork** is where we test game-side compatibility improvements for Sunny, while keeping upstream credit and history.
- **Sunny's Python/PowerShell prototypes (P01–P09)** are separate local artifacts. They are **not included in this GitHub fork** and do not automatically change when this repository changes.
- **P1** remains human-controlled. **P2** is the AI farmer. Neither a fork nor a GitHub commit changes the installed game until a new mod build is explicitly installed.

## Current experiment: sitting → standing

On a test farm, Sunny could sit on an Oak Chair at (7,4), but `walk_to(7,5)` and a repeated `interact(7,4)` produced `no_path` while Sunny remained seated. The existing `interact` implementation tries to walk beside its target before the action button is pressed.

[Draft PR #1](https://github.com/niabchan/stardew-ai-agent/pull/1) tests a narrow fix: if the AI farmer is *already seated on the targeted furniture*, use the game's `StopSitting()` entry point and then verify the seated state cleared. It does not change ordinary interactions, force daily schedules, or control P1.

**Verification status:** The source change is committed for review. It is **not yet compiled against the user's Stardew Valley/SMAPI installation or confirmed in live gameplay**. Please do not assume the feature works from reading the code alone.

### Verification before merging

1. Compile against installed Stardew Valley/SMAPI. To avoid replacing the installed mod during a compile-only check, use: `dotnet build mod/StardewMCP -c Release -p:EnableModDeploy=false -p:EnableModZip=false`.
2. Run game-free tests: `dotnet test mod/StardewMCP.Tests` and `python -m pytest -q mod/tests` (after installing pytest).
3. Back up the test save and current installed mod before copying any built files.
4. In a test save, verify P2 can sit using `interact(chair)`, stand using `interact(same chair)`, and then move independently; confirm P1 controls are unaffected.
5. Keep the PR as a **draft** and do not merge until the checks above are complete.

## หมายเหตุภาษาไทย

พื้นที่นี้เป็น **Fork สำหรับทดลองพัฒนา Sunny AI Companion** โดยใช้ Stardew MCP ของ Duckxy เป็นฐาน ไม่ใช่ Mod รุ่นใหม่ที่เผยแพร่สำเร็จแล้ว

- **Guy (P1)** คือมนุษย์ผู้เล่น ส่วน **Sunny (P2)** คือ Farmhand ที่ AI ควบคุมเอง
- สคริปต์ Python/PowerShell รุ่น P01–P09 ของ Sunny ยังคงแยกจาก Repository นี้
- การกำหนดให้ทักหรือทำกิจกรรมวันละกี่ครั้งในโปรโตไทป์เดิมเป็นเพียงเงื่อนไขทดสอบ ไม่ใช่กฎพฤติกรรมถาวร
- PR #1 ทดลองแก้กรณี Sunny นั่งเก้าอี้แล้วลุกไม่ได้ เพราะระบบ `interact` พยายามเดินก่อนโต้ตอบ
- **ยังต้อง Build และทดสอบในเกมจริงก่อน Merge** และห้ามใส่ API key, Save, Log หรือข้อมูลส่วนตัวลง Repository

We gratefully credit Duckxy and the original [Stardew MCP project](https://github.com/duckxy166/stardew-ai-agent). Please consult upstream's README, docs, and license for the original project.
