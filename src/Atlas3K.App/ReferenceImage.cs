using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Atlas3K.Core;

namespace Atlas3K.App;

/// <summary>
/// A reference picture (a historical map, a CAIME export, a sketch) laid over a 2D view at a set opacity, stretched over
/// the whole campaign map so the same image lines up in the terrain painter, the tile map editor and the scene editor's
/// top view. One per map, shared by every open window; the path, opacity and visibility persist in the app settings.
/// </summary>
public sealed class ReferenceImage
{
    private static readonly Dictionary<string, ReferenceImage> ByMap = new(StringComparer.OrdinalIgnoreCase);

    private readonly string _map;

    public BitmapSource? Image { get; private set; }
    public string? FilePath { get; private set; }
    public double Opacity { get; private set; } = 0.5;
    public bool Visible { get; private set; } = true;
    public string? Error { get; private set; }

    /// <summary>Raised after any change; views redraw.</summary>
    public event Action? Changed;

    public static ReferenceImage For(string map)
    {
        if (!ByMap.TryGetValue(map, out var image)) ByMap[map] = image = new ReferenceImage(map);
        return image;
    }

    private ReferenceImage(string map)
    {
        _map = map;
        var values = AppSettings.Current.Values;
        if (double.TryParse(values.GetValueOrDefault(Key("opacity")), System.Globalization.CultureInfo.InvariantCulture, out var o)) Opacity = Math.Clamp(o, 0.05, 1);
        Visible = values.GetValueOrDefault(Key("visible")) != "false";
        if (values.GetValueOrDefault(Key("path")) is { Length: > 0 } path && File.Exists(path)) TryRead(path);
    }

    private string Key(string what) => $"reference.{_map}.{what}";

    public bool Load(string path)
    {
        if (!TryRead(path)) { Changed?.Invoke(); return false; }
        Visible = true;
        Persist();
        return true;
    }

    public void Clear()
    {
        Image = null;
        FilePath = null;
        Error = null;
        Persist();
    }

    public void SetOpacity(double opacity)
    {
        Opacity = Math.Clamp(opacity, 0.05, 1);
        Persist();
    }

    public void SetVisible(bool visible)
    {
        Visible = visible;
        Persist();
    }

    /// <summary>Draws the image over <paramref name="mapOnScreen"/>, the whole map's rectangle in view coordinates.</summary>
    public void Draw(DrawingContext dc, Rect mapOnScreen)
    {
        if (Image is null || !Visible || mapOnScreen.IsEmpty) return;
        dc.PushOpacity(Opacity);
        dc.DrawImage(Image, mapOnScreen);
        dc.Pop();
    }

    private bool TryRead(string path)
    {
        try
        {
            var bmp = new BitmapImage();
            bmp.BeginInit();
            bmp.CacheOption = BitmapCacheOption.OnLoad; // don't keep the file locked
            bmp.UriSource = new Uri(Path.GetFullPath(path));
            bmp.EndInit();
            bmp.Freeze();
            Image = bmp;
            FilePath = path;
            Error = null;
            return true;
        }
        catch (Exception ex) when (ex is IOException or NotSupportedException or UnauthorizedAccessException or ArgumentException or InvalidOperationException)
        {
            Error = $"{Path.GetFileName(path)}: {ex.Message}";
            return false;
        }
    }

    private void Persist()
    {
        var values = AppSettings.Current.Values;
        values[Key("path")] = FilePath ?? "";
        values[Key("opacity")] = Opacity.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture);
        values[Key("visible")] = Visible ? "true" : "false";
        try { AppSettings.Current.Save(); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
        Changed?.Invoke();
    }

    /// <summary>Load / Clear buttons, a Show box and an opacity slider for <paramref name="image"/>; follows changes
    /// made in other windows until <paramref name="owner"/> closes.</summary>
    public static StackPanel Panel(ReferenceImage image, Window owner)
    {
        var panel = new StackPanel();
        var buttons = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 4) };
        var load = new Button { Content = "Load image…", Padding = new Thickness(8, 1, 8, 1), Margin = new Thickness(0, 0, 4, 0) };
        var clear = new Button { Content = "Clear", Padding = new Thickness(8, 1, 8, 1) };
        buttons.Children.Add(load);
        buttons.Children.Add(clear);
        panel.Children.Add(buttons);
        var show = new CheckBox { Content = "Show", Margin = new Thickness(0, 2, 0, 2) };
        panel.Children.Add(show);
        var opacityLabel = new TextBlock();
        panel.Children.Add(opacityLabel);
        var opacity = new Slider { Minimum = 0.05, Maximum = 1, SmallChange = 0.05, LargeChange = 0.1 };
        panel.Children.Add(opacity);
        var file = new TextBlock { Foreground = Theme.Brush("DimText"), FontSize = 11, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 2, 0, 0) };
        panel.Children.Add(file);
        panel.Children.Add(new TextBlock
        {
            Text = "Stretched over the whole map, so one image lines up in the painter, the tile map editor and the scene editor. View only: never exported.",
            Foreground = Theme.Brush("DimText"), FontSize = 11, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 0),
        });

        var syncing = false;
        void Sync()
        {
            syncing = true;
            show.IsChecked = image.Visible;
            show.IsEnabled = clear.IsEnabled = opacity.IsEnabled = image.Image is not null;
            opacity.Value = image.Opacity;
            opacityLabel.Text = $"Opacity: {image.Opacity * 100:F0}%";
            file.Text = image.Error ?? (image.FilePath is { } p ? $"{Path.GetFileName(p)} ({image.Image!.PixelWidth}x{image.Image.PixelHeight})" : "No image loaded.");
            file.ToolTip = image.FilePath;
            syncing = false;
        }
        load.Click += (_, _) =>
        {
            var dialog = new Microsoft.Win32.OpenFileDialog
            {
                Title = "Reference image (stretched over the whole map)",
                Filter = "Images (*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.gif)|*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.gif|All files (*.*)|*.*",
            };
            if (image.FilePath is { } current && Path.GetDirectoryName(current) is { } dir && Directory.Exists(dir)) dialog.InitialDirectory = dir;
            if (dialog.ShowDialog(owner) == true) image.Load(dialog.FileName);
        };
        clear.Click += (_, _) => image.Clear();
        show.Click += (_, _) => { if (!syncing) image.SetVisible(show.IsChecked == true); };
        opacity.ValueChanged += (_, _) => { if (!syncing) image.SetOpacity(opacity.Value); };
        image.Changed += Sync;
        owner.Closed += (_, _) => image.Changed -= Sync;
        Sync();
        return panel;
    }

    /// <summary>A small tool window with <see cref="Panel"/>, for windows without a side panel.</summary>
    public static void ShowWindow(Window owner, ReferenceImage image, string map)
    {
        var window = new Window
        {
            Title = AppInfo.Title($"Reference image — {map}"), Width = 320, SizeToContent = SizeToContent.Height, ResizeMode = ResizeMode.NoResize,
            Owner = owner, WindowStartupLocation = WindowStartupLocation.CenterOwner, ShowInTaskbar = false,
            Background = Theme.Brush("Panel"), Foreground = Theme.Brush("Text"),
        };
        window.Content = new Border { Padding = new Thickness(12), Child = Panel(image, window) };
        window.Show();
    }
}
