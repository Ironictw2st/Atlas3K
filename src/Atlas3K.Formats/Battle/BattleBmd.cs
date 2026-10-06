using System.Globalization;
using System.Reflection;
using System.Text;
using System.Text.Json;

namespace Atlas3K.Formats.Battle;

/// <summary>
/// One element of a battle BMD (FASTBIN0 v35 BATTLE_MAP_DEFINITION_DATA: a battle tile's bmd_data.bin,
/// &lt;climate&gt;_procedural_bmd_data.bin, bmd_nogo_data.bin). The tree mirrors BOB's debug .xml of the same file: same
/// tags, attribute names and order. Attribute values are typed (the layout table's type for that field).
/// </summary>
public sealed class BmdNode(string tag)
{
    public string Tag { get; } = tag;
    public List<BmdAttr> Attrs { get; } = [];
    public List<BmdNode> Children { get; } = [];
    /// <summary>Text content (a KEY / value / item element), or null.</summary>
    public string? Text { get; set; }

    public BmdNode Attr(string name, string type, object value)
    {
        Attrs.Add(new BmdAttr(name, type, value));
        return this;
    }

    public BmdNode Add(BmdNode child)
    {
        Children.Add(child);
        return this;
    }

    public BmdNode Child(string tag) => Children.First(c => c.Tag == tag);
    public BmdNode? Find(string tag) => Children.FirstOrDefault(c => c.Tag == tag);
    public object Get(string name) => Attrs.First(a => a.Name == name).Value;
    public void Set(string name, object value)
    {
        var i = Attrs.FindIndex(a => a.Name == name);
        Attrs[i] = Attrs[i] with { Value = value };
    }
}

public sealed record BmdAttr(string Name, string Type, object Value);

/// <summary>
/// Layout-driven codec for battle BMD files. The layout table (Battle/Data/bmd_layout.json, shared with
/// research/battle_build/bmd_codec.py) lists each element's binary fields in file order:
/// ["a", name, type] attribute, ["e", tag] child element, ["l", container, item] container element holding a u32 count
/// and its items (optional 4th entry: the parent name its items are looked up under), ["L", item] u32 count and items directly under the element, ["t", type] text. Types: u8, bool, u16,
/// i16, u32, i32, u64, i64, f32, f64, str (u16 length + UTF-8), ver (u16 serialise_version). A layout is looked up as
/// "parent&gt;tag", then "tag". Bin -> tree -> bin and bin -> tree -> xml are identical to BOB's files on the corpus
/// (all bmd files of the four kit battle maps, 2026-10-06).
/// </summary>
public static class BattleBmd
{
    public const string RootTag = "BATTLE_MAP_DEFINITION_DATA";

    private static readonly Lazy<Dictionary<string, string[][]>> LayoutTable = new(LoadLayout);

    private static Dictionary<string, string[][]> LoadLayout()
    {
        using var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("Atlas3K.bmd_layout.json")
                      ?? throw new InvalidOperationException("bmd_layout.json resource missing");
        using var doc = JsonDocument.Parse(s);
        var table = new Dictionary<string, string[][]>(StringComparer.Ordinal);
        foreach (var p in doc.RootElement.EnumerateObject())
            table[p.Name] = p.Value.EnumerateArray().Select(op => op.EnumerateArray().Select(x => x.GetString()!).ToArray()).ToArray();
        return table;
    }

    public static string[][] Layout(string tag, string parent)
    {
        var t = LayoutTable.Value;
        if (t.TryGetValue($"{parent}>{tag}", out var l) || t.TryGetValue(tag, out l)) return l;
        throw new KeyError($"no bmd layout for {parent}>{tag}");
    }

    /// <summary>The parent name an "l" op's items are looked up under: the op's optional 4th entry (a context such as
    /// "polylines_list", whose HINT_POLYLINE items differ from those of "polylines"), else the container tag.</summary>
    private static string ItemParent(string[] op) => op.Length > 3 ? op[3] : op[1];

    public sealed class KeyError(string message) : Exception(message);

    // ---- read ----

    public static BmdNode Read(ReadOnlySpan<byte> data)
    {
        if (data.Length < 10 || !data[..8].SequenceEqual("FASTBIN0"u8)) throw new InvalidDataException("not a FASTBIN0 bmd");
        var pos = 8;
        var root = ReadNode(data, ref pos, RootTag, "");
        if (pos != data.Length) throw new InvalidDataException($"bmd: {data.Length - pos} trailing bytes");
        return root;
    }

    private static BmdNode ReadNode(ReadOnlySpan<byte> d, ref int pos, string tag, string parent)
    {
        var n = new BmdNode(tag);
        foreach (var op in Layout(tag, parent))
        {
            switch (op[0])
            {
                case "a": n.Attrs.Add(new BmdAttr(op[1], op[2], ReadScalar(d, ref pos, op[2]))); break;
                case "e": n.Children.Add(ReadNode(d, ref pos, op[1], tag)); break;
                case "l":
                {
                    var c = new BmdNode(op[1]);
                    var count = (uint)ReadScalar(d, ref pos, "u32");
                    for (var i = 0; i < count; i++) c.Children.Add(ReadNode(d, ref pos, op[2], ItemParent(op)));
                    n.Children.Add(c);
                    break;
                }
                case "L":
                {
                    var count = (uint)ReadScalar(d, ref pos, "u32");
                    for (var i = 0; i < count; i++) n.Children.Add(ReadNode(d, ref pos, op[1], tag));
                    break;
                }
                case "t": n.Text = (string)ReadScalar(d, ref pos, op[1]); break;
                default: throw new InvalidDataException($"bad layout op {op[0]}");
            }
        }
        return n;
    }

    private static object ReadScalar(ReadOnlySpan<byte> d, ref int pos, string type)
    {
        object v;
        switch (type)
        {
            case "u8": v = d[pos]; pos += 1; break;
            case "bool": v = d[pos] != 0; pos += 1; break;
            case "u16" or "ver": v = BitConverter.ToUInt16(d[pos..]); pos += 2; break;
            case "i16": v = BitConverter.ToInt16(d[pos..]); pos += 2; break;
            case "u32": v = BitConverter.ToUInt32(d[pos..]); pos += 4; break;
            case "i32": v = BitConverter.ToInt32(d[pos..]); pos += 4; break;
            case "u64": v = BitConverter.ToUInt64(d[pos..]); pos += 8; break;
            case "i64": v = BitConverter.ToInt64(d[pos..]); pos += 8; break;
            case "f32": v = BitConverter.ToSingle(d[pos..]); pos += 4; break;
            case "f64": v = BitConverter.ToDouble(d[pos..]); pos += 8; break;
            case "str":
            {
                var len = BitConverter.ToUInt16(d[pos..]); pos += 2;
                v = Encoding.UTF8.GetString(d.Slice(pos, len)); pos += len;
                break;
            }
            default: throw new InvalidDataException($"bad bmd type {type}");
        }
        return v;
    }

    // ---- write ----

    public static byte[] Write(BmdNode root)
    {
        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms);
        w.Write("FASTBIN0"u8);
        WriteNode(w, root, "");
        w.Flush();
        return ms.ToArray();
    }

    private static void WriteNode(BinaryWriter w, BmdNode n, string parent)
    {
        int ai = 0, ci = 0;
        foreach (var op in Layout(n.Tag, parent))
        {
            switch (op[0])
            {
                case "a":
                {
                    var a = n.Attrs[ai++];
                    if (a.Name != op[1]) throw new InvalidDataException($"{n.Tag}: attribute {a.Name} where {op[1]} is expected");
                    WriteScalar(w, op[2], a.Value);
                    break;
                }
                case "e":
                {
                    var c = n.Children[ci++];
                    if (c.Tag != op[1]) throw new InvalidDataException($"{n.Tag}: child {c.Tag} where {op[1]} is expected");
                    WriteNode(w, c, n.Tag);
                    break;
                }
                case "l":
                {
                    var c = n.Children[ci++];
                    if (c.Tag != op[1]) throw new InvalidDataException($"{n.Tag}: child {c.Tag} where list {op[1]} is expected");
                    w.Write((uint)c.Children.Count);
                    foreach (var item in c.Children) WriteNode(w, item, ItemParent(op));
                    break;
                }
                case "L":
                {
                    var items = new List<BmdNode>();
                    while (ci < n.Children.Count && n.Children[ci].Tag == op[1]) items.Add(n.Children[ci++]);
                    w.Write((uint)items.Count);
                    foreach (var item in items) WriteNode(w, item, n.Tag);
                    break;
                }
                case "t": WriteScalar(w, op[1], n.Text ?? ""); break;
            }
        }
    }

    private static void WriteScalar(BinaryWriter w, string type, object v)
    {
        switch (type)
        {
            case "u8": w.Write(Convert.ToByte(v)); break;
            case "bool": w.Write((byte)((bool)v ? 1 : 0)); break;
            case "u16" or "ver": w.Write(Convert.ToUInt16(v)); break;
            case "i16": w.Write(Convert.ToInt16(v)); break;
            case "u32": w.Write(Convert.ToUInt32(v)); break;
            case "i32": w.Write(Convert.ToInt32(v)); break;
            case "u64": w.Write(Convert.ToUInt64(v)); break;
            case "i64": w.Write(Convert.ToInt64(v)); break;
            case "f32": w.Write((float)v); break;
            case "f64": w.Write((double)v); break;
            case "str":
            {
                var b = Encoding.UTF8.GetBytes((string)v);
                w.Write((ushort)b.Length);
                w.Write(b);
                break;
            }
            default: throw new InvalidDataException($"bad bmd type {type}");
        }
    }

    // ---- BOB's debug xml ----

    /// <summary>BOB's .xml dump of the same file (tab indented, single-quoted attributes, CRLF, "%f" floats truncated to
    /// BOB's 31 characters; non-zero meta_tags carry comments naming their tags).</summary>
    public static string ToXml(BmdNode root)
    {
        var meta = MetaCatalog(root);
        var sb = new StringBuilder();
        WriteXml(sb, root, 0, meta);
        return sb.ToString();
    }

    /// <summary>The META_TAG_KEYS types and values of a bmd tree, in file order.</summary>
    public static List<(string Type, List<string> Values)> MetaCatalog(BmdNode root) =>
        root.Find("META_TAG_KEYS")?.Find("meta_data_entries")?.Children
            .Select(e => ((string)e.Get("name"), e.Child("values").Children.Select(v => v.Text ?? "").ToList())).ToList() ?? [];

    private static void WriteXml(StringBuilder sb, BmdNode n, int depth, List<(string Type, List<string> Values)> meta)
    {
        var ind = new string('\t', depth);
        sb.Append(ind).Append('<').Append(n.Tag);
        foreach (var a in n.Attrs) sb.Append(' ').Append(a.Name).Append("='").Append(Format(a.Type, a.Value)).Append('\'');
        if (n.Tag == "meta_tags" && MetaComments(n, meta) is { Count: > 0 } com)
        {
            sb.Append(">\r\n");
            foreach (var c in com) sb.Append(ind).Append("\t<!-- ").Append(c).Append(" -->\r\n");
            sb.Append(ind).Append("</").Append(n.Tag).Append(">\r\n");
            return;
        }
        if (n.Text is not null)
        {
            sb.Append('>').Append(n.Text).Append("</").Append(n.Tag).Append(">\r\n");
            return;
        }
        if (n.Children.Count == 0)
        {
            sb.Append("/>\r\n");
            return;
        }
        sb.Append(">\r\n");
        foreach (var c in n.Children) WriteXml(sb, c, depth + 1, meta);
        sb.Append(ind).Append("</").Append(n.Tag).Append(">\r\n");
    }

    private static List<string> MetaComments(BmdNode n, List<(string Type, List<string> Values)> meta)
    {
        var flags = Convert.ToUInt64(n.Get("flags"));
        var mask = Convert.ToUInt64(n.Get("mask"));
        var outp = new List<string>();
        if (flags == 0 && mask == 0) return outp;
        var bits = meta.SelectMany(t => t.Values.Select(v => (t.Type, v))).ToList();
        var sel = bits.Where((b, i) => i < 64 && (flags >> i & 1) != 0).Select(b => $"{b.Type}.{b.v}").ToList();
        var msel = bits.Where((b, i) => i < 64 && (mask >> i & 1) != 0).Select(b => b.Type).Distinct().ToList();
        if (sel.Count > 0) outp.Add("flags = " + string.Join("; ", sel) + ";");
        if (msel.Count > 0) outp.Add("mask = " + string.Join("; ", msel) + ";");
        return outp;
    }

    public static string Format(string type, object v) => type switch
    {
        "bool" => (bool)v ? "true" : "false",
        "f32" => Truncate(Fixed6((float)v)),
        "f64" => Truncate(Fixed6((double)v)),
        _ => Convert.ToString(v, CultureInfo.InvariantCulture) ?? "",
    };

    /// <summary>MSVC "%f": the exact binary value rounded to 6 decimals, ties away from zero; a negative value (or -0)
    /// that rounds to zero keeps its sign.</summary>
    public static string Fixed6(double v)
    {
        if (double.IsNaN(v)) return "nan";
        if (double.IsInfinity(v)) return v > 0 ? "inf" : "-inf";
        var neg = v < 0 || (v == 0 && double.IsNegative(v));
        var bits = BitConverter.DoubleToInt64Bits(Math.Abs(v));
        var exp = (int)((bits >> 52) & 0x7ff);
        var man = bits & 0xfffffffffffffL;
        if (exp == 0) exp = 1; else man |= 1L << 52;
        exp -= 1075;
        // value = man * 2^exp; q = round_half_up(value * 10^6)
        System.Numerics.BigInteger num = man, den = 1;
        if (exp > 0) num <<= exp; else den <<= -exp;
        num *= 1_000_000;
        var q = System.Numerics.BigInteger.DivRem(num, den, out var rem);
        if (rem * 2 >= den) q += 1;
        var digits = q.ToString(CultureInfo.InvariantCulture).PadLeft(7, '0');
        var s = digits[..^6] + "." + digits[^6..];
        return neg ? "-" + s : s;
    }

    // BOB prints floats with "%f" into a 32-byte buffer
    private static string Truncate(string s) => s.Length > 31 ? s[..31] : s;
}
