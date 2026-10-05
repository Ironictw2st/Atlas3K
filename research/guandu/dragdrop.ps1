param([string]$File, [int]$ToX, [int]$ToY)
# Simulated Explorer-style drag of $File onto the screen point (ToX, ToY): a small topmost window starts an OLE
# file drag when pressed, and a second process drives the real mouse (press on the window, move, release).
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.TopMost = $true; $form.StartPosition = 'Manual'; $form.Location = New-Object System.Drawing.Point(100, 900)
$form.Size = New-Object System.Drawing.Size(200, 80); $form.Text = 'drag'; $form.FormBorderStyle = 'FixedToolWindow'
$lbl = New-Object System.Windows.Forms.Label; $lbl.Dock = 'Fill'; $lbl.Text = [IO.Path]::GetFileName($File); $form.Controls.Add($lbl)
$lbl.Add_MouseDown({
    $data = New-Object System.Windows.Forms.DataObject([System.Windows.Forms.DataFormats]::FileDrop, [string[]]@($File))
    $script:result = $lbl.DoDragDrop($data, [System.Windows.Forms.DragDropEffects]::Copy -bor [System.Windows.Forms.DragDropEffects]::Move -bor [System.Windows.Forms.DragDropEffects]::Link)
    $form.Close()
})
$mover = @"
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class MV { [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y); [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,IntPtr e); [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
[MV]::SetProcessDPIAware() | Out-Null
Start-Sleep -Milliseconds 1500
`$sx = 190; `$sy = 945; [MV]::SetCursorPos(`$sx, `$sy) | Out-Null; Start-Sleep -Milliseconds 300
[MV]::mouse_event(2,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 400
for (`$i = 1; `$i -le 60; `$i++) { [MV]::SetCursorPos([int](`$sx + ($ToX - `$sx) * `$i / 60), [int](`$sy + ($ToY - `$sy) * `$i / 60)) | Out-Null; Start-Sleep -Milliseconds 25 }
Start-Sleep -Milliseconds 700
[MV]::mouse_event(4,0,0,0,[IntPtr]::Zero)
"@
$form.Add_Shown({ Start-Process powershell -ArgumentList '-NoProfile', '-Command', $mover -WindowStyle Hidden })
[void]$form.ShowDialog()
"drop result: $script:result"
