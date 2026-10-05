using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace Atlas3K.App;

/// <summary>Code access to Themes/Dark.xaml (for windows built in code) plus small shared UI helpers.</summary>
public static class Theme
{
    public static Brush Brush(string key) => (Brush)Application.Current.Resources[key];
    public static FontFamily IconFont => (FontFamily)Application.Current.Resources["IconFont"];
    public static FontFamily MonoFont => (FontFamily)Application.Current.Resources["MonoFont"];

    /// <summary>Segoe Fluent / MDL2 glyphs used across the app.</summary>
    public static class Glyph
    {
        public const string Play = "", Stop = "", Save = "", Open = "", New = "",
            Package = "", Check = "", Error = "", Warning = "", Pending = "",
            Running = "", Skipped = "", Folder = "", Copy = "", Build = "",
            Settings = "", Info = "", Map = "", Terrain = "", Scene = "",
            Tiles = "", Battle = "", Up = "", Down = "", Delete = "", Lock = "",
            Tag = "", Star = "";
    }

    public static TextBlock Icon(string glyph, double size = 14, Brush? brush = null) => new()
    {
        Text = glyph, FontFamily = IconFont, FontSize = size, VerticalAlignment = VerticalAlignment.Center,
        Foreground = brush ?? Brush("Text"),
    };

    /// <summary>A button with an icon glyph and a label.</summary>
    public static Button IconButton(string glyph, string label, RoutedEventHandler click, string? tooltip = null, Style? style = null)
    {
        var b = new Button
        {
            Content = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                Children = { Icon(glyph, 13), new TextBlock { Text = label, Margin = new Thickness(6, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center } },
            },
            Margin = new Thickness(0, 0, 4, 0),
            ToolTip = tooltip,
        };
        if (style is not null) b.Style = style;
        b.Click += click;
        return b;
    }

    public static TextBlock Header(string text, double top = 10) => new()
    {
        Text = text, Style = (Style)Application.Current.Resources["Header"], Margin = new Thickness(0, top, 0, 4),
    };
}
