using Atlas3K.Formats.Battle;

namespace Atlas3K.Core.Battle.Build.Bmd;

/// <summary>
/// Builds bmd nodes in layout order: <see cref="Node"/> walks the element's layout (BattleBmd.Layout) and takes one
/// argument per field: a value for an attribute, a <see cref="BmdNode"/> for a child element, a list of item nodes for
/// a counted list, a string for text. Attribute types come from the layout, so a node is always writable.
/// </summary>
public static class BmdMake
{
    public static BmdNode Node(string tag, string parent, params object?[] args)
    {
        var n = new BmdNode(tag);
        var i = 0;
        foreach (var op in BattleBmd.Layout(tag, parent))
        {
            if (i >= args.Length) throw new ArgumentException($"{parent}>{tag}: too few values (at {op[0]} {op[1]})");
            var a = args[i++];
            switch (op[0])
            {
                case "a": n.Attrs.Add(new BmdAttr(op[1], op[2], Coerce(op[2], a!))); break;
                case "e":
                    var c = (BmdNode)a!;
                    if (c.Tag != op[1]) throw new ArgumentException($"{parent}>{tag}: {c.Tag} given for {op[1]}");
                    n.Children.Add(c);
                    break;
                case "l":
                    var list = new BmdNode(op[1]);
                    list.Children.AddRange((IEnumerable<BmdNode>?)a ?? []);
                    n.Children.Add(list);
                    break;
                case "L": n.Children.AddRange((IEnumerable<BmdNode>?)a ?? []); break;
                case "t": n.Text = (string)a!; break;
            }
        }
        if (i != args.Length) throw new ArgumentException($"{parent}>{tag}: {args.Length - i} values too many");
        return n;
    }

    private static object Coerce(string type, object v) => type switch
    {
        "u8" => Convert.ToByte(v),
        "bool" => (bool)v,
        "u16" or "ver" => Convert.ToUInt16(v),
        "i16" => Convert.ToInt16(v),
        "u32" => Convert.ToUInt32(v),
        "i32" => Convert.ToInt32(v),
        "u64" => Convert.ToUInt64(v),
        "i64" => Convert.ToInt64(v),
        "f32" => v is float f ? f : Convert.ToSingle(v),
        "f64" => Convert.ToDouble(v),
        _ => (string)v,
    };

    public static BmdNode MetaTags(ulong flags = 0, ulong mask = 0) => Node("meta_tags", "", 1, flags, mask);

    public static BmdNode Parent(int index = -1) => Node("parent_building_reference", "", 1, index);

    public static BmdNode Rgba(string tag, byte r, byte g, byte b, byte a) => Node(tag, "", r, g, b, a);

    public static BmdNode Flags(bool allowInOutfield, bool clamp, bool clampWater, uint seasons, bool visibleInSeenShroud) =>
        Node("flags", "", 4, allowInOutfield, clamp, clampWater, Node("meta_datas", "flags", 1, seasons), visibleInSeenShroud);

    /// <summary>3x4 transform (m00..m22 = the rotation-scale's columns, m30..m32 = position).</summary>
    public static BmdNode Transform12(string parent, double[] rowMajor3x3, float x, float y, float z) =>
        Node("transform", parent, Col(rowMajor3x3, 0, 0), Col(rowMajor3x3, 0, 1), Col(rowMajor3x3, 0, 2),
            Col(rowMajor3x3, 1, 0), Col(rowMajor3x3, 1, 1), Col(rowMajor3x3, 1, 2),
            Col(rowMajor3x3, 2, 0), Col(rowMajor3x3, 2, 1), Col(rowMajor3x3, 2, 2), x, y, z);

    /// <summary>4x4 transform (prefab instances, building slots).</summary>
    public static BmdNode Transform16(string parent, double[] rowMajor3x3, float x, float y, float z) =>
        Node("transform", parent, Col(rowMajor3x3, 0, 0), Col(rowMajor3x3, 0, 1), Col(rowMajor3x3, 0, 2), 0f,
            Col(rowMajor3x3, 1, 0), Col(rowMajor3x3, 1, 1), Col(rowMajor3x3, 1, 2), 0f,
            Col(rowMajor3x3, 2, 0), Col(rowMajor3x3, 2, 1), Col(rowMajor3x3, 2, 2), 0f, x, y, z, 1f);

    // record element m{c}{r} = rowMajor[r * 3 + c] (BmdRecords.WriteTransform)
    private static float Col(double[] m, int c, int r) => (float)m[r * 3 + c];
}
