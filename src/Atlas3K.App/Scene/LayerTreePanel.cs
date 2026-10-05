using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using Atlas3K.Formats.Terry;

namespace Atlas3K.App.Scene;

/// <summary>
/// Terry's scene tree: file layers, then (lazily, on expand) the folder/tag layers, groups and entities inside them.
/// Layers have visibility and lock toggles; right-click gives the layer/entity commands; entities can be dragged onto
/// a layer to move them there. The panel raises requests; the window turns them into entity ops.
/// </summary>
public sealed class LayerTreePanel : DockPanel
{
    private const int MaxChildren = 400;

    public sealed record Node(string Kind, string FileLayer, string? Id)
    {
        public string Key => $"{Kind}:{FileLayer}:{Id}";
        public string TargetId => Id ?? FileLayer;
        public bool IsLayer => Kind is "file" or "layer";
    }

    private readonly TreeView _tree = new() { Background = Brushes.Transparent, BorderThickness = new Thickness(0), Foreground = Theme.Brush("Text") };
    private SceneModel? _model;
    private bool _suppressSelection;
    private Point? _dragStart;
    private TreeViewItem? _dragItem;

    public event Action<string>? EntitySelected;
    /// <summary>A layer node was selected (file layer id, nested layer id or null).</summary>
    public event Action<Node>? LayerSelected;
    public event Action<Node, string, bool>? StateToggled;        // node, "visible"|"frozen", value
    public event Action<Node, string>? Command;                   // node, command name
    public event Action<IReadOnlyList<string>, Node>? DropRequested; // entity ids, target layer node

    public LayerTreePanel()
    {
        VirtualizingPanel.SetIsVirtualizing(_tree, true);
        VirtualizingPanel.SetVirtualizationMode(_tree, VirtualizationMode.Recycling);
        _tree.SelectedItemChanged += (_, e) =>
        {
            if (_suppressSelection || e.NewValue is not TreeViewItem { Tag: Node n }) return;
            if (n.IsLayer) LayerSelected?.Invoke(n);
            else if (n.Id is not null && n.Kind is "entity" or "group") EntitySelected?.Invoke(n.Id);
        };
        _tree.PreviewMouseLeftButtonDown += (_, e) =>
        {
            _dragStart = e.GetPosition(_tree);
            _dragItem = ItemAt(e.OriginalSource);
        };
        _tree.PreviewMouseMove += TreeMouseMove;
        _tree.AllowDrop = true;
        _tree.DragOver += (_, e) =>
        {
            e.Effects = ItemAt(e.OriginalSource) is { Tag: Node { IsLayer: true } } && e.Data.GetDataPresent("terry-ids")
                ? DragDropEffects.Move : DragDropEffects.None;
            e.Handled = true;
        };
        _tree.Drop += (_, e) =>
        {
            if (ItemAt(e.OriginalSource) is { Tag: Node { IsLayer: true } target } && e.Data.GetData("terry-ids") is string[] ids)
                DropRequested?.Invoke(ids, target);
        };
        Children.Add(_tree);
    }

    private static TreeViewItem? ItemAt(object source)
    {
        var d = source as DependencyObject;
        while (d is not null and not TreeViewItem) d = VisualTreeHelper.GetParent(d);
        return d as TreeViewItem;
    }

    private void TreeMouseMove(object sender, MouseEventArgs e)
    {
        if (e.LeftButton != MouseButtonState.Pressed || _dragStart is not { } start || _dragItem is not { Tag: Node n }) return;
        if (n.Kind is not ("entity" or "group" or "layer")) return;
        var p = e.GetPosition(_tree);
        if (Math.Abs(p.X - start.X) < SystemParameters.MinimumHorizontalDragDistance
            && Math.Abs(p.Y - start.Y) < SystemParameters.MinimumVerticalDragDistance) return;
        _dragStart = null;
        if (n.Kind == "layer") return; // moving whole nested layers is a TODO; drag their members instead
        DragDrop.DoDragDrop(_tree, new DataObject("terry-ids", new[] { n.Id! }), DragDropEffects.Move);
    }

    // ---------------------------------------------------------------- building

    public void Attach(SceneModel model)
    {
        _model = model;
        Rebuild();
    }

    /// <summary>Rebuilds the tree from the model, keeping which nodes were expanded.</summary>
    public void Rebuild()
    {
        if (_model is null) return;
        var expanded = new HashSet<string>();
        foreach (var item in Walk(_tree.Items)) if (item.IsExpanded && item.Tag is Node n) expanded.Add(n.Key);
        var selected = (_tree.SelectedItem as TreeViewItem)?.Tag as Node;

        _tree.Items.Clear();
        foreach (var layer in _model.Layers)
        {
            var count = _model.EntitiesOf(layer.Id).Count(e => !TerryEntityTypes.IsLayerType(e.Type));
            var node = new Node("file", layer.Id, null);
            var label = layer.Name + (layer.Export ? "" : "  (not exported)");
            _tree.Items.Add(MakeItem(node, label, $"{count}", true, _model.Invisible.Contains(layer.Id), _model.Frozen.Contains(layer.Id),
                                     active: _model.ActiveLayer == layer.Id));
        }
        Reexpand(_tree.Items, expanded, selected);
    }

    private void Reexpand(ItemCollection items, HashSet<string> expanded, Node? selected)
    {
        foreach (TreeViewItem item in items)
        {
            if (item.Tag is not Node n) continue;
            if (expanded.Contains(n.Key)) item.IsExpanded = true; // populates children
            if (selected is not null && n.Key == selected.Key)
            {
                _suppressSelection = true;
                item.IsSelected = true;
                _suppressSelection = false;
            }
            if (item.IsExpanded) Reexpand(item.Items, expanded, selected);
        }
    }

    private static IEnumerable<TreeViewItem> Walk(ItemCollection items)
    {
        foreach (var o in items)
            if (o is TreeViewItem t)
            {
                yield return t;
                foreach (var c in Walk(t.Items)) yield return c;
            }
    }

    private TreeViewItem MakeItem(Node node, string text, string? detail, bool expandable, bool hidden = false, bool frozen = false,
                                  string? icon = null, bool active = false)
    {
        var header = new StackPanel { Orientation = Orientation.Horizontal };
        if (node.IsLayer)
        {
            var vis = new CheckBox { IsChecked = !hidden, ToolTip = "Visible", VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 3, 0) };
            vis.Click += (_, _) => StateToggled?.Invoke(node, "visible", vis.IsChecked == true);
            var lockBtn = new ToggleButton
            {
                IsChecked = frozen, Content = Theme.Icon(Theme.Glyph.Lock, 10), ToolTip = "Locked (frozen)", Padding = new Thickness(1, 0, 1, 0),
                Margin = new Thickness(0, 0, 4, 0), Opacity = frozen ? 1 : 0.35, Background = Brushes.Transparent, BorderThickness = new Thickness(0),
            };
            lockBtn.Click += (_, _) => StateToggled?.Invoke(node, "frozen", lockBtn.IsChecked == true);
            header.Children.Add(vis);
            header.Children.Add(lockBtn);
        }
        else
        {
            var type = _model?.Find(node.Id!)?.Entity.Type ?? "";
            var c = SceneView.ColourOf(type);
            header.Children.Add(new Border
            {
                Width = 8, Height = 8, Margin = new Thickness(0, 0, 5, 0), VerticalAlignment = VerticalAlignment.Center,
                Background = new SolidColorBrush(Color.FromRgb((byte)(c >> 16), (byte)(c >> 8), (byte)c)),
            });
        }
        if (icon is not null) header.Children.Add(new TextBlock { Text = icon, FontFamily = Theme.IconFont, FontSize = 11, Margin = new Thickness(0, 0, 4, 0), VerticalAlignment = VerticalAlignment.Center, Foreground = Theme.Brush("DimText") });
        header.Children.Add(new TextBlock { Text = text, Foreground = hidden ? Theme.Brush("DimText") : Theme.Brush("Text") });
        if (active) header.Children.Add(new TextBlock { Text = Theme.Glyph.Star, FontFamily = Theme.IconFont, FontSize = 11, Margin = new Thickness(5, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center, Foreground = Theme.Brush("Accent"), ToolTip = "Active layer (new entities go here)" });
        if (detail is not null)
            header.Children.Add(new TextBlock { Text = "  " + detail, Foreground = Theme.Brush("DimText"), FontSize = 11, VerticalAlignment = VerticalAlignment.Center });

        var item = new TreeViewItem { Header = header, Tag = node, Foreground = Theme.Brush("Text"), ContextMenu = MenuFor(node) };
        if (expandable)
        {
            item.Items.Add(new TreeViewItem { Header = "…" });
            item.Expanded += (_, e) =>
            {
                if (!ReferenceEquals(e.OriginalSource, item)) return;
                if (item.Items.Count == 1 && item.Items[0] is TreeViewItem { Tag: null }) Populate(item, node);
            };
        }
        return item;
    }

    private void Populate(TreeViewItem item, Node node)
    {
        item.Items.Clear();
        if (_model is null) return;
        var all = _model.EntitiesOf(node.FileLayer);
        IEnumerable<TerryEntityData> children = node.Kind switch
        {
            "file" => all.Where(e => e.Parents.Count == 0 && e.Group is null),
            "layer" => all.Where(e => e.Parents.Contains(node.Id!)),
            "group" => all.Where(e => e.Group == node.Id),
            _ => [],
        };
        var list = children.OrderBy(e => TerryEntityTypes.IsLayerType(e.Type) ? 0 : 1).ToList();
        foreach (var e in list.Take(MaxChildren))
        {
            if (TerryEntityTypes.IsLayerType(e.Type))
            {
                var members = all.Count(m => m.Parents.Contains(e.Id));
                var label = e.Name ?? e.Id;
                item.Items.Add(MakeItem(new Node("layer", node.FileLayer, e.Id), label, $"{members}", members > 0,
                    _model.Invisible.Contains(e.Id), _model.Frozen.Contains(e.Id),
                    icon: e.Type == TerryEntityTypes.TagLayer ? Theme.Glyph.Tag : Theme.Glyph.Folder));
            }
            else
            {
                var isGroup = e.Type == TerryEntityTypes.Group;
                item.Items.Add(MakeItem(new Node(isGroup ? "group" : "entity", node.FileLayer, e.Id), Label(e), e.Type, isGroup));
            }
        }
        if (list.Count > MaxChildren)
            item.Items.Add(new TreeViewItem
            {
                Header = new TextBlock { Text = $"… {list.Count - MaxChildren} more (use Find, or select in the view)", Foreground = Theme.Brush("DimText") },
                Tag = new Node("more", node.FileLayer, null), IsEnabled = false,
            });
    }

    /// <summary>Short label: the entity's name, else the file name of its asset, else its id.</summary>
    public static string Label(TerryEntityData e)
    {
        if (!string.IsNullOrEmpty(e.Name)) return e.Name;
        var asset = e.Component("ECMesh")?["model_path"] ?? e.Component("ECDecal")?["model_path"] ?? e.Component("ECVFX")?["vfx"]
                    ?? e.Component("ECCompositeScene")?["path"] ?? e.Component("ECBuilding")?["key"] ?? e.Component("ECPrefab")?["key"]
                    ?? e.Component("ECVegetation")?["key"] ?? e.Component("ECSoundMarker")?["key"];
        if (string.IsNullOrEmpty(asset)) return e.Id;
        var slash = asset.LastIndexOfAny(['/', '\\']);
        return slash >= 0 ? asset[(slash + 1)..] : asset;
    }

    private ContextMenu MenuFor(Node node)
    {
        var menu = new ContextMenu();
        void Add(string header, string command)
        {
            var mi = new MenuItem { Header = header };
            mi.Click += (_, _) => Command?.Invoke(node, command);
            menu.Items.Add(mi);
        }
        if (node.IsLayer)
        {
            Add("New folder layer…", "new-folder");
            Add("New tag layer…", "new-tag-layer");
            Add("Add entity here…", "add-entity");
            Add("Place prefab here…", "place-prefab");
            menu.Items.Add(new Separator());
            Add("Rename…", "rename");
            if (node.Kind == "file")
            {
                Add("Set as active layer", "set-active");
                Add("Toggle export", "toggle-export");
            }
            Add("Select all in layer", "select-all");
            menu.Items.Add(new Separator());
            Add(node.Kind == "file" ? "Delete layer (and its file)…" : "Delete layer (members move up)", "delete");
            if (node.Kind == "layer") Add("Delete layer with members", "delete-with-members");
        }
        else if (node.Kind is "entity" or "group")
        {
            Add("Rename…", "rename");
            Add("Duplicate", "duplicate");
            if (_model?.Find(node.Id!)?.Entity.Component("ECPrefab") is not null)
            {
                Add("Open prefab", "open-prefab");
                Add("Expand prefab", "expand-prefab");
            }
            Add("Frame in view", "frame");
            menu.Items.Add(new Separator());
            Add("Delete", "delete");
        }
        return menu;
    }

    /// <summary>Selects the node for an entity if its branch is already loaded (does not expand lazily).</summary>
    public void Reveal(string? id)
    {
        if (id is null) return;
        foreach (var item in Walk(_tree.Items))
            if (item.Tag is Node n && n.Id == id)
            {
                _suppressSelection = true;
                item.IsSelected = true;
                item.BringIntoView();
                _suppressSelection = false;
                return;
            }
    }
}
