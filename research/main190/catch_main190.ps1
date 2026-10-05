param([int]$WaitSec = 900)
# Waits for Three_Kingdoms.exe (started by RPFM's build_starpos), attaches cdb with output\catch_cmds_main190.txt:
# logs every access violation / C++ exception (rip + stack) and the game's OutputDebugString lines, full dump on
# a second-chance AV. Log: output\catch_main190_cdb.log
$cdb = "C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\cdb.exe"
$t0 = Get-Date
while (-not ($p = Get-Process Three_Kingdoms -ErrorAction SilentlyContinue)) {
  if (((Get-Date) - $t0).TotalSeconds -gt $WaitSec) { "no game"; exit 1 }
  Start-Sleep -Milliseconds 100
}
"attaching to $($p.Id)"
& $cdb -p $p.Id -cf Z:\Claude\TerryClone\output\catch_cmds_main190.txt *> Z:\Claude\TerryClone\output\catch_main190_cdb.log
"cdb exit $LASTEXITCODE"
