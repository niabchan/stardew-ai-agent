# Sunny Phase 2 — local diagnostic status

Based on merged PR #15, `bb24cd3a29d720ada3a304abc4203492b04a9820`.
Invoke `sunny_observe_status` manually in the local SMAPI console. No arguments
are needed; supplied arguments are ignored and never echoed. This command prints
only a bounded metadata report. It does not enable collection. All observation
configuration defaults remain false.

The command always reports **P2 only**, including when explicit human P1 collection
consent is enabled. It reports the consent flag but never projects P1 captures.
P1 dialogue embedded in P2 text is also omitted: no text or response labels enter
the status projection. No IDs, names, paths, inventory, tokens, menu type, exception
details or personal data are printed. HTTP disclosure is always reported as
**not implemented**, regardless of the reserved HTTP configuration flag.

The report includes collection/consent flags, P2 sampling status, current captured
sequence count, monotonic capture age, prompt availability, lifecycle coverage,
identity confidence and the existing process aggregate `CaptureFailureCount` and
`LastSampleFailed`. The failure diagnostics are aggregate health counters from
the existing sampler, not per-seat observations; reads never reset them. The
count saturates at `long.MaxValue`. Normal unavailable sampling is not a failure.

Capture count is the sequence within the current P2 seat incarnation, not durable
history or a process total. Retirement/reload/join resets it to zero until a new
capture. Menu invalidation removes the latest snapshot; subsequent capture can
continue the sequence. Missing evidence has unavailable age. A negative monotonic
age or age over the existing one-second diagnostic gap bound is stale. Stale
captures retain their original age/count metadata, but prompt and identity are
reported unavailable/unknown. This age threshold is not an action guard. The real
sampler still reports unverified lifecycle coverage and unknown prompt identity.

The cache returns a new immutable metadata record from the existing immutable
capture under its lock. Reads only consult configuration, the cache and the
process clock. A configuration mismatch before the next ordinary sample hides
old evidence without clearing or reconfiguring the cache. Reading cannot capture,
restamp, change lifecycle identity, mark AI contact, enqueue runtime work, consume
mail, change freeze state, interact with menus or modify game state. The console
callback is the only production caller; no periodic log, MCP tool or HTTP route
is added. SMAPI may retain manually requested output in its normal console log.

All restricted capabilities remain hard-coded false: `guarded_dispatch`,
`gift_classification`, `transfer_verification`, `checkpoint_reconciliation`.

## Validation

From the repository root:

```sh
DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages \
  /workspace/.dotnet/dotnet test mod/StardewMCP.Tests --no-restore \
  --logger 'trx;LogFileName=status-final.trx' --results-directory work/test-results
.venv/bin/python -m pytest -q mod/tests reference/sunny_gift/tests
git diff --check
```

Game-free C# tests cover disabled/missing snapshots, repeated passive reads,
fresh/stale/invalid-age captures, incomplete/menu/title invalidation, host reload,
P2 rejoin, consent isolation, config changes before sampling, redaction, failure
and recovery counters, saturation and unchanged original capture objects/times,
roles/contact/mail bookkeeping. The actual reader/sampler compile against game-free
shims with no runtime enqueue, TakeMail, freeze or menu interaction methods.
Python checks verify the single console registration, sole explicit callback and
absence of game/sampling dependencies in the reader. These do not compile ModEntry
or certify SMAPI callback compatibility.

Final results: **337 C# passed, zero failed/skipped; 168 Python passed, one existing
xfail** (`close_menu` reason-parameter source check); `git diff --check` passed.
The initial C# invocation compiled but VSTest aborted on a sandbox-denied local
communication socket. The final successful run used an approved socket-capable
execution context. No baseline BrainTests failure reproduced.

Build-only attempt:

```sh
DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages \
  /workspace/.dotnet/dotnet build mod/StardewMCP/StardewMCP.csproj --no-restore \
  -p:EnableModDeploy=false -p:EnableModZip=false \
  -p:OutputPath=/workspace/stardew-ai-agent/work/status-build/
```

Exit 1, zero warnings, one `NETSDK1004`: missing
`mod/StardewMCP/obj/project.assets.json`. This fails before C# compilation.
No supported Stardew Valley/SMAPI assemblies or ModBuildConfig package were found
in the checked workspace/opt build locations. Full-mod compatibility remains
unverified. No game launch, DLL deployment, save access, Luna connection or merge.
