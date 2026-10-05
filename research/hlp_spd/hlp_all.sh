#!/usr/bin/env bash
# HLP field stats on the four vanilla maps (+ optional 190E with arg "190")
EXE=/z/Claude/TerryClone/output/hlp_spd/bsrc/src/Atlas3K.Cli/bin/Release/net9.0/Atlas3K.Cli.exe
for m in 3k_dlc07_main_map 3k_dlc06_main_map 3k_dlc04_main_map 8p_main_map; do
  D="Z:/Claude/TerryClone/output/hlp_spd/vanilla/campaign_maps/$m"; L=""; case $m in 3k_dlc04*|8p*) L=--legacy-stl;; esac
  echo "== $m $("$EXE" hlp-spd --only hlp $L --in "$D" --compare "$D" --out "Z:/Claude/TerryClone/output/hlp_spd/out_$m" 2>&1 | grep -E "^hlp fields|reference" | tr '\n' ' ')"
done
if [ "$1" = 190 ]; then D="Z:/Claude/TerryClone/output/hlp_spd/main190/campaign_maps/3k_190e_expanded_map"
  echo "== 190e $("$EXE" --ak "C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit_190E" --map 3k_190e_expanded_map hlp-spd --only hlp --in "$D" --compare "$D" --out Z:/Claude/TerryClone/output/hlp_spd/out190 2>&1 | grep -E "^hlp fields|reference|nodes," | tr '\n' ' ')"; fi
