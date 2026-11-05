// Minimal game-free surface for compiling the real diagnostic bridge. No gameplay methods exist.
namespace StardewModdingAPI
{
    internal static class Context
    {
        public static int ScreenId;
        public static bool IsWorldReady;
    }
}
namespace StardewValley
{
    internal static class Game1
    {
        public static int Reads;
        public static bool ThrowOnPlayerRead { get; set; }
        private static object? _player;
        private static object? _menu;
        public static object? player { get { Reads++; if (ThrowOnPlayerRead) throw new System.InvalidOperationException("PRIVATE_EXCEPTION_CANARY"); return _player; } set => _player = value; }
        public static object? activeClickableMenu { get { Reads++; return _menu; } set => _menu = value; }
        public static bool fadeToBlack { get; set; }
        public static bool isWarping { get; set; }
        public static bool newDay { get; set; }
    }
}
namespace StardewValley.Menus
{
    internal sealed class FakeResponse { public string responseText = ""; }
    internal sealed class DialogueBox
    {
        public bool isQuestion;
        public FakeResponse[]? responses;
        public string Text = "";
        public bool ThrowOnRead { get; set; }
        public string getCurrentString() => ThrowOnRead ? throw new System.InvalidOperationException("PRIVATE_EXCEPTION_CANARY") : Text;
    }
}
namespace StardewMCP.Agent
{
    internal enum SeatRole { Human, Ai, Camera, Off }
    internal sealed class PlayerSlot
    {
        public int Screen;
        public SeatRole Role;
        // Canary gameplay bookkeeping. The bridge can compile without any controller methods.
        public bool Connected, TimedOut, Released;
        public int MailCount = 3;
    }
}
