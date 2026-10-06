using System.Buffers.Binary;
using System.Globalization;
using System.Text;
using System.Xml.Linq;
using BitMiracle.LibTiff.Classic;

namespace Atlas3K.Core.Battle.Build;

/// <summary>
/// A kit tile's tile-database entry, _tile_database/TILES/_assembly_kit_&lt;id&gt;.bin + .xml (TILE v7, one VARIATION v10,
/// texture_set v2, no links). Terry writes it when the project is saved; BOB's TerryTile export reads it back and
/// rewrites it with the texture set reduced to the blend channels the tile uses.
/// </summary>
public sealed class TileDbEntry
{
    public string Name = "", TileSet = "_assembly_kit", Mask = "", Nogo = "";
    public int Width = 8, Height = 8;
    public byte R, G, B;
    public bool InfieldLodding = true, RandomRotatable = true, Encampable, Barbarian, UseAltLf;
    /// <summary>The "scalable" bool as a raw byte: Terry saves it uninitialised (0, 0x58, 0x8B seen) and BOB keeps it.</summary>
    public byte Scalable;
    public string CustomAlphaBlendTexture = "", CustomBlendTile = "";
    public string FactionKey = "";
    public string[] Channels = new string[8];
    public string Location = "", VariationName = "";
    public float MinHeight, Scale = 150, NormalStrength = 2, OverlapBorderSize = 1, ShadowCameraDepth;
    public int TriDensity = 128;
    public string BlendCommon = "", IndexCommon = "", NormalCommon = "", FogMask = "";
    public byte VR, VG, VB;
    public bool RequiresSeaInInfield, SeaWaterPlane, Subterranean;

    public TileDbEntry() { for (var i = 0; i < 8; i++) Channels[i] = ""; }

    public static TileDbEntry Read(byte[] b)
    {
        if (!b.AsSpan(0, 8).SequenceEqual("FASTBIN0"u8)) throw new InvalidDataException("tile entry: not FASTBIN0");
        var o = 8;
        ushort U16() { var v = BinaryPrimitives.ReadUInt16LittleEndian(b.AsSpan(o)); o += 2; return v; }
        int I32() { var v = BinaryPrimitives.ReadInt32LittleEndian(b.AsSpan(o)); o += 4; return v; }
        float F32() { var v = BinaryPrimitives.ReadSingleLittleEndian(b.AsSpan(o)); o += 4; return v; }
        byte U8() => b[o++];
        string S() { var n = U16(); var s = Encoding.Latin1.GetString(b, o, n); o += n; return s; }
        if (U16() != 7) throw new NotSupportedException("tile entry: only TILE v7");
        var e = new TileDbEntry { Name = S(), TileSet = S(), Mask = S(), Nogo = S(), Width = I32(), Height = I32() };
        e.R = U8(); e.G = U8(); e.B = U8();
        e.InfieldLodding = U8() != 0; e.RandomRotatable = U8() != 0;
        e.CustomAlphaBlendTexture = S(); e.Scalable = U8(); e.Encampable = U8() != 0; e.CustomBlendTile = S();
        if (I32() != 1) throw new NotSupportedException("tile entry: one variation expected");
        if (U16() != 10 || U16() != 2) throw new NotSupportedException("tile entry: VARIATION v10 / texture_set v2 expected");
        e.FactionKey = S();
        for (var i = 0; i < 8; i++) e.Channels[i] = S();
        e.Location = S(); e.VariationName = S();
        e.MinHeight = F32(); e.Scale = F32(); e.NormalStrength = F32(); e.OverlapBorderSize = F32();
        e.TriDensity = I32();
        e.BlendCommon = S(); e.IndexCommon = S(); e.NormalCommon = S();
        e.VR = U8(); e.VG = U8(); e.VB = U8();
        e.RequiresSeaInInfield = U8() != 0; e.ShadowCameraDepth = F32(); e.SeaWaterPlane = U8() != 0; e.Subterranean = U8() != 0;
        e.FogMask = S();
        if (I32() != 0 || I32() != 0) throw new NotSupportedException("tile entry: link targets / links not supported");
        e.Barbarian = U8() != 0; e.UseAltLf = U8() != 0;
        if (o != b.Length) throw new InvalidDataException($"tile entry: {b.Length - o} bytes left over");
        return e;
    }

    public byte[] ToBytes()
    {
        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms);
        void S(string s) { var bytes = Encoding.Latin1.GetBytes(s); w.Write((ushort)bytes.Length); w.Write(bytes); }
        w.Write("FASTBIN0"u8); w.Write((ushort)7);
        S(Name); S(TileSet); S(Mask); S(Nogo); w.Write(Width); w.Write(Height);
        w.Write(R); w.Write(G); w.Write(B);
        w.Write(InfieldLodding); w.Write(RandomRotatable);
        S(CustomAlphaBlendTexture); w.Write(Scalable); w.Write(Encampable); S(CustomBlendTile);
        w.Write(1); w.Write((ushort)10); w.Write((ushort)2);
        S(FactionKey);
        foreach (var c in Channels) S(c);
        S(Location); S(VariationName);
        w.Write(MinHeight); w.Write(Scale); w.Write(NormalStrength); w.Write(OverlapBorderSize);
        w.Write(TriDensity);
        S(BlendCommon); S(IndexCommon); S(NormalCommon);
        w.Write(VR); w.Write(VG); w.Write(VB);
        w.Write(RequiresSeaInInfield); w.Write(ShadowCameraDepth); w.Write(SeaWaterPlane); w.Write(Subterranean);
        S(FogMask);
        w.Write(0); w.Write(0);
        w.Write(Barbarian); w.Write(UseAltLf);
        return ms.ToArray();
    }

    /// <summary>The debug .xml BOB writes next to the .bin (CRLF, tabs, single-quoted attributes, %f floats).</summary>
    public string ToXml()
    {
        static string Bo(bool v) => v ? "true" : "false";
        static string F(float v) => v.ToString("F6", CultureInfo.InvariantCulture);
        static string A(string s) => s.Replace("&", "&amp;").Replace("'", "&apos;").Replace("<", "&lt;").Replace(">", "&gt;");
        var sb = new StringBuilder();
        sb.Append($"<TILE serialise_version='7' name='{A(Name)}' tile_set='{A(TileSet)}' mask='{A(Mask)}' nogo='{A(Nogo)}' width='{Width}' height='{Height}' " +
                  $"red='{R}' green='{G}' blue='{B}' requires_infield_lodding='{Bo(InfieldLodding)}' random_rotatable='{Bo(RandomRotatable)}' " +
                  $"custom_alpha_blend_texture='{A(CustomAlphaBlendTexture)}' scalable='{Bo(Scalable != 0)}' encampable='{Bo(Encampable)}' " +
                  $"custom_blend_tile='{A(CustomBlendTile)}' barbarian='{Bo(Barbarian)}' use_alt_lf='{Bo(UseAltLf)}'>\r\n");
        sb.Append("\t<VARIATIONS>\r\n");
        sb.Append($"\t\t<VARIATION serialise_version='10' location='{A(Location)}' name='{A(VariationName)}' min_height='{F(MinHeight)}' scale='{F(Scale)}' " +
                  $"normal_strength='{F(NormalStrength)}' overlap_border_size='{F(OverlapBorderSize)}' raw_data_tri_density='{TriDensity}' " +
                  $"blend_common='{A(BlendCommon)}' index_common='{A(IndexCommon)}' normal_common='{A(NormalCommon)}' red='{VR}' green='{VG}' blue='{VB}' " +
                  $"requires_sea_in_infield='{Bo(RequiresSeaInInfield)}' shadow_camera_depth='{F(ShadowCameraDepth)}' enable_sea_water_plane='{Bo(SeaWaterPlane)}' " +
                  $"is_subterranean='{Bo(Subterranean)}' fog_mask='{A(FogMask)}'>\r\n");
        string[] keys = ["red0", "green0", "blue0", "alpha0", "red1", "green1", "blue1", "alpha1"];
        sb.Append($"\t\t\t<texture_set serialise_version='2' faction_key='{A(FactionKey)}'");
        for (var i = 0; i < 8; i++) sb.Append($" {keys[i]}='{A(Channels[i])}'");
        sb.Append("/>\r\n");
        sb.Append("\t\t</VARIATION>\r\n\t</VARIATIONS>\r\n\t<TILE_LINK_TARGETS/>\r\n\t<TILE_LINKS/>\r\n</TILE>\r\n");
        return sb.ToString();
    }

    /// <summary>The entry Terry saves for a battle tile project (&lt;tile_database&gt;, size, texture channels). The
    /// scalable byte is uninitialised in Terry and comes out as 0 here.</summary>
    public static TileDbEntry FromTerry(string terryPath, string tileId)
    {
        var doc = XDocument.Load(terryPath);
        var data = doc.Descendants("pc").First(e => (string?)e.Attribute("type") == "QTU::ProjectTileWithVista").Element("data")!;
        var inner = data.Element("data")!;
        var db = inner.Element("tile_database")!;
        string A(XElement x, string n) => (string?)x.Attribute(n) ?? "";
        bool Bo(XElement x, string n) => A(x, n) == "true";
        var size = A(data, "size").Split('x');
        var colour = A(db, "colour").Split(' ', StringSplitOptions.RemoveEmptyEntries);
        var e = new TileDbEntry
        {
            Name = tileId, Width = int.Parse(size[0]), Height = int.Parse(size[1]),
            R = byte.Parse(colour[0]), G = byte.Parse(colour[1]), B = byte.Parse(colour[2]),
            InfieldLodding = Bo(db, "infield_tile"), RandomRotatable = Bo(db, "is_random_rotatable"),
            CustomAlphaBlendTexture = A(db, "custom_alpha_blend_texture"), Encampable = Bo(db, "is_encampable"),
            Location = $"terrain\\tiles\\battle\\_assembly_kit\\{tileId}\\", VariationName = tileId,
            NormalStrength = float.Parse(A(db, "normal_strength"), CultureInfo.InvariantCulture),
            TriDensity = int.Parse(A(data, "triangle_density")),
            NormalCommon = A(db, "normal_common"),
            RequiresSeaInInfield = Bo(db, "requires_sea_in_infield"),
            ShadowCameraDepth = float.Parse(A(db, "shadow_camera_depth"), CultureInfo.InvariantCulture),
            SeaWaterPlane = Bo(db, "sea_water_plane"), Subterranean = Bo(db, "is_subterranean"),
            FogMask = A(inner, "fog_mask_texture"), UseAltLf = Bo(db, "use_alternative_lf"),
        };
        for (var i = 0; i < 8; i++) e.Channels[i] = A(inner, $"texture_channel_{i}");
        return e;
    }
}

/// <summary>
/// The tile-database entry, both versions:
///  - Terry's save (an input to BOB): the kit's existing entry when there is one, else built from the .terry
///    (<see cref="TileDbEntry.FromTerry"/>); kept in memory as <c>ctx.Shared["tile_db_terry"]</c>;
///  - BOB's TerryTile rewrite (written): the same entry with the texture set reduced to the channels the blend map
///    uses, in channel order (channel 0 always), the rest empty.
/// </summary>
[BattleStepOrder(105)]
public sealed class BattleTileDbStep : IBattleBuildStep
{
    public string Name => "tile_db";

    public void Run(BattleBuildContext ctx, Action<string> log)
    {
        var tileId = Path.GetFileName(ctx.SourceTileDir.TrimEnd('\\', '/'));
        var saved = Path.Combine(ctx.TerryTileDbDir, ctx.TileDbStem + ".bin");
        TileDbEntry entry;
        if (File.Exists(saved)) entry = TileDbEntry.Read(File.ReadAllBytes(saved));
        else
        {
            entry = TileDbEntry.FromTerry(ctx.TerryFile, tileId);
            log("tile_db: no saved Terry entry, built from the .terry (scalable byte 0)");
        }
        ctx.Shared["tile_db_terry"] = entry;

        // the channel names come from the project (texture_channel_N), not the saved entry: BOB re-running on its own
        // output is a fixed point
        var used = UsedBlendChannels(ctx.SourceTileDir);
        var source = TileDbEntry.FromTerry(ctx.TerryFile, tileId).Channels;
        var k = 0;
        for (var c = 0; c < 8; c++)
            if (used[c]) entry.Channels[k++] = source[c];
        while (k < 8) entry.Channels[k++] = "";
        File.WriteAllBytes(Path.Combine(ctx.OutTileDbDir, ctx.TileDbStem + ".bin"), entry.ToBytes());
        File.WriteAllText(Path.Combine(ctx.OutTileDbDir, ctx.TileDbStem + ".xml"), entry.ToXml(), new UTF8Encoding(false));
    }

    /// <summary>Which of the 8 blend channels hold any non-zero weight (channel 0, the base, always counts). A project
    /// without a serialised blend layer uses channel 0 only.</summary>
    public static bool[] UsedBlendChannels(string tileDir)
    {
        var used = new bool[8];
        used[0] = true;
        var tif = Directory.EnumerateFiles(tileDir, "*.blend.*.tif").FirstOrDefault();
        if (tif is null) return used;
        using var t = Tiff.Open(tif, "r") ?? throw new IOException($"Cannot open {tif}");
        var spp = t.GetField(TiffTag.SAMPLESPERPIXEL)[0].ToInt();
        var h = t.GetField(TiffTag.IMAGELENGTH)[0].ToInt();
        var row = new byte[t.ScanlineSize()];
        for (var y = 0; y < h; y++)
        {
            t.ReadScanline(row, y);
            for (var i = 0; i < row.Length; i++)
                if (row[i] != 0) used[(i % spp) & 7] = true;
        }
        return used;
    }
}
