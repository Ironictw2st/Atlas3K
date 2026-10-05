param([string]$Rip = "0x7ff6a6ee6dbc", [string]$Out = "Z:\Claude\TerryClone\output\full_crash.dmp", [int]$WaitSec = 600)
# Waits for Three_Kingdoms.exe, attaches cdb, and on a first-chance access violation at $Rip writes a full dump.
$cdb = "C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe"
$t0 = Get-Date
while (-not ($p = Get-Process Three_Kingdoms -ErrorAction SilentlyContinue)) {
  if (((Get-Date) - $t0).TotalSeconds -gt $WaitSec) { "no game"; exit 1 }
  Start-Sleep -Milliseconds 200
}
"attaching to $($p.Id)"
$cmd = "sxe -c `".if (@rip == $Rip) {.dump /ma /o $Out; .kill; q} .else {gc}`" av; sxd -c `"gc`" ld; g"
& $cdb -p $p.Id -cf Z:\Claude\TerryClone\output\catch_cmds.txt *> Z:\Claude\TerryClone\output\dlc08_full_cdb.log
"cdb exit $LASTEXITCODE"
"cdb exited"
