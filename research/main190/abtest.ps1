param([string[]]$Include, [string]$Label)
# A/B test for the 190E startpos bad_alloc: rebuild zz_main190_abtest.pack = victory_objectives.txt + the listed
# binary tables from our pack (bin_ours\<rel>), then build 3k_main_campaign_map (no HLP/SPD) under cdb and report
# how far table loading / campaign model creation got. Our real pack stays Mod (not loaded).
$d = "C:\Program Files (x86)\Steam\steamapps\common\Total War THREE KINGDOMS\data"
$dummy = "$d\zz_main190_abtest.pack"
$bin = "Z:\Claude\TerryClone\research\main190\bin_ours"
$cli = "Z:\RPFM\rpfm_cli.exe"
& $cli --game three_kingdoms pack delete -p $dummy -F "db" 2>$null | Out-Null
& $cli --game three_kingdoms pack delete -p $dummy -F "text" 2>$null | Out-Null
& $cli --game three_kingdoms pack add -p $dummy -f "Z:\Claude\TerryClone\research\main190\source_vo\db\victory_objectives.txt;db/victory_objectives.txt" 2>$null | Out-Null
$n = 0
foreach ($inc in $Include) {
  Get-ChildItem -Recurse $bin -File | Where-Object { $_.FullName.Substring($bin.Length + 1).Replace('\', '/') -like $inc } | ForEach-Object {
    $rel = $_.FullName.Substring($bin.Length + 1).Replace('\', '/')
    & $cli --game three_kingdoms pack add -p $dummy -f "$($_.FullName);$rel" 2>$null | Out-Null; $n++
  }
}
"[$Label] $n files in test pack"
$log = "Z:\Claude\TerryClone\output\catch_main190_cdb.log"
if (Test-Path $log) { Remove-Item $log }
$job = Start-Job { & Z:\Claude\TerryClone\research\main190\catch_main190.ps1 }
$P = "C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/data/zz_main190_abtest.pack"
python Z:\Claude\TerryClone\research\guandu\rpfm_mcp.py close_pack ('{"pack_key":"' + $P + '"}') 2>$null | Out-Null
python Z:\Claude\TerryClone\research\guandu\rpfm_mcp.py set_game_selected '{"game_name":"three_kingdoms","rebuild_dependencies":false}' 2>$null | Out-Null
python Z:\Claude\TerryClone\research\guandu\rpfm_mcp.py open_packfiles ('{"paths":["' + $P + '"]}') 2>$null | Out-Null
python Z:\Claude\TerryClone\research\guandu\rpfm_mcp.py build_starpos ('{"pack_key":"' + $P + '","campaign_id":"3k_main_campaign_map","process_hlp_spd":false}') 2>$null | Out-Null
Wait-Job $job -Timeout 400 | Out-Null; Stop-Job $job -EA 0; Remove-Job $job -Force -EA 0
Get-Process Three_Kingdoms, cdb -EA 0 | Stop-Process -Force -EA 0
$t = Get-Content $log -EA 0
$exc = ($t | Select-String "CPP EXCEPTION|Access violation" | Select-Object -First 1)
$lastDb = ($t | Select-String "Loading database:" | Select-Object -Last 1).Line
$lastModel = ($t | Select-String "CAMPAIGN MODEL CREATION" | Select-Object -Last 1).Line
"[$Label] exception: $(if ($exc) { 'YES at line ' + $exc.LineNumber } else { 'none' })"
"[$Label] last table: $lastDb"
"[$Label] last model step: $lastModel"
