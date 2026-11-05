"""Source-level wiring regression only; does not compile ModEntry or certify SMAPI semantics."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "StardewMCP/ModEntry.cs").read_text()


def test_diagnostic_event_subscriptions_remain_single_and_on_expected_events():
    for subscription in (
        "helper.Events.GameLoop.SaveLoaded += OnSaveLoaded;",
        "helper.Events.Display.MenuChanged += (_, _) => _diagnostics.MenuChanged();",
        "helper.Events.GameLoop.UpdateTicked += OnUpdateTicked;",
        "helper.Events.GameLoop.ReturnedToTitle += (_, _) =>",
    ):
        assert SOURCE.count(subscription) == 1
    title = SOURCE.split("helper.Events.GameLoop.ReturnedToTitle += (_, _) =>", 1)[1].split("};", 1)[0]
    assert title.index("_diagnostics.ReturnedToTitle();") < title.index("Brains.StopAll();")


def test_diagnostic_invalidation_and_sampling_precede_existing_callback_side_effects():
    load = SOURCE.split("private void OnSaveLoaded(", 1)[1].split("private void OnUpdateTicked(", 1)[0]
    assert load.index("_diagnostics.SaveLoaded();") < load.index("SplitScreen.OnSaveLoaded();")
    assert load.index("if (Context.ScreenId != 0)") < load.index("Players.Resolve(")
    update = SOURCE.split("private void OnUpdateTicked(", 1)[1].split("private static void ParkCameraInBed(", 1)[0]
    sample = update.index("_diagnostics.Sample(seat, e.Ticks);")
    for operation in ("seat.OnTick();", "SplitScreen.HostTick();", "SplitScreen.GuestTick(",
                      "seat.Runtime.Tick();", "SleepWaitWatch.Tick(", "_http.RefreshState();"):
        assert sample < update.index(operation)
    assert SOURCE.count("_diagnostics.Sample(") == 1
