# Sunny posture awareness (G0)

The standalone Python reference models Sunny's P2 chair choices with synthetic
data. SIT and STAND represent intended posture changes. STAY records a
voluntary pause. [Issue #97 gameplay design](https://github.com/niabchan/stardew-ai-agent/issues/97#issuecomment-7163650785)

| Input | Result |
| --- | --- |
| Fresh STANDING, with no current chair and an identified, available, reachable candidate | Offer SIT on that chair and STAY. |
| Fresh SEATED, with an identified current chair | Offer STAND from that chair and STAY. Candidate availability and reachability concern SIT. |
| Unknown or stale posture, or insufficient chair facts for the posture | Offer STAY. |
| An eligible SIT or STAND is selected | Record one attempt with outcome UNKNOWN. Only STAY can be offered while the attempt remains unresolved. |
| A newer, fresh observation confirms SEATED on the SIT target, or STANDING with no current chair after STAND | Mark the attempt VERIFIED. A subsequent action requires a new selection. |
| STAY is selected | Record the observation and pause offers. Reopen choices on a newer, fresh observation with changed posture, chair facts or decision context. |

Each state consumes observations for one P2, save/load incarnation and map.
Observations from other scopes or at the same or an older revision are ignored.
Feed a newer revision with `fresh=False` to represent stale evidence in the
same scope. Choices are bound to their scene and revision. A mismatched,
superseded or unavailable choice leaves the state intact.

An acknowledgement and tile position are independent of posture. A tile
change alone also leaves the STAY pause in place. An unchanged or contradictory
post-action posture, a wrong chair, or a mismatched observation leaves the
attempt UNKNOWN. The model keeps accepting same-scene observations so later
explicit posture evidence can resolve the attempt.

A STAND choice can carry a MOVE or TV prerequisite annotation. An observed
stand records `completed_prerequisite=STAND` and leaves
`selected_activity_status=not_executed`. The state contains no queue and
reopening offers schedules no activity.

## Evidence and limits

Historical P11 source distinguished voluntary STAY, an unverified chair
interaction, and a stand-only prerequisite. Those concepts informed this
standalone model. [Historical P11 contract at the inspected SHA](https://github.com/niabchan/stardew-ai-agent/blob/38dd80603f0ba63297a8ad6fe5652434782ba97e/docs/sunny-agentic/L2_L3_OFFLINE_BRIDGE.md#L74-L139)

Real integration still needs independently observed P2 posture with defined
standing semantics, a scoped chair identity and seated binding, availability
and reachability, and ordered evidence across an attempt. In particular,
`IsSitting() == false` alone is insufficient evidence of standing across real
game contexts. The pinned mod source reports map, tile and facing, and its
chair-exit handling reports an action result. [Status source](https://github.com/niabchan/stardew-ai-agent/blob/4bae8d2d840e36578caac0bf79c9cbe0931c4d63/mod/StardewMCP/Agent/WorldText.cs#L26-L56) · [Interaction source](https://github.com/niabchan/stardew-ai-agent/blob/4bae8d2d840e36578caac0bf79c9cbe0931c4d63/mod/StardewMCP/Agent/AgentTools.cs#L748-L823)

Run the synthetic suite from the repository root:

```sh
python -m pytest -q mod/tests/test_sunny_posture_g0.py
```

G0 exercises synthetic transitions only. Real seating, autonomous standing
and live gameplay remain unverified. R25 remains paused.
