using System.Globalization;
using System.Xml.Linq;
using Atlas3K.Core.Campaign.Props;
using Atlas3K.Formats.Battle;
using static Atlas3K.Core.Battle.Build.Bmd.BmdMake;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// A battle tile's bmd files as BOB's TerryTile export writes them (bob_terrain "Process Terry tile"), from the tile
/// project's layers. Field rules recovered from the battle-parity corpus (BOB's own bmd_data.xml next to the sources):
///  - records of each kind in ascending entity id order; props grouped by model path (PROP_LIST keys sorted)
///  - transforms through QTU::ECTransform's float quaternion path (<see cref="QtuTransform"/>), no terrain clamping:
///    ECTerrainClamp active only switches height_mode to BHM_TERRAIN
///  - tags from tag layers (ECLayerExportTags) as meta_tags bits over the full META_TAG_KEYS catalog
///  - the "Reference" layer (ECLayerExport export="false") is not exported
/// </summary>
public sealed class BattleBmdBuilder(BmdMetaCatalog catalog)
{
    private readonly List<string> _seasons = [];
    public List<string> Notes { get; } = [];

    // ---- skeleton ----

    /// <summary>An empty BATTLE_MAP_DEFINITION_DATA; <paramref name="withCatalog"/> = META_TAG_KEYS filled (bmd_data),
    /// else empty with checksum 0 (procedural and nogo bmds).</summary>
    public static BmdNode Empty(BmdMetaCatalog? catalog, IReadOnlyList<string>? metaDataItems = null)
    {
        var entries = catalog?.Types.Select(t => Node("meta_data_entry", "", 1, t.Type, t.Values.Select(v => Node("value", "", v)).ToList())).ToList() ?? [];
        var hints = Node("AI_HINTS", "", 1,
            Node("separators", "AI_HINTS", 1, null), Node("directed_points", "AI_HINTS", 1, null),
            Node("polylines", "AI_HINTS", 1, null), Node("polylines_list", "AI_HINTS", 1, null));
        return Node(BattleBmd.RootTag, "", 35,
            Node("META_TAG_KEYS", "", 1, catalog?.Checksum ?? 0u, entries),
            Node("META_DATA_KEYS", "", 1, (metaDataItems ?? []).Select(s => Node("item", "", s)).ToList()),
            Node("PREMERGE_DATA", "", 1, false, 0UL),
            Node("BATTLEFIELD_BUILDING_LIST", "", 1, null), Node("BATTLEFIELD_BUILDING_LIST_FAR", "", 1, null),
            Node("CAPTURE_LOCATION_SET", "", 3, null), Node("EF_LINE_LIST", "", (object?)null), Node("GO_OUTLINES", "", (object?)null),
            Node("NON_TERRAIN_OUTLINES", "", (object?)null), Node("ZONES_TEMPLATE_LIST", "", 2, null),
            Node("PREFAB_INSTANCE_LIST", "", 1, null), Node("BMD_OUTLINE_LIST", "", 1, null), Node("TERRAIN_OUTLINES", "", (object?)null),
            Node("LITE_BUILDING_OUTLINES", "", (object?)null), Node("CAMERA_ZONES", "", 1, null), Node("CIVILIAN_DEPLOYMENT_LIST", "", (object?)null),
            Node("CIVILIAN_SHELTER_LIST", "", (object?)null), Node("PROP_LIST", "", 2, null, null), Node("PARTICLE_EMITTER_LIST", "", 1, null),
            hints, Node("LIGHT_PROBE_LIST", "", 1, null), Node("TERRAIN_STENCIL_TRIANGLE_LIST", "", 1, null), Node("POINT_LIGHT_LIST", "", 1, null),
            Node("BUILDING_PROJECTILE_EMITTER_LIST", "", 1, null),
            Node("PLAYABLE_AREA", "", 2, Node("area", "PLAYABLE_AREA", 64f, 64f, 1920f, 1920f), false, false, false, false, false),
            Node("CUSTOM_MATERIAL_MESH_LIST", "", 1, null), Node("TERRAIN_STENCIL_BLEND_TRIANGLE_LIST", "", 1, null),
            Node("SPOT_LIGHT_LIST", "", 1, null), Node("SOUND_SHAPE_LIST", "", 1, null), Node("COMPOSITE_SCENE_LIST", "", 1, null),
            Node("BUILDING_SLOT_LIST", "", 1, null), Node("DEPLOYMENT_LIST", "", 1, null), Node("BMD_CATCHMENT_AREA_LIST", "", 1, null),
            Node("LF_FLATTEN_TRIANGLE_LIST", "", 3, 1f, MetaTags(), null), Node("LF_FLATTEN_TRIANGLE_LIST_LIST", "", 1, null),
            Node("ENVIRONMENT_LIST", "", 1, null), Node("BMD_ROAD_SPLINE_LIST", "", 1, null), Node("LAYER_INSTANCE_LIST", "", 1, null),
            Node("TREE_LIST_REFERENCE_LIST", "", 1, null), Node("GRASS_LIST_REFERENCE_LIST", "", 1, null));
    }

    /// <summary>The list node of a section: root &gt; section &gt; container.</summary>
    public static BmdNode List(BmdNode root, string section, string? container = null)
    {
        var s = root.Child(section);
        return container is null ? s : s.Child(container);
    }

    // ---- bmd_data ----

    /// <param name="grassLists">Grass list files written for this tile (climate, pack path), in climate order.</param>
    /// <param name="treeLists">Tree list files written for this tile (climate, pack path).</param>
    public BmdNode BuildData(TileScene scene, IReadOnlyList<(string Climate, string Path)> grassLists,
                             IReadOnlyList<(string Climate, string Path)> treeLists)
    {
        var root = Empty(catalog);
        var exported = scene.Exported.ToList();

        var buildings = List(root, "BATTLEFIELD_BUILDING_LIST", "BUILDINGS");
        var prefabs = List(root, "PREFAB_INSTANCE_LIST", "PREFAB_INSTANCE");
        var propKeys = new SortedSet<string>(StringComparer.Ordinal);
        var props = new List<(string Key, SceneEntity E)>();
        var prefabIndex = new Dictionary<ulong, int>();

        foreach (var e in exported)
        {
            if (e.C("ECBuilding") is { } b && !e.Has("ECBuildingSlot")) buildings.Children.Add(Building(e, b));
            else if (e.C("ECPrefab") is { } pf)
            {
                prefabIndex[e.Id] = prefabs.Children.Count;
                prefabs.Children.Add(Prefab(e, pf));
            }
            else if (e.C("ECDecal") is { } dc && Str(dc, "model_path") is { Length: > 0 } dm) { propKeys.Add(dm); props.Add((dm, e)); }
            else if (e.Has("ECPropMesh") && Str(e.C("ECMesh"), "model_path") is { Length: > 0 } pm) { propKeys.Add(pm); props.Add((pm, e)); }
        }

        // props: the key table sorted, records grouped by key, each group by entity id
        var keys = propKeys.ToList();
        var propList = List(root, "PROP_LIST");
        propList.Child("KEYS").Children.AddRange(keys.Select(k => Node("KEY", "", k)));
        foreach (var (key, e) in props.OrderBy(p => keys.IndexOf(p.Key)).ThenBy(p => p.E.Id))
            propList.Child("PROPS").Children.Add(Prop(e, keys.IndexOf(key)));

        foreach (var e in exported)
        {
            if (e.C("ECVFX") is { } vfx) List(root, "PARTICLE_EMITTER_LIST", "PARTICLE_EMITTERS").Children.Add(Vfx(e, vfx));
            if (e.C("ECAIHint") is { } hint && e.C("ECPolyline") is { } hl)
                List(root, "AI_HINTS", "polylines").Child("HINT_POLYLINES").Children.Add(Node("HINT_POLYLINE", "", 2,
                    Str(hint, "type") ?? "", Polyline(e, hl).Select(p => Node("point", "points", p.X, p.Z)).ToList(), Tags(e)));
            if (e.C("ECLightProbe") is { } probe)
            {
                var (x, y, z) = Pos(e);
                List(root, "LIGHT_PROBE_LIST", "LIGHT_PROBES").Children.Add(Node("LIGHT_PROBE", "", 3, Node("position", "", x, y, z),
                    F(e.C("ECSphere"), "radius", 1), Str(probe, "primary") == "true", HeightMode(e), Tags(e)));
            }
            if (e.C("ECPointLight") is { } pl) List(root, "POINT_LIGHT_LIST", "POINT_LIGHTS").Children.Add(PointLight(e, pl));
            if (e.Has("ECPlayableArea") && e.C("ECRectangle") is { } rect)
            {
                var (x, _, z) = Pos(e);
                float hw = F(rect, "width", 0) * 0.5f, hh = F(rect, "height", 0) * 0.5f;
                root.Children[root.Children.FindIndex(c => c.Tag == "PLAYABLE_AREA")] =
                    Node("PLAYABLE_AREA", "", 2, Node("area", "PLAYABLE_AREA", x - hw, z - hh, x + hw, z + hh), true, false, false, false, false);
            }
            if (e.C("ECSpotLight") is { } sl) List(root, "SPOT_LIGHT_LIST", "SPOT_LIGHTS").Children.Add(SpotLight(e, sl));
            if (e.Has("ECRiver") && e.C("ECRiverSpline") is { } rs) List(root, "SOUND_SHAPE_LIST", "SOUND_SHAPES").Children.Add(RiverSound(e, rs));
            if (e.C("ECCompositeScene") is { } cs)
            {
                var (m, x, y, z) = World(e);
                List(root, "COMPOSITE_SCENE_LIST", "COMPOSITE_SCENE_LIST").Children.Add(Node("COMPOSITE_SCENE_REFERENCE", "", 6,
                    Transform12("COMPOSITE_SCENE_REFERENCE", m, x, y, z), Str(cs, "path") ?? "", HeightMode(e), 1,
                    Str(cs, "autoplay") != "false", Tags(e), Flags(false, false, false, Seasons(e), true)));
            }
            if (e.C("ECBuildingSlot") is { } bs)
            {
                var (m, x, y, z) = World(e);
                var rs2 = e.C("ECMeshRenderSettings");
                List(root, "BUILDING_SLOT_LIST", "BUILDING_SLOTS").Children.Add(Node("BUILDING_SLOT", "", 4,
                    U(bs, "slot_id"), Str(bs, "group") ?? "", Transform16("BUILDING_SLOT", m, x, y, z), HeightMode(e), Tags(e), -1,
                    Colour("tint", rs2, "tint_colour"), Colour("faction_colour", rs2, "faction_colour"), Alpha(rs2)));
            }
            if (e.Has("ECNoGoRegion") && e.C("ECPolyline") is { } ng)
                root.Child("NON_TERRAIN_OUTLINES").Children.Add(Node("EMPIRE_OUTLINE", "", Polyline(e, ng).Select(p => Node("position", "OUTLINE", p.X, p.Z)).ToList()));
        }

        CaptureLocations(root, exported, prefabs, prefabIndex);
        Deployment(root, scene, exported);

        foreach (var (climate, path) in treeLists)
        {
            var (f, m) = catalog.Encode(climate);
            List(root, "TREE_LIST_REFERENCE_LIST", "TREE_LIST_REFERENCES").Children.Add(Node("TREE_LIST_REFERENCE", "", 1, path, MetaTags(f, m)));
        }
        foreach (var (climate, path) in grassLists)
        {
            var (f, m) = catalog.Encode(climate);
            List(root, "GRASS_LIST_REFERENCE_LIST", "GRASS_LIST_REFERENCES").Children.Add(Node("GRASS_LIST_REFERENCE", "", 1, path, MetaTags(f, m)));
        }
        root.Child("META_DATA_KEYS").Child("items").Children.AddRange(_seasons.Select(s => Node("item", "", s)));
        return root;
    }

    private BmdNode Building(SceneEntity e, XElement b)
    {
        var (m, x, y, z) = World(e);
        var rs = e.C("ECMeshRenderSettings");
        return Node("BUILDING", "", 14, "", Tags(e), Parent(), Str(b, "key") ?? "", "BBPT_LF_RELATIVE", Transform12("BUILDING", m, x, y, z),
            BuildingProperties("properties", "BUILDING", "", b, rs), HeightMode(e), Colour("tint", rs, "tint_colour"),
            Colour("faction_colour", rs, "faction_colour"), Alpha(rs), false);
    }

    private static BmdNode BuildingProperties(string tag, string parent, string buildingId, XElement? b, XElement? rs) =>
        Node(tag, parent, 7, buildingId, F(b, "damage", 0), false, false, false, true, Str(b, "indestructible") == "true", true,
            Str(b, "toggleable") == "true", false, false, Str(rs, "cast_shadow") != "false", false, false, false);

    private BmdNode Prefab(SceneEntity e, XElement pf)
    {
        var (m, x, y, z) = World(e);
        var rs = e.C("ECMeshRenderSettings");
        var overrides = pf.Elements("override").Select(o => BuildingProperties("property_override", "property_overrides",
            (string?)o.Attribute("name") ?? "", o.Element("ECBuilding"), rs)).ToList();
        return Node("PREFAB_INSTANCE", "PREFAB_INSTANCE", 9, $"prefabs/{Str(pf, "key")}.bmd", Transform16("PREFAB_INSTANCE", m, x, y, z),
            Node("property_overrides", "", overrides), 0u, "", false, HeightMode(e), Tags(e), Str(pf, "turn_buildings_into_props") == "true",
            Colour("tint", rs, "tint_colour"), Colour("faction_colour", rs, "faction_colour"), Alpha(rs));
    }

    private BmdNode Prop(SceneEntity e, int keyIndex)
    {
        var (m, x, y, z) = World(e);
        var rs = e.C("ECMeshRenderSettings");
        var dc = e.C("ECDecal");
        var decal = dc is not null;
        var outfield = Str(e.C("ECBattleProperties"), "visible_beyond_outfield") == "true";
        return Node("PROP", "", 20, keyIndex, Tags(e), Transform12("PROP", m, x, y, z),
            decal, false, false, true, true, true, true, Str(e.C("ECMesh"), "animation_path") is { Length: > 0 },
            F(dc, "parallax_scale", 0), F(dc, "tiling", 0), Str(dc, "normal_mode") == "DNM_DECAL_OVERRIDE",
            Flags(outfield, false, false, Seasons(e), true),
            false, decal && Str(dc, "apply_to_terrain") != "false", Str(dc, "apply_to_objects") == "true", Str(dc, "render_above_snow") == "true",
            HeightMode(e), 1, Str(rs, "cast_shadow") != "false", false, Colour("tint", rs, "tint_colour"), Colour("faction_colour", rs, "faction_colour"),
            Alpha(rs), Parent(), false, false, false);
    }

    private BmdNode Vfx(SceneEntity e, XElement vfx)
    {
        var (m, x, y, z) = World(e);
        return Node("PARTICLE_EMITTER", "", 6, Str(vfx, "vfx") ?? "", Transform12("PARTICLE_EMITTER", m, x, y, z), 0f,
            Str(vfx, "instance_name") ?? "", Flags(false, false, false, Seasons(e), true), HeightMode(e), 1, Tags(e), Parent());
    }

    private BmdNode PointLight(SceneEntity e, XElement l)
    {
        var (x, y, z) = Pos(e);
        var c = Floats(Str(l, "colour") ?? "255 255 255 255");
        var speed = Floats(Str(l, "animation_speed_scale") ?? "0 0");
        var anim = Str(l, "animation_type") switch { "LAT_RADIUS_SIN" => 1, "LAT_RADIUS_SIN_SIN" => 2, _ => 0 };
        return Node("POINT_LIGHT", "", 6, Node("position", "", x, y, z), F(l, "radius", 1),
            Node("colour", "", c[0] * (1f / 255f), c[1] * (1f / 255f), c[2] * (1f / 255f)), F(l, "colour_scale", 1), anim,
            Node("params", "", speed.ElementAtOrDefault(0), speed.ElementAtOrDefault(1)), F(l, "colour_min", 0), F(l, "random_offset", 0),
            Str(l, "falloff_type") ?? "", true, HeightMode(e), Str(l, "for_light_probes_only") == "true", 1, Tags(e),
            Flags(false, false, false, Seasons(e), true));
    }

    private BmdNode SpotLight(SceneEntity e, XElement l)
    {
        var (x, y, z) = Pos(e);
        var r = Floats(Str(e.C("ECTransform"), "rotation") ?? "0 0 0");
        var (qx, qy, qz, qw) = QtuTransform.Quaternion(r[0], r[1], r[2]);
        var c = Floats(Str(l, "colour") ?? "255 255 255 255");
        var intensity = F(l, "intensity", 1);
        // degrees -> radians as ECTransform does it: deg * pi * (1/180) in float
        static float Rad(float d) => d * 3.14159274f * 0.00555555569f;
        return Node("SPOT_LIGHT", "", 5, Node("position", "", x, y, z), Node("end", "", qx, qy, qz, qw), F(l, "length", 10),
            Rad(F(l, "inner_angle", 0)), Rad(F(l, "outer_angle", 0)),
            Node("colour", "", c[0] / 255f * intensity, c[1] / 255f * intensity, c[2] / 255f * intensity), F(l, "falloff", 1),
            Str(l, "gobo") ?? "", Str(l, "volumetric") == "true", HeightMode(e), 1, Tags(e));
    }

    private BmdNode RiverSound(SceneEntity e, XElement spline)
    {
        var (x, y, z) = Pos(e);
        var nodes = new List<BmdNode>();
        foreach (var p in spline.Element("spline")?.Elements("point") ?? [])
        {
            var o = Floats(Str(p, "position") ?? "0,0,0");
            nodes.Add(Node("river_node", "", 1, Node("vertex", "", x + o[0], y + o[1], z + o[2]), F(p, "width", 0), F(p, "flow_speed", 0)));
        }
        var zero = Node("inner_cube", "", 0f, 0f, 0f, 0f, 0f, 0f);
        return Node("SOUND_SHAPE", "", 7, "", "SST_RIVER", null, 0f, 0f, zero, Node("outer_cube", "", 0f, 0f, 0f, 0f, 0f, 0f), nodes,
            false, HeightMode(e), 0u, 1, Tags(e));
    }

    // ---- capture locations ----

    private void CaptureLocations(BmdNode root, List<SceneEntity> exported, BmdNode prefabs, Dictionary<ulong, int> prefabIndex)
    {
        // building links: prefab overrides naming this capture location
        var links = new Dictionary<ulong, List<(int Prefab, string Key)>>();
        foreach (var e in exported)
            if (e.C("ECPrefab") is { } pf && prefabIndex.TryGetValue(e.Id, out var pi))
                foreach (var o in pf.Elements("override"))
                    if (TileScene.ParseId((string?)o.Element("ECBuilding")?.Attribute("capture_location")) is var cl and > 0)
                    {
                        if (!links.TryGetValue(cl, out var l)) links[cl] = l = [];
                        l.Add((pi, (string?)o.Attribute("name") ?? ""));
                    }
        // one CAPTURE_LOCATION_LIST per tag set. BOB's order varies between runs (run1 = run2 != run3 on df46bdbc): a
        // pointer-keyed map; descending first entity id reproduces run1.
        var groups = exported.Where(e => e.Has("ECCaptureLocation")).GroupBy(e => e.Tags).OrderByDescending(g => g.Min(e => e.Id));
        var set = List(root, "CAPTURE_LOCATION_SET", "CAPTURE_LOCATION_SET");
        foreach (var g in groups)
        {
            var locs = new List<BmdNode>();
            foreach (var e in g.OrderBy(e => e.Id))
            {
                var c = e.C("ECCaptureLocation")!;
                var (x, _, z) = Pos(e);
                var flag = Floats(Str(c, "flag_position") ?? "0 0");
                // the facing angle is used as radians (Terry shows degrees): (cos a, -sin a)
                var a = F(c, "flag_facing_direction", 0);
                var points = e.C("ECCircle") is not null ? [Node("point", "location_points", x, z)]
                    : e.C("ECPolyline") is { } poly ? Polyline(e, poly).Select(p => Node("point", "location_points", p.X, p.Z)).ToList() : new List<BmdNode>();
                var bl = links.TryGetValue(e.Id, out var ll) ? ll.Select(l => Node("building_link", "", 2, Node("building_reference", "", 1, -1), l.Prefab, l.Key)).ToList() : [];
                locs.Add(Node("CAPTURE_LOCATION", "", Node("location", "CAPTURE_LOCATION", x + flag[0], z + flag[1]), F(e.C("ECCircle"), "radius", 0),
                    U(c, "min_players"), U(c, "max_players"), Importance(Str(c, "importance")), points, Str(c, "type") ?? "",
                    Node("flag_facing", "", MathF.Cos(a), -MathF.Sin(a)), bl));
            }
            var (f, m) = catalog.Encode(g.Key);
            set.Children.Add(Node("CAPTURE_LOCATION_LIST", "CAPTURE_LOCATION_SET", locs, MetaTags(f, m)));
        }
    }

    private static string Importance(string? s) => s switch
    {
        "CLIT_MAJOR" => "CAPTURE_LOCATION_MAJOR",
        "CLIT_KEY" => "CAPTURE_LOCATION_KEY",
        _ => "CAPTURE_LOCATION_MINOR",
    };

    // ---- deployment ----

    private void Deployment(BmdNode root, TileScene scene, List<SceneEntity> exported)
    {
        var zones = exported.Where(e => e.Has("ECDeploymentZone")).ToList();
        if (zones.Count == 0) return;
        var areas = List(root, "DEPLOYMENT_LIST", "DEPLOYMENT_AREAS");
        foreach (var cat in zones.GroupBy(z => Str(z.C("ECDeploymentZone"), "deployment_category") ?? "DZC_DEFAULT"))
        {
            var zoneNodes = new List<BmdNode>();
            foreach (var z in cat.OrderBy(z => U(z.C("ECDeploymentZone"), "alliance_id")).ThenBy(z => z.Id))
            {
                var dz = z.C("ECDeploymentZone")!;
                var regions = new List<BmdNode>();
                foreach (var r in z.Children.Where(c => c.Has("ECDeploymentZoneRegion") && c.C("ECPolyline") is not null).OrderBy(c => c.Id))
                {
                    var type = Str(r.C("ECDeploymentZoneRegion"), "region_type") == "DZRT_SUBTRACTIVE" ? "standard subtractive" : "standard additive";
                    var boundary = Node("BOUNDARY", "BOUNDARY_LIST", 1, type,
                        Polyline(r, r.C("ECPolyline")!).Select(p => Node("position", "BOUNDARY", p.X, p.Z)).ToList());
                    regions.Add(Node("DEPLOYMENT_ZONE_REGION", "", 1, new List<BmdNode> { boundary }, F(dz, "facing_direction", 0) + 90f, false,
                        U(dz, "deployment_zone_id")));
                }
                zoneNodes.Add(Node("DEPLOYMENT_ZONE", "", 1, regions));
            }
            var category = cat.Key.StartsWith("DZC_", StringComparison.Ordinal) ? "DAC_" + cat.Key[4..] : cat.Key;
            areas.Children.Add(Node("DEPLOYMENT_AREA", "", 2, category, zoneNodes, MetaTags()));
        }
    }

    // ---- helpers ----

    private BmdNode Tags(SceneEntity e)
    {
        var (f, m) = catalog.Encode(e.Tags);
        return MetaTags(f, m);
    }

    /// <summary>Season mask from ECCampaignProperties season_mask (empty = every season); 0 without the component.
    /// Codes go into META_DATA_KEYS in first-use order.</summary>
    private uint Seasons(SceneEntity e)
    {
        if (e.C("ECCampaignProperties") is not { } cp) return 0;
        var names = (Str(cp, "season_mask") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        foreach (var code in names.Length == 0 ? BmdMetaCatalog.SeasonCatalog : names.Select(n => BmdMetaCatalog.SeasonCatalog.FirstOrDefault(c => SeasonName(c) == n)))
            if (code is not null && !_seasons.Contains(code)) _seasons.Add(code);
        uint bits = 0;
        for (var i = 0; i < _seasons.Count; i++)
            if (names.Length == 0 || names.Contains(SeasonName(_seasons[i]))) bits |= 1u << i;
        return bits;
    }

    private static string SeasonName(string code) => code switch
    {
        "sp" => "season_spring", "su" => "season_summer", "ha" => "season_harvest", "au" => "season_autumn", "wi" => "season_winter", _ => code,
    };

    private static string HeightMode(SceneEntity e) =>
        Str(e.C("ECTerrainClamp"), "active") == "true" ? "BHM_TERRAIN" : "BHM_ABSOLUTE";

    private static (float X, float Y, float Z) Pos(SceneEntity e)
    {
        var p = Floats(Str(e.C("ECTransform"), "position") ?? "0 0 0");
        return (p[0] + 0f, p[1] + 0f, p[2] + 0f);
    }

    private static (double[] M, float X, float Y, float Z) World(SceneEntity e)
    {
        var t = e.C("ECTransform");
        var p = Floats(Str(t, "position") ?? "0 0 0");
        var r = Floats(Str(t, "rotation") ?? "0 0 0");
        var s = Floats(Str(t, "scale") ?? "1 1 1");
        return (QtuTransform.Matrix(r[0], r[1], r[2], s[0], s[1], s[2], p[0], p[1], p[2]), p[0] + 0f, p[1] + 0f, p[2] + 0f);
    }

    /// <summary>An ECPolyline's points in world x/z: the entity's matrix applied to (x, 0, y), plus its position (float).</summary>
    private static List<(float X, float Z)> Polyline(SceneEntity e, XElement poly)
    {
        var (m, px, _, pz) = World(e);
        var result = new List<(float, float)>();
        foreach (var pt in poly.Element("polyline")?.Elements("point") ?? [])
        {
            float x = F(pt, "x", 0), y = F(pt, "y", 0);
            result.Add((px + ((float)m[0] * x + (float)m[2] * y), pz + ((float)m[6] * x + (float)m[8] * y)));
        }
        return result;
    }

    private static BmdNode Colour(string tag, XElement? rs, string attr)
    {
        var c = Floats(Str(rs, attr) ?? "255 255 255 255");
        return Rgba(tag, (byte)c[0], (byte)c[1], (byte)c[2], (byte)c[3]);
    }

    private static byte Alpha(XElement? rs) => (byte)MathF.Round(F(rs, "alpha", 1) * 255f);

    private static string? Str(XElement? e, string name) => (string?)e?.Attribute(name);

    private static float F(XElement? e, string name, float def) =>
        e?.Attribute(name) is { } a ? float.Parse((string)a, CultureInfo.InvariantCulture) : def;

    private static uint U(XElement? e, string name) =>
        e?.Attribute(name) is { } a ? uint.Parse((string)a, CultureInfo.InvariantCulture) : 0;

    private static float[] Floats(string s) =>
        s.Split([' ', ','], StringSplitOptions.RemoveEmptyEntries).Select(v => float.Parse(v, CultureInfo.InvariantCulture)).ToArray();
}
