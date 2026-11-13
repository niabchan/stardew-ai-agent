"""Read-only, G0-only assessment of a *synthetic* P11 MCP reply envelope.

This file never calls the Mod, Luna, the Windows controller, or HTTP. It
identifies only reply credibility, NOT verified effects or authorization.
The historical P11 mcp_call() itself has not been modified.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReplyAssessment:
    verdict: str
    reason: str = "unknown"
    text: str = ""

    @property
    def unresolved(self):
        return self.verdict != "ACK_REOBSERVE"


def inspect_mcp_reply(envelope, *, expected_id=20013):
    """Classify one simulated JSON-RPC tools/call response conservatively.

    Every UNKNOWN verdict means the caller must NOT blindly issue another
    effectful command. A well-formed ACK merely allows *independent*
    post-action observation; it does not verify game effects.
    """
    if not isinstance(envelope, dict):
        return ReplyAssessment("UNKNOWN_MALFORMED")
    # v0.3.10 emits a fixed ID; matching it cannot prove correlation to a
    # unique attempt (or solve process-crash / duplicate-command risks).
    if type(envelope.get("id")) is not int or envelope["id"] != expected_id:
        return ReplyAssessment("UNKNOWN_ID")
    if envelope.get("jsonrpc") != "2.0" or envelope.get("error") is not None:
        return ReplyAssessment("UNKNOWN_RPC")
    result = envelope.get("result")
    if not isinstance(result, dict):
        return ReplyAssessment("UNKNOWN_MALFORMED")
    is_error = result.get("isError")
    structured = result.get("structuredContent")
    content = result.get("content")
    if type(is_error) is not bool or not isinstance(structured, dict) or not isinstance(content, list):
        return ReplyAssessment("UNKNOWN_MALFORMED")
    ok = structured.get("ok")
    reason = structured.get("reason")
    partial = structured.get("partial", False)
    if (type(ok) is not bool or type(partial) is not bool
            or type(reason) is not str or not reason):
        return ReplyAssessment("UNKNOWN_MALFORMED")
    texts = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "text" or type(part.get("text")) is not str:
            return ReplyAssessment("UNKNOWN_MALFORMED", reason)
        texts.append(part["text"])
    message = " ".join(texts)[:500]
    if is_error == ok:
        return ReplyAssessment("UNKNOWN_CONTRADICTORY", reason, message)
    if partial:
        return ReplyAssessment("UNKNOWN_PARTIAL", reason, message)
    if not ok:
        return ReplyAssessment("UNKNOWN_TOOL_FAILURE", reason, message)
    if reason != "ok":
        return ReplyAssessment("UNKNOWN_REASON", reason, message)
    return ReplyAssessment("ACK_REOBSERVE", reason, message)


def stand_reply_hint(assessment, chair_x, chair_y):
    """Check source-specific textual hint; NEVER certify actual chair state."""
    if assessment.verdict != "ACK_REOBSERVE":
        return "STAND_UNCONFIRMED"
    if type(chair_x) is not int or type(chair_y) is not int:
        return "STAND_UNCONFIRMED"
    prefix = f"Stood up from chair at ({chair_x},{chair_y})"
    return "STAND_REOBSERVE" if assessment.text.startswith(prefix) else "STAND_UNCONFIRMED"
