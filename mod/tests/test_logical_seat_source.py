"""Source-only safety checks, not a replacement for a full SMAPI build or live game test."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "StardewMCP"
PLAYERS = (ROOT / "Agent/Players.cs").read_text()
SAMPLER = (ROOT / "Agent/DiagnosticEvidenceSampler.cs").read_text()
ENTRY = (ROOT / "ModEntry.cs").read_text()


def test_physical_screen_id_never_indexes_a_runtime_or_licenses_a_diagnostic_sample():
    assert "Math.Clamp(Context.ScreenId" not in PLAYERS
    assert "LogicalSeatBinding.Resolve(" in PLAYERS
    assert "gameInstances.IndexOf(currentGame)" in PLAYERS
    assert "currentGame.instancePlayerOneIndex" in PLAYERS
    assert "Players.TryCurrent" in ENTRY
    assert "seat.Screen != Context.ScreenId" not in SAMPLER
    assert "seat.Screen != confirmedLogicalSeat" in SAMPLER


def test_unmapped_screen_does_not_dispatch_gameplay_or_diagnostics():
    tick = ENTRY.split("private void OnUpdateTicked(", 1)[1].split("private static void ParkCameraInBed(", 1)[0]
    assert tick.index("if (seat == null)") < tick.index("_diagnostics.Sample(")
    assert tick.index("if (seat == null)") < tick.index("seat.Runtime.Tick();")
    assert "_diagnostics.SaveLoaded(Players.TryCurrent?.Screen);" in ENTRY
    assert "_diagnostics.MenuChanged(Players.TryCurrent?.Screen);" in ENTRY
