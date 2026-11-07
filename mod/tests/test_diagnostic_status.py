"""Source wiring only; game-free tests compile the reader, not ModEntry/SMAPI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "StardewMCP"


def test_status_is_registered_once_as_an_explicit_local_console_callback():
    source = (ROOT / "ModEntry.cs").read_text()
    assert source.count('"sunny_observe_status"') == 1
    registration = source.split('"sunny_observe_status"', 1)[1].split(";", 1)[0]
    assert '(_, _) => Monitor.Log(_diagnostics.ReadStatus(), LogLevel.Info)' in registration
    assert source.count("_diagnostics.ReadStatus()") == 1
    for path in ROOT.rglob("*.cs"):
        if path.name != "ModEntry.cs":
            assert "sunny_observe_status" not in path.read_text()


def test_status_reader_has_no_gameplay_or_sampling_dependencies():
    source = (ROOT / "Agent/DiagnosticEvidenceSampler.cs").read_text()
    # ReadStatus is now a block-bodied method; isolate its entire body rather than
    # assuming the old expression-bodied spelling. Keep the source-only safety check.
    start = source.index("internal string ReadStatus()")
    opening = source.index("{", start)
    depth = 0
    closing = None
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                closing = index
                break
    assert closing is not None
    reader = source[opening : closing + 1]
    assert "_cache.ReadStatus(" in reader
    for forbidden in ("Game1.", "Players.", "Sample(", "Configure(", "MarkContact",
                      "Enqueue", "TakeMail", "Freeze", "MenuChanged", "HostLoaded"):
        assert forbidden not in reader
    projection = (ROOT / "Agent/DiagnosticStatus.cs").read_text()
    for forbidden in ("Game1.", "Players.", "EvidenceCapture", "EvidencePrompt", "Exception"):
        assert forbidden not in projection
    cache = (ROOT / "Agent/DiagnosticEvidence.cs").read_text()
    projection = cache.split("internal DiagnosticStatus ReadStatus(", 1)[1]
    for forbidden in ("Capture(", "Configure(", "Retire(", "Clear(", "BreakScreen(",
                      "HostLoaded(", "MarkContact", "Enqueue", "TakeMail", "Game1."):
        assert forbidden not in projection
