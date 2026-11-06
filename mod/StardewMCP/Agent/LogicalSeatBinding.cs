namespace StardewMCP.Agent;

/// <summary>
/// Bind a SMAPI screen to the mod's stable logical seat without relying on the screen ID.
/// PlayerIndex (One=0, Two=1...) and the active GameRunner instance ordinal must agree.
/// The caller verifies that the current Game1 object belongs to GameRunner.gameInstances.
/// </summary>
internal static class LogicalSeatBinding
{
    internal static int? Resolve(int physicalScreenId, int playerIndex, int activeInstanceIndex, int seatCount)
    {
        if (physicalScreenId < 0 || seatCount is < 1 or > 4 ||
            playerIndex < 0 || playerIndex >= seatCount || activeInstanceIndex != playerIndex)
            return null;
        // Only physical screen 0 may control the host. Rejoining P2 can receive 2, 3, 4...
        if (physicalScreenId == 0)
            return playerIndex == 0 ? 0 : null;
        return playerIndex == 0 ? null : playerIndex;
    }
}
