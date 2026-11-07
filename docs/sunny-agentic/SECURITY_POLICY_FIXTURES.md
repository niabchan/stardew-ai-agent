# Test-only HTTP/MCP security policy

This is an executable acceptance proposal based on
[the security boundary](HTTP_MCP_SECURITY_BOUNDARY.md) and
[its source review](HTTP_MCP_SECURITY_REVIEW.md). It does **not** harden production
HTTP/MCP. No production source, configuration, route or dispatcher contract changes.

`mod/StardewMCP.Tests/FakeSecurityBoundary.cs` and `SecurityBoundaryTests.cs`
follow the existing game-free xUnit / `FakeEvidenceHttp` convention. The SDK
includes these files only in the test project; the mod does not reference them.
No listener, sockets, saves, game assemblies, credential files or external clients
are used. Credentials, session IDs, epochs and seat state are synthetic.

| Proposed boundary | Regression coverage |
| --- | --- |
| Authentication and authorization | Missing, wrong, expired, revoked and rotated credentials; separate operator/log/diagnostic grants cannot act as P2; missing grants fail closed |
| Validation before effects | Exact route/method/authority allowlists; IPv4/IPv6 loopback peer; all Origin headers denied; browser simple POST media types, duplicate-header flag, query ambiguity, JSON shape/version/id/params, unknown and mutation tools |
| Denial privacy and effects | Empty denial body, no session disclosure or wildcard CORS; unchanged reads, contact, enqueue, session count, session-break/deadline counters, roles and clock flags |
| Session ownership | Initialization required; foreign caller with identical scope denied; predictable legacy session rejected; owner-only DELETE invalidates session and queued work |
| Save lifecycle | Repeated same-process synthetic epochs; old sessions and accepted work denied after epoch change; fresh initialization required |
| P1/P2 isolation | No default-seat/P1 MCP, aggregate state, runtime control, feed or evidence routes; no P1 projection or consent bypass; status result allowlists only P2 seat/status |
| Discovery | Initialize, ping, tools/list and initialized notification leave contact, clock, deadline and role state unchanged |
| Execution guard | Queued status rechecks credential validity, owner, epoch, role, activity and disconnect before simulated contact/tool/read counters |
| Availability | UTF-8 byte, read-duration, batch, queue, connection and request budgets; exact byte boundary; whole-batch preflight prevents partial admission; queue recovers when drained |

The model intentionally supports only native P2 discovery and a metadata-only
`status` tool. It proposes strict JSON/media-type handling and whole-batch
admission, rather than implementing full MCP interoperability. Limits are small
fixture constants, not production tuning. The request budget resets by fixture
epoch, not elapsed time. Connection count, elapsed body-read time, duplicate-header
and disconnect flags are supplied inputs; there is no real concurrent reader,
header parser or timer. Session labels have no cryptographic strength. Synthetic
grants express ownership and rotation, not secret provisioning or OS ACL policy.
The fixture is sequential and does not establish atomicity under concurrent callers.

Run with the existing test project:

```sh
dotnet test mod/StardewMCP.Tests
python -m pytest -q mod/tests reference/sunny_gift/tests
```

Existing production `McpDispatcherTests` deliberately retain current contact and
session behavior. Passing the new tests establishes only the proposal above.
Production adapter integration, HTTP.sys/Windows IPv6/Host/header parsing, real
clock/freeze semantics, cancellation races, streaming/timeouts, response limits,
rate fairness, mutation completion ambiguity and retry safety remain unvalidated.
The model cancels queued work before execution; it makes no promise to undo a
mutation once execution has begun. There is no retry mechanism.

External Luna, native launcher/PowerShell, overlay/replay at default/custom ports,
OBS, runner and watchdog compatibility remains unvalidated. A full mod build and
Windows/SMAPI operator pilot require a separate authorized environment. No live
endpoint checks, original or test saves, secrets, DLL deployment or PR merge are
part of this fixture work. Future enforcement must separately review these design
choices and wire real inputs/effects into policy before claiming a security fix.
