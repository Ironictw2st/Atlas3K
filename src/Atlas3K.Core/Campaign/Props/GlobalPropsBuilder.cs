using System.Collections.Concurrent;
using System.Globalization;
using System.Xml.Linq;
using Atlas3K.Formats.Models;
using Atlas3K.Formats.Packs;
using Atlas3K.Formats.Props;
using Atlas3K.Formats.Terry;

namespace Atlas3K.Core.Campaign.Props;

/// <summary>
/// Native global_props.bin from the AK layers (BOB "Terry file"), game-valid. Layout recovered from vanilla 3k_dlc07:
///  - each object's region is the map.hex region under its entity position (HexRegionLookup, as BOB), or its
///    layer's region when there is no map.hex; each object goes to the deepest quadtree cell that holds its bounds
///    (7 levels, each a row-major 2^L x 2^L grid over the world, row 0 = north; cell id = cells of shallower levels
///    + row·2^L + col) and to a season bucket 16 + bits (spring 1, summer 2, autumn 4, winter 8; no season mask = 31)
///  - bucket bodies bmd_objects.&lt;region&gt;.&lt;cell&gt;.&lt;bucket&gt;.bin hold the objects; cell bodies
///    bmd_objects.&lt;region&gt;.&lt;cell&gt;.bin reference their buckets (campaign mask 1); the root bmd_objects.bin
///    references every cell body with its region key
///  - records are built from vanilla's most common record of each type (from the game packs), with the fields the
///    layers define replaced: paths, transforms, tags, seasons, snow/destruction/shroud visibility, decal flags,
///    shadows, height patches, light and sound parameters
/// </summary>
public sealed class GlobalPropsBuilder
{
    public const string VanillaGlobalProps = "terrain/campaigns/3k_dlc07_main_map/global_props.bin";

    /// <param name="EntityX">The entity's ECTransform position, which BOB's region lookup uses (differs from X/Z for
    /// river models, placed at the origin, and polygon meshes).</param>
    private sealed record Obj(string Kind, double X, double Z, double Radius, string SeasonMask, Func<BmdBody, byte[]> Build, string? PropPath,
                              double? EntityX = null, double? EntityZ = null, int? Bucket = null);

    private readonly Templates _t;
    private readonly PackSet _packs;
    private readonly double _worldW, _worldH;
    public List<string> Notes { get; } = [];

    /// <summary>Campaign prefab library: Prefab instances in the layers are flattened into their entities (the game
    /// has no campaign prefab .bmd files for them to reference). Null = instances are skipped with a note.</summary>
    public PrefabLibrary? Prefabs { get; init; }

    public GlobalPropsBuilder(PackSet packs, double worldWidth, double worldHeight)
    {
        _packs = packs;
        _worldW = worldWidth;
        _worldH = worldHeight;
        var vanilla = packs.TryRead(VanillaGlobalProps) ?? throw new FileNotFoundException("Vanilla global_props.bin not found in the game packs (templates).");
        _t = Templates.From(GlobalProps.Read(vanilla));
    }

    /// <summary>(entry name, body) pairs in vanilla order: each cell's buckets, the cell, and the root last.</summary>
    /// <param name="regionAt">BOB's region for an entity position (HexRegionLookup); when it returns null, or is not given,
    /// the layer's region is used.</param>
    public List<(string Name, byte[] Body)> Build(string mapName, IEnumerable<(string Region, string LayerPath)> layers,
                                                  Func<double, double, string?>? regionAt = null)
    {
        var prefix = $"terrain/campaigns/{mapName}/bmd_objects";
        var entries = new List<(string, byte[])>();
        var root = BmdBody.EmptyLike(_t.Framing);
        // several layers can end up in one region (e.g. every layer the map has no region for)
        var byRegion = new List<(string Region, List<Obj> Objects)>();
        foreach (var (region, layerPath) in layers)
        {
            var objects = ReadLayer(mapName, layerPath);
            foreach (var group in objects.GroupBy(o => regionAt?.Invoke(o.EntityX ?? o.X, o.EntityZ ?? o.Z) ?? region))
            {
                var existing = byRegion.FindIndex(r => r.Region == group.Key);
                if (existing >= 0) byRegion[existing].Objects.AddRange(group);
                else byRegion.Add((group.Key, group.ToList()));
            }
        }
        foreach (var (region, objects) in byRegion)
        {
            foreach (var cell in objects.GroupBy(o => Cell(o.X, o.Z, o.Radius)).OrderBy(g => g.Key))
            {
                var cellBody = BmdBody.EmptyLike(_t.Framing);
                foreach (var bucket in cell.GroupBy(o => o.Bucket ?? Bucket(o.SeasonMask)).OrderBy(g => g.Key))
                {
                    var body = BmdBody.EmptyLike(_t.Framing);
                    foreach (var o in bucket) Add(body, o);
                    var name = $"{prefix}.{region}.{cell.Key}.{bucket.Key}.bin";
                    entries.Add((name, body.ToBytes()));
                    cellBody.Nested.Add(BmdRecords.Nested(_t.Nested, name, 0, region));   // vanilla and BOB: 0 for every bucket
                }
                var cellName = $"{prefix}.{region}.{cell.Key}.bin";
                entries.Add((cellName, cellBody.ToBytes()));
                root.Nested.Add(BmdRecords.Nested(_t.RootNested, cellName, 0, region));
            }
        }
        entries.Add(($"{prefix}.bin", root.ToBytes()));
        return entries;
    }

    private void Add(BmdBody body, Obj o)
    {
        var record = o.Build(body);
        switch (o.Kind)
        {
            case "prop":
                var index = body.PropPaths.IndexOf(o.PropPath!);
                if (index < 0) { index = body.PropPaths.Count; body.PropPaths.Add(o.PropPath!); }
                BitConverter.TryWriteBytes(record.AsSpan(BmdRecords.PropPathIndex), (uint)index);
                body.Props.Add(record);
                break;
            case "vfx": body.Vfx.Add(record); break;
            case "light": body.PointLights.Add(record); break;
            case "scene": body.CompositeScenes.Add(record); break;
            case "sound": body.Sounds.Add(record); break;
            case "probe": body.LightProbes.Add(record); break;
            case "poly": body.PolyMeshes.Add(record); break;
        }
    }

    /// <summary>Deepest quadtree cell whose rectangle contains the object's circle.</summary>
    public int Cell(double x, double z, double radius)
    {
        for (var level = 6; level >= 1; level--)
        {
            var n = 1 << level;
            double cw = _worldW / n, ch = _worldH / n;
            int c0 = (int)Math.Floor((x - radius) / cw), c1 = (int)Math.Floor((x + radius) / cw);
            int r0 = (int)Math.Floor((_worldH - (z + radius)) / ch), r1 = (int)Math.Floor((_worldH - (z - radius)) / ch);
            if (c0 != c1 || r0 != r1 || c0 < 0 || r0 < 0 || c0 >= n || r0 >= n) continue;
            var first = 0;
            for (var l = 0; l < level; l++) first += 1 << (2 * l);
            return first + r0 * n + c0;
        }
        return 0;
    }

    /// <summary>Season bucket: 16 + spring 1 + summer 2 + autumn 4 + winter 8; no season mask = 31.</summary>
    public static int Bucket(string seasonMask)
    {
        var names = seasonMask.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (names.Length == 0) return 31;
        var bits = 0;
        foreach (var n in names)
            bits |= n switch { "season_spring" => 1, "season_summer" => 2, "season_autumn" => 4, "season_winter" => 8, _ => 0 };
        return 16 + bits;
    }

    private List<Obj> ReadLayer(string mapName, string path)
    {
        var doc = XDocument.Load(path);
        var root = doc.Root!;
        var entities = root.Element("entities")?.Elements("entity").ToList() ?? [];
        // tags: tag-layer entities (ECLayerExportTags) own their members through the Logical association; a tag layer
        // can itself sit inside another tag layer, whose tags then apply too
        var TagsFor = LayerDocument.TagResolver(root);

        // Prefab instances become the entities they stand for, with the instance's tags added to their own.
        var flat = new List<(XElement Entity, string Tags)>();
        foreach (var e in entities)
        {
            if (e.Element("ECLayer") is not null) continue;
            var tagsOf = TagsFor((string?)e.Attribute("id") ?? "");
            if (PrefabExpander.KeyOf(e) is not { } key) { flat.Add((e, tagsOf)); continue; }
            if (Prefabs is null) { Notes.Add($"prefab instance '{key}' in {Path.GetFileName(path)} skipped (no prefab library)"); continue; }
            var missing = new List<string>();
            var expanded = PrefabExpander.Expand(e, Prefabs, recursive: true, missing);
            foreach (var m in missing.Distinct()) Notes.Add($"prefab '{m}' (in {Path.GetFileName(path)}) not found in {Prefabs.Root}; skipped");
            flat.AddRange(expanded.Select(x => (x.Entity, PrefabExpander.Union(tagsOf, x.Tags))));
        }

        var objects = new List<Obj>();
        foreach (var (e, tags) in flat)
        {
            var tr = Transform(e.Element("ECTransform"));
            var cp = e.Element("ECCampaignProperties");
            var seasons = (string?)cp?.Attribute("season_mask") ?? "";
            bool Cp(string name, bool def) => cp?.Attribute(name) is { } a ? (string)a == "true" : def;

            if (e.Element("ECRiver") is not null)
            {
                var name = (string?)e.Attribute("name") ?? "river_0";
                var number = int.TryParse(name.Split('_').Last(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var n) ? n : 0;
                var riverPath = $"terrain/campaigns/{mapName}/models/river_{number}.wsmodel";
                // vanilla and BOB: river flag set, cast shadow on, season bucket 16
                var river = PropObj(riverPath, (0, 0, 0), Identity, 1e9, tags, seasons, decal: false, applyToTerrain: true,
                    applyToObjects: false, Cp, castShadow: true, hasHp: false, applyHp: false);
                objects.Add(river with
                {
                    Build = b => { var rec = river.Build(b); rec[BmdRecords.PropRiver] = 1; return rec; },
                    EntityX = tr.Position.X, EntityZ = tr.Position.Z, Bucket = 16,
                });
                continue;
            }
            if (e.Element("ECPropMesh") is not null || e.Element("ECDecal") is not null)
            {
                var decal = e.Element("ECDecal");
                var model = (string?)(decal ?? e.Element("ECMesh"))?.Attribute("model_path") ?? "";
                if (model.Length == 0) continue;
                var rs = e.Element("ECMeshRenderSettings");
                var hp = e.Element("ECPropHeightPatch");
                // cell by position only: BOB's main190 cells match a radius-0 point for 92% of objects; the model radius
                // put mountain props in much coarser cells than BOB's, and the game didn't draw them (checked in game)
                objects.Add(PropObj(model, tr.Position, tr.Matrix, 0, tags, seasons, decal is not null,
                    (string?)decal?.Attribute("apply_to_terrain") != "false", (string?)decal?.Attribute("apply_to_objects") == "true", Cp,
                    (string?)rs?.Attribute("cast_shadow") != "false", (string?)hp?.Attribute("has_height_patch") == "true",
                    (string?)hp?.Attribute("apply_height_patch") == "true"));
                continue;
            }
            if (e.Element("ECVFX") is { } vfx)
            {
                var name = (string?)vfx.Attribute("vfx") ?? "";
                var instance = (string?)vfx.Attribute("instance_name") ?? "";
                objects.Add(new Obj("vfx", tr.Position.X, tr.Position.Z, 0, seasons, b =>
                {
                    var (f, m) = b.EncodeTags(tags);
                    return BmdRecords.Vfx(_t.Vfx, name, tr.Matrix, tr.Position, instance, b.EncodeSeasons(seasons), f, m);
                }, null));
                continue;
            }
            if (e.Element("ECPointLight") is { } light)
            {
                var c = Floats((string?)light.Attribute("colour") ?? "255 255 255 255");
                var speed = Floats((string?)light.Attribute("animation_speed_scale") ?? "0 0");
                var anim = (string?)light.Attribute("animation_type") switch { "LAT_RADIUS_SIN" => (byte)1, "LAT_RADIUS_SIN_SIN" => (byte)2, _ => (byte)0 };
                float A(string n, float d) => light.Attribute(n) is { } a ? float.Parse((string)a, CultureInfo.InvariantCulture) : d;
                var falloff = (string?)light.Attribute("falloff_type") ?? "";
                var probesOnly = (string?)light.Attribute("for_light_probes_only") == "true";
                objects.Add(new Obj("light", tr.Position.X, tr.Position.Z, 0, seasons, b =>
                {
                    var (f, m) = b.EncodeTags(tags);
                    return BmdRecords.PointLight(_t.Light, tr.Position, A("radius", 1), (c[0] / 255f, c[1] / 255f, c[2] / 255f),
                        A("colour_scale", 1), anim, speed.ElementAtOrDefault(0), speed.ElementAtOrDefault(1), A("colour_min", 0),
                        A("random_offset", 0), falloff, probesOnly, f, m, b.EncodeSeasons(seasons));
                }, null));
                continue;
            }
            if (e.Element("ECCompositeScene") is { } scene)
            {
                var path2 = (string?)scene.Attribute("path") ?? "";
                objects.Add(new Obj("scene", tr.Position.X, tr.Position.Z, 0, seasons, b =>
                {
                    var (f, m) = b.EncodeTags(tags);
                    return BmdRecords.CompositeScene(_t.Scene, tr.Matrix, tr.Position, path2, f, m, b.EncodeSeasons(seasons));
                }, null));
                continue;
            }
            if (e.Element("ECSoundMarker") is { } sound)
            {
                var key = (string?)sound.Attribute("key") ?? "";
                var cloud = e.Element("ECPointCloud");
                var sphere = e.Element("ECSphere");
                var pts = cloud is null ? [tr.Position]
                    : cloud.Descendants("point").Select(p => (tr.Position.X + A3(p, "x"), tr.Position.Y + A3(p, "y"), tr.Position.Z + A3(p, "z"))).ToList();
                // vanilla uses SST_POINT, SST_MULTI_POINT and SST_LINE_LIST (the last doesn't survive in Terry layers)
                var shape = cloud is not null ? "SST_MULTI_POINT" : "SST_POINT";
                float? radius = sphere is null ? null : float.Parse((string?)sphere.Attribute("radius") ?? "0", CultureInfo.InvariantCulture);
                var template = shape == "SST_MULTI_POINT" ? _t.SoundMulti : _t.SoundPoint;
                objects.Add(new Obj("sound", tr.Position.X, tr.Position.Z, 0, "", _ => BmdRecords.Sound(template, key, shape, pts, radius), null));
                continue;
            }
            if (e.Element("ECLightProbe") is not null)
            {
                var radius = float.Parse((string?)e.Element("ECSphere")?.Attribute("radius") ?? "1", CultureInfo.InvariantCulture);
                objects.Add(new Obj("probe", tr.Position.X, tr.Position.Z, 0, "", _ => BmdRecords.LightProbe(_t.Probe, tr.Position, radius), null));
                continue;
            }
            if (e.Element("ECPolygonMesh") is { } poly && _t.Poly is not null)
            {
                var material = (string?)poly.Attribute("material") ?? "";
                var outline = e.Descendants("point").Select(p => (A3(p, "x"), A3(p, "y"))).ToList();
                if (outline.Count < 3) continue;
                var vertices = outline.Select(p => (p.Item1, tr.Position.Y, p.Item2)).ToList();
                var indices = Triangulate(outline);
                objects.Add(new Obj("poly", vertices.Average(v => v.Item1), vertices.Average(v => v.Item3), 1e9, "",
                    _ => BmdRecords.PolyMesh(_t.Poly, vertices, indices, material), null, tr.Position.X, tr.Position.Z));
            }
        }
        return objects;

        Obj PropObj(string model, (double X, double Y, double Z) position, double[] matrix, double radius, string tags, string seasons,
            bool decal, bool applyToTerrain, bool applyToObjects, Func<string, bool, bool> cp, bool castShadow, bool hasHp, bool applyHp) =>
            new("prop", position.X, position.Z, radius, seasons, b =>
            {
                var (f, m) = b.EncodeTags(tags);
                var rec = BmdRecords.Prop(decal ? _t.Decal : _t.Prop, 0, f, m, matrix, position, decal,
                    cp("visible_inside_snow_region", true), cp("visible_outside_snow_region", true),
                    cp("visible_inside_destruction_region", true), cp("visible_outside_destruction_region", true),
                    b.EncodeSeasons(seasons), cp("visible_in_seen_shroud", true), cp("visible_in_unseen_shroud", false),
                    castShadow, hasHp, applyHp);
                if (decal)
                {
                    rec[BmdRecords.PropApplyToTerrain] = applyToTerrain ? (byte)0 : (byte)1;
                    rec[BmdRecords.PropApplyToObjects] = applyToObjects ? (byte)1 : (byte)0;
                }
                return rec;
            }, model);
    }

    private static readonly double[] Identity = [1, 0, 0, 0, 1, 0, 0, 0, 1];

    private static (double[] Matrix, (double X, double Y, double Z) Position, double MaxScale) Transform(XElement? t)
    {
        var p = Floats((string?)t?.Attribute("position") ?? "0 0 0");
        var r = Floats((string?)t?.Attribute("rotation") ?? "0 0 0");
        var s = Floats((string?)t?.Attribute("scale") ?? "1 1 1");
        var matrix = CameraHeightmapStep.Matrix(new PropTransform(p[0], p[1], p[2], r[0], r[1], r[2], s[0], s[1], s[2]));
        return (matrix, (p[0], p[1], p[2]), Math.Max(Math.Abs(s[0]), Math.Max(Math.Abs(s[1]), Math.Abs(s[2]))));
    }

    private static float[] Floats(string s) =>
        s.Split([' ', ','], StringSplitOptions.RemoveEmptyEntries).Select(v => float.Parse(v, CultureInfo.InvariantCulture)).ToArray();

    private static double A3(XElement p, string name) => double.Parse((string?)p.Attribute(name) ?? "0", CultureInfo.InvariantCulture);


    /// <summary>Ear-clipping triangulation of a simple polygon (x, z outline).</summary>
    private static List<ushort> Triangulate(List<(double X, double Z)> pts)
    {
        var idx = Enumerable.Range(0, pts.Count).ToList();
        double Area() { double a = 0; for (var i = 0; i < idx.Count; i++) { var p = pts[idx[i]]; var q = pts[idx[(i + 1) % idx.Count]]; a += p.X * q.Z - q.X * p.Z; } return a; }
        if (Area() < 0) idx.Reverse();
        var result = new List<ushort>();
        var guard = 0;
        while (idx.Count > 3 && guard++ < 10000)
        {
            for (var i = 0; i < idx.Count; i++)
            {
                int a = idx[(i + idx.Count - 1) % idx.Count], b = idx[i], c = idx[(i + 1) % idx.Count];
                var cross = (pts[b].X - pts[a].X) * (pts[c].Z - pts[a].Z) - (pts[b].Z - pts[a].Z) * (pts[c].X - pts[a].X);
                if (cross <= 0) continue;
                var inside = idx.Any(k => k != a && k != b && k != c && InTri(pts[k], pts[a], pts[b], pts[c]));
                if (inside) continue;
                result.AddRange([(ushort)a, (ushort)b, (ushort)c]);
                idx.RemoveAt(i);
                break;
            }
        }
        if (idx.Count == 3) result.AddRange([(ushort)idx[0], (ushort)idx[1], (ushort)idx[2]]);
        return result;

        static bool InTri((double X, double Z) p, (double X, double Z) a, (double X, double Z) b, (double X, double Z) c)
        {
            double d1 = (p.X - b.X) * (a.Z - b.Z) - (a.X - b.X) * (p.Z - b.Z);
            double d2 = (p.X - c.X) * (b.Z - c.Z) - (b.X - c.X) * (p.Z - c.Z);
            double d3 = (p.X - a.X) * (c.Z - a.Z) - (c.X - a.X) * (p.Z - a.Z);
            return !((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0));
        }
    }

    /// <summary>Most common vanilla record of each kind, plus a framing body whose preamble lists every enum type.</summary>
    private sealed record Templates(BmdBody Framing, byte[] Prop, byte[] Decal, byte[] Vfx, byte[] Light, byte[] Scene,
        byte[] SoundPoint, byte[] SoundMulti, byte[] Probe, byte[]? Poly, byte[] Nested, byte[] RootNested)
    {
        public static Templates From(GlobalProps vanilla)
        {
            var bodies = vanilla.Bodies().Select(b => (b.Name, Body: BmdBody.Parse(b.Body))).ToList();
            byte[] MostCommon(IEnumerable<byte[]> records, Func<byte[], string> shape) =>
                records.GroupBy(shape).OrderByDescending(g => g.Count()).First().First();
            var props = bodies.SelectMany(b => b.Body.Props).ToList();
            string PropShape(byte[] r) => Convert.ToHexString(r, 72, 33) + Convert.ToHexString(r, BmdRecords.PropHeadSize, r.Length - BmdRecords.PropHeadSize);
            var prop = MostCommon(props.Where(r => r[BmdRecords.PropDecal] == 0), PropShape);
            var decal = MostCommon(props.Where(r => r[BmdRecords.PropDecal] == 1), PropShape);
            byte[] First(Func<BmdBody, IEnumerable<byte[]>> pick, Func<byte[], bool>? where = null) =>
                bodies.SelectMany(b => pick(b.Body)).First(r => where?.Invoke(r) ?? true);
            bool HasShape(byte[] r, string shape) => System.Text.Encoding.UTF8.GetString(r).Contains(shape, StringComparison.Ordinal);

            // every enum type, values merged in first-seen order
            var types = new List<(string Name, List<string> Values)>();
            foreach (var (_, body) in bodies)
                foreach (var (name, first, count) in body.EnumTypes)
                {
                    var t = types.FirstOrDefault(x => x.Name == name);
                    if (t.Values is null) types.Add(t = (name, []));
                    foreach (var v in body.EnumValues.Skip(first).Take(count)) if (!t.Values.Contains(v)) t.Values.Add(v);
                }
            var framing = BmdBody.WithEnumTypes(bodies.First(b => b.Body.Props.Count > 0).Body,
                types.Select(t => (t.Name, (IReadOnlyList<string>)t.Values)).ToList());
            var root = bodies.Single(b => b.Name.EndsWith("/bmd_objects.bin", StringComparison.Ordinal)).Body;
            var cellNested = bodies.Where(b => !b.Name.EndsWith("/bmd_objects.bin", StringComparison.Ordinal)).SelectMany(b => b.Body.Nested).First();
            return new Templates(framing, prop, decal, First(b => b.Vfx), First(b => b.PointLights), First(b => b.CompositeScenes),
                First(b => b.Sounds, r => HasShape(r, "SST_POINT") && !HasShape(r, "SST_MULTI_POINT")), First(b => b.Sounds, r => HasShape(r, "SST_MULTI_POINT")),
                First(b => b.LightProbes), bodies.SelectMany(b => b.Body.PolyMeshes).FirstOrDefault(), cellNested, root.Nested[0]);
        }
    }
}
