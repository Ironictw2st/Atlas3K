param([int]$ProcId, [int]$X = 0, [int]$Y = 0, [string]$Shot = "")
# Click at window-relative (X,Y) of a specific process's main window; optionally capture that window's screen rect.
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class PC {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, IntPtr e);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[PC]::SetProcessDPIAware() | Out-Null
$p = Get-Process -Id $ProcId; [PC]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 400
$r = New-Object PC+RECT; [PC]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
if ($X -or $Y) { [PC]::SetCursorPos($r.Left + $X, $r.Top + $Y) | Out-Null; Start-Sleep -Milliseconds 150
  [PC]::mouse_event(2,0,0,0,[IntPtr]::Zero); [PC]::mouse_event(4,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 800 }
if ($Shot) { $w = $r.Right - $r.Left; $h = $r.Bottom - $r.Top; $bmp = New-Object System.Drawing.Bitmap $w, $h
  [System.Drawing.Graphics]::FromImage($bmp).CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size); $bmp.Save($Shot) }
"rect $($r.Left),$($r.Top),$($r.Right),$($r.Bottom) title '$($p.MainWindowTitle)'"
