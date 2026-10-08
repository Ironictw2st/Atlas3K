using Atlas3K.Core;
using Atlas3K.Core.Collab;
using Atlas3K.Core.Editing;
using Atlas3K.Formats.Maps;
using Atlas3K.Formats.Terry;

namespace Atlas3K.Tests;

public class CollabMergeTests
{
    private static string Entity(string id, string pos, string model = "a.rigid_model_v2", string season = "") =>
        $"""
             <entity id="{id}">
               <ECMesh model_path="{model}" animation_path=""/>
               <ECCampaignProperties season_mask="{season}"/>
               <ECTransform position="{pos}" rotation="0 0 0" scale="1 1 1" pivot="0 0 0"/>
             </entity>

         """;

    private static string Layer(string entities, string links = "") =>
        ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<layer version=\"35\">\n  <entities>\n" + entities + "  </entities>\n"
         + "  <associations>\n" + (links.Length == 0 ? "    <Logical/>\n" : "    <Logical>\n" + links + "    </Logical>\n")
         + "    <Transform/>\n  </associations>\n</layer>\n").ReplaceLineEndings("\n");

    private static string Link(string from, params string[] to) =>
        $"      <from id=\"{from}\">\n" + string.Concat(to.Select(t => $"        <to id=\"{t}\"/>\n")) + "      </from>\n";

    private const string A = "1000000000000aa", B = "1000000000000bb", C = "1000000000000cc", D = "1000000000000dd";

    [Fact]
    public void Unchanged_OnOneSide_TakesTheOther()
    {
        var b = Layer(Entity(A, "1 0 1"));
        var o = Layer(Entity(A, "2 0 1"));
        Assert.Equal(o, TerryXmlMerge.Merge(b, o, b, "x.layer").Text);
        Assert.Equal(o, TerryXmlMerge.Merge(b, b, o, "x.layer").Text);
    }

    [Fact]
    public void DifferentEntities_MergeCleanly_AndKeepTerryLayout()
    {
        var b = Layer(Entity(A, "1 0 1") + Entity(B, "5 0 5"));
        var o = Layer(Entity(A, "2 0 1") + Entity(B, "5 0 5"));
        var t = Layer(Entity(A, "1 0 1") + Entity(B, "5 0 6"));
        var r = TerryXmlMerge.Merge(b, o, t, "x.layer");
        Assert.Empty(r.Conflicts);
        Assert.Equal(Layer(Entity(A, "2 0 1") + Entity(B, "5 0 6")), r.Text);
    }

    [Fact]
    public void AddsAndDeletes_FromBothSides()
    {
        var b = Layer(Entity(A, "1 0 1") + Entity(B, "5 0 5"));
        var o = Layer(Entity(A, "1 0 1") + Entity(B, "5 0 5") + Entity(C, "9 0 9"));
        var t = Layer(Entity(A, "1 0 1") + Entity(D, "7 0 7"));
        var r = TerryXmlMerge.Merge(b, o, t, "x.layer");
        Assert.Empty(r.Conflicts);
        Assert.Equal(Layer(Entity(A, "1 0 1") + Entity(D, "7 0 7") + Entity(C, "9 0 9")), r.Text);
    }

    [Fact]
    public void SameEntity_DifferentComponents_MergeByAttribute()
    {
        var b = Layer(Entity(A, "1 0 1"));
        var o = Layer(Entity(A, "2 0 1"));
        var t = Layer(Entity(A, "1 0 1", season: "season_spring"));
        var r = TerryXmlMerge.Merge(b, o, t, "x.layer");
        Assert.Empty(r.Conflicts);
        Assert.Equal(Layer(Entity(A, "2 0 1", season: "season_spring")), r.Text);
    }

    [Fact]
    public void SameAttribute_DifferentValues_IsAConflict_KeepingOurs()
    {
        var b = Layer(Entity(A, "1 0 1"));
        var o = Layer(Entity(A, "2 0 1"));
        var t = Layer(Entity(A, "3 0 4"));
        var r = TerryXmlMerge.Merge(b, o, t, "x.layer");
        var c = Assert.Single(r.Conflicts);
        Assert.Equal("attribute", c.Kind);
        Assert.Equal($"{A}/ECTransform.position", c.Target);
        Assert.Equal([2.0, 1.0], c.Location!);
        Assert.Equal(o, r.Text);
    }

    [Fact]
    public void EditAgainstDelete_IsAConflict()
    {
        var b = Layer(Entity(A, "1 0 1") + Entity(B, "5 0 5"));
        var o = Layer(Entity(A, "1 0 1"));
        var t = Layer(Entity(A, "1 0 1") + Entity(B, "6 0 5"));
        var r = TerryXmlMerge.Merge(b, o, t, "x.layer");
        Assert.Equal("entity", Assert.Single(r.Conflicts).Kind);
    }

    [Fact]
    public void Associations_MergeAsLinkSets()
    {
        var ents = Entity(A, "1 0 1") + Entity(B, "5 0 5") + Entity(C, "9 0 9");
        var b = Layer(ents, Link(A, B));
        var o = Layer(ents, Link(A, B, C));
        var t = Layer(ents);
        var r = TerryXmlMerge.Merge(b, o, t, "x.layer");
        Assert.Empty(r.Conflicts);
        Assert.Equal(Layer(ents, Link(A, C)), r.Text);
    }

    [Fact]
    public void ResolveTheirs_ReplacesTheConflictedAttribute()
    {
        var dir = Directory.CreateTempSubdirectory("a3k_collab_");
        try
        {
            var b = Layer(Entity(A, "1 0 1"));
            var o = Layer(Entity(A, "2 0 1", season: "x"));
            var t = Layer(Entity(A, "3 0 4"));
            string P(string n) => Path.Combine(dir.FullName, n);
            File.WriteAllText(P("base"), b);
            File.WriteAllText(P("m.layer"), o);
            File.WriteAllText(P("theirs"), t);
            var r = MapMerge.Merge(P("base"), P("m.layer"), P("theirs"), P("m.layer"), "m.layer");
            Assert.Single(r.Conflicts);
            var set = new ConflictSet(P("conflicts"));
            set.Add(dir.FullName, "m.layer", r.Conflicts, P("theirs"));
            Assert.Equal(1, ConflictResolver.Resolve(set, "theirs"));
            Assert.Equal(Layer(Entity(A, "3 0 4", season: "x")), File.ReadAllText(P("m.layer")));
            Assert.Empty(set.Open());
        }
        finally { dir.Delete(true); }
    }

    [Fact]
    public void Rasters_MergePerPixel()
    {
        var dir = Directory.CreateTempSubdirectory("a3k_collab_");
        try
        {
            string P(string n) => Path.Combine(dir.FullName, n);
            Raster<ushort> R(params (int X, int Y, ushort V)[] px)
            {
                var r = new Raster<ushort>(128, 128);
                foreach (var (x, y, v) in px) r[x, y] = v;
                return r;
            }
            TiffMap.WriteGray16(P("base.tif"), R());
            TiffMap.WriteGray16(P("h.tif"), R((1, 1, 10), (100, 100, 5)));
            TiffMap.WriteGray16(P("theirs.tif"), R((2, 2, 20), (100, 100, 6)));
            var r = MapMerge.Merge(P("base.tif"), P("h.tif"), P("theirs.tif"), P("h.tif"), "h.tif");
            var c = Assert.Single(r.Conflicts);
            Assert.Equal([64, 64, 64, 64], c.Rect!);
            var merged = TiffMap.ReadGray16(P("h.tif"));
            Assert.Equal(10, merged[1, 1]);
            Assert.Equal(20, merged[2, 2]);
            Assert.Equal(5, merged[100, 100]);

            var set = new ConflictSet(P("conflicts"));
            set.Add(dir.FullName, "h.tif", r.Conflicts, P("theirs.tif"));
            ConflictResolver.Resolve(set, "theirs");
            Assert.Equal(6, TiffMap.ReadGray16(P("h.tif"))[100, 100]);
            Assert.Equal(10, TiffMap.ReadGray16(P("h.tif"))[1, 1]);
        }
        finally { dir.Delete(true); }
    }

    [Fact]
    public void Diff_ReportsEntityChanges()
    {
        var b = Layer(Entity(A, "1 0 1") + Entity(B, "5 0 5"));
        var a = Layer(Entity(A, "2 0 1") + Entity(C, "9 0 9"));
        var d = TerryXmlMerge.Diff(b, a).ToDictionary(c => c.Id);
        Assert.Equal("changed", d[A].Change);
        Assert.Equal(["ECTransform.position"], d[A].Fields);
        Assert.Equal("added", d[C].Change);
        Assert.Equal("removed", d[B].Change);
    }

    [Fact]
    public void AkLayers_MergeEditsFromBothSides_ByteExact()
    {
        var dir = TestKits.VanillaPaths.AkTerrainDir;
        if (!Directory.Exists(dir)) return; // data not available on this machine
        var files = Directory.GetFiles(dir, "*.layer").OrderByDescending(f => new FileInfo(f).Length).Take(20).ToList();
        Parallel.ForEach(files, f =>
        {
            var b = File.ReadAllText(f);
            var ids = TerryXmlMerge.Entities(TerryXml.Parse(b)).Keys.ToList();
            if (ids.Count < 2) return;
            string Edit(string text, string id)
            {
                var doc = LayerDocument.Parse(text);
                doc.SetName(id, "edited_" + id);
                return doc.ToText();
            }
            var o = Edit(b, ids[0]);
            var t = Edit(b, ids[^1]);
            var r = TerryXmlMerge.Merge(b, o, t, Path.GetFileName(f));
            Assert.Empty(r.Conflicts);
            Assert.Equal(Edit(o, ids[^1]), r.Text);
        });
    }

    [Fact]
    public void Package_ExportImport_MergesOntoADivergedCopy_AndUndoes()
    {
        var root = Directory.CreateTempSubdirectory("a3k_patch_");
        try
        {
            ProjectPaths Kit(string name) => new()
            {
                AssemblyKitRoot = Path.Combine(root.FullName, name),
                OutputRoot = Path.Combine(root.FullName, name + "_out"),
                MapName = "m",
            };
            void Seed(ProjectPaths p, string layer, params (int X, int Y, ushort V)[] px)
            {
                Directory.CreateDirectory(p.AkTerrainDir);
                File.WriteAllText(Path.Combine(p.AkTerrainDir, "m.l1.layer"), layer);
                var r = new Raster<ushort>(256, 256);
                foreach (var (x, y, v) in px) r[x, y] = v;
                TiffMap.WriteGray16(Path.Combine(p.AkTerrainDir, "m.height.1.tif"), r);
            }
            var baseLayer = Layer(Entity(A, "1 0 1") + Entity(B, "5 0 5"));
            var baseCopy = Kit("base");
            Seed(baseCopy, baseLayer);

            var alice = Kit("alice");
            Seed(alice, Layer(Entity(A, "2 0 1") + Entity(B, "5 0 5")), (10, 10, 100));
            var package = Path.Combine(root.FullName, "alice.a3kpatch");
            var m = PatchPackage.Export(PatchSources.FromFolder(alice, baseCopy.AkTerrainDir), package, "m", "alice's edits");
            Assert.Equal(2, m.Files.Count);
            Assert.Equal("cells", m.Files.Single(f => f.Path.EndsWith(".tif")).Storage);

            // Bob changed other things meanwhile.
            var bob = Kit("bob");
            Seed(bob, Layer(Entity(A, "1 0 1") + Entity(B, "5 0 9")), (200, 200, 7));
            var journal = new FileJournal(PatchSources.ImportDir(bob));
            var set = new ConflictSet(Path.Combine(journal.Dir, "conflicts"));
            var dry = PatchPackage.Import(package, bob.AssemblyKitRoot, journal, set, dryRun: true);
            Assert.All(dry.Files, f => Assert.Equal("merged", f.Action));
            Assert.Equal(Layer(Entity(A, "1 0 1") + Entity(B, "5 0 9")), File.ReadAllText(Path.Combine(bob.AkTerrainDir, "m.l1.layer")));

            var r = PatchPackage.Import(package, bob.AssemblyKitRoot, journal, set);
            Assert.Equal(0, r.Conflicts);
            Assert.Equal(Layer(Entity(A, "2 0 1") + Entity(B, "5 0 9")), File.ReadAllText(Path.Combine(bob.AkTerrainDir, "m.l1.layer")));
            var h = TiffMap.ReadGray16(Path.Combine(bob.AkTerrainDir, "m.height.1.tif"));
            Assert.Equal(100, h[10, 10]);
            Assert.Equal(7, h[200, 200]);

            // Importing twice is a no-op; undo restores Bob's files.
            Assert.All(PatchPackage.Import(package, bob.AssemblyKitRoot, journal, set).Files, f => Assert.Equal("already applied", f.Action));
            journal.Undo();
            Assert.Equal(Layer(Entity(A, "1 0 1") + Entity(B, "5 0 9")), File.ReadAllText(Path.Combine(bob.AkTerrainDir, "m.l1.layer")));

            // On an unchanged base the package applies byte for byte.
            PatchPackage.Import(package, baseCopy.AssemblyKitRoot, new FileJournal(PatchSources.ImportDir(baseCopy)),
                new ConflictSet(Path.Combine(root.FullName, "c2")));
            foreach (var f in new[] { "m.l1.layer", "m.height.1.tif" })
                Assert.Equal(File.ReadAllBytes(Path.Combine(alice.AkTerrainDir, f)), File.ReadAllBytes(Path.Combine(baseCopy.AkTerrainDir, f)));
        }
        finally { root.Delete(true); }
    }
}
