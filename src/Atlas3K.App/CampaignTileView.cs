using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Atlas3K.Core.Campaign.TileMapCheck;
using Atlas3K.Core.Rendering;

namespace Atlas3K.App;

/// <summary>
/// Pan/zoom canvas for a campaign tile_map.png (same controls as <see cref="MapView"/>): right/middle drag pans, wheel
/// zooms around the cursor, left button goes to the window's tool callbacks as hexes. View pixels are tile-map pixels
/// (2×2 per hex, top row = north). Hex overlays: 1 = changed (white tint), 2 = warning (orange), 3 = blocking (red),
/// 4 = pending stroke (cyan).
/// </summary>
public sealed class CampaignTileView : FrameworkElement
{
    private WriteableBitmap? _bitmap;
    private uint[] _buffer = [];
    private bool _dirty = true;
    private Point? _panStart;
    private Viewport _panOrigin;
    private bool _dragging;
    private Point _lastMouse;
    private double _dpiScale = 1;

    public HexTileMap? Map { get; private set; }
    /// <summary>Per-hex overlay code [row * W + col].</summary>
    public byte[] Overlay { get; private set; } = [];
    public Viewport View { get; private set; } = new(0, 0, 1);
    /// <summary>Brush radius in hexes, for the cursor ring (−1 = no ring).</summary>
    public int BrushRadius { get; set; } = -1;
    /// <summary>Line tool waypoints, drawn as a polyline.</summary>
    public List<(int Col, int Row)> LinePoints { get; } = [];

    public event Action<(int Col, int Row)?>? HoverChanged;
    /// <summary>Left button down / drag / up on a hex (up passes null when released outside the map).</summary>
    public event Action<(int Col, int Row)>? HexDown, HexDrag;
    public event Action? HexUp;

    public CampaignTileView()
    {
        ClipToBounds = true;
        Focusable = true;
        CompositionTarget.Rendering += (_, _) =>
        {
            if (_dirty && IsVisible) RenderNow();
        };
    }

    public void Load(HexTileMap map)
    {
        var first = Map is null || Map.PixelWidth != map.PixelWidth || Map.PixelHeight != map.PixelHeight;
        Map = map;
        Overlay = new byte[map.Width * map.Height];
        if (first) FitToWindow();
        Invalidate();
    }

    public void Invalidate() => _dirty = true;

    public void FitToWindow()
    {
        if (Map == null || ActualWidth < 1) return;
        var (w, h) = PixelSize();
        var scale = Math.Max((double)Map.PixelWidth / w, (double)Map.PixelHeight / h);
        View = new Viewport((Map.PixelWidth - w * scale) / 2, (Map.PixelHeight - h * scale) / 2, scale);
        Invalidate();
    }

    /// <summary>Centres the view on a hex at a zoom where one hex is <paramref name="screenPxPerHex"/> pixels.</summary>
    public void CentreOn(int col, int row, double screenPxPerHex = 14)
    {
        if (Map == null) return;
        var (w, h) = PixelSize();
        var (x, y) = Map.HexPixel(col, row);
        var scale = 2 / screenPxPerHex;
        View = new Viewport(x + 1 - w * scale / 2, y - h * scale / 2, scale);
        Invalidate();
    }

    /// <summary>Hex under a tile-map pixel, or null for filler / outside.</summary>
    public (int Col, int Row)? HexAt(double px, double py)
    {
        if (Map == null || px < 0 || py < 0 || px >= Map.PixelWidth || py >= Map.PixelHeight) return null;
        var col = (int)px / 2;
        var row = (int)Math.Floor((2.0 * Map.Height - (int)py - (col & 1)) / 2);
        return col < Map.Width && row >= 0 && row < Map.Height ? (col, row) : null;
    }

    private (double X, double Y) ToView(Point p) => View.ScreenToMap(p.X * _dpiScale, p.Y * _dpiScale);

    private Point HexToScreen(int col, int row)
    {
        var (x, y) = Map!.HexPixel(col, row);
        var (sx, sy) = View.MapToScreen(x + 1, y);
        return new Point(sx / _dpiScale, sy / _dpiScale);
    }

    private (int W, int H) PixelSize()
    {
        _dpiScale = VisualTreeHelper.GetDpi(this).DpiScaleX;
        return (Math.Max(1, (int)(ActualWidth * _dpiScale)), Math.Max(1, (int)(ActualHeight * _dpiScale)));
    }

    private void RenderNow()
    {
        _dirty = false;
        if (Map == null || ActualWidth < 1 || ActualHeight < 1) return;
        var (w, h) = PixelSize();
        if (_bitmap == null || _bitmap.PixelWidth != w || _bitmap.PixelHeight != h)
        {
            _bitmap = new WriteableBitmap(w, h, 96 * _dpiScale, 96 * _dpiScale, PixelFormats.Bgra32, null);
            _buffer = new uint[w * h];
        }
        var map = Map;
        var overlay = Overlay;
        var view = View;
        var buffer = _buffer;
        var showGrid = view.Scale < 0.2;   // > 10 screen px per hex: draw hex edges darker
        Parallel.For(0, h, sy =>
        {
            var py = (int)Math.Floor(view.OriginY + sy * view.Scale);
            for (var sx = 0; sx < w; sx++)
            {
                var px = (int)Math.Floor(view.OriginX + sx * view.Scale);
                uint c;
                if (px < 0 || py < 0 || px >= map.PixelWidth || py >= map.PixelHeight) c = 0xff202020;
                else
                {
                    var rgb = map.Pixels[py * map.PixelWidth + px];
                    var col = px / 2;
                    var row = (2 * map.Height - py - (col & 1)) / 2;
                    var o = row >= 0 && row < map.Height && 2 * map.Height - py - (col & 1) >= 0 ? overlay[row * map.Width + col] : (byte)0;
                    uint r = rgb >> 16 & 0xff, g = rgb >> 8 & 0xff, b = rgb & 0xff;
                    (r, g, b) = o switch
                    {
                        1 => ((r + 255 * 2) / 3, (g + 255 * 2) / 3, (b + 255 * 2) / 3),
                        2 => ((r + 255) / 2, (g + 150) / 2, b / 2),
                        3 => ((r + 255 * 3) / 4, g / 4, b / 4),
                        4 => (r / 2, (g + 255) / 2, (b + 255) / 2),
                        _ => (r, g, b),
                    };
                    if (showGrid)
                    {
                        // darken the pixel edges of each hex block
                        var fx = view.OriginX + sx * view.Scale - px;
                        var fy = view.OriginY + sy * view.Scale - py;
                        var edgeX = (px & 1) == 0 ? fx < view.Scale : fx > 1 - view.Scale;
                        var hexTop = (py + (col & 1)) % 2 == 0;
                        var edgeY = hexTop ? fy < view.Scale : fy > 1 - view.Scale;
                        if (edgeX || edgeY) { r = r * 3 / 4; g = g * 3 / 4; b = b * 3 / 4; }
                    }
                    c = 0xff000000 | r << 16 | g << 8 | b;
                }
                buffer[sy * w + sx] = c;
            }
        });
        _bitmap.WritePixels(new Int32Rect(0, 0, w, h), _buffer, w * 4, 0);
        InvalidateVisual();
    }

    protected override void OnRender(DrawingContext dc)
    {
        dc.DrawRectangle(new SolidColorBrush(Color.FromRgb(32, 32, 32)), null, new Rect(RenderSize));
        if (_bitmap != null) dc.DrawImage(_bitmap, new Rect(0, 0, ActualWidth, ActualHeight));
        if (Map == null) return;
        if (LinePoints.Count > 0)
        {
            var pen = new Pen(Brushes.Cyan, 2) { DashStyle = DashStyles.Dash };
            for (var i = 1; i < LinePoints.Count; i++)
                dc.DrawLine(pen, HexToScreen(LinePoints[i - 1].Col, LinePoints[i - 1].Row), HexToScreen(LinePoints[i].Col, LinePoints[i].Row));
            foreach (var p in LinePoints) dc.DrawEllipse(Brushes.Cyan, null, HexToScreen(p.Col, p.Row), 3, 3);
        }
        if (BrushRadius >= 0 && IsMouseOver)
        {
            // a hex is 2 tile-map pixels wide; radius r covers about (2r + 1) hexes across
            var radius = Math.Max(3, (BrushRadius + 0.5) * 2 / View.Scale / _dpiScale);
            dc.DrawEllipse(null, new Pen(Brushes.Black, 2.5), _lastMouse, radius, radius);
            dc.DrawEllipse(null, new Pen(Brushes.White, 1) { DashStyle = DashStyles.Dash }, _lastMouse, radius, radius);
        }
    }

    protected override void OnRenderSizeChanged(SizeChangedInfo info)
    {
        base.OnRenderSizeChanged(info);
        if (info.PreviousSize.Width < 1) FitToWindow();
        Invalidate();
    }

    protected override void OnMouseWheel(MouseWheelEventArgs e)
    {
        var p = e.GetPosition(this);
        var (mx, my) = ToView(p);
        var factor = e.Delta > 0 ? 1 / 1.25 : 1.25;
        var scale = Math.Clamp(View.Scale * factor, 0.02, 40);
        View = new Viewport(mx - p.X * _dpiScale * scale, my - p.Y * _dpiScale * scale, scale);
        Invalidate();
    }

    protected override void OnMouseDown(MouseButtonEventArgs e)
    {
        Focus();
        var p = e.GetPosition(this);
        if (e.ChangedButton is MouseButton.Right or MouseButton.Middle)
        {
            _panStart = p;
            _panOrigin = View;
            CaptureMouse();
            return;
        }
        if (e.ChangedButton != MouseButton.Left) return;
        var (vx, vy) = ToView(p);
        if (HexAt(vx, vy) is not { } hex) return;
        _dragging = true;
        CaptureMouse();
        HexDown?.Invoke(hex);
        Invalidate();
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        var p = e.GetPosition(this);
        if (_panStart is { } start)
        {
            var d = p - start;
            View = _panOrigin with
            {
                OriginX = _panOrigin.OriginX - d.X * _dpiScale * View.Scale,
                OriginY = _panOrigin.OriginY - d.Y * _dpiScale * View.Scale,
            };
            Invalidate();
        }
        var (vx, vy) = ToView(p);
        var hex = HexAt(vx, vy);
        if (_dragging && hex is { } h)
        {
            // fill in hexes skipped by a fast mouse move
            var (x0, y0) = ToView(_lastMouse);
            var steps = Math.Max(1, (int)(Math.Sqrt((vx - x0) * (vx - x0) + (vy - y0) * (vy - y0)) / 1.5));
            for (var i = 1; i < steps; i++)
                if (HexAt(x0 + (vx - x0) * i / steps, y0 + (vy - y0) * i / steps) is { } mid) HexDrag?.Invoke(mid);
            HexDrag?.Invoke(h);
            Invalidate();
        }
        _lastMouse = p;
        HoverChanged?.Invoke(hex);
        InvalidateVisual();
    }

    protected override void OnMouseUp(MouseButtonEventArgs e)
    {
        if (_panStart != null && e.ChangedButton is MouseButton.Right or MouseButton.Middle)
        {
            _panStart = null;
            ReleaseMouseCapture();
        }
        else if (_dragging && e.ChangedButton == MouseButton.Left)
        {
            _dragging = false;
            ReleaseMouseCapture();
            HexUp?.Invoke();
            Invalidate();
        }
    }

    protected override void OnMouseLeave(MouseEventArgs e)
    {
        HoverChanged?.Invoke(null);
        InvalidateVisual();
    }
}
