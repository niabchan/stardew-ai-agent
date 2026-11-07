# Sunny Phase 2 — C# read-only diagnostic observation spike

Implementation scope authorized by the Phase 2 task. Baseline is
`docs/sunny-agentic-design-review-round1`, merged PR #14,
`8e425c10fa1c323a2086d497fe0f14fb33bb7658`. The Phase 1 research-only documents
remain historical guidance; this small implementation does not enable actions.

## What is implemented

- `Agent/DiagnosticEvidence.cs`: immutable scope/capture/prompt/response copies,
  process clock identity, provisional load/branch identities, opaque farmer aliases,
  seat incarnations, candidate prompt instances/revisions and two latest-only slots.
  No save identifier or checkpoint ancestry is discovered. Both remain null.
- `Agent/DiagnosticEvidenceSampler.cs`: normal own-screen P1/P2 update copier.
  ModEntry calls it before this callback's seat bookkeeping, split-screen helpers,
  runtime, watchers and HTTP refresh. It never invokes those paths itself. Existing
  automation can still change a menu later in the same frame; capture is no action guard.
- ModEntry host SaveLoaded invalidates both seats and establishes a new provisional
  load/branch. P2 SaveLoaded only retires P2 while joining; it never mints a host epoch.
  Title return clears authority. Candidate MenuChanged invalidates the current screen.
- No field, controller role, contact/timeout/freeze flag, mailbox, runtime lane or
  gameplay state is intentionally written by the sampler. Original monotonic ticks,
  clock frequency, UTC and screen tick belong to the capture and never to a read.
- An ordinary ready tick binds its own farmer by private reference identity. Role
  mismatch, unready screen, farmer replacement or join retires its incarnation.
  No names, multiplayer farmer IDs, save paths, hashing, logs or disk export are added.
- Bounds: two latest captures, 2,048 question characters, 16 responses, 256 characters
  per label. Truncation is explicit incomplete/unavailable evidence. Inventory and
  semantic response keys remain unsupported. Non-dialogue menus are unsupported,
  observed no menu is absent, and unavailable is never interpreted as absence.

## Opt-in configuration

All flags default to false, independently of debug and AI configuration:

```json
{
  "DiagnosticObservation": {
    "CollectionEnabled": false,
    "AllowHumanP1Collection": false,
    "HttpDisclosureEnabled": false
  }
}
```

Collection requires `CollectionEnabled`. P1 additionally requires explicit
`AllowHumanP1Collection` and an already configured human role; P2 requires an AI role.
The sampler never changes either role. Existing repository defaults include AI P1;
those defaults are not silently rewritten. A mismatched role produces no capture.
P3/P4 are excluded. Configuration changes clear both diagnostic slots on the next
normal update. These flags have no remote setter. No config menu controls are added.

`HttpDisclosureEnabled` is **reserved and ineffective**: setting it true does not
register a route, expose a cache or enable collection. Its change also clears captures.
There is no supported external reader in this PR. Inspection is limited to isolated
tests and future authorized in-process diagnostics. Raw samples remain sensitive
in-memory data while collection is enabled.

## Continuity and capability limits

Unchanged continuous synthetic captures preserve an instance and revision. A changed
question, question flag or ordered labels increments revision. Replacement menus get
new instances even when text matches. Menu events, nonconsecutive screen ticks,
more than one process-monotonic second between samples, transitions, incomplete copy
or coverage loss break continuity. Both entry into uncertainty and recovery retire
candidate identity; it cannot be revived by matching text. The one-second threshold
is a conservative diagnostic bound, not a proof of safety. Reads reject wrong clocks,
negative/invalid ages, stale samples and retired scopes without restamping.

**Actual SMAPI/menu lifecycle coverage is unverified.** The real bridge always supplies
`LifecycleCoverage=false`; real captures consequently have `IdentityKnown=false` and
new candidate prompt instances on each sample. Pure fixture tests can assert coverage
and exercise stable revisions, but do not demonstrate game callback semantics.
No C# Sunny Gift token format is introduced: `OfferToken` is always null. No offers,
decisions, attempts or reference Python dispatches are connected to these captures.

The following stay hard-coded false, with no configuration override:

- `guarded_dispatch`
- `gift_classification`
- `transfer_verification`
- `checkpoint_reconciliation`

No response key inference, Yes/No classifier, inventory transfer claim, checkpoint
linkage, durable history, Luna call, legacy respond, MCP observation/action tool or
controller integration is implemented. Latest captures from P1/P2 are independent,
not an atomic two-seat snapshot. CPU/allocation impact and game callback ordering
have not been measured. This is diagnostic evidence, not actionable identity.

## HTTP blocker and fake policy fixture

PR #14 requires secure credential provisioning, independent seat/field grants,
revocation, redaction, authority and Origin restrictions, private headers and bounded
requests. This spike does not establish an operator-only high-entropy credential
provisioning/rotation mechanism or validate real HttpListener parsing, OS binding,
browser/DNS-rebinding behavior, concurrent revocation or connection-level limits.
Adding a real route to the current wildcard-CORS handler without those checks would
expose sensitive human data. **Real HTTP evidence disclosure is not implemented.**
AgentHttp and Players are unchanged; `/api/state` is not a replacement evidence API.
Existing legacy HTTP routes retain their pre-existing exposure, including wildcard
CORS and unauthenticated state/log/control surfaces; this PR does not harden them.
No evidence cache is included in their state or logging objects.

`StardewMCP.Tests/FakeEvidenceHttp.cs` is a test-only request policy/projection design
fixture. It is not linked into the mod and cannot listen. It exercises native-only
GET, exact loopback authorities/port and peer checks, rejecting every Origin,
fixed discovery/disabled output, hashed constant-time bearer comparison, expiry,
rotation/revocation with cache clearing, explicit seat and metadata/raw field grants,
exact unambiguous query grammar, bounded requests, no-store/nosniff JSON and no CORS
headers on every response. Credentials are visibly synthetic test strings, not
production entropy or provisioning examples. Its synthetic budget is not a real
server rate/connection limit. IPv6 is deliberately unsupported in this fixture.

Default metadata projection omits raw text/labels, menu/offer tokens, farmer aliases
and world identities. A P1 canary deliberately embedded inside P2 text/labels is absent
from metadata, denials, discovery and disabled responses. Explicit raw grants can
reveal another person's content; seat permission alone does not sanitize it. Wrong-seat
cache entries fail closed. Reads only call the immutable cache reader after policy;
the fixture cannot invoke runtime/tools, mark contact, consume mail or mutate a game.
No claim about a real listener follows from these tests.

## Validation

Commands run from the repository root, with SDK 8.0.419 and installed .NET 6 runtime:

```sh
DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages \
  /workspace/.dotnet/dotnet test mod/StardewMCP.Tests --no-restore \
  --logger 'trx;LogFileName=full.trx' --results-directory work/test-results
.venv/bin/python -m pytest -q mod/tests reference/sunny_gift/tests
git diff --check
```

Initial implementation results: **326 passed, 0 failed, 0 skipped** in C# (268 existing + 58 new
cases, including fake HTTP and sampler-shim cases); **164 passed, 1 xfailed** in
Python. The expected failure is the existing `close_menu` missing `reason` parameter
source check (`mod/tests/test_tool_sources.py`). `git diff --check` passed.

The first C# attempt compiled but VSTest aborted because the sandbox disallowed its
local communication socket; the successful test runs used the approved socket-capable
execution context. An initial focused run found 1 failing coverage-gap case (55 passed);
identity retirement on coverage loss was corrected before the successful full runs.
The final compilation emitted no compiler warnings. Earlier shim-only unassigned-field
warnings were removed by using test properties. No prior BrainTests failure reproduced.

The test project compiles the pure cache and the actual sampler against minimal,
test-only Game1/Context/DialogueBox/seat shims. The shims have no gameplay methods.
The ModEntry/real SMAPI integration remains uncompiled: the full-mod build-only
attempt described below failed before compilation. Shim compilation cannot establish
real API/version/event compatibility. No Stardew Valley,
real saves, deployed DLLs, controller or model was accessed; no deployment or merge.

Later review must validate host/farmhand ordering, menu event completeness and
same-object reuse with known game/SMAPI versions, assess allocations/frame impact,
and separately complete secure native transport before disclosure. Any operator game
validation requires separate authorization and a backed-up Test_ save. Classification,
action guards, causal transfer proof and checkpoint reconciliation each require their
own evidence and review before their capability can become true.


## Integration validation follow-up (PR #15)

Build prerequisite inspection found no supported Stardew Valley/SMAPI assemblies in
workspace or /opt build locations, no cached Pathoschild.Stardew.ModBuildConfig
package, no mod `obj/project.assets.json`, and no standard Linux Steam Stardew
installation directory. The repository documents Stardew Valley 1.6+ and SMAPI 4.0+;
no installed versions could be established. No game was installed and no saves or
installed/deployed mod files were read or changed.

Attempted build-only validation, from the repository root:

```sh
DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages \
  /workspace/.dotnet/dotnet build mod/StardewMCP/StardewMCP.csproj --no-restore \
  -p:EnableModDeploy=false -p:EnableModZip=false \
  -p:OutputPath=/workspace/stardew-ai-agent/work/integration-build/
```

**Result: exit 1, Build FAILED, 0 warnings, 1 error.** SDK 8.0.419 reported
`NETSDK1004`: assets file `mod/StardewMCP/obj/project.assets.json` not found;
run a NuGet restore to generate it. This is a dependency-resolution failure before
C# compilation, not a compiler result for ModEntry. No restore/download, substitute
game assemblies, deployment, zip packaging or game launch was attempted. Even a
package restore would not supply the missing supported proprietary game/SMAPI assembly
set. Actual full-mod and ModEntry API/version compatibility remain **unverified**.

Callback source review and focused change:

| Hook | Ordering and scope reviewed |
| --- | --- |
| SaveLoaded | A single subscription still calls OnSaveLoaded. Diagnostic invalidation now runs first, before SplitScreen/load helpers or possible menu events. The sampler dispatches by current screen: host 0 establishes a fresh provisional epoch and clears both slots; P2 only retires its own joining slot. An early P2 callback cannot establish authority. Existing host-only role resolution and brain startup stay behind the non-host return. |
| MenuChanged | One subscription invalidates only Context.ScreenId. No sampler capture or gameplay helper runs in this event. Missed/in-place transitions remain unverified; lifecycle coverage stays false. |
| ReturnedToTitle | Invalidates all diagnostic authority before existing brain/split-screen teardown. Repeated per-screen title callbacks conservatively clear again; no rollback or action cancellation is claimed. |
| UpdateTicked | One sample on the ordinary current-screen callback, before seat.OnTick, split-screen helpers, runtime, watchers and HTTP refresh. Existing downstream behavior remains unchanged. No extra update/runtime invocation is used to acquire evidence. |

`mod/tests/test_diagnostic_integration.py` adds two isolated **source wiring** checks:
single subscriptions and relative ordering in the actual ModEntry source. They do not
compile ModEntry, instantiate SMAPI events or prove actual event delivery/order.
Three additional C# cases exercise the actual sampler with shims: host/P2 load
routing (including pre-host quarantine and rejoin) and injected player/menu read
failures. Existing menu/title/update sampler tests remain in place.

The defensive catch is retained as `catch (Exception)` so a diagnostic read failure
can retire evidence without interrupting ordinary gameplay callbacks. Game1.player
readiness access is now inside that boundary as well. Two internal in-memory values
make failure distinguishable from ordinary unavailable/disabled sampling:
`CaptureFailureCount` is a saturating process-lifetime aggregate; `LastSampleFailed`
is reset on each Sample invocation and set only on caught failure. They retain no
exception type/message/stack, dialogue, seat/farmer/world identifier or timestamp.
They are game-thread diagnostics with no HTTP, logging, persistence or automatic
recovery action. Normal unavailable evidence does not increment the counter; recovery
keeps the cumulative count and cannot restore the retired prompt instance. This is
best-effort exception isolation, not recovery from process-fatal/resource failures.

Follow-up test commands:

```sh
DOTNET_CLI_HOME=/workspace/.dotnet-home NUGET_PACKAGES=/workspace/.nuget/packages \
  /workspace/.dotnet/dotnet test mod/StardewMCP.Tests --no-restore \
  --logger 'trx;LogFileName=followup.trx' --results-directory work/test-results
.venv/bin/python -m pytest -q mod/tests reference/sunny_gift/tests
git diff --check
```

**Results: C# 329 passed, 0 failed, 0 skipped; Python 166 passed, 1 xfailed;
whitespace check passed.** The existing expected Python failure is still close_menu's
missing reason parameter. C# ran with the approved local VSTest socket context and
emitted no compiler warnings. These are isolated tests, not a passing full-mod build.
All opt-ins still default false, real HTTP disclosure remains unimplemented, and all
four restricted capabilities stay false. No model/gameplay/controller integration,
deployment or merge was added.
