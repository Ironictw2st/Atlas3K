# Working on a map together

Atlas3K gives you two ways to share map work. Both use the same map-aware three-way merge:

- **Change packages** (`.a3kpatch`): send a file, with no setup.
- **Project repositories**: git, optionally on GitHub, with history, branches, pull requests, map pins and locks.

The merge works per entity and per pixel, not per line:

| File | Merged by | Conflict only when |
|---|---|---|
| `.layer`, `.terry` | entity id, then component and attribute; tag/folder links merge as sets | both sides set the same attribute to different values, or one side edits an entity the other deletes, or both change the file header |
| `.tif`, `.png` (height, sea, blend, tree, tile map, climate) | pixel | both sides change the same pixel differently (reported per 64-pixel cell) |
| anything else | whole file | both sides changed it |

A conflict keeps your side ("ours") in the merged file until you resolve it to theirs. Resolve in the GUI (**Collaboration → Conflicts**) or with `conflicts` / `conflicts-resolve ours|theirs [--ids 1,2]`. Double-click a conflict to see it on the map. `.terry.user` (visibility, locks, active layer) is per user and never shared.

## Change packages

- **Export:** **Collaboration → Change packages → Export** writes either everything your edit journals changed after a time, or the map folder compared against a copy of it.
  - Layers ship whole.
  - Rasters ship only their changed cells, so a heightmap edit is a few KB.
- **Import:** applies files that are still at the package's base, and merges the rest with your edits. The whole import is one undo step (**Undo last import**).

CLI:

```
Atlas3K.Cli --map <map> patch-export edits.a3kpatch --since "2026-10-08 09:00" [--label "Hexi lakes"]
Atlas3K.Cli --map <map> patch-export edits.a3kpatch --base D:\handout\<map>
Atlas3K.Cli --map <map> patch-import edits.a3kpatch --dry-run      (then without --dry-run)
Atlas3K.Cli --map <map> patch-undo
```

## Project repositories

The repository is the kit's map folder, `raw_data\terrain\campaigns\<map>`, so every editor keeps working in place.

- Rasters go to Git LFS.
- `collab-init` / `collab-clone` register Atlas3K as git's merge driver for map files and as the diff for rasters.

You need git, git-lfs, and for GitHub the GitHub CLI (`gh auth login`).

**Keep GitHub repositories private.** Assembly-kit data is Creative Assembly's.

| Task | GUI (Window → Collaboration…) | CLI |
|---|---|---|
| Share a map | Set up → Create on GitHub / remote URL / local | `collab-init --github owner/name` |
| Join | Set up → Clone | `collab-clone owner/name` |
| Commit, pull, push | Changes (message suggested from your edit history) | `collab-commit -m …`, `collab-pull`, `collab-push` |
| Branches | Changes → Switch / Create / Merge selected | `collab-branch [name] [--create]`, `collab-merge origin/main` |
| History, revert | History → Map diff / Revert | `collab-log`, `collab-diff a b`, `collab-revert <rev>` |
| Pull requests | Pull requests (the description gets the map diff; Map diff, Post map diff, Approve, Merge) | `pr-create`, `pr-list`, `pr-diff <n> [--post]`, `pr-review`, `pr-merge` |
| Map pins | Map pins (issues labelled `map-pin` with a world position, drawn on the scene editor's top view; Ctrl+Shift+P there pins the point under the mouse) | `pin-create --title … --x … --z …`, `pin-list` |
| Locks | Locks | `lock-acquire --layer <name> \| --file <rel> \| --rect x0,z0,x1,z1`, `lock-release` |

**Locks.** Locks live on the repository's `atlas3k/locks` branch.

- **File and layer locks are enforced.** Every Atlas3K editor saves through its edit journal, which refuses files someone else has locked.
- **Region locks are advisory.** They are drawn on the map.

**Merging pull requests.** GitHub merges PRs line by line. When a PR conflicts:

1. Check it out (`pr-checkout <n>`).
2. Merge its base branch locally (`collab-merge origin/main`), so Atlas3K's driver merges the map files.
3. Resolve any conflicts, then commit and push.
4. Merge the PR.

**LFS storage.** GitHub's free Git LFS quota is 1 GB. An 80 MB heightmap stores one full copy per committed version, so commit terrain work in batches rather than after every stroke.

The terry MCP server exposes all of this as tools: `patch_export`, `patch_import`, `conflicts`, `resolve_conflicts`, `collab_*`, `pull_request`, `map_pins`, `locks`.
