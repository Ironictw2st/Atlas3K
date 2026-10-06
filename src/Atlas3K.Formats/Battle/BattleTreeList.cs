using System.Text;

namespace Atlas3K.Formats.Battle;

/// <summary>One tree of a battle tile's tree list: model key, position, scale, yaw byte (256 steps per turn).</summary>
public readonly record struct BattleTreeItem(string Key, float X, float Y, float Z, float Scale, byte Rotation, bool IsFreeform);

/// <summary>
/// &lt;climate&gt;.tree_list.bin (FASTBIN0 TREE_LIST v3) and BOB's .xml dump of it, as bob_vegetation writes them
/// (FUN_18000afd0): the climate's items sorted by (model key bytes, x, y, z) (FUN_180019370 / 1800178f0), grouped into
/// EMPIREUTILITY::TREE_LIST (a CA hash map keyed by model, written in its list order: <see cref="CaHash.HashMapOrder"/>
/// of the sorted keys). File: "FASTBIN0", u16 3, u32 model count, per model u16 length + latin1 key, u32 item count,
/// items of x, y, z, scale (f32), rotation (u8), is_freeform (u8).
/// </summary>
public static class BattleTreeList
{
    public static List<(string Key, List<BattleTreeItem> Items)> Arrange(IEnumerable<BattleTreeItem> items)
    {
        var sorted = items.ToList();
        sorted.Sort((a, b) =>
        {
            var c = string.CompareOrdinal(a.Key, b.Key);
            if (c != 0) return c;
            c = a.X.CompareTo(b.X);
            if (c != 0) return c;
            c = a.Y.CompareTo(b.Y);
            return c != 0 ? c : a.Z.CompareTo(b.Z);
        });
        var byKey = new Dictionary<string, List<BattleTreeItem>>(StringComparer.Ordinal);
        foreach (var it in sorted)
        {
            if (!byKey.TryGetValue(it.Key, out var l)) byKey[it.Key] = l = [];
            l.Add(it);
        }
        return CaHash.HashMapOrder(sorted.Select(i => i.Key)).Select(k => (k, byKey[k])).ToList();
    }

    public static byte[] Write(IReadOnlyList<(string Key, List<BattleTreeItem> Items)> list)
    {
        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms);
        w.Write("FASTBIN0"u8);
        w.Write((ushort)3);
        w.Write((uint)list.Count);
        foreach (var (key, items) in list)
        {
            var kb = Encoding.Latin1.GetBytes(key);
            w.Write((ushort)kb.Length);
            w.Write(kb);
            w.Write((uint)items.Count);
            foreach (var t in items)
            {
                w.Write(t.X);
                w.Write(t.Y);
                w.Write(t.Z);
                w.Write(t.Scale);
                w.Write(t.Rotation);
                w.Write((byte)(t.IsFreeform ? 1 : 0));
            }
        }
        w.Flush();
        return ms.ToArray();
    }

    public static string ToXml(IReadOnlyList<(string Key, List<BattleTreeItem> Items)> list)
    {
        var sb = new StringBuilder();
        sb.Append("<TREE_LIST serialise_version='3'>\r\n\t<TREE_LIST>\r\n");
        foreach (var (key, items) in list)
        {
            sb.Append("\t\t<BATTLE_TREE_ITEM_VECTOR key='").Append(key).Append("'>\r\n\t\t\t<value>\r\n");
            foreach (var t in items)
                sb.Append("\t\t\t\t<BATTLE_TREE_ITEM x='").Append(BattleBmd.Fixed6(t.X)).Append("' y='").Append(BattleBmd.Fixed6(t.Y))
                  .Append("' z='").Append(BattleBmd.Fixed6(t.Z)).Append("' scale='").Append(BattleBmd.Fixed6(t.Scale))
                  .Append("' rotation='").Append(t.Rotation).Append("' is_freeform='").Append(t.IsFreeform ? "true" : "false").Append("'/>\r\n");
            sb.Append("\t\t\t</value>\r\n\t\t</BATTLE_TREE_ITEM_VECTOR>\r\n");
        }
        sb.Append("\t</TREE_LIST>\r\n</TREE_LIST>\r\n");
        return sb.ToString();
    }

    /// <summary>bob_vegetation FUN_180009fe0: yaw radians wrapped once into [0, 2π), then (int)(yaw · 256/2π).</summary>
    public static byte RotationByte(float yaw)
    {
        const float twoPi = 6.28318548f;
        if (yaw < 0f) yaw += twoPi;
        if (twoPi <= yaw) yaw += -twoPi;
        return (byte)(int)(yaw * 40.7436638f);
    }
}
