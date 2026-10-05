#!/usr/bin/env bash
# Builds Atlas3K.Cli from a private copy of the tracked sources plus this session's files, so other sessions'
# uncommitted, half-edited files cannot break the build. Usage: build_copy.sh
set -e
R=/z/Claude/TerryClone
B=$R/output/hlp_spd/bsrc
cd $R
mkdir -p $B
# tracked files at HEAD + working-tree versions of the hlp_spd files
git ls-files src Directory.Build.props global.json Atlas3K.slnx | while read f; do
  mkdir -p "$B/$(dirname "$f")"; cp "$f" "$B/$f" 2>/dev/null || true; done
for f in $(git ls-files --others --exclude-standard src | grep -E "AiPathfinding|HlpSpd|Esf/"); do mkdir -p "$B/$(dirname "$f")"; cp "$f" "$B/$f"; done
# tracked-but-modified files from other sessions: use HEAD version unless it is one of ours
for f in $(git diff --name-only -- src); do
  case "$f" in *AiPathfinding*|*HlpSpd*|*Esf/*|*AiPathfindingCommands*|*Program.cs) cp "$f" "$B/$f";; *) git show HEAD:"$f" > "$B/$f";; esac
done
cd $B/src/Atlas3K.Cli && dotnet build -c Release -v q 2>&1 | grep -E " error |rror\(s\)"
