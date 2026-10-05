param([string]$ProcessName = "CAIME", [int]$X, [int]$Y, [string]$Keys = "", [string]$Shot = "")
# Clicks at window-relative (X,Y) of the process's main window (or top window if a dialog owns focus), optionally sends keys, optionally screenshots.
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class U {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[U]::SetProcessDPIAware() | Out-Null
$p = Get-Process $ProcessName | Select-Object -First 1
[U]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 300
$r = New-Object U+RECT; [U]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
if ($X -or $Y) {
  [U]::SetCursorPos($r.Left + $X, $r.Top + $Y) | Out-Null; Start-Sleep -Milliseconds 100
  [U]::mouse_event(2, 0, 0, 0, [IntPtr]::Zero); [U]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Milliseconds 700
}
if ($Keys) { [System.Windows.Forms.SendKeys]::SendWait($Keys); Start-Sleep -Milliseconds 700 }
if ($Shot) {
  $s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $s.Width, $s.Height
  [System.Drawing.Graphics]::FromImage($bmp).CopyFromScreen(0, 0, 0, 0, $bmp.Size)
  $bmp.Save($Shot, [System.Drawing.Imaging.ImageFormat]::Png); "window at $($r.Left),$($r.Top); screen $($s.Width)x$($s.Height)"
}
