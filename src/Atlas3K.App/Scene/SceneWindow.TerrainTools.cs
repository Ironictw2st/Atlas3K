using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace Atlas3K.App.Scene;

/// <summary>Scene editor hooks for the terrain tools (<see cref="TerrainToolsPanel"/>): a tab next to the inspector, the
/// terrain undo keys while that tab is shown, [ / ] brush size, and a prompt before unsaved terrain edits are dropped.</summary>
public sealed partial class SceneWindow
{
    private TerrainToolsPanel? _terrainTools;
    private TerrainToolsPanel TerrainTools => _terrainTools ??= new TerrainToolsPanel(_paths, _view, _view3d);
    private TabControl? _rightTabs;

    /// <summary>The right-hand column: inspector and terrain tools as tabs.</summary>
    private UIElement RightPanel(UIElement inspector)
    {
        var tabs = _rightTabs = new TabControl { Background = Theme.Brush("Panel"), BorderThickness = new Thickness(0) };
        tabs.Items.Add(new TabItem { Header = "Inspector", Content = inspector });
        tabs.Items.Add(new TabItem
        {
            Header = "Terrain & trees", Content = TerrainTools,
            ToolTip = "Edit the kit's land / sea height maps and the CampaignTree map (brushes, fills, undo, save)",
        });
        tabs.SelectionChanged += (_, e) =>
        {
            if (!ReferenceEquals(e.OriginalSource, tabs)) return;
            TerrainTools.IsShown = tabs.SelectedIndex == 1;
        };
        return tabs;
    }

    private void WireTerrainTools()
    {
        TerrainTools.Status += (text, error) => Status(text, error);
        PreviewKeyDown += (_, e) =>
        {
            if (!TerrainTools.IsShown || Keyboard.FocusedElement is TextBox) return;
            var ctrl = Keyboard.Modifiers.HasFlag(ModifierKeys.Control);
            var shift = Keyboard.Modifiers.HasFlag(ModifierKeys.Shift);
            e.Handled = e.Key switch
            {
                // while the tab is shown, Ctrl+Z never falls through to the entity journal
                Key.Z when ctrl && !shift => Do(() => TerrainTools.Undo()),
                Key.Y when ctrl => Do(() => TerrainTools.Redo()),
                Key.Z when ctrl && shift => Do(() => TerrainTools.Redo()),
                Key.OemOpenBrackets => Do(() => TerrainTools.ScaleRadius(1 / 1.25)),
                Key.OemCloseBrackets => Do(() => TerrainTools.ScaleRadius(1.25)),
                _ => false,
            };
        };
        Closing += (_, e) =>
        {
            if (!TerrainTools.ConfirmDiscard(this)) e.Cancel = true;
        };
        static bool Do(Action a) { a(); return true; }
    }
}
