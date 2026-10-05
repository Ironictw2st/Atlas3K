#!/usr/bin/env bash
# Build the CLI into a private dir, rebuild native global_props from the frozen kit, diff against BOB main190.
set -e
cd /z/Claude/TerryClone
dotnet build src/Atlas3K.Cli -c Release -o output/props_finish/cli_bin 2>&1 | grep -E " error |Build succeeded"
C=output/props_finish/cli_bin/Atlas3K.Cli.exe
B=output/bob_runs/20261004_230523_frida_trees_main190/bob_terrain_out/global_props.bin
N=output/props_parity/native/terrain/campaigns/3k_190e_expanded_map/global_props.bin
$C build-campaign --ak 'Z:\Claude\TerryClone\output\props_parity\ak' --map 3k_190e_expanded_map --steps rasters,rivers,global_props --out 'Z:\Claude\TerryClone\output\props_parity\native' 2>&1 | grep -E "note|error" | tail -4
$C gp-diff $B $N 2>&1 | tail -16 | cut -c1-170
$C props-cells $N output/props_parity/native_cells.csv --map 3k_190e_expanded_map > /dev/null
python research/props/cells_compare.py output/props_parity/bob_cells.csv output/props_parity/native_cells.csv 2>&1 | tail -3 | cut -c1-300
