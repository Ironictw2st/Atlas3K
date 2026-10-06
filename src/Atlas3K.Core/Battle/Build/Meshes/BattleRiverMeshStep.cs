using System.Xml.Linq;
using Atlas3K.Core.Campaign.Rivers;
using Atlas3K.Formats.Models;

namespace Atlas3K.Core.Battle.Build.Meshes;

/// <summary>
/// river_mesh.wsmodel(.rigid_model_v2) and outfield_river_mesh.wsmodel(.rigid_model_v2) of a battle tile
/// ("Process Terry tile (heightmap)": FUN_1800edbf0 → FUN_1800d98c0 → FUN_1800d99e0 per river → MODEL_PROCESSOR
/// open_river_spline + write). The river geometry is the campaign one (<see cref="BobRiver"/>: FUN_18015e9e0, the
/// FUN_180146460 snap pass, VERTEX_LIST_CLEANER, MESH_SPLITTER), from the ECRiverSpline entities of the tile's layers,
/// in the layer's own (scene) coordinates; the world uv spans the tile: width · unit_scale · terrain tile size.
/// A tile without rivers gets an RMV2 without LODs and a wsmodel with an empty materials list.
/// </summary>
[BattleStepOrder(210)]
public sealed class BattleRiverMeshStep : IBattleBuildStep
{
    public string Name => "river_meshes";

    /// <summary>Battle tile database render_params.unit_scale (vanilla _settings.bin); the world uv spans tiles × unit_scale ×
    /// m_terrain_tile_size (128).</summary>
    public const float UnitScale = 2f;
    public const float TileWorldSize = UnitScale * 128f;

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var terry = ctx.TerryFile;
        var project = TerryTileProject.Load(terry);
        var rivers = LayerFiles(terry).SelectMany(RiverBuilder.ReadLayer).ToList();
        var riverMaterial = (string?)XDocument.Load(terry).Descendants("data").Attributes("river_material").FirstOrDefault() ?? "";
        Directory.CreateDirectory(ctx.OutTileDir);
        var geometryDir = $"terrain/tiles/battle/_assembly_kit/{Path.GetFileName(ctx.OutTileDir)}";
        var bounds = (0f, 0f, project.TilesWide * TileWorldSize, project.TilesHigh * TileWorldSize);
        foreach (var stem in new[] { "outfield_river_mesh", "river_mesh" })
        {
            byte[] model;
            var materials = new List<string>();
            if (rivers.Count == 0) model = BattleTileMeshStep.EmptyModel();
            else
            {
                RigidModelV2? first = null;
                foreach (var river in rivers)
                {
                    var raw = BobRiver.BuildRaw(BobRiver.BuildSpline(river),
                        BobRiver.RiverPointsInOrder(river).Select(p => (float)p.Width).ToList(), bounds);
                    var part = BobRiver.ToModel(raw, UnitScale);
                    if (first is null) first = part;
                    else first.MoreMeshes.Add(part);
                    materials.Add(river.Material.Length > 0 ? river.Material : riverMaterial);
                }
                model = first!.ToBytes();
            }
            File.WriteAllBytes(Path.Combine(ctx.OutTileDir, stem + ".wsmodel.rigid_model_v2"), model);
            File.WriteAllText(Path.Combine(ctx.OutTileDir, stem + ".wsmodel"), WsModelXml($"{geometryDir}/{stem}.wsmodel.rigid_model_v2", materials));
            log($"{stem}: {rivers.Count} river(s)");
        }
    }

    /// <summary>BOB's wsmodel (LF, no final newline); "&lt;materials/&gt;" when there is no part.</summary>
    public static string WsModelXml(string geometry, IReadOnlyList<string> materials)
    {
        var s = "<model version=\"1\">\n" + $"  <geometry>{geometry}</geometry>\n";
        if (materials.Count == 0) s += "  <materials/>\n";
        else
        {
            s += "  <materials>\n";
            for (var i = 0; i < materials.Count; i++)
                s += $"    <material lod_index=\"0\" part_index=\"{i}\">{materials[i]}</material>\n";
            s += "  </materials>\n";
        }
        return s + "</model>";
    }

    /// <summary>The project's layer files: every ECLayerFile entity of the .terry scene (and of the layers, recursively)
    /// is saved as &lt;project&gt;.&lt;entity id&gt;.layer next to the .terry.</summary>
    public static List<string> LayerFiles(string terryPath)
    {
        var dir = Path.GetDirectoryName(terryPath)!;
        var stem = Path.GetFileNameWithoutExtension(terryPath);
        var result = new List<string>();
        void Visit(XDocument doc)
        {
            foreach (var e in doc.Descendants("entity").Where(e => e.Element("ECLayerFile") is not null))
            {
                var path = Path.Combine(dir, $"{stem}.{(string?)e.Attribute("id")}.layer");
                if (!File.Exists(path) || result.Contains(path)) continue;
                result.Add(path);
                Visit(XDocument.Load(path));
            }
        }
        Visit(XDocument.Load(terryPath));
        return result;
    }
}
