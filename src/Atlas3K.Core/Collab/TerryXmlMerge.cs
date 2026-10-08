using System.Globalization;
using System.Text;
using System.Xml.Linq;
using Atlas3K.Formats.Terry;

namespace Atlas3K.Core.Collab;

/// <summary>
/// Three-way merge of Terry XML (.layer, .terry) at the level of entities rather than lines. Entities are matched by
/// their stable id: an entity changed on one side only takes that side; when both sides changed it, its components
/// and attributes are merged one by one, and only the same attribute set to different values (or an edit against a
/// delete) is a conflict. Associations (tag/folder membership, transform parenting) merge as sets of links. The
/// non-entity rest of the file (the "header": layer version, project settings) must change on one side only.
///
/// The result is written in Terry's layout through <see cref="TerryXml"/>, so a merge that keeps ours unchanged gives
/// ours byte for byte. Conflicts keep ours.
/// </summary>
public static class TerryXmlMerge
{
    public sealed record Result(string Text, List<MergeConflict> Conflicts, int TakenFromTheirs, int Added, int Removed);

    /// <summary>Merges the three texts; <paramref name="baseText"/> null means the file did not exist in the base.</summary>
    public static Result Merge(string? baseText, string oursText, string theirsText, string file)
    {
        var conflicts = new List<MergeConflict>();
        if (oursText == theirsText) return new Result(oursText, conflicts, 0, 0, 0);
        if (baseText == theirsText) return new Result(oursText, conflicts, 0, 0, 0);
        if (baseText == oursText) return new Result(theirsText, conflicts, 1, 0, 0);

        var b = baseText is null ? null : TerryXml.Parse(baseText);
        var o = TerryXml.Parse(oursText);
        var t = TerryXml.Parse(theirsText);
        var newline = TerryXml.NewlineOf(oursText);

        // Header: start from whichever side changed it.
        var (sb, so, st) = (b is null ? null : Skeleton(b), Skeleton(o), Skeleton(t));
        var start = o;
        if (so != st && st != sb)
        {
            if (so == sb) start = new XDocument(t);
            else conflicts.Add(new MergeConflict(file, "header", "header", "the file header (non-entity part) changed on both sides; kept ours"));
        }
        if (start == o) start = new XDocument(o);

        var bEnt = b is null ? new Dictionary<string, XElement>() : Entities(b);
        var oEnt = Entities(o);
        var tEnt = Entities(t);
        int fromTheirs = 0, added = 0, removed = 0;

        // Decide each entity.
        var merged = new Dictionary<string, XElement?>();
        foreach (var id in oEnt.Keys.Union(tEnt.Keys).Union(bEnt.Keys))
        {
            var be = bEnt.GetValueOrDefault(id);
            var oe = oEnt.GetValueOrDefault(id);
            var te = tEnt.GetValueOrDefault(id);
            string? bx = Text(be), ox = Text(oe), tx = Text(te);
            if (ox == tx) { merged[id] = oe; continue; }
            if (bx == tx) { merged[id] = oe; continue; }
            if (bx == ox)
            {
                merged[id] = te;
                fromTheirs++;
                if (oe is null) added++;
                if (te is null) removed++;
                continue;
            }
            // Changed on both sides.
            if (oe is null || te is null || be is null)
            {
                merged[id] = oe;
                var what = be is null ? "added on both sides with different content"
                    : oe is null ? "deleted in ours but edited in theirs" : "edited in ours but deleted in theirs";
                conflicts.Add(new MergeConflict(file, "entity", id, $"entity {id} {what}; kept ours", bx, ox, tx, Location(oe ?? te)));
                continue;
            }
            merged[id] = MergeEntity(id, be, oe, te, file, conflicts);
            fromTheirs++;
        }

        // Rebuild every entity container of the start document in merged order.
        var containers = Containers(start);
        var tOrder = OrderByContainer(t);
        var oOrder = OrderByContainer(o);
        var placed = new HashSet<string>();
        foreach (var (key, container) in containers)
        {
            var order = MergeOrder(oOrder.GetValueOrDefault(key) ?? [], tOrder.GetValueOrDefault(key) ?? []);
            foreach (var e in container.Elements("entity").ToList()) e.Remove();
            foreach (var id in order)
                if (merged.GetValueOrDefault(id) is { } e && placed.Add(id)) container.Add(new XElement(e));
        }
        // Entities whose container exists only on the other side (rare): append to the first container.
        if (containers.Count > 0)
            foreach (var (id, e) in merged)
                if (e is not null && placed.Add(id)) containers[0].Container.Add(new XElement(e));

        MergeAssociations(start, b, o, t);
        return new Result(TerryXml.ToText(start.Root!, newline), conflicts, fromTheirs, added, removed);
    }

    // ---------------------------------------------------------------- entities

    /// <summary>Top-level entities (not nested in another entity) by id.</summary>
    public static Dictionary<string, XElement> Entities(XDocument doc)
    {
        var map = new Dictionary<string, XElement>();
        foreach (var e in TopEntities(doc))
            if ((string?)e.Attribute("id") is { } id) map.TryAdd(id, e);
        return map;
    }

    private static IEnumerable<XElement> TopEntities(XDocument doc) =>
        doc.Descendants("entity").Where(e => e.Attribute("id") is not null && !e.Ancestors("entity").Any());

    private static List<(string Key, XElement Container)> Containers(XDocument doc) =>
        TopEntities(doc).Select(e => e.Parent!).Distinct().Select(c => (ContainerKey(c), c)).ToList()
            is { Count: > 0 } list ? list : EmptyContainers(doc);

    /// <summary>A file with no entities still has its container (layer/entities, scene data).</summary>
    private static List<(string, XElement)> EmptyContainers(XDocument doc) =>
        doc.Root!.Element("entities") is { } ents ? [(ContainerKey(ents), ents)]
        : doc.Root!.Elements("pc").Where(pc => (string?)pc.Attribute("type") == "QTU::Scene").Select(pc => pc.Element("data"))
            .OfType<XElement>().Select(d => (ContainerKey(d), d)).ToList();

    private static string ContainerKey(XElement c) =>
        string.Join('/', c.AncestorsAndSelf().Reverse().Select(a =>
            a.Name.LocalName + ((string?)a.Attribute("type") is { } type ? $"[{type}]" : "")));

    private static Dictionary<string, List<string>> OrderByContainer(XDocument doc) =>
        TopEntities(doc).GroupBy(e => ContainerKey(e.Parent!))
            .ToDictionary(g => g.Key, g => g.Select(e => (string)e.Attribute("id")!).ToList());

    /// <summary>Ours' order, with ids only theirs has inserted after the id that precedes them in theirs.</summary>
    internal static List<string> MergeOrder(List<string> ours, List<string> theirs)
    {
        var result = new List<string>(ours);
        var present = new HashSet<string>(ours);
        string? prev = null;
        foreach (var id in theirs)
        {
            if (present.Add(id))
            {
                var at = prev is null ? 0 : result.IndexOf(prev) + 1;
                result.Insert(at, id);
            }
            prev = id;
        }
        return result;
    }

    private static string? Text(XElement? e)
    {
        if (e is null) return null;
        var sb = new StringBuilder();
        TerryXml.Write(sb, e, 0);
        return sb.ToString();
    }

    /// <summary>Merges an entity changed on both sides: its own attributes, then its child elements (components) by
    /// name and occurrence.</summary>
    private static XElement MergeEntity(string id, XElement be, XElement oe, XElement te, string file, List<MergeConflict> conflicts)
    {
        var result = new XElement(oe);
        var location = Location(oe);
        MergeAttributes(id, "", be, oe, te, result, file, conflicts, location);

        var bc = Children(be);
        var oc = Children(oe);
        var tc = Children(te);
        var keys = MergeOrder(oc.Keys.ToList(), tc.Keys.ToList());
        foreach (var k in bc.Keys) if (!keys.Contains(k)) keys.Add(k);
        var children = new List<XElement>();
        foreach (var k in keys)
        {
            var b = bc.GetValueOrDefault(k);
            var o = oc.GetValueOrDefault(k);
            var t = tc.GetValueOrDefault(k);
            string? bx = Text(b), ox = Text(o), tx = Text(t);
            XElement? pick;
            if (ox == tx || bx == tx) pick = o;
            else if (bx == ox) pick = t;
            else if (o is null || t is null || b is null || o.HasElements || t.HasElements || b.HasElements)
            {
                pick = o;
                var name = k.Split('#')[0];
                conflicts.Add(new MergeConflict(file, "entity", id,
                    $"{name} of entity {id} changed on both sides; kept ours", bx, ox, tx, location));
            }
            else
            {
                pick = new XElement(o);
                MergeAttributes(id, k.Split('#')[0] + ".", b, o, t, pick, file, conflicts, location);
            }
            if (pick is not null) children.Add(new XElement(pick));
        }
        result.RemoveNodes();
        foreach (var c in children) result.Add(c);
        return result;
    }

    private static Dictionary<string, XElement> Children(XElement e)
    {
        var map = new Dictionary<string, XElement>();
        var seen = new Dictionary<string, int>();
        foreach (var c in e.Elements())
        {
            var n = c.Name.LocalName;
            var i = seen[n] = seen.GetValueOrDefault(n) + 1;
            map[i == 1 ? n : $"{n}#{i}"] = c;
        }
        return map;
    }

    private static void MergeAttributes(string id, string prefix, XElement b, XElement o, XElement t, XElement into,
                                        string file, List<MergeConflict> conflicts, double[]? location)
    {
        var names = o.Attributes().Select(a => a.Name).Union(t.Attributes().Select(a => a.Name)).Union(b.Attributes().Select(a => a.Name)).ToList();
        foreach (var n in names)
        {
            string? bv = (string?)b.Attribute(n), ov = (string?)o.Attribute(n), tv = (string?)t.Attribute(n);
            if (ov == tv || bv == tv) continue;
            if (bv == ov) { into.SetAttributeValue(n, tv); continue; }
            conflicts.Add(new MergeConflict(file, "attribute", $"{id}/{prefix}{n.LocalName}",
                $"{prefix}{n.LocalName} of entity {id}: ours '{ov}', theirs '{tv}' (base '{bv}'); kept ours", bv, ov, tv, location));
        }
    }

    /// <summary>World [x, z] of an entity's ECTransform position.</summary>
    public static double[]? Location(XElement? e)
    {
        if ((string?)e?.Element("ECTransform")?.Attribute("position") is not { } p) return null;
        var parts = p.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return parts.Length >= 3
               && double.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var x)
               && double.TryParse(parts[2], NumberStyles.Float, CultureInfo.InvariantCulture, out var z)
            ? [x, z] : null;
    }

    // ---------------------------------------------------------------- header & associations

    /// <summary>The file without its entities and association links: what must not change on both sides.</summary>
    private static string Skeleton(XDocument doc)
    {
        var copy = new XDocument(doc);
        foreach (var e in TopEntities(copy).ToList()) e.Remove();
        if (copy.Root!.Element("associations") is { } assoc)
            foreach (var kind in assoc.Elements()) kind.RemoveNodes();
        return TerryXml.ToText(copy.Root!);
    }

    /// <summary>Association links (from id → to element) merged as sets per kind (Logical, Transform, ...).</summary>
    private static void MergeAssociations(XDocument start, XDocument? b, XDocument o, XDocument t)
    {
        if (start.Root!.Element("associations") is not { } assoc) return;
        var bl = Links(b);
        var ol = Links(o);
        var tl = Links(t);
        var sl = Links(start);
        foreach (var kind in assoc.Elements().ToList())
        {
            var k = kind.Name.LocalName;
            var ob = ol.GetValueOrDefault(k) ?? [];
            var tb = tl.GetValueOrDefault(k) ?? [];
            var bb = bl.GetValueOrDefault(k) ?? [];
            var tSet = tb.Select(l => l.Key).ToHashSet();
            var bSet = bb.Select(l => l.Key).ToHashSet();
            var oSet = ob.Select(l => l.Key).ToHashSet();
            // Keep ours unless theirs removed it from base; add theirs' new links.
            var links = ob.Where(l => !(bSet.Contains(l.Key) && !tSet.Contains(l.Key))).ToList();
            links.AddRange(tb.Where(l => !bSet.Contains(l.Key) && !oSet.Contains(l.Key)));
            if (links.Select(l => l.Key).SequenceEqual((sl.GetValueOrDefault(k) ?? []).Select(l => l.Key))) continue; // unchanged
            kind.RemoveNodes();
            foreach (var group in links.GroupBy(l => l.From))
            {
                var from = new XElement(group.First().FromElement);
                from.RemoveNodes();
                foreach (var l in group) from.Add(new XElement(l.To));
                kind.Add(from);
            }
        }
    }

    private sealed record Link(string From, XElement FromElement, XElement To, string Key);

    private static Dictionary<string, List<Link>> Links(XDocument? doc)
    {
        var result = new Dictionary<string, List<Link>>();
        if (doc?.Root?.Element("associations") is not { } assoc) return result;
        foreach (var kind in assoc.Elements())
        {
            var list = new List<Link>();
            foreach (var from in kind.Elements())
            {
                var fromId = (string?)from.Attribute("id") ?? Text(from)!;
                foreach (var to in from.Elements()) list.Add(new Link(fromId, from, to, fromId + "→" + Text(to)));
            }
            result[kind.Name.LocalName] = list;
        }
        return result;
    }

    // ---------------------------------------------------------------- diff

    public sealed record EntityChange(string Id, string Change, string? Name, double[]? Location, List<string> Fields);

    /// <summary>What changed between two versions of a Terry XML file, per entity.</summary>
    public static List<EntityChange> Diff(string? beforeText, string? afterText)
    {
        var b = beforeText is null ? [] : Entities(TerryXml.Parse(beforeText));
        var a = afterText is null ? [] : Entities(TerryXml.Parse(afterText));
        var result = new List<EntityChange>();
        foreach (var (id, e) in a)
        {
            if (!b.TryGetValue(id, out var old)) { result.Add(new EntityChange(id, "added", Name(e), Location(e), [])); continue; }
            if (Text(old) == Text(e)) continue;
            result.Add(new EntityChange(id, "changed", Name(e), Location(e) ?? Location(old), ChangedFields(old, e)));
        }
        foreach (var (id, e) in b)
            if (!a.ContainsKey(id)) result.Add(new EntityChange(id, "removed", Name(e), Location(e), []));
        return result;
    }

    private static string? Name(XElement e) =>
        (string?)e.Attribute("name")
        ?? ((string?)e.Element("ECMesh")?.Attribute("model_path") is { } m ? Path.GetFileNameWithoutExtension(m) : null);

    private static List<string> ChangedFields(XElement b, XElement a)
    {
        var fields = new List<string>();
        var bc = Children(b);
        var ac = Children(a);
        foreach (var k in bc.Keys.Union(ac.Keys))
        {
            var bx = bc.GetValueOrDefault(k);
            var ax = ac.GetValueOrDefault(k);
            if (bx is null) { fields.Add($"+{k}"); continue; }
            if (ax is null) { fields.Add($"-{k}"); continue; }
            if (Text(bx) == Text(ax)) continue;
            var attrs = bx.Attributes().Select(x => x.Name).Union(ax.Attributes().Select(x => x.Name))
                .Where(n => (string?)bx.Attribute(n) != (string?)ax.Attribute(n)).Select(n => $"{k}.{n.LocalName}").ToList();
            fields.AddRange(attrs.Count > 0 ? attrs : [k]);
        }
        foreach (var n in b.Attributes().Select(x => x.Name).Union(a.Attributes().Select(x => x.Name)))
            if ((string?)b.Attribute(n) != (string?)a.Attribute(n)) fields.Add(n.LocalName);
        return fields;
    }
}
