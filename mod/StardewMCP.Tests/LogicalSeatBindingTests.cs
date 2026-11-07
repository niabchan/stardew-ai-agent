using StardewMCP.Agent;
using Xunit;

namespace StardewMCP.Tests;

public class LogicalSeatBindingTests
{
    [Theory]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(31)]
    public void Each_rejoined_physical_screen_remains_logical_P2(int screenId)
    {
        Assert.Equal(1, LogicalSeatBinding.Resolve(screenId, playerIndex: 1, activeInstanceIndex: 1, seatCount: 4));
    }

    [Theory]
    [InlineData(0, 0, 0, 0)]
    [InlineData(1, 2, 2, 2)]
    [InlineData(9, 3, 3, 3)]
    public void Valid_local_instances_bind_only_to_matching_logical_seats(int physical, int player, int position, int expected)
    {
        Assert.Equal(expected, LogicalSeatBinding.Resolve(physical, player, position, 4));
    }

    [Theory]
    [InlineData(0, 1, 1)]
    [InlineData(1, 0, 0)]
    [InlineData(2, 0, 0)]
    [InlineData(3, 1, 2)]
    [InlineData(3, 2, 1)]
    [InlineData(3, -1, -1)]
    [InlineData(-1, 1, 1)]
    [InlineData(150, 4, 4)]
    public void Untrusted_or_conflicting_bindings_fail_closed(int physical, int player, int position)
    {
        Assert.Null(LogicalSeatBinding.Resolve(physical, player, position, 4));
    }

    [Fact]
    public void Two_active_players_cannot_route_screen_3_to_P3_or_P4()
    {
        Assert.Equal(1, LogicalSeatBinding.Resolve(3, 1, 1, 2));
        Assert.Null(LogicalSeatBinding.Resolve(3, 2, 2, 2));
        Assert.Null(LogicalSeatBinding.Resolve(3, 3, 3, 2));
        Assert.Null(LogicalSeatBinding.Resolve(0, 1, 1, 2)); // No P1 authority on a guest.
    }
}
