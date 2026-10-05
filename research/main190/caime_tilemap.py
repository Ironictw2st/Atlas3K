#!/usr/bin/env python3
"""Campaign tile map from CAIME's baseline tilemap export, tweaked toward 190E's hand-made conventions.

Replaces the programmatic tilemap_main.py: instead of redrawing 190E's lines through the warp, CAIME writes the tile
map straight from the map.hex flags (BaselineTilemapExporter, three_kingdoms branch):
    sea 3971b7 | beach ffff00 | cliff f9ad69 (cliff touching a beach: cliff end 9f222a) | river 0000ff, river start
    b4b4ff (1 river neighbour), river mouth ccccff (river touching sea) | every road bit as roads_tracks 5d0018,
    road+river as river_crossing_track da43ff | ground type "mountain" by climate (cold 1820c1, temperate b69237,
    subtropical 53b021) | everything else generic 96aa64.
Size 2W x (2H+1), hex (col,row) = 2x2 px, odd columns 1 px north, row 0 south (flipped) - the same layout as
190E's and our tile maps (tilemap_hex.py), checked: 99.99% sea agreement with 190E's hand-made map, 69% if flipped.
On stock 190E the export reproduces the hand-made map's lines: rivers 7114/7122 hexes, roads 13365/13398, beach
4278/4464, cliff 2701/2887 - so 190E's tile map was itself a map.hex export plus hand edits.

Tweaks (each only where CAIME's baseline is weaker than 190E's map):
 1. AREAS  - land area tile sets come from the reference tile map (190E's hand-made map, sampled at the scaled-back
             hex: new (c, r) ~ ref (c/s, r/s), s = 1.5 for the CAIME upscale). CAIME only knows generic + 3 climate
             mountains from the map.hex ground type; 190E also uses ffff7f / 463a76 / 10ffe4 and paints mountain
             ranges that follow the terrain art, not the impassable flag. Areas are one class for tile matching, so
             this cannot create holes.
 2. ROADS  - road family (track 5d0018 / paved 5d4218 / imperial c10018) per road segment (junction to junction)
             by majority of the reference's road family within one hex of the scaled-back position; segments with
             no reference road (e.g. Korea - 190E's tile map has no roads there) stay tracks. Crossings take their
             segment's crossing colour (da43ff / 7f00ff / 2c067f). CAIME draws everything as tracks.
 3. REPAIR - tile_repair.py's fix: crossing layouts BOB can't tile get a road end moved (or become plain river), and
             coast / river / mouth / crossing hexes whose 7-hex pattern vanilla never uses are recoloured greedily
             (beach->sea/land, cliff->end/beach/sea, ...). Visual only - map.hex is untouched. The round-8 feedback
             list (holes/feedback.json, coordinates of the OLD grid) is NOT applied.
Not done: canals (no map.hex flag; 190E's few canal hexes were holes in round 8), no line thinning (CAIME lines
follow map.hex 1:1; measured below whether it helps).

usage: caime_tilemap.py <map.hex> <out tile_map.png> [--ref tile_map.png] [--raw caime_export.png] [--no-areas]
       [--no-roads] [--no-repair] [--preview preview.png]
--ref defaults to 190E's original hand-made tile map; the scale is new grid / ref grid per axis.
"""
import argparse, os, subprocess, sys
from collections import Counter, deque
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
for p in (HERE, HERE.parent / "guandu", HERE.parent): sys.path.insert(0, str(p))
from build_tilemap import (SEA, BEACH, CLIFF, CLIFF_END, AREAS, RIVER, START, MOUTH, PAVED, IMPERIAL, TRACK,
                           X_PAVED, X_IMPERIAL, X_TRACK, KNOWN, BLACK, rgb, load_hex, area_base)
from hexgrid import neighbour_arrays, nearest_hex, centre
from tilemap_hex import hex_pixels, read_codes
import tile_repair

CAIME = Path(r"Z:/Claude/TerryClone/output/caime_upscaler")
REF_190E = r"Z:/Claude/TerryClone/output/backups/main190_originals_20260929_130639/ak190E_terrain_3k_dlc07_main_map/tile_map.png"
MSBUILD = r"C:/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/MSBuild.exe"
ROADS = (TRACK, PAVED, IMPERIAL)
CROSS = {TRACK: X_TRACK, PAVED: X_PAVED, IMPERIAL: X_IMPERIAL}
FAMILY_OF = {TRACK: TRACK, PAVED: PAVED, IMPERIAL: IMPERIAL, X_TRACK: TRACK, X_PAVED: PAVED, X_IMPERIAL: IMPERIAL}


def caime_export(map_hex, out_png, log=print):
    """CAIME's BaselineTilemapExporter via the MSTest driver CAIME.Tests/Unit/ZzTilemapExport.cs (no dialog)."""
    env = dict(os.environ, TILEMAP_SRC=str(Path(map_hex).resolve()), TILEMAP_OUT=str(Path(out_png).resolve()))
    env["PATH"] = env.get("PATH", "") + os.pathsep + r"C:\Windows\System32"
    dll = CAIME / "CAIME.Tests" / "bin" / "Release"
    if not any(dll.rglob("CAIME.Tests.dll")):
        subprocess.run([MSBUILD, "CampaignMapToolkit.sln", "-p:Configuration=Release", "-m", "-v:q"], cwd=CAIME, check=True)
    r = subprocess.run(["dotnet", "test", "CAIME.Tests/CAIME.Tests.csproj", "--no-build", "-c", "Release",
                        "--filter", "FullyQualifiedName~ZzTilemapExport", "--logger", "console;verbosity=detailed"],
                       cwd=CAIME, env=env, capture_output=True, text=True)
    if r.returncode != 0 or not Path(out_png).exists():
        raise SystemExit("CAIME export failed:\n" + r.stdout[-3000:] + r.stderr[-2000:])
    log("CAIME: " + " | ".join(l.strip() for l in r.stdout.splitlines() if l.strip().startswith(("loaded", "saved"))))


def hex_codes(img, W, H):
    code = read_codes(img); ys, xs = hex_pixels(W, H); return code[ys[..., 0], xs[..., 0]].astype(np.int64)


def ref_codes(path):
    """Per-hex colour of a reference tile map (2x2 majority), stray editing colours snapped to the palette."""
    code = read_codes(Image.open(path)); H, W = (code.shape[0] - 1) // 2, code.shape[1] // 2
    ys, xs = hex_pixels(W, H); blk = code[ys, xs]
    hc = blk[..., 0]; same = (blk == blk[..., :1]).sum(-1)
    for k in range(1, 4):
        cnt = (blk == blk[..., k:k + 1]).sum(-1)
        hc = np.where(cnt > same, blk[..., k], hc); same = np.maximum(same, cnt)
    pal = sorted(KNOWN); P = np.stack([rgb(c) for c in pal])
    for c in np.unique(hc[~np.isin(hc, pal)]):
        hc[hc == c] = pal[int(np.argmin(((P - rgb(int(c))) ** 2).sum(1)))]
    return hc.astype(np.int64), W, H


def ref_index(NW, NH, RW, RH):
    """Reference hex under each new hex (hex centres). Uses warp.current()'s inverse when it maps the reference grid
    onto this one (x1.5 + the Hexi west pad), else a uniform scale per axis."""
    rows, cols = np.mgrid[0:NH, 0:NW]; x, z = centre(cols, rows)
    try:
        import warp
        W = warp.current()
        if (W.W, W.H) == (NW, NH) and hasattr(W, "f"):
            ox, oy = W.inverse(x / 0.668, z / 0.772)
            return nearest_hex(ox * 0.668, oy * 0.772, RW, RH)
    except Exception:
        pass
    return nearest_hex(x * RW / NW, z * RH / NH, RW, RH)


def apply_hexi_zone(out, NW, NH, log):
    """Hexi west pad / zone (warp.is_hexi): no 190E reference there - land tile sets from the new terrain: the 190E
    western high-mountain set where the blend raster is a mountain class, the generic land set elsewhere."""
    import warp
    if not warp.is_hexi(): return
    import hexi_geo
    from regions_carve import hex_blend_and_height
    Z = hexi_geo._zone(); w = Z["w"]
    if w.shape != (NH, NW): return
    hb, _ = hex_blend_and_height(NW, NH)
    zone = ((w > 0.5) | (np.arange(NH)[:, None] >= Z["H0"])) & np.isin(out, AREAS)     # + the north pad rows
    mnt = np.isin(hb, (4, 5, 6, 7))
    out[zone & mnt] = 0x1820c1; out[zone & ~mnt] = AREAS[0]
    log(f"hexi zone: {int(zone.sum())} land hexes from the new terrain ({int((zone & mnt).sum())} mountain)")


def apply_areas(out, ref, rc, rr, log):
    base = area_base(ref)[rr, rc]
    m = np.isin(out, AREAS)
    n = int((out[m] != base[m]).sum()); out[m] = base[m]
    log(f"areas: {n} of {int(m.sum())} land hexes recoloured from the reference "
        f"({dict(Counter('%06x' % v for v in out[m]).most_common(8))})")


def apply_roads(out, ref, rc, rr, NA, log):
    NH, NW = out.shape; RH, RW = ref.shape
    road = np.isin(out, list(FAMILY_OF))
    # vote: reference road families on the scaled-back hex and its 6 neighbours
    rNA = neighbour_arrays(RH, RW)
    rfam = np.vectorize(lambda v: FAMILY_OF.get(int(v), 0))(ref)
    votes = {f: (rfam == f).astype(np.int32) for f in ROADS}
    for f in ROADS:
        v0 = votes[f].copy()
        for nr, nc, v in rNA: votes[f] += np.where(v, v0[nr, nc], 0)
    vote = {f: votes[f][rr, rc] * road for f in ROADS}
    deg = np.zeros(out.shape, np.int32)
    for nr, nc, v in NA: deg += v & road[nr, nc]
    junction = road & (deg >= 3)
    seg = np.full(out.shape, -1, np.int64); fam_of_seg = []
    for r0, c0 in zip(*np.nonzero(road & ~junction)):
        if seg[r0, c0] >= 0: continue
        sid = len(fam_of_seg); q = deque([(r0, c0)]); seg[r0, c0] = sid; tally = Counter(); members = []
        while q:
            r, c = q.popleft(); members.append((r, c))
            for f in ROADS: tally[f] += int(vote[f][r, c])
            for nr, nc, v in NA:
                if v[r, c]:
                    a, b = int(nr[r, c]), int(nc[r, c])
                    if road[a, b] and not junction[a, b] and seg[a, b] < 0: seg[a, b] = sid; q.append((a, b))
        fam_of_seg.append(max(ROADS, key=lambda f: (tally[f], f == TRACK)) if sum(tally.values()) else TRACK)
    fam = np.zeros(out.shape, np.int64)
    sr, sc = np.nonzero(seg >= 0); fam[sr, sc] = np.array(fam_of_seg, np.int64)[seg[sr, sc]]
    for r, c in zip(*np.nonzero(junction)):                         # junctions: majority of the adjoining segments
        t = Counter(int(fam[nr[r, c], nc[r, c]]) for nr, nc, v in NA if v[r, c] and seg[nr[r, c], nc[r, c]] >= 0)
        if not t:
            t = Counter({f: int(vote[f][r, c]) for f in ROADS})
        fam[r, c] = max(ROADS, key=lambda f: (t[f], f == TRACK)) if sum(t.values()) else TRACK
    crossing = np.isin(out, [X_TRACK, X_PAVED, X_IMPERIAL])
    for f in ROADS:
        out[road & ~crossing & (fam == f)] = f; out[road & crossing & (fam == f)] = CROSS[f]
    log(f"roads: {len(fam_of_seg)} segments + {int(junction.sum())} junction hexes; hexes per family "
        f"{ {('%06x' % f): int((road & (fam == f)).sum()) for f in ROADS} }")


def repair_ring(out, NA, log, passes=4):
    """tile_repair only recolours the unseen hex itself; this also tries its coast / river neighbours (a 2-hex
    configuration is often only fixable from the side). Greedy, accepts a change only if the number of unseen
    patterns on the changed hex and its ring drops. Re-applies the cliff-end rule after each accepted change."""
    TR = tile_repair; vs = TR.vanilla_set(); CAT = TR.CAT; T = TR.TARGET
    NH, NW = out.shape
    def cat(v): return CAT.get(v, 11 if v in TR.CANALS else 10)
    def ring(r, c): return [(int(nr[r, c]), int(nc[r, c])) for nr, nc, v in NA if v[r, c]]
    def bad_at(a, b):
        if cat(int(out[a, b])) not in T: return 0
        k = cat(int(out[a, b]))
        for nr, nc, v in NA: k = k * 12 + (cat(int(out[nr[a, b], nc[a, b]])) if v[a, b] else 0)
        return int(not np.isin(k, vs))
    def local(pts): return sum(bad_at(a, b) for a, b in pts)
    def land_of(r, c):
        ns = [int(out[p]) for p in ring(r, c) if int(out[p]) in AREAS]; return max(set(ns), key=ns.count) if ns else AREAS[0]
    def cands(r, c):
        k = cat(int(out[r, c])); L = land_of(r, c)
        return {2: [SEA, L, CLIFF, CLIFF_END], 3: [CLIFF_END, BEACH, SEA, L], 4: [BEACH, CLIFF, SEA],
                7: [SEA, RIVER, BEACH], 6: [RIVER, L], 5: [START, MOUTH, L], 8: [RIVER]}.get(k, [])
    def coast_rule(pts):
        for a, b in pts:
            v = int(out[a, b])
            if v not in (CLIFF, CLIFF_END): continue
            nb = any(int(out[p]) == BEACH for p in ring(a, b))
            out[a, b] = CLIFF_END if nb else CLIFF
    total = 0
    for _ in range(passes):
        bad = TR.unseen(out, NA); n = 0
        for r, c in zip(*np.nonzero(bad)):
            if not bad_at(r, c): continue
            for h in [(r, c)] + ring(r, c):
                area = {h} | set(ring(*h)); area |= {q for p in list(area) for q in ring(*p)}
                base = local(area); keep = {p: int(out[p]) for p in area}; best = None
                for x in cands(*h):
                    out[h] = x; coast_rule(area); s = local(area)
                    if s < base and (best is None or s < best[0]): best = (s, x)
                    for p, v in keep.items(): out[p] = v
                if best:
                    out[h] = best[1]; coast_rule(area); n += 1; break
        total += n
        if not n: break
    log(f"ring repair: {total} hexes recoloured, unseen patterns now {int(TR.unseen(out, NA).sum())}")


def coast_ring(out, NA, log):
    """Vanilla's coast is one ring: an area (land) hex never touches sea (vanilla tile map: 40, ours had 784 - BOB has
    no tile for land meeting sea, 40 of the last 53 hole clusters sat on one). Area hexes touching SEA become BEACH
    (after the repairs / measured-hole feedback, which can turn a beach into sea), then the cliff-end rule."""
    sea = out == SEA
    line = np.isin(out, [RIVER, START, MOUTH, PAVED, IMPERIAL, TRACK, X_PAVED, X_IMPERIAL, X_TRACK])
    area = ~sea & ~np.isin(out, [BEACH, CLIFF, CLIFF_END, BLACK]) & ~line
    ns = np.zeros(out.shape, bool)
    for nr, nc, v in NA: ns |= v & sea[nr, nc]
    fix = area & ns; out[fix] = BEACH
    for _ in range(2):
        nbB = np.zeros(out.shape, bool)
        for nr, nc, v in NA: nbB |= v & (out[nr, nc] == BEACH)
        out[(out == CLIFF) & nbB] = CLIFF_END; out[(out == CLIFF_END) & ~nbB] = CLIFF
    log(f"coast ring: {int(fix.sum())} land hexes touching sea -> beach")


def unseen_count(out, NA):
    return int(tile_repair.unseen(out, NA).sum())


def build(map_hex, raw_png, ref_path=REF_190E, areas=True, roads=True, repair=True, log=print):
    N, NW, NH = load_hex(map_hex)
    if not Path(raw_png).exists(): caime_export(map_hex, raw_png, log)
    raw = Image.open(raw_png)
    assert raw.size == (2 * NW, 2 * NH + 1), (raw.size, NW, NH)
    out = hex_codes(raw, NW, NH)
    NA = neighbour_arrays(NH, NW)
    log(f"grid {NW}x{NH}; CAIME export {raw.size}; unseen coast/river patterns {unseen_count(out, NA)}")
    if areas or roads:
        ref, RW, RH = ref_codes(ref_path); rc, rr = ref_index(NW, NH, RW, RH)
        log(f"reference {ref_path} {RW}x{RH}, scale {NW / RW:.3f} x {NH / RH:.3f}")
        if areas:
            apply_areas(out, ref, rc, rr, log); apply_hexi_zone(out, NW, NH, log)
            import x15_land; x15_land.tile_clear(out, NW, NH, log, Path(map_hex))     # x15 tile plan (new land, tier 1 + 2)
        if roads: apply_roads(out, ref, rc, rr, NA, log)
    if repair:
        tile_repair.HERE = Path(raw_png).parent                     # no holes/feedback.json there: old-grid list off
        tile_repair.repair(out, log)
        repair_ring(out, NA, log)
        coast_ring(out, NA, log)
    # paint over CAIME's image so its fill of the spare pixels (row 0 of even columns) follows the top hex row
    img = read_codes(raw).astype(np.int64)
    ys, xs = hex_pixels(NW, NH)
    for k in range(4): img[ys[..., k], xs[..., k]] = out
    x = np.arange(2 * NW); ev = (x // 2) % 2 == 0
    img[0, x[ev]] = out[NH - 1, x[ev] // 2]
    rgba = np.stack([(img >> 16) & 255, (img >> 8) & 255, img & 255, np.full_like(img, 255)], -1).astype(np.uint8)
    unknown = set(np.unique(out).tolist()) - KNOWN
    if unknown: log(f"WARNING colours outside the tile-set palette: {['%06x' % u for u in unknown]}")
    log(f"final unseen coast/river/crossing patterns {unseen_count(out, NA)}; colours "
        f"{ {('%06x' % v): int(n) for v, n in Counter(out.ravel().tolist()).most_common(20)} }")
    return Image.fromarray(rgba, "RGBA"), out


def preview(paths, labels, dest, width=900):
    from PIL import ImageDraw
    ims = [Image.open(p).convert("RGB") for p in paths]
    h = int(width * ims[0].height / ims[0].width)
    canvas = Image.new("RGB", (width * len(ims), h + 20), "white"); d = ImageDraw.Draw(canvas)
    for i, (im, lb) in enumerate(zip(ims, labels)):
        canvas.paste(im.resize((width, h), Image.NEAREST), (i * width, 20)); d.text((i * width + 5, 4), lb, fill="black")
    canvas.save(dest)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("map_hex"); ap.add_argument("out")
    ap.add_argument("--ref", default=REF_190E); ap.add_argument("--raw")
    ap.add_argument("--no-areas", action="store_true"); ap.add_argument("--no-roads", action="store_true")
    ap.add_argument("--no-repair", action="store_true"); ap.add_argument("--reexport", action="store_true")
    ap.add_argument("--preview")
    a = ap.parse_args()
    raw = a.raw or str(Path(a.out).with_name(Path(a.out).stem + "_caime_raw.png"))
    if a.reexport and Path(raw).exists(): caime_export(a.map_hex, raw)
    im, out = build(a.map_hex, raw, a.ref, not a.no_areas, not a.no_roads, not a.no_repair)
    im.save(a.out); print("wrote", a.out, im.size)
    if a.preview:
        preview([a.ref, raw, a.out], ["reference (190E hand-made)", "CAIME baseline export", "tweaked (this)"], a.preview)
        print("wrote", a.preview)
