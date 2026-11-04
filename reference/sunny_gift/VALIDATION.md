# Validation record

Validated 2026-11-04 against base branch
`docs/sunny-agentic-design-review-round1` at
`5712110d2835ae5ee654598cd3818c2fb2dfc5f6`.

Git transport was unavailable through the environment proxy. The base was read
through the GitHub connector; its tracked file blob IDs were compared with the
local checkout. All pre-existing gameplay sources, existing tests, and workflow
matched the base. Only the root agent instructions and `docs/sunny-agentic/`
documents were absent locally and were materialized from the pinned base before
work. They are not changes in this PR. The independent implementation is under
`reference/sunny_gift/`; the Python CI command includes its tests.

## Architecture review update (2026-11-05, Asia/Bangkok)

Updated PR #11 from head `4e11ecedd015be8ba030667669e4ef71fd4fb3ec`.
Only `contract.py`, `tests/test_contract.py`, this validation record and the
package README changed in this update. The workflow, fixtures and gameplay
sources are unchanged. Local reference files matched the PR head's blob IDs
before editing; publication uses that exact parent through the GitHub connector.

Record keys now include the complete world object, local ID and revision;
world-scoped resolution cannot fall back to another branch. Same-world duplicate
content remains idempotent and conflicting content still rejects. Dispatch call
results now explicitly separate epoch status and whether this invocation caused
a dispatch from the original attempt's historical status. Unknown stale attempts
return null status without fabricated execution facts or dependency resolution.
The dispatch log retains world identity with each reference.

Fourteen added test cases cover all seven record kinds, each save/load/branch
identity dimension, historical dispatched/acknowledged/rejected attempts, and an
unseen stale attempt. Existing duplicate/reload tests now assert the explicit
result wrapper; the new real-gift-after-reload test reuses every local source ID
and revision while preserving distinct old and current actions/events.

| Exact command (repository root) | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q reference/sunny_gift/tests` | **43 passed in 0.12s** |
| `.venv/bin/python -m pytest -q mod/tests` | **93 passed, 1 xfailed in 2.11s** |
| `.venv/bin/python -m pytest -q mod/tests reference/sunny_gift/tests` | **136 passed, 1 xfailed in 2.03s** |
| `DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages /workspace/.dotnet/dotnet test mod/StardewMCP.Tests --no-restore` | **268 passed, 0 failed, 0 skipped**, duration 262 ms; exit 0 |

No unexpected test failures occurred in this update. The existing expected
`close_menu` missing-`reason` failure remains unchanged. The C# runner used the
same authorized sandbox permission for its local test-host socket as the initial
successful run. No SMAPI, MCP, Luna, game saves, live controllers or deployed
artifacts were accessed. Synthetic-only limitations in the README still apply.

## Initial implementation results (2026-11-04)

Run from repository root with existing `.venv` (pytest 9.2.0):

| Exact command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q reference/sunny_gift/tests` | **29 passed in 0.07s** |
| `.venv/bin/python -m pytest -q mod/tests` | **93 passed, 1 xfailed in 2.08s** |
| `.venv/bin/python -m pytest -q mod/tests reference/sunny_gift/tests` | **122 passed, 1 xfailed in 2.31s** |
| `DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages /workspace/.dotnet/dotnet test mod/StardewMCP.Tests --no-restore` | **268 passed, 0 failed, 0 skipped**, duration 216 ms; exit 0 |
| `git diff --check` | Exit 0 |

The expected failure is the existing
`test_action_tools_have_a_reason_parameter[close_menu]` in
`mod/tests/test_tool_sources.py`: `close_menu` has no `reason` parameter. It is
unchanged. The historical `BrainTests.System_prompt_fills_every_placeholder`
failure mentioned in companion notes did **not** reproduce in this run.

## Resolved development/environment failures

The first new-test run returned **4 failed, 15 passed**. Tests reused immutable
record identities while changing their content: the correction test now uses a
new verification revision and the non-action tests use a new attempt ID. The
reducer's conflict rejection was retained. The final new suite has no failures.

The default `python -m pytest --version` failed because pytest was absent from
that interpreter. A pip install attempt could not reach the proxy; the existing
repository `.venv` supplied pytest without downloading anything. Git fetch also
failed to connect to the proxy; connector Git operations were used instead.

The first C# invocation failed before testing because its default CLI home was
read-only. With the writable CLI home/package paths above, the sandboxed runner
compiled successfully but aborted on a denied local test-host socket. Re-running
the same game-free command with sandbox permission succeeded; no live service or
game was contacted. No mod/gameplay build, game test, SMAPI/MCP call, model call,
save access, controller integration or deployment was performed.
