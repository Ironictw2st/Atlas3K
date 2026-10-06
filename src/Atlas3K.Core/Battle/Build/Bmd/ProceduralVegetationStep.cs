using System.Xml.Linq;
using Atlas3K.Formats.Battle;
using static Atlas3K.Core.Battle.Build.Bmd.BmdMake;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// BOB Vegetation "Procedural Generation" (bob_vegetation FUN_180007630), per climate of the tile's climate_mask in the
/// tile database's climate order: <see cref="ProceduralParameters"/> compiled for the climate
/// (<see cref="ProceduralTables"/>), <see cref="ProceduralGenerator"/> on the composited Height and Blend8 maps with the
/// project's vegetation_seed, then each instance inside the tile's inner box becomes
///  - tree (1): a &lt;climate&gt;.tree_list item, key BattleTerrain/vegetation/&lt;model&gt;.rigid_model_v2 (skipped when the model
///    is not in the VFS), y 0, the instance scale, yaw byte
///  - prop (2) / decal (4): a PROP of &lt;climate&gt;_procedural_bmd_data, key RigidModels/[Decals/]&lt;model&gt;.rigid_model_v2,
///    transform = base scale · instance scale, rotated about the terrain normal (or up, keep_upright) by the yaw
///  - vfx (8): a PARTICLE_EMITTER (key = instance name = model, emission rate 1, clamped to the surface)
/// plus the layers' hand-placed ECVegetation trees in every climate's tree list (FUN_1800095e0). A tree list is
/// written only when it has trees; the procedural bmd always. Prefab (0x10) and building (0x20) objects are not
/// written yet (no vanilla tree_parameters file uses them on the corpus climates).
/// </summary>
[BattleStepOrder(321)]
public sealed class ProceduralVegetationStep : IBattleBuildStep
{
    public string Name => "procedural_vegetation";

    public const string SettingsPath = "terrain/tiles/battle/_tile_database/_settings.bin";
    public const float UnitScale = 2f;

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var project = Meshes.TerryTileProject.Load(ctx.TerryFile);
        var terry = XDocument.Load(ctx.TerryFile);
        var inner = terry.Descendants("pc").First(e => (string?)e.Attribute("type") == "QTU::ProjectTileWithVista").Element("data")!.Element("data")!;
        var textures = Enumerable.Range(0, 8).Select(i => (string?)inner.Attribute($"texture_channel_{i}") ?? "").ToList();
        var seed = uint.Parse((string?)inner.Element("procedural")?.Attribute("vegetation_seed") ?? "0");
        var climates = OrderedClimates(ctx, TileProject.Climates(ctx));
        var (hw, hh, height, blend) = Maps(ctx, project);
        var parameters = ProceduralParameters.Load(ctx);
        foreach (var e in parameters.Errors) log($"{Name}: {e}");
        var handPlaced = HandPlacedTrees(ctx);
        foreach (var climate in climates)
        {
            if (!parameters.MaxTreesPerSquareMetre.ContainsKey(climate))
            {
                log($"{Name}: no density for climate {climate}, skipped");
                continue;
            }
            var tables = ProceduralTables.Compile(parameters, climate, textures, project.TilesWide, project.TilesHigh,
                project.TriangleDensity, UnitScale);
            var passes = new ProceduralGenerator(tables, height, blend, hw, hh, seed).Run();
            var total = passes.Sum(p => p.Count);
            if (total >= project.TilesWide * project.TilesHigh * 1000 * 0.25f)
                log($"{Name}: {total} procedural instances on climate '{climate}' (BOB warns from 25% of its soft limit, " +
                    $"{project.TilesWide * project.TilesHigh * 250}; its hard limit, where it writes nothing, is not ported)");

            var trees = new List<BattleTreeItem>();
            var keys = new List<string>();
            var props = new List<(string Key, BmdNode Prop)>();
            var emitters = new List<BmdNode>();
            int valid = 0, invalid = 0, skipped = 0;
            foreach (var pass in passes)
                foreach (var inst in pass)
                {
                    var o = tables.ObjectList[inst.Object];
                    if (o.Model.Length == 0) continue;
                    if (!(0f <= inst.X && 0f <= inst.Z && inst.X < tables.Width && inst.Z < tables.Height)) { invalid++; continue; }
                    valid++;
                    var model = o.Model.Replace('\\', '/');
                    switch (o.Type)
                    {
                        case 1:
                            var key = "BattleTerrain/vegetation/" + model + ".rigid_model_v2";
                            if (!ModelExists(ctx, key)) { log($"{Name}: could not find model for '{key}'"); continue; }
                            trees.Add(new BattleTreeItem(key, inst.X, 0f, inst.Z, inst.Scale, BattleTreeList.RotationByte(inst.Rotation), false));
                            break;
                        case 2:
                        case 4:
                            var pkey = (o.Type == 2 ? "RigidModels/" : "RigidModels/Decals/") + model + ".rigid_model_v2";
                            if (!keys.Contains(pkey)) keys.Add(pkey);
                            props.Add((pkey, Prop(o, inst, PropTransform(o, inst, height, hw, hh, tables))));
                            break;
                        case 8:
                            emitters.Add(Emitter(o, inst));
                            break;
                        default:
                            skipped++;
                            break;
                    }
                }
            if (skipped > 0) log($"{Name}: {skipped} prefab/building instances on {climate} not written (not ported)");
            log($"{Name}: {climate}: {valid} valid positions, {invalid} invalid positions generated");

            var root = BattleBmdBuilder.Empty(null);
            keys.Sort(string.CompareOrdinal);
            var propList = BattleBmdBuilder.List(root, "PROP_LIST");
            propList.Child("KEYS").Children.AddRange(keys.Select(k => Node("KEY", "", k)));
            foreach (var (k, p) in props.Select((p, i) => (p, i)).OrderBy(t => keys.IndexOf(t.p.Key)).ThenBy(t => t.i).Select(t => t.p))
            {
                p.Set("key_index", keys.IndexOf(k));
                propList.Child("PROPS").Children.Add(p);
            }
            BattleBmdBuilder.List(root, "PARTICLE_EMITTER_LIST", "PARTICLE_EMITTERS").Children.AddRange(emitters);
            TileProject.WriteBmd(Path.Combine(ctx.OutTileDir, $"{climate}_procedural_bmd_data.bin"), root);

            trees.AddRange(handPlaced);
            var treeFile = Path.Combine(ctx.OutTileDir, $"{climate}.tree_list.bin");
            if (trees.Count == 0)
            {
                File.Delete(treeFile);
                File.Delete(Path.ChangeExtension(treeFile, ".xml"));
                continue;
            }
            var list = BattleTreeList.Arrange(trees);
            File.WriteAllBytes(treeFile, BattleTreeList.Write(list));
            File.WriteAllText(Path.ChangeExtension(treeFile, ".xml"), BattleTreeList.ToXml(list));
            log($"{Name}: {climate}: {trees.Count} trees ({list.Count} models), {props.Count} props, {emitters.Count} vfx");
        }
    }

    /// <summary>The climates of the mask in the tile database's climate order (BOB's action loops over that list).</summary>
    public static List<string> OrderedClimates(BattleBuildContext ctx, IReadOnlyList<string> mask)
    {
        var settings = ctx.ReadVfs(SettingsPath);
        var order = settings is null ? [] : BattleTileDatabase.ReadClimates(settings).Select(c => c.Name).ToList();
        if (order.Count == 0) order = ["arid", "arid_fertile", "cold", "subtropical", "temperate", "tropical"];
        return order.Where(mask.Contains).Concat(mask.Where(c => !order.Contains(c))).Distinct().ToList();
    }

    /// <summary>The composited Height (the base layer TIF) and Blend8 maps: channels 1..7 = byte · (1/255); channel 0 =
    /// its own weight plus the remainder 1 − Σ (all eight, summed in float in channel order). A missing map is all zero.</summary>
    public static (int W, int H, float[] Height, float[] Blend) Maps(BattleBuildContext ctx, Meshes.TerryTileProject project)
    {
        var size = project.TilesWide * project.TriangleDensity + 2 * project.TriangleDensity;
        int w = size, h = size;
        float[] height;
        if (project.HeightTif is not null)
        {
            var (tw, th, v) = Meshes.TerryTileProject.ReadFloatTif(project.HeightTif);
            (w, h, height) = (tw, th, v);
        }
        else height = new float[w * h];
        var blend = new float[w * h * 8];
        var b = TileBlend.Read(ctx.SourceTileDir);
        const float k = 1f / 255f;
        for (var p = 0; p < w * h; p++)
        {
            var acc = 0f;
            for (var c = 0; c < 8; c++)
            {
                var v = b is { } bb && p * 8 + c < bb.Data.Length ? bb.Data[p * 8 + c] * k : 0f;
                blend[p * 8 + c] = v;
                acc += v;
            }
            blend[p * 8] = blend[p * 8] + (1f - acc);
        }
        return (w, h, height, blend);
    }

    private static bool ModelExists(BattleBuildContext ctx, string path) =>
        File.Exists(Path.Combine(ctx.WorkingData, path)) || ctx.Packs.FindOwner(path) is not null;

    // ---- the hand-placed trees (FUN_1800095e0) ----

    private static List<BattleTreeItem> HandPlacedTrees(BattleBuildContext ctx)
    {
        var items = new List<BattleTreeItem>();
        foreach (var e in TileScene.Load(ctx.TerryFile).Exported)
        {
            if ((string?)e.C("ECVegetation")?.Attribute("key") is not { Length: > 0 } model) continue;
            var t = e.C("ECTransform");
            var pos = Floats((string?)t?.Attribute("position") ?? "0 0 0");
            var rot = Floats((string?)t?.Attribute("rotation") ?? "0 0 0");
            var scale = Floats((string?)t?.Attribute("scale") ?? "1 1 1");
            var yaw = rot[1] * 3.14159274f * 0.00555555569f;
            items.Add(new BattleTreeItem("BattleTerrain/vegetation/" + model.Replace('\\', '/') + ".rigid_model_v2",
                pos[0], pos[1], pos[2], scale[0], BattleTreeList.RotationByte(yaw), false));
        }
        return items;
    }

    private static float[] Floats(string s) =>
        s.Split(' ', StringSplitOptions.RemoveEmptyEntries).Select(v => float.Parse(v, System.Globalization.CultureInfo.InvariantCulture)).ToArray();

    // ---- records ----

    private static BmdNode Emitter(VegetationObject o, ProceduralInstance inst)
    {
        var s = inst.Scale;
        return Node("PARTICLE_EMITTER", "", 6, o.Model,
            Node("transform", "PARTICLE_EMITTER", s, 0f, 0f, 0f, s, 0f, 0f, 0f, s, inst.X, 0f, inst.Z),
            1f, o.Model, Flags(false, true, false, 0, true), "BHM_TERRAIN", -1, MetaTags(), Parent());
    }

    private static BmdNode Prop(VegetationObject o, ProceduralInstance inst, float[] m)
    {
        var decal = o.Type == 4;
        return Node("PROP", "", 20, 0, MetaTags(),
            Node("transform", "PROP", m[0], m[4], m[8], m[1], m[5], m[9], m[2], m[6], m[10], m[3], m[7], m[11]),
            decal, false, false, true, true, true, true, false,
            decal ? o.Parallax : 0f, 0f, decal && !o.DecalBlendNormals,
            Flags(o.IncludeInOutfield, true, false, 0, true),
            false, decal && o.DecalApplyToTerrain, decal && o.DecalApplyToObjects, decal && o.DecalRenderAboveSnow,
            "BHM_TERRAIN", -1, true, false, Rgba("tint", 255, 255, 255, 255), Rgba("faction_colour", 255, 255, 255, 255),
            (byte)255, Parent(), false, false, false);
    }

    /// <summary>
    /// bob_vegetation FUN_18000a390: the scale diag(base · s) rotated by the quaternion of FUN_180036990 (the yaw about
    /// the up vector: the terrain normal of the Height map, FUN_180034240's Sobel at pixel (int)(x/2) + density, or
    /// (0, 1, 0) for keep_upright), then the position (x, 0, z). Returns the 3x4 as BOB keeps it: p[c·4 + r] = m{r}{c}
    /// (rows 0-2 rotation-scale, row 3 translation).
    /// </summary>
    public static float[] PropTransform(VegetationObject o, ProceduralInstance inst, float[] height, int w, int h, ProceduralTables t)
    {
        var s = inst.Scale;
        var p = new float[12];
        p[0] = s * o.BaseScale.X;
        p[5] = s * o.BaseScale.Y;
        p[10] = o.BaseScale.Z * s;
        float ux = 0f, uy = 1f, uz = 0f;
        if (!o.KeepUpright)
        {
            var ix = (int)(1f / t.Pixel * inst.X) + (int)t.OffsetX;
            var iz = (int)(1f / t.Pixel * inst.Z) + (int)t.OffsetY;
            var (n0, n1, n2) = SobelNormal(height, w, h, ix, iz, t.InvUnitScale);
            (ux, uy, uz) = (n0, n2, n1);
        }
        var (q0, q1, q2, q3) = Quaternion(ux, uy, uz, inst.Rotation);
        var w2 = q3 * 2f;
        var x2 = q0 * 2f;
        var f23 = q1 * 2f * q2;
        var f19 = q2 * 2f * q2;
        var f15 = w2 * q2 + x2 * q1;
        var f20 = q1 * 2f * q1;
        var f24 = x2 * q1 - w2 * q2;
        var f16 = x2 * q2 - w2 * q1;
        var f21 = w2 * q1 + x2 * q2;
        var f25 = 1f - x2 * q0;
        var f22 = (1f - f20) - f19;
        var f17 = w2 * q0 + f23;
        f23 = f23 - w2 * q0;
        f20 = f25 - f20;
        f25 = f25 - f19;
        float a0 = p[0], a1 = p[1], a2 = p[2], a3 = p[3], a4 = p[4], a5 = p[5], a6 = p[6], a7 = p[7], a8 = p[8], a9 = p[9], a10 = p[10], a11 = p[11];
        p[0] = a4 * f24 + a0 * f22 + a8 * f21;
        p[1] = a5 * f24 + a1 * f22 + a9 * f21;
        p[2] = a6 * f24 + a2 * f22 + a10 * f21;
        p[3] = f24 * a7 + f22 * a3 + f21 * a11;
        p[4] = a0 * f15 + a4 * f25 + a8 * f23;
        p[5] = a1 * f15 + a5 * f25 + a9 * f23;
        p[6] = a2 * f15 + a6 * f25 + f23 * a10;
        p[7] = f15 * a3 + a7 * f25 + f23 * a11;
        p[8] = a4 * f17 + a0 * f16 + a8 * f20;
        p[9] = a5 * f17 + a1 * f16 + a9 * f20;
        p[10] = f16 * a2 + f17 * a6 + a10 * f20;
        p[11] = f17 * a7 + f16 * a3 + a11 * f20;
        p[3] += inst.X;
        p[7] = 0f + p[7];
        p[11] = inst.Z + p[11];
        return p;
    }

    /// <summary>FUN_180036990: the up vector normalised, the rotation taking +Y to it, times the yaw about it (half angle
    /// through BOB's sincos).</summary>
    public static (float, float, float, float) Quaternion(float x, float y, float z, float yaw)
    {
        var f6 = 1f / MathF.Sqrt(y * y + x * x + z * z);
        var fy = f6 * y;
        var fz = f6 * z;
        var fx = f6 * x;
        var f5 = -fx;
        var f3 = MathF.Sqrt(fx * fx + fy * fy + fz * fz) + fy;
        var f4 = 1f / MathF.Sqrt(f5 * f5 + fz * fz + f3 * f3);
        var (sin, cos) = Campaign.Props.QtuTransform.SinCos(yaw * 0.5f);
        return (cos * fz * f4 - sin * f5 * f4, sin * f3 * f4, cos * f5 * f4 + sin * fz * f4, cos * f3 * f4);
    }

    /// <summary>FUN_180034240: the Sobel normal (gB, gA, 1)/|..| of height · scale at a pixel (edges clamped).</summary>
    public static (float, float, float) SobelNormal(float[] height, int w, int h, int x, int y, float scale)
    {
        float[] k = [1, 0, -1, 2, 0, -2, 1, 0, -1];
        float At(int px, int py)
        {
            px = px < 0 ? 0 : px > w - 1 ? w - 1 : px;
            py = py < 0 ? 0 : py > h - 1 ? h - 1 : py;
            return height[py * w + px];
        }
        float ga = 0f, gb = 0f;
        for (var j = 0; j < 3; j++)
            for (var i = 0; i < 3; i++)
            {
                var v = scale * At(x - 1 + i, y - 1 + j);
                ga += v * k[3 * i + j];
                gb += v * k[3 * j + i];
            }
        ga /= 8f;
        gb /= 8f;
        const float f4 = 1f;
        var inv = 1f / MathF.Sqrt(gb * gb + ga * ga + f4 * f4);
        return (gb * inv, inv * ga, f4 * inv);
    }
}
