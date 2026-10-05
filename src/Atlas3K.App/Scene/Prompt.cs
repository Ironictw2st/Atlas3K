using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace Atlas3K.App.Scene;

/// <summary>Small modal prompts: a line of text, or a choice from a list.</summary>
public static class Prompt
{
    public static string? Text(Window owner, string title, string label, string initial = "") =>
        Show(owner, title, label, new TextBox { Text = initial, MinWidth = 320 }, c => ((TextBox)c).Text);

    public static string? Choose(Window owner, string title, string label, IEnumerable<string> options, string? initial = null)
    {
        var combo = new ComboBox { ItemsSource = options.ToList(), MinWidth = 320, IsEditable = true, Text = initial ?? "" };
        return Show(owner, title, label, combo, c => ((ComboBox)c).Text);
    }

    private static string? Show(Window owner, string title, string label, Control input, Func<Control, string> read)
    {
        var dialog = new Window
        {
            Title = title, Owner = owner, SizeToContent = SizeToContent.WidthAndHeight, ResizeMode = ResizeMode.NoResize,
            WindowStartupLocation = WindowStartupLocation.CenterOwner, Background = Theme.Brush("Panel"),
        };
        string? result = null;
        var ok = new Button { Content = "OK", IsDefault = true, Width = 80, Margin = new Thickness(0, 0, 6, 0) };
        var cancel = new Button { Content = "Cancel", IsCancel = true, Width = 80 };
        ok.Click += (_, _) => { result = read(input); dialog.DialogResult = true; };
        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 10, 0, 0) };
        buttons.Children.Add(ok);
        buttons.Children.Add(cancel);
        var panel = new StackPanel { Margin = new Thickness(12) };
        panel.Children.Add(new TextBlock { Text = label, Foreground = Theme.Brush("Text"), Margin = new Thickness(0, 0, 0, 6) });
        panel.Children.Add(input);
        panel.Children.Add(buttons);
        dialog.Content = panel;
        dialog.Loaded += (_, _) => input.Focus();
        return dialog.ShowDialog() == true ? result : null;
    }
}
