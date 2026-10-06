using System.Text;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>One &lt;group&gt; of a tree_parameters file (qttoolutility QTU::Procedural::VegetationGroupParameters).
/// Ranges are stored normalised (<see cref="ProceduralParameters.Normalise"/>), slopes in radians.</summary>
public sealed class VegetationGroup
{
    public required string Name { get; init; }
    public (float Low, float High, float Falloff) ChannelRange { get; init; }
    public (float Low, float High, float Falloff) HeightRange { get; init; }
    public float SlopeMin { get; init; }
    public float SlopeMax { get; init; }
    public float Probability { get; init; }
    public float GroupingProbability { get; init; }
    public float GroupingRadius { get; init; }
    /// <summary>&lt;texture&gt;: the blend channel the group belongs to and whose weight its objects test.</summary>
    public required string Texture { get; init; }
    /// <summary>&lt;texture_for_probability&gt; split on ',' (at most 8; defaults to the texture): the channels summed for
    /// the group's own range test.</summary>
    public required IReadOnlyList<string> ProbabilityTextures { get; init; }
}

/// <summary>One object of a group (QTU::Procedural::SingleGenerationObjectParameters).</summary>
public sealed class VegetationObject
{
    public required string Group { get; init; }
    public required string Model { get; init; }
    /// <summary>GENERATION_OBJECT_TYPE: 1 tree, 2 prop, 4 decal, 8 vfx, 0x10 prefab, 0x20 building.</summary>
    public required byte Type { get; init; }
    public (float X, float Y, float Z) BaseScale { get; init; } = (1f, 1f, 1f);
    public float SizeLow { get; init; }
    public float SizeRange { get; init; }
    public (float Low, float High, float Falloff) BlendRange { get; init; }
    public (float Low, float High, float Falloff) HeightRange { get; init; }
    /// <summary>Scaled while parsing so the group's most probable object has probability 1.</summary>
    public float Probability { get; set; }
    public float MinimumSeparation { get; init; }
    public bool SmallObject { get; init; }
    public bool IncludeInOutfield { get; init; }
    public bool KeepUpright { get; init; }
    public float Parallax { get; init; } = 1f;
    public bool DecalApplyToTerrain { get; init; } = true;
    public bool DecalApplyToObjects { get; init; }
    public bool DecalBlendNormals { get; init; } = true;
    public bool DecalRenderAboveSnow { get; init; }
}

/// <summary>
/// BOB's procedural vegetation parameters (qttoolutility QTU::Procedural::GenerationParameters): every
/// battleterrain/vegetation/*tree_parameters.xml (groups and their tree / prop / decal / vfx / prefab / building
/// objects), generation_categories.xml (the climate categories) and per_climate_densities.xml (max trees per m²).
/// Parsing follows parse_group_xml / parse_object_parameters_xml:
///  - numbers are read with calibs CA::UniString::parse(float&amp;) (<see cref="ParseFloat"/>), not a correctly rounded parser
///  - (low, high, falloff) triples are normalised by FUN_1800723d0 (<see cref="Normalise"/>)
///  - slopes: degrees · π · (1/180) in float; the group's slope_max defaults to π/2
///  - objects are keyed group + "/" + model, the first definition wins; each object goes into the category maps it lists
///  - after every group the group's objects (all groups of that name) are scaled so the most probable has probability 1
///    (FUN_180072430, when that maximum is ≥ 0.001)
/// </summary>
public sealed class ProceduralParameters
{
    public IReadOnlyList<string> Categories { get; }
    public IReadOnlyDictionary<string, float> MaxTreesPerSquareMetre { get; }
    /// <summary>Groups by name (the first of a name wins).</summary>
    public Dictionary<string, VegetationGroup> Groups { get; } = new(StringComparer.Ordinal);
    private readonly Dictionary<string, VegetationObject> _objects = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Dictionary<string, VegetationObject>> _byGroup = new(StringComparer.Ordinal);
    private readonly Dictionary<int, Dictionary<string, VegetationObject>> _byCategory = [];
    public List<string> Errors { get; } = [];

    public const string Folder = "battleterrain/vegetation/";

    private ProceduralParameters(IReadOnlyList<string> categories, IReadOnlyDictionary<string, float> maxTrees)
    {
        Categories = categories;
        MaxTreesPerSquareMetre = maxTrees;
    }

    /// <summary>The objects of a category (climate), in no particular order.</summary>
    public IEnumerable<VegetationObject> CategoryObjects(string category)
    {
        var i = IndexOf(Categories, category);
        return i >= 0 && _byCategory.TryGetValue(i, out var m) ? m.Values : [];
    }

    private static int IndexOf(IReadOnlyList<string> list, string s)
    {
        for (var i = 0; i < list.Count; i++) if (list[i] == s) return i;
        return -1;
    }

    /// <summary>Reads the parameters BOB's VFS sees: the vegetation folder of the kit's working_data, else the packs.</summary>
    public static ProceduralParameters Load(BattleBuildContext ctx)
    {
        var names = new SortedSet<string>(StringComparer.Ordinal);
        foreach (var pack in ctx.Packs.Packs)
            foreach (var key in pack.Entries.Keys)
                if (key.StartsWith(@"battleterrain\vegetation\", StringComparison.Ordinal) && key.IndexOf('\\', 25) < 0
                    && key.EndsWith("tree_parameters.xml", StringComparison.Ordinal))
                    names.Add(key[25..]);
        var loose = Path.Combine(ctx.WorkingData, "BattleTerrain", "vegetation");
        if (Directory.Exists(loose))
            foreach (var f in Directory.EnumerateFiles(loose, "*tree_parameters.xml"))
                names.Add(Path.GetFileName(f).ToLowerInvariant());
        byte[] Read(string name) => ctx.ReadVfs(Folder + name) ?? throw new FileNotFoundException($"{Folder}{name} not in the VFS");
        return Load(names.Select(n => (n, Read(n))), Read("generation_categories.xml"), Read("per_climate_densities.xml"));
    }

    public static ProceduralParameters Load(IEnumerable<(string Name, byte[] Data)> treeParameterFiles, byte[] categoriesXml,
                                            byte[] densitiesXml)
    {
        var categories = ParseXml(categoriesXml).Elements("category").Select(e => e.Value.Trim()).ToList();
        var dens = new Dictionary<string, float>(StringComparer.Ordinal);
        foreach (var c in ParseXml(densitiesXml).Elements("climate"))
            if (c.Element("name") is { } n && c.Element("max_trees_per_metre_squared") is { } m)
                dens[n.Value.Trim()] = ParseFloat(m.Value);
        var p = new ProceduralParameters(categories, dens);
        foreach (var (_, data) in treeParameterFiles)
            foreach (var g in ParseXml(data).Elements("group"))
                p.ParseGroup(g);
        return p;
    }

    /// <summary>CA's XML reader ends a comment at the first "-->" (the shipped sbt_grass0 file nests one, which a strict
    /// parser rejects), so comments are cut that way before parsing.</summary>
    public static XElement ParseXml(byte[] data)
    {
        var text = Encoding.UTF8.GetString(data);
        if (text.Length > 0 && text[0] == '﻿') text = text[1..];
        text = Regex.Replace(text, "<!--.*?-->", "", RegexOptions.Singleline);
        return XDocument.Parse(text, LoadOptions.PreserveWhitespace).Root!;
    }

    private static string? Child(XElement e, string name) => e.Element(name)?.Value;

    private static float Value(XElement e, string name, float def) => Child(e, name) is { } s ? ParseFloat(s) : def;

    private bool ParseGroup(XElement e)
    {
        if ((string?)e.Attribute("group_name") is not { } name) return false;
        string[] range = ["group_channel_range_low", "group_channel_range_high", "group_channel_range_falloff"];
        string[] height = ["height_range_low", "height_range_high", "height_range_falloff"];
        if (range.Concat(height).Concat(["probability", "texture"]).Any(r => Child(e, r) is null))
        {
            Errors.Add($"group {name}: a required value is missing");
            return false;
        }
        var texture = Child(e, "texture")!;
        var tfp = Child(e, "texture_for_probability");
        var g = new VegetationGroup
        {
            Name = name,
            ChannelRange = Normalise(ParseFloat(Child(e, range[0])!), ParseFloat(Child(e, range[1])!), ParseFloat(Child(e, range[2])!)),
            SlopeMin = Child(e, "slope_min") is { } smin ? Radians(ParseFloat(smin)) : 0f,
            SlopeMax = Child(e, "slope_max") is { } smax ? Radians(ParseFloat(smax)) : 1.57079637f,
            HeightRange = Normalise(ParseFloat(Child(e, height[0])!), ParseFloat(Child(e, height[1])!), ParseFloat(Child(e, height[2])!)),
            Probability = ParseFloat(Child(e, "probability")!),
            Texture = texture,
            ProbabilityTextures = tfp is null ? [texture] : tfp.Split(',').Take(8).ToList(),
            GroupingProbability = Value(e, "grouping_probability", 0f),
            GroupingRadius = Value(e, "grouping_radius", 0f),
        };
        if (!Groups.TryAdd(name, g)) Errors.Add($"Group name '{name}' is used multiple times");
        foreach (var c in e.Elements())
        {
            var type = c.Name.LocalName switch
            {
                "tree" => 1, "prop" => 2, "decal" => 4, "vfx" => 8, "prefab" => 0x10, "building" => 0x20, _ => 0,
            };
            if (type != 0 && !ParseObject(c, name, (byte)type)) return false;
        }
        NormaliseProbabilities(name);
        return true;
    }

    private static float Radians(float degrees) => degrees * 3.14159274f * 0.00555555569f;

    private bool ParseObject(XElement e, string group, byte type)
    {
        var model = Child(e, "model");
        string[] req = ["size_low", "size_high", "blendmap_range_low", "blendmap_range_high", "blendmap_range_falloff",
            "height_low", "height_high", "height_falloff", "probability"];
        if (model is null || req.Any(r => Child(e, r) is null))
        {
            Errors.Add($"group {group}: an object misses a required value");
            return false;
        }
        var categories = e.Element("categories");
        if (e.Element("humidities") is null || categories is null) return false;
        if (categories.Elements().Any(c => c.Name.LocalName != "category") || !categories.Elements().Any()) return false;
        float low = ParseFloat(Child(e, "size_low")!), high = ParseFloat(Child(e, "size_high")!);
        var df = e.Element("decal_flags");
        bool Flag(string attr, bool def) => df?.Attribute(attr) is { } a ? a.Value.Trim().Equals("true", StringComparison.OrdinalIgnoreCase) : def;
        var o = new VegetationObject
        {
            Group = group,
            Model = model,
            Type = type,
            BaseScale = (Value(e, "base_scale_x", 1f), Value(e, "base_scale_y", 1f), Value(e, "base_scale_z", 1f)),
            SizeLow = low,
            SizeRange = high - low,
            BlendRange = Normalise(ParseFloat(Child(e, "blendmap_range_low")!), ParseFloat(Child(e, "blendmap_range_high")!),
                ParseFloat(Child(e, "blendmap_range_falloff")!)),
            HeightRange = Normalise(ParseFloat(Child(e, "height_low")!), ParseFloat(Child(e, "height_high")!),
                ParseFloat(Child(e, "height_falloff")!)),
            Probability = ParseFloat(Child(e, "probability")!),
            MinimumSeparation = Value(e, "minimum_seperation", 0f),
            SmallObject = e.Element("small_object") is not null,
            IncludeInOutfield = e.Element("include_in_outfield") is not null,
            KeepUpright = e.Element("keep_upright") is not null,
            Parallax = Value(e, "parallax", 1f),
            DecalApplyToTerrain = Flag("apply_to_terrain", true),
            DecalApplyToObjects = Flag("apply_to_objects", false),
            DecalBlendNormals = Flag("blend_normals", true),
            DecalRenderAboveSnow = Flag("render_above_snow", false),
        };
        var key = group + "/" + model;
        if (!_objects.TryGetValue(key, out var kept)) _objects[key] = kept = o;
        (_byGroup.TryGetValue(group, out var gm) ? gm : _byGroup[group] = new(StringComparer.Ordinal)).TryAdd(key, kept);
        foreach (var c in categories.Elements())
        {
            var i = IndexOf(Categories, c.Value.Trim());
            if (i < 0) continue;
            (_byCategory.TryGetValue(i, out var cm) ? cm : _byCategory[i] = new(StringComparer.Ordinal)).TryAdd(key, kept);
        }
        return true;
    }

    private void NormaliseProbabilities(string group)
    {
        if (!_byGroup.TryGetValue(group, out var m) || m.Count == 0) return;
        VegetationObject? max = null;
        foreach (var o in m.Values) if (max is null || !(o.Probability <= max.Probability)) max = o;
        if (!(max!.Probability >= 0.001f)) return;
        var k = 1f / max.Probability;
        foreach (var o in m.Values) o.Probability = k * o.Probability;
    }

    /// <summary>FUN_1800723d0: (low, high, falloff) → (centre − falloff/2, centre + falloff/2 ... ) i.e. the range shrunk by
    /// half the falloff on each side, with the falloff kept as the width outside it; a falloff wider than the range is
    /// dropped (range unchanged, falloff 0).</summary>
    public static (float Low, float High, float Falloff) Normalise(float low, float high, float falloff)
    {
        var f2 = falloff * 0.5f;
        var f1 = (high - low) * 0.5f;
        var f3 = (high + low) * 0.5f;
        if (f1 < f2) return (low, high, 0f);
        return (f3 - f2, f2 + f3, f1 - f2);
    }

    /// <summary>calibs CA::UniString::parse(float&amp;) (XML_VALUE::as_float32): optional '-', digits accumulated in float
    /// (v·10 + d), fraction digits as d · 0.1f^k added on, an optional exponent applied as repeated ·10 or ·0.1f; text that
    /// does not parse completely gives 0.</summary>
    public static float ParseFloat(string s)
    {
        var i = 0;
        var neg = s.Length > 0 && s[0] == '-';
        if (neg) i = 1;
        var v = 0f;
        while (i < s.Length && s[i] is >= '0' and <= '9') v = v * 10f + (s[i++] - '0');
        const float tenth = 0.100000001f;
        if (i < s.Length && s[i] == '.')
        {
            i++;
            var f = 1f;
            while (i < s.Length && s[i] is >= '0' and <= '9')
            {
                f *= tenth;
                v = (s[i++] - '0') * f + v;
            }
        }
        if (i < s.Length && (s[i] == 'e' || s[i] == 'E'))
        {
            var sign = i + 1 < s.Length ? s[i + 1] : '\0';
            var j = sign is '-' or '+' ? i + 2 : i + 1;
            var exp = 0;
            while (j < s.Length && s[j] is >= '0' and <= '9') exp = exp * 10 + (s[j++] - '0');
            if (j != s.Length) return 0f;
            for (var k = 0; k < exp; k++) v *= sign == '-' ? tenth : 10f;
            i = j;
        }
        if (i != s.Length) return 0f;
        return neg ? -v : v;
    }
}

/// <summary>
/// QTU::ProceduralTerrainContent::ParametersCompiled for one tile and climate (FUN_1800855c0): the category's objects
/// sorted by (group, model) byte order, the groups that have objects and whose texture is a tile channel sorted by
/// (channel, name), each group's objects copied to the front in that group order (the rest of the array keeps its
/// sorted entries), compact 20-byte groups (FUN_1800d7660) and 12-byte objects (FUN_1800c64d0), and the generation
/// grid: spacing 1 / √(max trees per m²), the tile's inner box, density-pixel offsets of the composited maps.
/// </summary>
public sealed class ProceduralTables
{
    public required short[] ChannelEnds { get; init; }
    public required byte[][] Groups { get; init; }
    public required byte[][] Objects { get; init; }
    public required IReadOnlyList<VegetationObject> ObjectList { get; init; }
    public int Nx { get; init; }
    public int Ny { get; init; }
    /// <summary>World units per composited-map pixel (cell size / triangle density).</summary>
    public float Pixel { get; init; }
    public float OffsetX { get; init; }
    public float OffsetY { get; init; }
    public float OriginX { get; init; }
    public float OriginZ { get; init; }
    public float Spacing { get; init; }
    public float InvUnitScale { get; init; }
    public float Width { get; init; }
    public float Height { get; init; }

    public static ProceduralTables Compile(ProceduralParameters p, string climate, IReadOnlyList<string> textures,
                                           int tilesWide, int tilesHigh, int density, float unitScale)
    {
        var objs = p.CategoryObjects(climate).ToList();
        objs.Sort((a, b) =>
        {
            var c = Ordinal(a.Group, b.Group);
            return c != 0 ? c : Ordinal(a.Model, b.Model);
        });
        int Channel(string t)
        {
            for (var i = 0; i < textures.Count; i++) if (textures[i] == t) return i;
            return -1;
        }
        var used = objs.Select(o => o.Group).ToHashSet(StringComparer.Ordinal);
        var pairs = p.Groups.Values.Where(g => used.Contains(g.Name)).Select(g => (Ch: Channel(g.Texture), g))
            .Where(t => t.Ch >= 0).ToList();
        pairs.Sort((a, b) => a.Ch != b.Ch ? a.Ch.CompareTo(b.Ch) : Ordinal(a.g.Name, b.g.Name));
        var ends = new short[8];
        for (var ch = 0; ch < textures.Count && ch < 8; ch++) ends[ch] = (short)pairs.Count(t => t.Ch <= ch);
        var layout = new List<VegetationObject>(objs);
        var groups = new byte[pairs.Count][];
        var pos = 0;
        for (var gi = 0; gi < pairs.Count; gi++)
        {
            var (ch, g) = pairs[gi];
            var start = objs.FindIndex(o => o.Group == g.Name);
            var count = objs.Count(o => o.Group == g.Name);
            for (var k = 0; k < count; k++) layout[pos + k] = objs[start + k];
            var mask = 0;
            foreach (var t in g.ProbabilityTextures)
                if (t.Length > 0 && Channel(t) is var c and >= 0) mask |= 1 << c;
            var b = new byte[20];
            var prob = g.Probability >= 0f ? g.Probability : 0f;
            if (10f <= prob) prob = 10f;
            Put16(b, 0, (int)(prob * 6553.5f));
            Put16(b, 2, pos);
            b[4] = (byte)count;
            b[5] = (byte)mask;
            b[6] = (byte)ch;
            b[7] = (byte)(int)(Clamp01(g.ChannelRange.Low) * 255f);
            b[8] = (byte)(int)(Clamp01(g.ChannelRange.High) * 255f);
            b[9] = (byte)(int)(Clamp01(g.ChannelRange.Falloff) * 255f);
            Put16(b, 10, H16(g.HeightRange.Low));
            Put16(b, 12, H16(g.HeightRange.High));
            Put16(b, 14, H16(g.HeightRange.Falloff));
            b[16] = (byte)(int)(Clamp01(MathF.Cos(g.SlopeMin)) * 255f);
            b[17] = (byte)(int)(Clamp01(MathF.Cos(g.SlopeMax)) * 255f);
            b[18] = (byte)(int)(Clamp01(g.GroupingProbability) * 255f);
            var gr = g.GroupingRadius >= 0f ? g.GroupingRadius : 0f;
            b[19] = (byte)(int)(255f <= gr ? 255f : gr);
            groups[gi] = b;
            pos += count;
        }
        var objects = new byte[layout.Count][];
        for (var i = 0; i < layout.Count; i++)
        {
            var o = layout[i];
            var b = new byte[12];
            b[0] = (byte)(int)(Clamp01(o.Probability) * 255f);
            var ms = o.MinimumSeparation >= 0f ? o.MinimumSeparation : 0f;
            b[1] = (byte)(int)(255f <= ms ? 255f : ms);
            b[2] = (byte)((o.Model.Length == 0 ? 0x40 : 0) | (o.SmallObject ? 0x80 : 0) | (o.Type & 0x3f));
            b[3] = (byte)(int)(Clamp01(o.BlendRange.Low) * 255f);
            b[4] = (byte)(int)(Clamp01(o.BlendRange.High) * 255f);
            b[5] = (byte)(int)(Clamp01(o.BlendRange.Falloff) * 255f);
            Put16(b, 6, H16(o.HeightRange.Low));
            Put16(b, 8, H16(o.HeightRange.High));
            Put16(b, 10, H16(o.HeightRange.Falloff));
            objects[i] = b;
        }
        var maxTrees = p.MaxTreesPerSquareMetre[climate];
        var s = 1f / MathF.Sqrt(maxTrees);
        var cell = density * unitScale;
        float w = tilesWide * cell, h = tilesHigh * cell;
        var nx = (int)MathF.Floor(1f / s * w);
        var ny = (int)MathF.Floor(1f / s * h);
        return new ProceduralTables
        {
            ChannelEnds = ends, Groups = groups, Objects = objects, ObjectList = layout, Nx = nx, Ny = ny,
            Pixel = cell * (1f / density), OffsetX = density, OffsetY = density,
            OriginX = (w - (nx - 1) * s) * 0.5f, OriginZ = (h - (ny - 1) * s) * 0.5f, Spacing = s,
            InvUnitScale = 1f / unitScale, Width = w, Height = h,
        };
    }

    private static int Ordinal(string a, string b) => string.CompareOrdinal(a, b);

    private static float Clamp01(float v) => !(v >= 0f) ? 0f : 1f <= v ? 1f : v;

    private static int H16(float v)
    {
        var c = !(-5000f <= v) ? -5000f : 5000f <= v ? 5000f : v;
        return (int)((c - -5000f) * 6.5535f);
    }

    private static void Put16(byte[] b, int at, int v)
    {
        b[at] = (byte)v;
        b[at + 1] = (byte)(v >> 8);
    }
}
