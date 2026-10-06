using System.Globalization;
using System.Xml.Linq;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>One entity of a battle tile project's layers, with what BOB's export needs to know about its place in the
/// layer tree.</summary>
public sealed class SceneEntity(XElement element, ulong id)
{
    public XElement Element { get; } = element;
    public ulong Id { get; } = id;
    public string Name => (string?)Element.Attribute("name") ?? "";
    /// <summary>Export tags of the tag layers (ECLayerExportTags) the entity is in, comma separated.</summary>
    public string Tags { get; set; } = "";
    /// <summary>The entity's logical parent (layer, group or deployment zone), or null.</summary>
    public SceneEntity? Parent { get; set; }
    public List<SceneEntity> Children { get; } = [];
    public XElement? C(string component) => Element.Element(component);
    public bool Has(string component) => Element.Element(component) is not null;
}

/// <summary>
/// The entities of a battle tile project (the .terry's QTU::Scene layer files and the layer files they reference),
/// the way BOB's TerryTile export walks them: Logical associations make the layer tree; entities under a layer whose
/// ECLayerExport is export="false" (the "Reference" layer with the scale man) are not exported; tag layers
/// (ECLayerExportTags tags="...") tag their members.
/// </summary>
public sealed class TileScene
{
    public List<SceneEntity> Entities { get; } = [];
    public Dictionary<ulong, SceneEntity> ById { get; } = [];

    /// <summary>The exported entities (not under a non-exported layer), in ascending id order.</summary>
    public IEnumerable<SceneEntity> Exported => Entities.Where(e => !IsHidden(e)).OrderBy(e => e.Id);

    public static TileScene Load(string terryFile)
    {
        var scene = new TileScene();
        var dir = Path.GetDirectoryName(terryFile)!;
        var stem = Path.GetFileNameWithoutExtension(terryFile);
        var terry = XDocument.Load(terryFile);
        var queue = new Queue<string>();
        foreach (var e in terry.Descendants("entity").Where(e => e.Element("ECLayerFile") is not null))
            queue.Enqueue((string?)e.Attribute("id") ?? "");
        var seen = new HashSet<string>();
        while (queue.Count > 0)
        {
            var layerId = queue.Dequeue();
            if (!seen.Add(layerId)) continue;
            var path = Path.Combine(dir, $"{stem}.{layerId}.layer");
            if (!File.Exists(path)) continue;
            var doc = XDocument.Load(path);
            foreach (var e in doc.Root?.Element("entities")?.Elements("entity") ?? [])
            {
                var id = ParseId((string?)e.Attribute("id"));
                var se = new SceneEntity(e, id);
                scene.Entities.Add(se);
                scene.ById.TryAdd(id, se);
                if (e.Element("ECLayerFile") is not null) queue.Enqueue((string?)e.Attribute("id") ?? "");
            }
            foreach (var from in doc.Root?.Element("associations")?.Element("Logical")?.Elements("from") ?? [])
            {
                if (!scene.ById.TryGetValue(ParseId((string?)from.Attribute("id")), out var parent)) continue;
                foreach (var to in from.Elements("to"))
                    if (scene.ById.TryGetValue(ParseId((string?)to.Attribute("id")), out var child))
                    {
                        child.Parent = parent;
                        parent.Children.Add(child);
                    }
            }
        }
        foreach (var e in scene.Entities) e.Tags = TagsOf(e);
        return scene;
    }

    public static ulong ParseId(string? s) =>
        ulong.TryParse(s, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var v) ? v : 0;

    private static bool IsHidden(SceneEntity e)
    {
        for (var p = e.Parent; p is not null; p = p.Parent)
            if ((string?)p.C("ECLayerExport")?.Attribute("export") == "false") return true;
        return false;
    }

    private static string TagsOf(SceneEntity e)
    {
        var tags = new List<string>();
        for (var p = e.Parent; p is not null; p = p.Parent)
            if ((string?)p.C("ECLayerExportTags")?.Attribute("tags") is { Length: > 0 } t)
                tags.AddRange(t.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries));
        return string.Join(",", tags.Distinct());
    }
}
