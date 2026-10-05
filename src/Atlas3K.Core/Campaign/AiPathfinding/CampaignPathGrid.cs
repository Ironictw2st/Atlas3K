using Atlas3K.Formats.Maps;

namespace Atlas3K.Core.Campaign.AiPathfinding;

/// <summary>
/// The game's campaign movement grid (EMPIRECAMPAIGN::CAMPAIGN_PATHFINDER) as the campaign AI's offline analysis sees
/// it, rebuilt from pathfinding.ppd, map_data.esf and three DB values. Reverse-engineered from
/// empirecampaign.modder.x64.dll (CAMPAIGN_PATHFINDER constructor FUN_1811f7fa0, road application FUN_1812028c0, the
/// AI landmark search FUN_18059f480); see docs/hlp_spd.md.
///
///  - Edge byte per hex and direction (ppd): bits 0-5 index the 256-entry cost table, bit 6 is set to bit 7 on load;
///    the table holds the ppd move costs at i, i+64, i+128, i+192, the beach costs (campaign variables
///    pathfinding_land_to_sea / sea_to_land_beach_transition_action_point_cost) at 1 and 2, and the road cost
///    (campaign_map_roads, lowest threshold of the campaign) at 62.
///  - Roads: every road hex's masked edges get index 62; a road hex on a river (type 6) gets it on all six edges and
///    so do its neighbours' edges back to it.
///  - Settlements: edges between a slot hex (primary or port slot area) and a neighbour that is land (0), sea (1) or
///    another slot hex cost 0 both ways (observed: identical costs across a settlement and its ring in CA's files).
///  - Moves are allowed by hex type pairs (FUN_1805fa120 + FUN_1805d3a70); type 2 is impassable.
///  - Bridges (ppd): every hex of one side links to every hex of the other side at cost 500.
/// </summary>
public sealed class CampaignPathGrid
{
    public const uint NoEdge = uint.MaxValue;
    public const uint BridgeCost = 500;

    public int Width { get; }
    public int Height { get; }
    /// <summary>Hex type (byte 7 high nibble) per hex.</summary>
    public byte[] Types { get; }
    /// <summary>Cost of leaving hex h in direction d: Forward[h*6+d] (NoEdge when the move is not allowed).</summary>
    public uint[] Forward { get; }
    /// <summary>Reverse search: cost of the neighbour's edge back into h, gated like the game by the type of h first:
    /// Reverse[h*6+d] = allowed(type h → type n) ? cost(n, d+3) : NoEdge.</summary>
    public uint[] Reverse { get; }
    /// <summary>Neighbour index of hex h in direction d, or −1.</summary>
    public int[] Neighbour { get; }
    /// <summary>Bridge links (CSR): LinkStart[h]..LinkStart[h+1] index into Links.</summary>
    public int[] LinkStart { get; }
    public int[] Links { get; }
    /// <summary>Largest finite edge cost (for bucket queues).</summary>
    public uint MaxEdgeCost { get; }

    /// <summary>Allowed moves by hex type: bit u of TypeMask[t] = may move from type t to type u.</summary>
    public static readonly ushort[] TypeMask = BuildTypeMask();

    private static ushort[] BuildTypeMask()
    {
        var m = new ushort[16];
        (int, int)[] pairs =
        [
            (0, 0), (1, 1), (4, 4), (8, 8), (9, 9), (0, 6), (6, 0), (1, 3), (3, 1), (0, 4), (4, 0), (1, 8), (8, 1), (1, 7), (7, 1),
            (0, 5), (5, 0), (4, 5), (5, 4), (8, 7), (7, 8), (4, 6), (6, 4), (8, 3), (3, 8), (9, 0), (0, 9), (9, 3), (3, 9), (9, 4),
            (4, 9), (9, 5), (5, 9),
            // FUN_1805d3a70 (the table the AI searches use)
            (0, 3), (3, 0), (0, 7), (7, 0), (4, 7), (7, 4), (4, 3), (3, 4), (9, 7), (7, 9),
        ];
        foreach (var (t, u) in pairs) m[t] |= (ushort)(1 << u);
        return m;
    }

    public sealed record Settings(uint RoadCost = 100, uint LandToSeaCost = 1250, uint SeaToLandCost = 1250);

    public int Index(int x, int y) => y * Width + x;

    public CampaignPathGrid(PathfindingPpd ppd, MapDataRegions? regions, Settings? settings = null)
    {
        settings ??= new Settings();
        Width = ppd.Width;
        Height = ppd.Height;
        var n = Width * Height;
        var edges = new byte[n * 6];
        Types = new byte[n];
        for (var h = 0; h < n; h++)
        {
            for (var d = 0; d < 6; d++)
            {
                var e = ppd.Cells[h * 8 + d];
                edges[h * 6 + d] = (byte)((e & 0xBF) | (e >> 1 & 0x40));
            }
            Types[h] = (byte)(ppd.Cells[h * 8 + 7] >> 4);
        }
        var table = new uint[256];
        for (var i = 0; i < ppd.MoveCosts.Length && i < 64; i++)
            for (var b = 0; b < 256; b += 64) table[i + b] = ppd.MoveCosts[i];
        const int roadSlot = 0x3E;
        for (var b = 0; b < 256; b += 64)
        {
            table[1 + b] = settings.LandToSeaCost;
            table[2 + b] = settings.SeaToLandCost;
            table[roadSlot + b] = settings.RoadCost;
        }

        Neighbour = new int[n * 6];
        for (var y = 0; y < Height; y++)
        for (var x = 0; x < Width; x++)
        for (var d = 0; d < 6; d++)
            Neighbour[(y * Width + x) * 6 + d] = ppd.Neighbour(x, y, d, out var nx, out var ny) ? ny * Width + nx : -1;

        void SetMask(int h, int mask, byte index)
        {
            for (var d = 0; d < 6; d++)
                if ((mask >> d & 1) != 0) edges[h * 6 + d] = (byte)(edges[h * 6 + d] & 0xC0 | index);
        }

        foreach (var (_, hexes) in ppd.Roads)
            foreach (var (x, y, mask) in hexes)
            {
                var h = Index(x, y);
                if (Types[h] != 6) { SetMask(h, mask, roadSlot); continue; }
                for (var d = 0; d < 6; d++)
                {
                    var nb = Neighbour[h * 6 + d];
                    if (nb >= 0) SetMask(nb, 1 << (d + 3) % 6, roadSlot);
                    SetMask(h, 1 << d, roadSlot);
                }
            }

        if (regions is not null)
        {
            var slot = new bool[n];
            foreach (var r in regions.Regions)
                foreach (var (x, y) in r.PrimarySlot.Concat(r.PortSlot))
                    if ((uint)x < (uint)Width && (uint)y < (uint)Height) slot[Index(x, y)] = true;
            for (var h = 0; h < n; h++)
            {
                if (!slot[h]) continue;
                for (var d = 0; d < 6; d++)
                {
                    var nb = Neighbour[h * 6 + d];
                    if (nb < 0 || !(Types[nb] <= 1 || slot[nb])) continue;
                    edges[h * 6 + d] &= 0xC0;
                    edges[nb * 6 + (d + 3) % 6] &= 0xC0;
                }
            }
        }

        Forward = new uint[n * 6];
        Reverse = new uint[n * 6];
        uint max = BridgeCost;
        for (var h = 0; h < n; h++)
        {
            var mask = TypeMask[Types[h]];
            for (var d = 0; d < 6; d++)
            {
                var nb = Neighbour[h * 6 + d];
                if (nb < 0 || (mask >> Types[nb] & 1) == 0)
                {
                    Forward[h * 6 + d] = Reverse[h * 6 + d] = NoEdge;
                    continue;
                }
                var f = table[edges[h * 6 + d] & 0x7F];
                var r = table[edges[nb * 6 + (d + 3) % 6] & 0x7F];
                Forward[h * 6 + d] = f;
                Reverse[h * 6 + d] = r;
                if (f != NoEdge && f > max) max = f;
                if (r != NoEdge && r > max) max = r;
            }
        }
        MaxEdgeCost = max;

        var lists = new Dictionary<int, List<int>>();
        foreach (var (a, b) in ppd.Bridges)
        {
            foreach (var (x, y) in a)
            {
                if (!lists.TryGetValue(Index(x, y), out var l)) lists[Index(x, y)] = l = [];
                l.AddRange(b.Select(p => Index(p.X, p.Y)));
            }
            foreach (var (x, y) in b)
            {
                if (!lists.TryGetValue(Index(x, y), out var l)) lists[Index(x, y)] = l = [];
                l.AddRange(a.Select(p => Index(p.X, p.Y)));
            }
        }
        LinkStart = new int[n + 1];
        var all = new List<int>();
        for (var h = 0; h < n; h++)
        {
            LinkStart[h] = all.Count;
            if (lists.TryGetValue(h, out var l)) all.AddRange(l);
        }
        LinkStart[n] = all.Count;
        Links = all.ToArray();
    }

    /// <summary>Shortest path costs from <paramref name="source"/> over the whole grid (uint.MaxValue = unreachable).
    /// reverse = costs of paths from every hex to the source. Dial's bucket queue: costs are small integers.
    /// <paramref name="visit"/> gets each hex as it is settled, in increasing cost order.</summary>
    public uint[] Search(int source, bool reverse, Action<int, uint>? visit = null)
    {
        var n = Width * Height;
        var dist = new uint[n];
        Array.Fill(dist, uint.MaxValue);
        var done = new bool[n];
        var ring = (int)MaxEdgeCost + 1;
        var buckets = new List<int>[ring];
        for (var i = 0; i < ring; i++) buckets[i] = [];
        var costs = reverse ? Reverse : Forward;
        dist[source] = 0;
        buckets[0].Add(source);
        var pending = 1;
        for (uint cur = 0; pending > 0; cur++)
        {
            var bucket = buckets[cur % ring];
            for (var i = 0; i < bucket.Count; i++)
            {
                var h = bucket[i];
                pending--;
                if (done[h] || dist[h] != cur) continue;
                done[h] = true;
                visit?.Invoke(h, cur);
                var o = h * 6;
                for (var d = 0; d < 6; d++)
                {
                    var c = costs[o + d];
                    if (c == NoEdge) continue;
                    var nb = Neighbour[o + d];
                    if (done[nb]) continue;
                    var nd = cur + c;
                    if (nd < dist[nb])
                    {
                        dist[nb] = nd;
                        buckets[nd % ring].Add(nb);
                        pending++;
                    }
                }
                for (var k = LinkStart[h]; k < LinkStart[h + 1]; k++)
                {
                    var nb = Links[k];
                    if (done[nb]) continue;
                    var nd = cur + BridgeCost;
                    if (nd < dist[nb])
                    {
                        dist[nb] = nd;
                        buckets[nd % ring].Add(nb);
                        pending++;
                    }
                }
            }
            bucket.Clear();
        }
        return dist;
    }
}
