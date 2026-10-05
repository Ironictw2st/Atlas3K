#!/bin/bash
# round 6 terrain chain (north x1.4 + pinned passes + Hexi DEM); log: run_r6_chain.log
set -eo pipefail
cd /z/Claude/TerryClone/research/main190
for s in terrain_main dem_fill coast_carve class_fill north_cull korea_fix tilemap_main ak_main; do
  echo "=== $s $(date +%T)"; if [ $s = north_cull ]; then python north_cull.py --rasters terrain 2>&1 | tail -12; else python $s.py 2>&1 | tail -12; fi
done
echo "=== done $(date +%T)"
