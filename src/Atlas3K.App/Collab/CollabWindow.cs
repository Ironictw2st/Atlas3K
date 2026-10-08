using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Media;
using Atlas3K.Core;
using Atlas3K.Core.Collab;
using Atlas3K.Core.Editing;

namespace Atlas3K.App.Collab;

/// <summary>
/// Working on a map with other people: the map's project repository (commit, pull, push, branches, history with map
/// diffs), GitHub pull requests and map pins, locks, merge conflicts, and change packages for sending edits without a
/// repository. One window per map; git, git-lfs and gh do the transport (see <see cref="CollabRepo"/>).
/// </summary>
public sealed class CollabWindow : Window
{
    /// <summary>Map files changed under the editors (pull, merge, revert, import, conflict resolution): the map folder.</summary>
    public static event Action<string>? MapFilesChanged;
    /// <summary>Show a world point (map folder, x, z) in the scene editor.</summary>
    public static event Action<string, double, double>? JumpRequested;
    /// <summary>Pins or locks were refreshed (map folder): redraw their markers.</summary>
    public static event Action<string>? MarkersChanged;

    /// <summary>Where "Pin here" puts a new pin: the last world point hovered in a scene editor.</summary>
    public static (double X, double Z)? LastHover { get; set; }

    private readonly ProjectPaths _paths;
    private CollabRepo? _repo;
    private readonly TextBox _log = new()
    {
        IsReadOnly = true, TextWrapping = TextWrapping.Wrap, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Height = 120,
        FontFamily = new FontFamily("Consolas"), FontSize = 11,
    };
    private readonly TextBlock _busy = new() { Margin = new Thickness(8, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center };
    private readonly TabControl _tabs = new();
    private readonly List<Func<Task>> _refreshers = [];

    private string MapDir => _paths.AkTerrainDir;

    public static CollabWindow ShowFor(Window? owner, ProjectPaths paths)
    {
        var open = Application.Current.Windows.OfType<CollabWindow>()
            .FirstOrDefault(w => w._paths.AkTerrainDir.Equals(paths.AkTerrainDir, StringComparison.OrdinalIgnoreCase));
        if (open is not null)
        {
            open.Activate();
            return open;
        }
        var w = new CollabWindow(paths) { Owner = null };
        if (owner is not null) w.Left = owner.Left + 60;
        w.Show();
        return w;
    }

    private CollabWindow(ProjectPaths paths)
    {
        _paths = paths;
        Title = $"Collaboration — {paths.MapName}";
        Width = 1050;
        Height = 760;
        Background = Theme.Brush("Bg");
        Foreground = Theme.Brush("Text");
        Content = BuildLayout();
        Loaded += async (_, _) => await ReloadAsync();
    }

    // ---------------------------------------------------------------- layout

    private UIElement BuildLayout()
    {
        var dock = new DockPanel { Margin = new Thickness(8) };
        var bottom = new DockPanel { Margin = new Thickness(0, 6, 0, 0) };
        var bar = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 4) };
        bar.Children.Add(new TextBlock { Text = "Output", Foreground = Theme.Brush("DimText"), VerticalAlignment = VerticalAlignment.Center });
        bar.Children.Add(_busy);
        DockPanel.SetDock(bar, Dock.Top);
        bottom.Children.Add(bar);
        bottom.Children.Add(_log);
        DockPanel.SetDock(bottom, Dock.Bottom);
        dock.Children.Add(bottom);
        dock.Children.Add(_tabs);
        return dock;
    }

    private async Task ReloadAsync()
    {
        _repo = CollabRepo.Open(_paths);
        _tabs.Items.Clear();
        _refreshers.Clear();
        if (_repo is null) _tabs.Items.Add(Tab("Set up", SetupTab()));
        else
        {
            _tabs.Items.Add(Tab("Changes", ChangesTab(_repo)));
            _tabs.Items.Add(Tab("History", HistoryTab(_repo)));
            _tabs.Items.Add(Tab("Pull requests", PullRequestsTab(_repo)));
            _tabs.Items.Add(Tab("Map pins", PinsTab(_repo)));
            _tabs.Items.Add(Tab("Locks", LocksTab(_repo)));
        }
        _tabs.Items.Add(Tab("Conflicts", ConflictsTab()));
        _tabs.Items.Add(Tab("Change packages", PackagesTab()));
        _tabs.SelectedIndex = 0;
        foreach (var r in _refreshers.ToList()) await r();
        if (_repo is not null && !await Task.Run(() => _repo.HasRemote))
            Log("This repository has no remote yet: pull requests, map pins and shared locks need one (git remote add origin <url>, or create it on GitHub with gh).");
    }

    private static TabItem Tab(string header, UIElement content) =>
        new() { Header = header, Content = new ScrollViewer { Content = content, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Padding = new Thickness(8) } };

    private static TextBlock Note(string text) => new()
    {
        Text = text, TextWrapping = TextWrapping.Wrap, Foreground = Theme.Brush("DimText"), Margin = new Thickness(0, 2, 0, 6),
    };

    private static StackPanel Row(params UIElement[] children)
    {
        var row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 3, 0, 3) };
        foreach (var c in children) row.Children.Add(c);
        return row;
    }

    private static TextBlock Label(string text, double width = 0) => new()
    {
        Text = text, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 6, 0), Width = width > 0 ? width : double.NaN,
    };

    private static TextBox Input(double width, string text = "", string? tip = null) =>
        new() { Width = width, Text = text, Margin = new Thickness(0, 0, 6, 0), ToolTip = tip, VerticalContentAlignment = VerticalAlignment.Center };

    private Button Action(string label, Func<Task> run, string? tip = null)
    {
        var b = new Button { Content = label, Padding = new Thickness(10, 2, 10, 2), Margin = new Thickness(0, 0, 6, 0), ToolTip = tip };
        b.Click += async (_, _) => await run();
        return b;
    }

    private static DataGrid Grid(double height, params (string Header, string Path, double Width)[] columns)
    {
        var g = new DataGrid
        {
            AutoGenerateColumns = false, IsReadOnly = true, Height = height, Margin = new Thickness(0, 4, 0, 4),
            SelectionMode = DataGridSelectionMode.Extended, HeadersVisibility = DataGridHeadersVisibility.Column,
        };
        foreach (var (header, path, width) in columns)
            g.Columns.Add(new DataGridTextColumn
            {
                Header = header, Binding = new Binding(path),
                Width = width > 0 ? new DataGridLength(width) : new DataGridLength(1, DataGridLengthUnitType.Star),
            });
        return g;
    }

    /// <summary>Runs work off the UI thread, logs its result, and reports errors in the output.</summary>
    private async Task<T?> Run<T>(string what, Func<T> work, bool filesChanged = false)
    {
        _busy.Text = what + "…";
        IsEnabled = false;
        try
        {
            var result = await Task.Run(work);
            Log($"{what}: done" + (result is string s && s.Length > 0 ? $"\n{s}" : ""));
            if (filesChanged) MapFilesChanged?.Invoke(MapDir);
            return result;
        }
        catch (Exception e)
        {
            Log($"{what} failed: {e.Message}");
            ErrorDialog.Log(what, e);
            return default;
        }
        finally
        {
            IsEnabled = true;
            _busy.Text = "";
        }
    }

    private void Log(string text)
    {
        _log.AppendText($"[{DateTime.Now:HH:mm:ss}] {text}\n");
        _log.ScrollToEnd();
    }

    /// <summary>Saves a PNG of every tab (after the first refresh) to <paramref name="dir"/>.</summary>
    public async Task ShotsAsync(string dir)
    {
        Directory.CreateDirectory(dir);
        for (var wait = 0; wait < 600 && (_tabs.Items.Count == 0 || !IsEnabled); wait++) await Task.Delay(100);
        for (var i = 0; i < _tabs.Items.Count; i++)
        {
            _tabs.SelectedIndex = i;
            await Task.Delay(400);
            for (var wait = 0; wait < 600 && !IsEnabled; wait++) await Task.Delay(100);
            UpdateLayout();
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
            var png = new System.Windows.Media.Imaging.PngBitmapEncoder();
            png.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(bmp));
            var name = ((string)((TabItem)_tabs.Items[i]).Header).Replace(' ', '_').ToLowerInvariant();
            await using var f = File.Create(Path.Combine(dir, $"{i + 1:D2}_{name}.png"));
            png.Save(f);
        }
    }

    // ---------------------------------------------------------------- set up

    private UIElement SetupTab()
    {
        var panel = new StackPanel { MaxWidth = 900, HorizontalAlignment = HorizontalAlignment.Left };
        panel.Children.Add(Theme.Header("Share this map", 0));
        panel.Children.Add(Note($"Turns the map folder ({MapDir}) into a git repository: map files are merged per entity and per pixel by " +
                                "Atlas3K, rasters are stored in Git LFS. Needs git, git-lfs, and for GitHub the GitHub CLI (gh auth login). " +
                                "Assembly-kit data is Creative Assembly's: keep GitHub repositories private."));
        var github = Input(260, $"{_paths.MapName}", "owner/name, or just a name for your own account");
        var isPublic = new CheckBox { Content = "Public", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 10, 0) };
        panel.Children.Add(Row(Label("GitHub repository", 130), github, isPublic,
            Action("Create on GitHub", async () =>
            {
                if (await Run("Create repository", () => CollabRepo.Init(_paths, CollabRepo.FindCli(), github: github.Text.Trim(), isPublic: isPublic.IsChecked == true)) is not null)
                    await ReloadAsync();
            })));
        var remote = Input(360, "", "Any git remote URL (GitHub, GitLab, a server, a shared folder)");
        panel.Children.Add(Row(Label("…or remote URL", 130), remote,
            Action("Create and push", async () =>
            {
                if (await Run("Create repository", () => CollabRepo.Init(_paths, CollabRepo.FindCli(), remote: remote.Text.Trim())) is not null)
                    await ReloadAsync();
            })));
        panel.Children.Add(Row(Label("", 130),
            Action("Local repository only", async () =>
            {
                if (await Run("Create repository", () => CollabRepo.Init(_paths, CollabRepo.FindCli())) is not null) await ReloadAsync();
            }, "History, branches and diffs without a remote; add one later")));

        panel.Children.Add(Theme.Header("Join a shared map"));
        panel.Children.Add(Note("Clones a project repository into this assembly kit, as the map it holds (the folder must not exist yet)."));
        var source = Input(360, "", "Repository URL, or GitHub owner/name");
        panel.Children.Add(Row(Label("Repository", 130), source,
            Action("Clone", async () =>
            {
                var repo = await Run("Clone", () => CollabRepo.Clone(_paths, source.Text.Trim(), CollabRepo.FindCli()));
                if (repo is not null)
                    Log($"Cloned into {repo.Root}. Open the map '{repo.Paths.MapName}' (Settings → map) to edit it; " +
                        "this window manages it once that map is current.");
            })));
        return panel;
    }

    // ---------------------------------------------------------------- changes

    private UIElement ChangesTab(CollabRepo repo)
    {
        var panel = new StackPanel();
        var state = new TextBlock { Margin = new Thickness(0, 0, 0, 6), TextWrapping = TextWrapping.Wrap };
        var changes = Grid(220, ("Status", "Status", 90), ("File", "Path", 0));
        var message = new TextBox { AcceptsReturn = true, Height = 70, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 4) };
        var branches = new ComboBox { Width = 200, Margin = new Thickness(0, 0, 6, 0) };
        var newBranch = Input(160, "", "Name of a new branch, made from the current one");

        async Task Refresh()
        {
            var status = await Run("Status", () =>
            {
                if (repo.HasRemote) repo.Git.TryGit("fetch", "-q", "origin");
                new LockService(repo).Refresh();
                return (Status: repo.GetStatus(), Branches: repo.Branches());
            });
            if (status.Status is not { } s) return;
            state.Text = $"Branch {s.Branch}" + (s.Upstream is null ? " (not pushed yet)" : $" · {s.Ahead} to push, {s.Behind} to pull from {s.Upstream}")
                         + (s.Merging ? " · MERGING: resolve conflicts, then Commit" : "")
                         + (s.OpenConflicts > 0 ? $" · {s.OpenConflicts} open conflict(s)" : "");
            changes.ItemsSource = s.Changes;
            if (message.Text.Trim().Length == 0) message.Text = s.SuggestedMessage;
            branches.ItemsSource = status.Branches;
            branches.SelectedItem = s.Branch;
            MarkersChanged?.Invoke(MapDir);
        }
        _refreshers.Add(Refresh);

        panel.Children.Add(Row(Action("Refresh", Refresh), Action("Pull", async () => { await Sync("Pull", repo.Pull); await Refresh(); },
                "Merge collaborators' commits into yours (map-aware)"),
            Action("Push", async () => { await Run("Push", repo.Push); await Refresh(); }, "Publish your commits"),
            Action("Open on GitHub", async () => await Run("Open", () => repo.Git.Gh("repo", "view", "--web").Text))));
        panel.Children.Add(state);
        panel.Children.Add(Theme.Header("Uncommitted changes", 4));
        panel.Children.Add(changes);
        panel.Children.Add(Row(Action("Map diff of these changes", async () =>
        {
            var diff = await Run("Diff", () => repo.Diff());
            if (diff is not null) ShowDiff("Uncommitted changes", diff);
        })));
        panel.Children.Add(Label("Commit message (suggested from your edit history)"));
        panel.Children.Add(message);
        panel.Children.Add(Row(Action("Commit", async () =>
        {
            var text = message.Text;
            if (await Run("Commit", () => repo.Commit(text)) is not null) message.Text = "";
            await Refresh();
        }), Action("Commit and push", async () =>
        {
            var text = message.Text;
            if (await Run("Commit", () => repo.Commit(text)) is not null)
            {
                message.Text = "";
                await Run("Push", repo.Push);
            }
            await Refresh();
        })));
        panel.Children.Add(Theme.Header("Branches"));
        panel.Children.Add(Row(Label("Switch to"), branches, Action("Switch", async () =>
        {
            if (branches.SelectedItem is string b) await Run($"Switch to {b}", () => { repo.Switch(b.StartsWith("origin/") ? b["origin/".Length..] : b, false); return b; }, filesChanged: true);
            await Refresh();
        }), Label("  New branch"), newBranch, Action("Create", async () =>
        {
            var name = newBranch.Text.Trim();
            if (name.Length == 0) return;
            await Run($"Create {name}", () => { repo.Switch(name, true); return name; });
            await Refresh();
        }), Action("Merge selected into current", async () =>
        {
            if (branches.SelectedItem is string b) await Sync($"Merge {b}", () => repo.Merge(b));
            await Refresh();
        })));
        return panel;
    }

    private async Task Sync(string what, Func<CollabRepo.SyncResult> work)
    {
        var r = await Run(what, work, filesChanged: true);
        if (r is null) return;
        Log(r.Output);
        if (r.Conflicts > 0 || r.Unmerged.Count > 0)
        {
            Log($"{r.Conflicts} conflict(s) in {r.Unmerged.Count} file(s): see the Conflicts tab, then Commit.");
            _tabs.SelectedIndex = _tabs.Items.Count - 2;
            foreach (var refresh in _refreshers.ToList()) await refresh();
        }
    }

    // ---------------------------------------------------------------- history

    private UIElement HistoryTab(CollabRepo repo)
    {
        var panel = new StackPanel();
        var log = Grid(380, ("Commit", "Hash", 80), ("Date", "Date", 130), ("Author", "Author", 120), ("Message", "Subject", 0));
        async Task Refresh()
        {
            var commits = await Run("History", () => repo.Log(200));
            if (commits is not null) log.ItemsSource = commits;
        }
        _refreshers.Add(Refresh);
        CollabRepo.CommitInfo? Selected() => log.SelectedItem as CollabRepo.CommitInfo;
        panel.Children.Add(Row(Action("Refresh", Refresh),
            Action("Map diff of commit", async () =>
            {
                if (Selected() is not { } c) return;
                var diff = await Run("Diff", () => repo.Diff(c.Hash + "^", c.Hash));
                if (diff is not null) ShowDiff($"{c.Hash[..8]} {c.Subject}", diff);
            }),
            Action("Revert commit", async () =>
            {
                if (Selected() is not { } c) return;
                if (MessageBox.Show(this, $"Make a new commit that undoes {c.Hash[..8]} \"{c.Subject}\"?", Title, MessageBoxButton.OKCancel) != MessageBoxResult.OK) return;
                await Sync("Revert", () => repo.Revert(c.Hash));
                await Refresh();
            }, "A new commit undoing the selected one (merged per entity / pixel with later work)")));
        panel.Children.Add(log);
        return panel;
    }

    /// <summary>A map diff as a list; entities with positions can be shown in the scene editor.</summary>
    private void ShowDiff(string title, List<CollabRepo.FileDiff> diff)
    {
        var rows = diff.SelectMany(d => d.Entities is { Count: > 0 } es
            ? es.Select(e => new DiffRow(d.Path, e.Change, e.Id, e.Name ?? "", e.Location, string.Join(", ", e.Fields.Take(8))))
            : [new DiffRow(d.Path, d.Status, "", d.Summary, null, d.Kind)]).ToList();
        var grid = Grid(460, ("File", "File", 260), ("Change", "Change", 80), ("Id", "Id", 130), ("What", "Name", 200), ("Where", "Where", 110), ("Fields", "Fields", 0));
        grid.ItemsSource = rows;
        grid.MouseDoubleClick += (_, _) =>
        {
            if (grid.SelectedItem is DiffRow { Location: { } l }) JumpRequested?.Invoke(MapDir, l[0], l[1]);
        };
        var md = CollabRepo.DiffMarkdown(diff);
        var copy = new Button { Content = "Copy as Markdown", Padding = new Thickness(10, 2, 10, 2), HorizontalAlignment = HorizontalAlignment.Left };
        copy.Click += (_, _) => Clipboard.SetText(md);
        var content = new DockPanel { Margin = new Thickness(8) };
        var top = new StackPanel();
        top.Children.Add(Note($"{diff.Count} file(s). Double-click an entity to show it in the scene editor."));
        top.Children.Add(copy);
        DockPanel.SetDock(top, Dock.Top);
        content.Children.Add(top);
        content.Children.Add(grid);
        new Window
        {
            Title = $"Map diff — {title}", Owner = this, Width = 1100, Height = 600, Content = content,
            Background = Theme.Brush("Bg"), Foreground = Theme.Brush("Text"),
        }.Show();
    }

    private sealed record DiffRow(string File, string Change, string Id, string Name, double[]? Location, string Fields)
    {
        public string Where => Location is { } l ? $"{l[0]:0.#}, {l[1]:0.#}" : "";
    }

    // ---------------------------------------------------------------- pull requests

    private UIElement PullRequestsTab(CollabRepo repo)
    {
        var gh = new GitHubService(repo);
        var panel = new StackPanel();
        panel.Children.Add(Note("Pull requests on GitHub. A new PR's description gets the map diff of your branch; reviewers can " +
                                "open the same diff here. GitHub merges by lines: if a PR conflicts, check it out, merge its base " +
                                "branch here (Changes → Merge), resolve, commit and push, then merge."));
        var state = new ComboBox { Width = 100, ItemsSource = new[] { "open", "closed", "merged", "all" }, SelectedIndex = 0, Margin = new Thickness(0, 0, 6, 0) };
        var list = Grid(260, ("#", "Number", 50), ("Title", "Title", 0), ("Author", "Author", 120), ("Branch", "Branch", 160), ("Review", "Review", 130));
        async Task Refresh()
        {
            if (!await Task.Run(() => repo.HasRemote)) return;
            var kind = (string)state.SelectedItem;
            var prs = await Run("Pull requests", () => gh.ListPrs(kind).AsArray().Select(p => new PrRow(
                p!["number"]!.GetValue<int>(), p["title"]!.GetValue<string>(), p["author"]?["login"]?.GetValue<string>() ?? "",
                $"{p["headRefName"]} → {p["baseRefName"]}", p["reviewDecision"]?.GetValue<string>() ?? "", p["url"]!.GetValue<string>())).ToList());
            if (prs is not null) list.ItemsSource = prs;
        }
        _refreshers.Add(Refresh);
        state.SelectionChanged += async (_, _) => await Refresh();
        PrRow? Selected() => list.SelectedItem as PrRow;
        panel.Children.Add(Row(Label("Show"), state, Action("Refresh", Refresh)));
        panel.Children.Add(list);
        var body = new TextBox { AcceptsReturn = true, Height = 60, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 4), ToolTip = "Comment / review text" };
        panel.Children.Add(Row(
            Action("Map diff", async () =>
            {
                if (Selected() is not { } p) return;
                var diff = await Run($"Diff #{p.Number}", () => gh.PrDiff(p.Number));
                if (diff is not null) ShowDiff($"PR #{p.Number} {p.Title}", diff);
            }),
            Action("Post map diff", async () =>
            {
                if (Selected() is { } p) await Run($"Post diff to #{p.Number}", () => gh.CommentPr(p.Number, CollabRepo.DiffMarkdown(gh.PrDiff(p.Number))));
            }, "Comment the map diff on the PR"),
            Action("Check out", async () =>
            {
                if (Selected() is { } p) await Run($"Check out #{p.Number}", () => gh.CheckoutPr(p.Number), filesChanged: true);
            }, "Switch to the PR's branch to try it in the editors"),
            Action("Open in browser", async () =>
            {
                if (Selected() is { } p) await Run("Open", () => { Process.Start(new ProcessStartInfo(p.Url) { UseShellExecute = true }); return p.Url; });
            }),
            Action("Merge", async () =>
            {
                if (Selected() is not { } p) return;
                if (MessageBox.Show(this, $"Merge PR #{p.Number} \"{p.Title}\" on GitHub?", Title, MessageBoxButton.OKCancel) != MessageBoxResult.OK) return;
                await Run($"Merge #{p.Number}", () => gh.MergePr(p.Number));
                await Refresh();
            })));
        panel.Children.Add(Label("Comment / review"));
        panel.Children.Add(body);
        panel.Children.Add(Row(
            Action("Comment", async () => { if (Selected() is { } p) await Run("Comment", () => gh.CommentPr(p.Number, body.Text)); }),
            Action("Approve", async () => { if (Selected() is { } p) await Run("Approve", () => gh.ReviewPr(p.Number, "approve", body.Text)); }),
            Action("Request changes", async () => { if (Selected() is { } p) await Run("Request changes", () => gh.ReviewPr(p.Number, "request-changes", body.Text)); })));

        panel.Children.Add(Theme.Header("New pull request from the current branch"));
        var title = Input(420, "", "PR title");
        var baseBranch = Input(120, "", "Base branch (default: the repository's default branch)");
        var draft = new CheckBox { Content = "Draft", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) };
        var description = new TextBox { AcceptsReturn = true, Height = 60, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 4) };
        panel.Children.Add(Row(Label("Title", 50), title, Label("Base"), baseBranch, draft));
        panel.Children.Add(description);
        panel.Children.Add(Row(Action("Push and open PR", async () =>
        {
            var (t, d, b, dr) = (title.Text.Trim(), description.Text, baseBranch.Text.Trim(), draft.IsChecked == true);
            if (t.Length == 0) { Log("A PR needs a title."); return; }
            var r = await Run("Create PR", () => gh.CreatePr(t, d, b.Length == 0 ? null : b, dr));
            if (r is not null) Log($"PR: {r["url"]}");
            await Refresh();
        })));
        return panel;
    }

    private sealed record PrRow(int Number, string Title, string Author, string Branch, string Review, string Url);

    // ---------------------------------------------------------------- map pins

    private UIElement PinsTab(CollabRepo repo)
    {
        var gh = new GitHubService(repo);
        var panel = new StackPanel();
        panel.Children.Add(Note("Issues pinned to map positions (GitHub issues labelled map-pin). They show as markers on the scene " +
                                "editor's top view; double-click one here to go to it."));
        var state = new ComboBox { Width = 100, ItemsSource = new[] { "open", "closed", "all" }, SelectedIndex = 0, Margin = new Thickness(0, 0, 6, 0) };
        var list = Grid(260, ("#", "Number", 50), ("Title", "Title", 0), ("Assignees", "Assigned", 140), ("Where", "Where", 120), ("State", "State", 70));
        async Task Refresh()
        {
            if (!await Task.Run(() => repo.HasRemote)) return;
            var kind = (string)state.SelectedItem;
            var pins = await Run("Map pins", () => gh.ListPins(kind));
            if (pins is null) return;
            list.ItemsSource = pins.Select(p => new PinRow(p)).ToList();
            MarkersChanged?.Invoke(MapDir);
        }
        _refreshers.Add(Refresh);
        state.SelectionChanged += async (_, _) => await Refresh();
        list.MouseDoubleClick += (_, _) => { if (list.SelectedItem is PinRow r) JumpRequested?.Invoke(MapDir, r.Pin.X, r.Pin.Z); };
        GitHubService.Pin? Selected() => (list.SelectedItem as PinRow)?.Pin;
        var comment = new TextBox { AcceptsReturn = true, Height = 50, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 4) };
        panel.Children.Add(Row(Label("Show"), state, Action("Refresh", Refresh)));
        panel.Children.Add(list);
        panel.Children.Add(comment);
        panel.Children.Add(Row(
            Action("Comment", async () => { if (Selected() is { } p) await Run("Comment", () => gh.CommentIssue(p.Number, comment.Text)); }),
            Action("Close", async () => { if (Selected() is { } p) { await Run("Close", () => gh.ClosePin(p.Number, comment.Text)); await Refresh(); } }),
            Action("Open in browser", async () =>
            {
                if (Selected() is { } p) await Run("Open", () => { Process.Start(new ProcessStartInfo(p.Url) { UseShellExecute = true }); return p.Url; });
            })));

        panel.Children.Add(Theme.Header("New pin"));
        var title = Input(380, "", "What needs doing here");
        var x = Input(80);
        var z = Input(80);
        var assignee = Input(120, "", "GitHub login (optional)");
        var body = new TextBox { AcceptsReturn = true, Height = 50, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 4, 0, 4) };
        var here = new Button { Content = "Use last hovered point", Padding = new Thickness(8, 2, 8, 2), Margin = new Thickness(0, 0, 6, 0),
            ToolTip = "The world point last under the mouse in a scene editor (or Ctrl+Shift+P there)" };
        here.Click += (_, _) =>
        {
            if (LastHover is var (hx, hz)) { x.Text = $"{hx:0.##}"; z.Text = $"{hz:0.##}"; }
        };
        panel.Children.Add(Row(Label("Title", 50), title, Label("Assign"), assignee));
        panel.Children.Add(Row(Label("x", 50), x, Label("z"), z, here));
        panel.Children.Add(body);
        panel.Children.Add(Row(Action("Create pin", async () =>
        {
            if (!double.TryParse(x.Text, System.Globalization.CultureInfo.InvariantCulture, out var px)
                || !double.TryParse(z.Text, System.Globalization.CultureInfo.InvariantCulture, out var pz) || title.Text.Trim().Length == 0)
            {
                Log("A pin needs a title and x / z.");
                return;
            }
            var (t, b, a) = (title.Text.Trim(), body.Text, assignee.Text.Trim());
            var pin = await Run("Create pin", () => gh.CreatePin(t, b, px, pz, assignees: a.Length > 0 ? [a] : null));
            if (pin is not null) { Log($"Pin #{pin.Number}: {pin.Url}"); title.Text = body.Text = ""; }
            await Refresh();
        })));
        return panel;
    }

    /// <summary>Fills the new-pin position (from a scene editor's "Pin here").</summary>
    public void StartPin(double x, double z)
    {
        LastHover = (x, z);
        foreach (TabItem tab in _tabs.Items)
            if ((string)tab.Header == "Map pins") _tabs.SelectedItem = tab;
        Log($"Pin position {x:0.##}, {z:0.##}: press \"Use last hovered point\", add a title, Create pin.");
    }

    private sealed record PinRow(GitHubService.Pin Pin)
    {
        public int Number => Pin.Number;
        public string Title => Pin.Title;
        public string Assigned => string.Join(", ", Pin.Assignees);
        public string Where => $"{Pin.X:0.#}, {Pin.Z:0.#}";
        public string State => Pin.State;
    }

    // ---------------------------------------------------------------- locks

    private UIElement LocksTab(CollabRepo repo)
    {
        var locks = new LockService(repo);
        var panel = new StackPanel();
        panel.Children.Add(Note("Tell collaborators what you are working on. File and layer locks are enforced: Atlas3K's editors refuse " +
                                "to save them for anyone else. Region locks are advisory and drawn on the map."));
        var list = Grid(240, ("Id", "Id", 80), ("Owner", "Owner", 120), ("Kind", "Kind", 60), ("What", "What", 0), ("Reason", "Reason", 200), ("Since", "Created", 130));
        async Task Refresh()
        {
            var all = await Run("Locks", locks.Refresh);
            if (all is null) return;
            list.ItemsSource = all.Select(l => new LockRow(l)).ToList();
            MarkersChanged?.Invoke(MapDir);
        }
        _refreshers.Add(Refresh);
        panel.Children.Add(Row(Action("Refresh", Refresh),
            Action("Release selected", async () =>
            {
                var ids = list.SelectedItems.OfType<LockRow>().Select(r => r.Id).ToList();
                if (ids.Count == 0) return;
                await Run("Release", () => locks.Release(ids));
                await Refresh();
            }),
            Action("Release all mine", async () => { await Run("Release", () => locks.Release(null)); await Refresh(); }),
            Action("Break selected", async () =>
            {
                var ids = list.SelectedItems.OfType<LockRow>().Select(r => r.Id).ToList();
                if (ids.Count == 0 || MessageBox.Show(this, "Break other people's locks? Only do this when they agreed or are gone.", Title,
                        MessageBoxButton.OKCancel) != MessageBoxResult.OK) return;
                await Run("Break", () => locks.Release(ids, force: true));
                await Refresh();
            })));
        panel.Children.Add(list);
        panel.Children.Add(Theme.Header("Lock"));
        var reason = Input(300, "", "Why (shown to others)");
        var layer = Input(260, "", "File layer name (as in the layer tree)");
        var file = Input(260, "", "File in the map folder, e.g. tile_map.png");
        var rect = Input(260, "", "World rect x0,z0,x1,z1");
        panel.Children.Add(Row(Label("Reason", 60), reason));
        panel.Children.Add(Row(Label("Layer", 60), layer, Action("Lock layer", async () =>
        {
            var (name, why) = (layer.Text.Trim(), reason.Text.Trim());
            await Run($"Lock {name}", () =>
            {
                var path = new EntityEditor(_paths).Layer(name).FilePath ?? throw new InvalidOperationException($"layer {name} has no file");
                return locks.Acquire("layer", Path.GetRelativePath(repo.Root, path).Replace('\\', '/'), name, why.Length > 0 ? why : null);
            });
            await Refresh();
        })));
        panel.Children.Add(Row(Label("File", 60), file, Action("Lock file", async () =>
        {
            var (name, why) = (file.Text.Trim().Replace('\\', '/'), reason.Text.Trim());
            await Run($"Lock {name}", () => locks.Acquire("file", name, Path.GetFileName(name), why.Length > 0 ? why : null));
            await Refresh();
        })));
        panel.Children.Add(Row(Label("Region", 60), rect, Action("Lock region", async () =>
        {
            var v = rect.Text.Split(',').Select(s => double.TryParse(s, System.Globalization.CultureInfo.InvariantCulture, out var d) ? d : double.NaN).ToArray();
            if (v.Length != 4 || v.Any(double.IsNaN)) { Log("Region is x0,z0,x1,z1 in world units."); return; }
            double[] r = [Math.Min(v[0], v[2]), Math.Min(v[1], v[3]), Math.Max(v[0], v[2]), Math.Max(v[1], v[3])];
            var why = reason.Text.Trim();
            await Run("Lock region", () => locks.Acquire("region", string.Join(',', r.Select(d => d.ToString(System.Globalization.CultureInfo.InvariantCulture))),
                null, why.Length > 0 ? why : null, r));
            await Refresh();
        })));
        return panel;
    }

    private sealed record LockRow(LockService.Lock Lock)
    {
        public string Id => Lock.Id;
        public string Owner => Lock.Owner;
        public string Kind => Lock.Kind;
        public string What => Lock.Label is { } l && l != Lock.Target ? $"{l} ({Lock.Target})" : Lock.Target;
        public string Reason => Lock.Reason ?? "";
        public string Created => Lock.Created.ToString("g");
    }

    // ---------------------------------------------------------------- conflicts

    private ConflictSet CurrentConflicts(bool import) =>
        !import && _repo is not null ? _repo.Conflicts : new ConflictSet(Path.Combine(PatchSources.ImportDir(_paths), "conflicts"));

    private UIElement ConflictsTab()
    {
        var panel = new StackPanel();
        panel.Children.Add(Note("What a merge could not decide: the same attribute or pixels changed differently on both sides, or an " +
                                "entity edited on one side and deleted on the other. The merged files hold yours (ours) until you pick " +
                                "theirs. In a repository, Commit afterwards to finish the merge."));
        var source = new ComboBox { Width = 220, Margin = new Thickness(0, 0, 6, 0),
            ItemsSource = new[] { "Repository merge", "Last package import" }, SelectedIndex = _repo is null ? 1 : 0 };
        var list = Grid(330, ("#", "Index", 40), ("File", "Conflict.File", 230), ("Kind", "Conflict.Kind", 70), ("Ours", "Conflict.Ours", 110),
            ("Theirs", "Conflict.Theirs", 110), ("Detail", "Conflict.Detail", 0));
        bool Import() => source.SelectedIndex == 1;
        Task Refresh()
        {
            list.ItemsSource = CurrentConflicts(Import()).Open();
            return Task.CompletedTask;
        }
        _refreshers.Add(Refresh);
        source.SelectionChanged += async (_, _) => await Refresh();
        list.MouseDoubleClick += (_, _) =>
        {
            if (list.SelectedItem is ConflictSet.Entry { Conflict.Location: { } l }) JumpRequested?.Invoke(MapDir, l[0], l[1]);
        };
        async Task Resolve(string side, bool all)
        {
            var ids = all ? null : list.SelectedItems.OfType<ConflictSet.Entry>().Select(e => e.Index).ToList();
            if (ids is { Count: 0 }) return;
            var set = CurrentConflicts(Import());
            await Run($"Resolve to {side}", () => $"{ConflictResolver.Resolve(set, side, ids)} resolved", filesChanged: side == "theirs");
            await Refresh();
        }
        panel.Children.Add(Row(Label("Conflicts of"), source, Action("Refresh", Refresh)));
        panel.Children.Add(list);
        panel.Children.Add(Row(Action("Keep ours (selected)", () => Resolve("ours", false)), Action("Take theirs (selected)", () => Resolve("theirs", false)),
            Action("All ours", () => Resolve("ours", true)), Action("All theirs", () => Resolve("theirs", true))));
        panel.Children.Add(Note("Double-click a conflict with a position to show it in the scene editor."));
        return panel;
    }

    // ---------------------------------------------------------------- change packages

    private UIElement PackagesTab()
    {
        var panel = new StackPanel { MaxWidth = 900, HorizontalAlignment = HorizontalAlignment.Left };
        panel.Children.Add(Note("Send edits without a repository: a change package (.a3kpatch) holds what changed in the map files; " +
                                "importing merges it with the importer's own edits (per entity / per pixel) as one undoable step."));
        panel.Children.Add(Theme.Header("Export", 0));
        var since = Input(160, DateTime.Today.ToString("yyyy-MM-dd HH:mm"), "Every edit Atlas3K journaled after this time");
        var baseDir = Input(380, "", "Or: a copy of the map folder as it was (the package holds everything that differs from it)");
        var label = Input(380, "", "Short description for the importer");
        panel.Children.Add(Row(Label("Edits since", 110), since));
        panel.Children.Add(Row(Label("…or against folder", 110), baseDir, Action("Browse…", () =>
        {
            var d = new Microsoft.Win32.OpenFolderDialog { Title = "Copy of the map folder the edits started from" };
            if (d.ShowDialog(this) == true) baseDir.Text = d.FolderName;
            return Task.CompletedTask;
        })));
        panel.Children.Add(Row(Label("Label", 110), label));
        panel.Children.Add(Row(Label("", 110), Action("Export package…", async () =>
        {
            var save = new Microsoft.Win32.SaveFileDialog
            {
                Filter = "Atlas3K change package|*.a3kpatch", FileName = $"{_paths.MapName}_{DateTime.Now:yyyyMMdd_HHmm}.a3kpatch",
            };
            if (save.ShowDialog(this) != true) return;
            var (s, b, l, file) = (since.Text.Trim(), baseDir.Text.Trim(), label.Text.Trim(), save.FileName);
            var m = await Run("Export", () =>
            {
                var sources = b.Length > 0 ? PatchSources.FromFolder(_paths, b)
                    : PatchSources.FromJournals(_paths, DateTime.Parse(s, System.Globalization.CultureInfo.CurrentCulture));
                var manifest = PatchPackage.Export(sources, file, _paths.MapName, l.Length > 0 ? l : $"{_paths.MapName} edits");
                if (manifest.Files.Count == 0) { File.Delete(file); throw new InvalidOperationException("nothing changed: no package written"); }
                return string.Join("\n", manifest.Files.Select(f => $"  {f.Change,-8} {f.Path}  {f.Summary}"))
                       + $"\n{new FileInfo(file).Length:N0} bytes → {file}";
            });
            if (m is not null) Process.Start(new ProcessStartInfo("explorer.exe", $"/select,\"{file}\"") { UseShellExecute = true });
        })));

        panel.Children.Add(Theme.Header("Import"));
        var package = Input(380, "", "A .a3kpatch someone sent you");
        panel.Children.Add(Row(Label("Package", 110), package, Action("Browse…", () =>
        {
            var open = new Microsoft.Win32.OpenFileDialog { Filter = "Atlas3K change package|*.a3kpatch" };
            if (open.ShowDialog(this) == true) package.Text = open.FileName;
            return Task.CompletedTask;
        })));
        async Task Import(bool dryRun)
        {
            var file = package.Text.Trim();
            if (!File.Exists(file)) { Log("Pick a package first."); return; }
            var dir = PatchSources.ImportDir(_paths);
            var r = await Run(dryRun ? "Preview import" : "Import", () =>
            {
                var m = PatchPackage.ReadManifest(file);
                if (!m.Map.Equals(_paths.MapName, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"the package is for map {m.Map}, not {_paths.MapName}");
                var result = PatchPackage.Import(file, _paths.AssemblyKitRoot, new FileJournal(dir), new ConflictSet(Path.Combine(dir, "conflicts")), dryRun);
                return $"{m.Label} by {m.Author} ({m.Created:g})\n"
                       + string.Join("\n", result.Files.Select(f => $"  {f.Action,-22} {f.Path}  {f.Merge?.Summary}"))
                       + (result.Conflicts > 0 ? $"\n{result.Conflicts} conflict(s){(dryRun ? "" : ": see the Conflicts tab (Last package import)")}" : "");
            }, filesChanged: !dryRun);
            if (r is not null && !dryRun) foreach (var refresh in _refreshers.ToList()) await refresh();
        }
        panel.Children.Add(Row(Label("", 110), Action("Preview", () => Import(true), "What would change, nothing written"),
            Action("Import", () => Import(false)),
            Action("Undo last import", async () =>
            {
                await Run("Undo import", () => string.Join("\n", new FileJournal(PatchSources.ImportDir(_paths)).Undo().Select(h => h.Label)), filesChanged: true);
            })));
        return panel;
    }
}
