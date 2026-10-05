#!/bin/bash
# swaptest.sh <map.hex named 3k_dlc07_main_map> : run CA's map-data builder on it in vanilla's slot, then restore vanilla.
B="C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit"
R="$B/raw_data/EmpireDesignData/campaign_maps/3k_dlc07_main_map"; W="$B/working_data/campaign_maps/3k_dlc07_main_map"
BK=/z/Claude/TerryClone/output/backups/swaptest_keep; mkdir -p "$BK"
[ -f "$BK/map.hex" ] || { cp -p "$R/map.hex" "$BK/map.hex"; cp -p "$W/map_data.esf" "$BK/map_data.esf"; }
cp "$1" "$R/map.hex"
( cd /z/CAIME/Tools/Release && ./MapDataBuilder.x64.exe game=three_kingdoms "akit_path=$B" campaign_map=3k_dlc07_main_map process=map_data >/dev/null 2>&1 ); rc=$?
cp -p "$BK/map.hex" "$R/map.hex"; cp -p "$BK/map_data.esf" "$W/map_data.esf"
echo "$(basename $(dirname $1)): exit=$rc  restored=$(md5sum < "$R/map.hex" | cut -c1-8)/$(md5sum < "$W/map_data.esf" | cut -c1-8)"
