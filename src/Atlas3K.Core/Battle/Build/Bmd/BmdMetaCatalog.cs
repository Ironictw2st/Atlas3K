using System.Xml.Linq;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// The META_TAG_KEYS a battle bmd_data.bin carries: every bmd_export_types value whose group is a battle layer group
/// (bmd_layer_groups is_battle = 1), from the kit's raw_data/db. BOB adds them in DB record order
/// (BMD_META_TAG_COLLECTION::add_available_meta_data), so types appear in first-use order with their values in record
/// order, and the checksum mixes every value in that same order. A tag's bit is its position over all values in file
/// order. Checked: checksum 124565231 on the 190E and vanilla kits (2026-10-06).
/// </summary>
public sealed class BmdMetaCatalog
{
    public List<(string Type, List<string> Values)> Types { get; } = [];
    public uint Checksum { get; private set; }

    /// <summary>Season codes in the order BOB lists them in META_DATA_KEYS when an object has every season.</summary>
    public static readonly string[] SeasonCatalog = ["ha", "au", "wi", "sp", "su"];

    public static BmdMetaCatalog FromKit(string rawData)
    {
        var db = Path.Combine(rawData, "db");
        var groups = XDocument.Load(Path.Combine(db, "bmd_layer_groups.xml")).Root!.Elements("bmd_layer_groups")
            .Where(g => g.Element("is_battle")?.Value.Trim() == "1").Select(g => g.Element("key")?.Value.Trim() ?? "").ToHashSet();
        var c = new BmdMetaCatalog();
        foreach (var r in XDocument.Load(Path.Combine(db, "bmd_export_types.xml")).Root!.Elements("bmd_export_types"))
        {
            var group = r.Element("group")?.Value.Trim() ?? "";
            var name = r.Element("name")?.Value.Trim() ?? "";
            if (!groups.Contains(group)) continue;
            var t = c.Types.FindIndex(x => x.Type == group);
            if (t < 0) { c.Types.Add((group, [])); t = c.Types.Count - 1; }
            c.Types[t].Values.Add(name);
            c.Checksum = Mix(c.Checksum, StringHash(name));
        }
        return c;
    }

    /// <summary>Flags and mask of a comma-separated tag list: each tag's value bit, and every bit of its type.</summary>
    public (ulong Flags, ulong Mask) Encode(string tags)
    {
        ulong flags = 0, mask = 0;
        foreach (var tag in tags.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var bit = 0;
            foreach (var (_, values) in Types)
            {
                var i = values.IndexOf(tag);
                if (i >= 0)
                {
                    flags |= 1UL << (bit + i);
                    for (var k = 0; k < values.Count; k++) mask |= 1UL << (bit + k);
                }
                bit += values.Count;
            }
        }
        return (flags, mask);
    }

    // empireutility: BMD_META_TAG_COLLECTION checksum (research/bob_re/meta_checksum)
    private static uint Mix(uint h, uint v)
    {
        var b = (int)(((v ^ h) + 13) & 0x1f);
        return ((h << (b ^ 31)) | (h >> b)) ^ v;
    }

    private static uint StringHash(string s)
    {
        var d = System.Text.Encoding.ASCII.GetBytes(s);
        uint h = 0;
        for (var i = 0; i < d.Length; i += 4)
        {
            uint v = 0;
            for (var j = i; j < Math.Min(i + 4, d.Length); j++) v = v * 256 + d[j];
            h = Mix(h, v);
        }
        return h;
    }
}
