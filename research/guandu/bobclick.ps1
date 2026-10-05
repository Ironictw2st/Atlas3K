param([string]$Points = "", [string]$Shot = "", [int]$Wait = 2500, [switch]$Restart, [switch]$Wheel, [int]$WX = 960, [int]$WY = 600, [int]$Notches = 5)
# Drives BOB by absolute screen points "x,y;x,y;...". Brings BOB to the front before every click (it drops clicks
# while not focused / still loading). -Restart kills and relaunches BOB first. -Wheel scrolls down at (WX,WY).
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class BC {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, int d, IntPtr e);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, IntPtr e);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@
[BC]::SetProcessDPIAware() | Out-Null
$bin = "C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\assembly_kit\binaries"
if ($Restart) {
  Get-Process bob* -ErrorAction SilentlyContinue | Stop-Process -Confirm:$false; Start-Sleep 2
  Start-Process -FilePath "$bin\bob.retail.x64.exe" -WorkingDirectory $bin
  for ($i = 0; $i -lt 60; $i++) { Start-Sleep 1; $p = Get-Process bob.retail.x64 -ErrorAction SilentlyContinue; if ($p -and $p.MainWindowTitle -match 'Select') { break } }
  Start-Sleep 8
}
function Front {
  $p = Get-Process bob.retail.x64 -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $p) { throw "BOB not running" }
  for ($k = 0; $k -lt 10; $k++) {
    [BC]::keybd_event(0x12, 0, 0, [IntPtr]::Zero); [BC]::keybd_event(0x12, 0, 2, [IntPtr]::Zero)   # Alt tap lifts the focus lock
    [BC]::ShowWindow($p.MainWindowHandle, 5) | Out-Null; [BC]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 400
    $fp = 0; [BC]::GetWindowThreadProcessId([BC]::GetForegroundWindow(), [ref]$fp) | Out-Null
    if ($fp -eq $p.Id) { return }
  }
  throw "BOB is not the foreground window - refusing to click"
}
foreach ($pt in ($Points -split ';' | Where-Object { $_ })) {
  $x, $y = $pt -split ','
  Front
  [BC]::SetCursorPos([int]$x, [int]$y) | Out-Null; Start-Sleep -Milliseconds 300
  [BC]::mouse_event(2, 0, 0, 0, [IntPtr]::Zero); [BC]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero)
  Start-Sleep -Milliseconds $Wait
}
if ($Wheel) { Front; [BC]::SetCursorPos($WX, $WY) | Out-Null; Start-Sleep -Milliseconds 300; [BC]::mouse_event(0x800, 0, 0, -120 * $Notches, [IntPtr]::Zero); Start-Sleep -Milliseconds 1500 }
if ($Shot) {
  $s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $bmp = New-Object System.Drawing.Bitmap $s.Width, $s.Height
  [System.Drawing.Graphics]::FromImage($bmp).CopyFromScreen(0, 0, 0, 0, $bmp.Size); $bmp.Save($Shot); $bmp.Dispose()
  "shot $Shot"
}
