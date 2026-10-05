namespace TerryClone.Formats.Models;

/// <summary>models\river_N.wsmodel: the XML wrapper pointing at the river mesh and its water material (CRLF).</summary>
public static class WsModel
{
    public const string RiverMaterial = "materials/campaign_navigable_yellow_river_plane_default.xml.material";

    public static string River(string mapName, int index, string material = RiverMaterial) =>
        "<model version=\"1\">\r\n" +
        $"  <geometry>terrain/campaigns/{mapName}/models/river_{index}.wsmodel.rigid_model_v2</geometry>\r\n" +
        "  <materials>\r\n" +
        $"    <material lod_index=\"0\" part_index=\"0\">{material}</material>\r\n" +
        "  </materials>\r\n" +
        "</model>";
}
