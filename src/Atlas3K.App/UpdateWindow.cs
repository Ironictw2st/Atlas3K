using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Atlas3K.Core;
using Atlas3K.Core.Updates;

namespace Atlas3K.App;

/// <summary>
/// Help → Check for updates: the update channel (stable / unstable), the newest release on it with its notes, and
/// download + install (Atlas3K closes, the helper swaps the files and starts the new version). Also opens by itself
/// at start-up when a new version is out (<see cref="CheckAtStartupAsync"/>), and rolls back to the version an update
/// replaced. Source builds only show what is available.
/// </summary>
public sealed class UpdateWindow : Window
{
    private readonly UpdateService _service = new();
    private readonly SemVersion _current = SemVersion.TryParse(AppInfo.Version) ?? new SemVersion(0, 0, 0);
    private readonly UpdateService.InstallInfo? _installed = UpdateService.Install();
    private readonly ComboBox _channel = new() { Width = 340, Margin = new Thickness(0, 0, 8, 0) };
    private readonly CheckBox _auto = new() { Content = "Check when Atlas3K starts", VerticalAlignment = VerticalAlignment.Center };
    private readonly TextBlock _status = new() { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 10, 0, 6), FontSize = 14 };
    private readonly TextBox _notes = new()
    {
        IsReadOnly = true, TextWrapping = TextWrapping.Wrap, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Height = 260,
        FontFamily = new FontFamily("Consolas"), FontSize = 11,
    };
    private readonly ProgressBar _progress = new() { Height = 6, Margin = new Thickness(0, 6, 0, 6), Visibility = Visibility.Collapsed, Maximum = 1 };
    private readonly Button _install = new() { Content = "Download and install", Padding = new Thickness(12, 3, 12, 3), Margin = new Thickness(0, 0, 6, 0), IsEnabled = false };
    private readonly Button _skip = new() { Content = "Skip this version", Padding = new Thickness(12, 3, 12, 3), Margin = new Thickness(0, 0, 6, 0), IsEnabled = false };
    private readonly Button _page = new() { Content = "Release page", Padding = new Thickness(12, 3, 12, 3), Margin = new Thickness(0, 0, 6, 0), IsEnabled = false };
    private readonly Button _rollback = new() { Padding = new Thickness(12, 3, 12, 3), Margin = new Thickness(0, 0, 6, 0) };
    private List<ReleaseInfo> _releases = [];
    private ReleaseInfo? _offer;

    private UpdateWindow()
    {
        Title = AppInfo.Title("Updates");
        Width = 720;
        SizeToContent = SizeToContent.Height;
        WindowStartupLocation = WindowStartupLocation.CenterOwner;
        Background = Theme.Brush("Bg");
        Foreground = Theme.Brush("Text");
        ResizeMode = ResizeMode.NoResize;
        Content = BuildLayout();
    }

    private UIElement BuildLayout()
    {
        var panel = new StackPanel { Margin = new Thickness(14) };
        panel.Children.Add(new TextBlock
        {
            Text = $"You have {AppInfo.Product} {AppInfo.Version}" + (_installed is null ? " (a development build: it is never replaced automatically)" : ""),
            Foreground = Theme.Brush("DimText"),
        });
        var settings = AppSettings.Current;
        _channel.Items.Add("Stable — full releases only");
        _channel.Items.Add("Unstable — also alpha / beta / release candidates");
        _channel.SelectedIndex = UpdateService.ChannelFor(settings, _current, _installed) == UpdateChannel.Stable ? 0 : 1;
        _channel.SelectionChanged += async (_, _) =>
        {
            settings.UpdateChannel = _channel.SelectedIndex == 0 ? "stable" : "unstable";
            settings.Save();
            Offer();
            await Task.CompletedTask;
        };
        _auto.IsChecked = settings.CheckForUpdates;
        _auto.Click += (_, _) => { settings.CheckForUpdates = _auto.IsChecked == true; settings.Save(); };
        var row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 10, 0, 0) };
        row.Children.Add(new TextBlock { Text = "Channel", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
        row.Children.Add(_channel);
        row.Children.Add(_auto);
        panel.Children.Add(row);
        panel.Children.Add(_status);
        panel.Children.Add(_notes);
        panel.Children.Add(_progress);
        var buttons = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 6, 0, 0) };
        var check = new Button { Content = "Check again", Padding = new Thickness(12, 3, 12, 3), Margin = new Thickness(0, 0, 6, 0) };
        check.Click += async (_, _) => await CheckAsync();
        _install.Click += async (_, _) => await InstallAsync();
        _skip.Click += (_, _) =>
        {
            if (_offer is null) return;
            settings.SkippedVersion = _offer.Version.ToString();
            settings.Save();
            Close();
        };
        _page.Click += (_, _) => { if (_offer is not null) Open(_offer.PageUrl); };
        var previous = UpdateService.Previous();
        _rollback.Content = previous is null ? "Roll back" : $"Roll back to {previous.Version}";
        _rollback.IsEnabled = previous is not null && _installed is not null;
        _rollback.ToolTip = "Put back the version the last update replaced (kept in " + UpdateService.BackupDir + ")";
        _rollback.Click += (_, _) => RollBack();
        buttons.Children.Add(_install);
        buttons.Children.Add(_skip);
        buttons.Children.Add(_page);
        buttons.Children.Add(check);
        buttons.Children.Add(_rollback);
        panel.Children.Add(buttons);
        return panel;
    }

    public static UpdateWindow Show(Window? owner)
    {
        var w = new UpdateWindow { Owner = owner };
        w.Loaded += async (_, _) => await w.CheckAsync();
        w.Show();
        return w;
    }

    /// <summary>At most once a day, and only for a release install: looks for a newer version on the user's channel
    /// and opens this window when there is one the user did not skip.</summary>
    public static async Task CheckAtStartupAsync(Window owner)
    {
        var settings = AppSettings.Current;
        if (!settings.CheckForUpdates || UpdateService.Install() is null || DateTime.Now - settings.LastUpdateCheck < TimeSpan.FromHours(20)) return;
        try
        {
            var current = SemVersion.TryParse(AppInfo.Version);
            if (current is null) return;
            var releases = await new UpdateService().ReleasesAsync();
            settings.LastUpdateCheck = DateTime.Now;
            settings.Save();
            var offer = UpdateService.Pick(releases, UpdateService.ChannelFor(settings, current, UpdateService.Install()), current);
            if (offer is null || offer.Version.ToString() == settings.SkippedVersion) return;
            var w = new UpdateWindow { Owner = owner };
            w._releases = releases;
            w.Offer();
            w.Show();
        }
        catch (Exception e) when (e is HttpRequestException or TaskCanceledException or InvalidOperationException or System.Text.Json.JsonException)
        {
            ErrorDialog.Log("Update check failed", e); // offline or rate-limited: say nothing at start-up
        }
    }

    private async Task CheckAsync()
    {
        _status.Text = "Looking for updates…";
        try
        {
            _releases = await _service.ReleasesAsync();
            AppSettings.Current.LastUpdateCheck = DateTime.Now;
            AppSettings.Current.Save();
            Offer();
        }
        catch (Exception e) when (e is HttpRequestException or TaskCanceledException or InvalidOperationException or System.Text.Json.JsonException)
        {
            _status.Text = "Could not reach GitHub: " + e.Message;
        }
    }

    /// <summary>Saves a picture of the window once the check finished.</summary>
    public async Task ShotAsync(string png)
    {
        for (var i = 0; i < 300 && (_status.Text.Length == 0 || _status.Text.StartsWith("Looking")); i++) await Task.Delay(100);
        await Task.Delay(300);
        var root = (FrameworkElement)Content;
        var dpi = VisualTreeHelper.GetDpi(this);
        var bmp = new System.Windows.Media.Imaging.RenderTargetBitmap((int)(root.ActualWidth * dpi.DpiScaleX), (int)(root.ActualHeight * dpi.DpiScaleY),
            dpi.PixelsPerInchX, dpi.PixelsPerInchY, PixelFormats.Pbgra32);
        var visual = new DrawingVisual();
        using (var dc = visual.RenderOpen())
        {
            dc.DrawRectangle(Background, null, new Rect(0, 0, root.ActualWidth, root.ActualHeight));
            dc.DrawRectangle(new VisualBrush(root), null, new Rect(0, 0, root.ActualWidth, root.ActualHeight));
        }
        bmp.Render(visual);
        var encoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
        encoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(bmp));
        Directory.CreateDirectory(Path.GetDirectoryName(png)!);
        await using var f = File.Create(png);
        encoder.Save(f);
    }

    private UpdateChannel Channel => _channel.SelectedIndex == 0 ? UpdateChannel.Stable : UpdateChannel.Unstable;

    private void Offer()
    {
        _offer = UpdateService.Pick(_releases, Channel, _current);
        _install.IsEnabled = _skip.IsEnabled = _offer is not null && _installed is not null;
        _page.IsEnabled = _offer is not null;
        if (_offer is null)
        {
            var newestOther = UpdateService.Pick(_releases, UpdateChannel.Unstable, _current);
            _status.Text = $"{AppInfo.Product} is up to date on the {(Channel == UpdateChannel.Stable ? "stable" : "unstable")} channel."
                           + (Channel == UpdateChannel.Stable && newestOther is not null ? $" (Unstable has {newestOther.Version}.)" : "");
            _notes.Text = "";
            return;
        }
        _status.Text = $"{_offer.Name} ({_offer.Version}{(_offer.Prerelease ? ", pre-release" : "")}) is available — published {_offer.Published:d}, {_offer.AssetSize / 1048576.0:0} MB."
                       + (_installed is null ? "\nThis is a development build: get it from the release page, or pull and build the source." : "");
        _notes.Text = string.Join("\n\n", _releases.Where(r => r.Version > _current && r.Version <= _offer.Version && (Channel == UpdateChannel.Unstable || !r.Prerelease))
            .Select(r => $"== {r.Name} ==\n{r.Notes.Trim()}"));
    }

    private async Task InstallAsync()
    {
        if (_offer is null || _installed is null) return;
        if (Application.Current.Windows.OfType<Window>().Any(w => w is BuildWindow { IsVisible: true })
            && MessageBox.Show(this, "A Build window is open. Installing closes Atlas3K; a running build would stop. Continue?", Title,
                MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK) return;
        _install.IsEnabled = _skip.IsEnabled = false;
        _progress.Visibility = Visibility.Visible;
        _status.Text = $"Downloading {_offer.AssetName}…";
        try
        {
            var staged = await _service.DownloadAsync(_offer, new Progress<double>(p => _progress.Value = p));
            _status.Text = "Downloaded and verified. Atlas3K will close, update and start again.";
            if (MessageBox.Show(this, $"Install {AppInfo.Product} {_offer.Version} now? Atlas3K closes (save your work first) and starts again when done.\n\n" +
                                      $"The current version is kept for rolling back. Log: {UpdateService.LogPath}", Title,
                    MessageBoxButton.OKCancel, MessageBoxImage.Question) != MessageBoxResult.OK)
            {
                _install.IsEnabled = true;
                return;
            }
            UpdateService.StartApply(staged, _installed.Folder, Environment.ProcessId, "Atlas3K.exe");
            Application.Current.Shutdown();
        }
        catch (Exception e) when (e is HttpRequestException or TaskCanceledException or InvalidDataException or IOException or InvalidOperationException)
        {
            _status.Text = "Update failed: " + e.Message;
            _install.IsEnabled = true;
            ErrorDialog.Log("Update failed", e);
        }
        finally { _progress.Visibility = Visibility.Collapsed; }
    }

    private void RollBack()
    {
        if (_installed is null || UpdateService.Previous() is not { } previous) return;
        if (MessageBox.Show(this, $"Go back to {AppInfo.Product} {previous.Version}? Atlas3K closes and starts again.", Title,
                MessageBoxButton.OKCancel, MessageBoxImage.Question) != MessageBoxResult.OK) return;
        AppSettings.Current.SkippedVersion = AppInfo.Version; // don't offer this version straight back
        AppSettings.Current.Save();
        UpdateService.StartRollback(_installed.Folder, Environment.ProcessId, "Atlas3K.exe");
        Application.Current.Shutdown();
    }

    private static void Open(string url)
    {
        if (url.Length > 0) Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
    }
}
