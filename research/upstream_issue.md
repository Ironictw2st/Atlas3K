### Problem
`3K global_props bin file to Terry layers.py` writes every object into one flat layer per region. Two things that decide
*when* an object shows are thrown away:

- **Meta tags:** `building_level_1..5`, `settlement_level_0..10`, `campaign_map_object_regional_resource/security`,
  `building_state` (`building_construction`, `building_siege_damaged`, …) and `day`/`night`.
- **Season masks:** every object is written with `season_mask=""`.

After a BOB rebuild, every building level and settlement level variant of a settlement shows at the same time, night-only
lights and VFX show during the day, and seasonal props (e.g. the `*_harvest_*` katsura/poplar/fir trees) show all year.

### Where the data is
**Meta tags**
- Each fastbin already lists its enum values at the top (the `#Enums (building_level/time_of_day)` loop), but the names
  are discarded. The order matters: it is the bit order for that file.
- Every prop has an 18-byte block: `u16 version (=1), u64 flags, u64 mask`. These are the 18 bytes read as
  `#Unknown stuff` straight after the prop type index.
- Bit *i* refers to the *i*-th enum value of the same fastbin. The tags are the values whose bit is set in `flags & mask`.
  Example: in a file with `building_level_1..5, campaign_map_object_regional_resource, campaign_map_object_security`,
  `flags=0x5c, mask=0x7f` means `building_level_3,building_level_4,building_level_5,campaign_map_object_security`.
- The same block appears in:
  - **point lights**: inside the trailing `read(34)`, at +4
  - **composite scenes**: inside the trailing `read(35)`, at +5
  - **VFX**: inside the trailing `read(27)`, at +3
  
  Sound emitters don't seem to have one.

**Season masks**
- The `#Seasons` list at the top of each fastbin (`ha, au, wi, sp, su`, or a subset) gives the bit order.
- The props' and VFX's `binary_file.read(4) #possibly bit-wise seasons mask?` is exactly that: a `u32` bitmask over
  that list.
- Point lights and composite scenes have it in the 12 bytes after the meta tags: 5 unknown bytes, `u16 version (=1)`,
  `u32` season mask, 1 unknown byte.
- Map the codes to `season_harvest/autumn/winter/spring/summer`. All five set means no mask.
- On `3k_dlc07_main_map`, 1,149 props in all-season files have only `ha` set:
  - 1,145 are `*_harvest_*` tree models;
  - the other 4 are metasequoia season variants.
  
  Composite scenes in five-season files often have `0x0f`, i.e. not in winter.

On `3k_dlc07_main_map`, 42,512 entities in 264 region layers carry tags, across 30 distinct tag sets.

### How Terry stores tags
Tags live on a nested Layer entity, not on the objects. The objects are linked to it through the `Logical` association.
This is the same as CA's own 3K assembly kit files, e.g.
`raw_data/art/prefabs/battle/test_field/test_prefab_elementaldecoration_smallbuilding.*.layer`:
```xml
<entity id="167652aa95b997d" name="level5">
  <ECLayerInternal/>
  <ECLayer/>
  <ECLayerExport export="true" buildings_have_linked_destruction="false"/>
  <ECLayerExportTags tags="building_level_5"/>
</entity>
...
<associations>
  <Logical>
    <from id="167652aa95b997d">
      <to id="164605d257bb231"/>
    </from>
  </Logical>
  <Transform/>
</associations>
```

### Fix (diff below)
- Keep the enum value names and season codes per fastbin. Read the meta tags (`read_meta_tags`) and season masks
  (`season_mask_string` / `read_trailing_season_mask`) for props, VFX, point lights and composite scenes. Both assert
  their block version, and the tag reader asserts that no bit falls outside the enum list.
- Give those object classes `tags` and `season_mask` fields and include them in `__eq__`. This way
  `combine_and_simplify` never merges two objects at the same spot that are shown under different conditions.
  On `3k_dlc07_main_map` that affects a few objects in 26 regions. OR-ing the tags together would be wrong, because it
  allows combinations that didn't exist, such as building_level_1 with settlement_level_3.
- `write_xml_file` writes one Layer entity per distinct tag set (named after the tags), plus the `Logical`
  associations. `write_campaign_properties` writes the season mask. Untagged objects are written as before.
- Smaller things:
  - `combine_and_simplify` only compares objects in the same 0.01 x/z grid cell, also checking the neighbouring
    cells 1e-5 away, instead of scanning the whole list. The full 3K map goes from more than 10 minutes to about
    3 seconds.
  - The `mathutils` import falls back to a small numpy version of `to_euler()`/`to_scale()` (Blender's XYZ
    `mat3_normalized_to_eul2`), so the script also runs outside Blender.
  - Optional command line args: `script.py [global_props.bin] [output folder]`.
  - `random.seed(map_name)` gives stable ids between runs. Also fixed the duplicated `0` in the id alphabet.

### Checked
Output for vanilla `3k_dlc07_main_map` compared with the region layers made by the current script (after a Terry
load/save):
- same regions;
- positions, rotations and scales agree to the last written decimal (at most 2e-5 apart) for all 56,450 objects in
  regions with the same entity count, so the numpy fallback matches `mathutils`;
- the only count differences are the same-spot/different-tag objects described above.

I also cross-checked it entity by entity against an independent C# reader, and tags and season masks agree everywhere.

### Unrelated things I noticed (not in the diff)
- Light probes are written as `<ECDoubleSphere radius=…/>`, which Terry drops on load; they come back as
  `<ECSphere radius="1"/>`. Writing `<ECSphere radius=…/>` keeps the radius.
- The `SST_SPHERE` sound line is missing its `f` prefix and newline:
  `xml_file.write("<ECSphere radius=\"{sound_emitter.radius}\"/>")`.
- `SST_LINE_LIST` sounds are written as `ECPolyline3D`, which Terry also drops for campaign sound markers.

<details><summary>Patch against main (b8d5144)</summary>

```diff
diff --git a/3K global_props bin file to Terry layers.py b/3K global_props bin file to Terry layers.py
index c3a67b9..c21df07 100644
--- a/3K global_props bin file to Terry layers.py
+++ b/3K global_props bin file to Terry layers.py
@@ -1,7 +1,32 @@
 import struct
 from collections import defaultdict
 import random, string
-from mathutils import Matrix
+import sys
+import re
+try:
+    from mathutils import Matrix
+except ImportError:
+    #Minimal stand-in for Blender's mathutils.Matrix so the script also runs outside Blender
+    class Matrix:
+        def __init__(self, rows):
+            self.m = np.array(rows, dtype=np.float64)
+
+        def transpose(self):
+            self.m = self.m.T
+
+        def to_scale(self):
+            return tuple(np.linalg.norm(self.m, axis=0))
+
+        def to_euler(self):
+            #Same as Blender's mat3_normalized_to_eul2 (XYZ order), which picks the smaller of the two solutions
+            scale = np.array(self.to_scale())
+            m = self.m / np.where(scale == 0, 1, scale)
+            cy = math.hypot(m[0][0], m[1][0])
+            if cy > 16 * np.finfo(np.float32).eps:
+                e1 = (math.atan2(m[2][1], m[2][2]), math.atan2(-m[2][0], cy), math.atan2(m[1][0], m[0][0]))
+                e2 = (math.atan2(-m[2][1], -m[2][2]), math.atan2(-m[2][0], -cy), math.atan2(-m[1][0], -m[0][0]))
+                return e1 if sum(map(abs, e1)) <= sum(map(abs, e2)) else e2
+            return (math.atan2(-m[1][2], m[1][1]), math.atan2(-m[2][0], cy), 0.0)
 import math
 import os.path
 import numpy as np
@@ -23,6 +48,53 @@ xml_output_folder = "./terry_layer_output/"
 
 binary_file_path = "C:/Users/rob/Desktop/terrain/campaigns/3k_dlc07_main_map/global_props.bin"
 
+#Optional command line override: script.py [global_props.bin] [output folder]
+if len(sys.argv) > 1:
+    binary_file_path = sys.argv[1]
+if len(sys.argv) > 2:
+    xml_output_folder = sys.argv[2].rstrip("/\\") + "/"
+os.makedirs(xml_output_folder, exist_ok=True)
+
+#Same random ids every run, so re-running doesn't churn every layer file
+random.seed(map_name)
+
+
+#Every object carries a meta tag block: u16 version, u64 flags, u64 mask.
+#Bit i refers to the i-th enum value listed at the top of the same fastbin (e.g. building_level_3, settlement_level_5, night).
+#The values whose bit is set in both flags and mask are the tags; in Terry they become an ECLayerExportTags layer.
+def natural_key(s):
+    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]
+
+def read_meta_tags(file, enum_values):
+    version, flags, mask = struct.unpack("<HQQ", file.read(18))
+    assert version == 1, f"unexpected meta tag version {version} at {file.tell() - 18}"
+    bits = flags & mask
+    assert bits >> len(enum_values) == 0, f"meta tag bits {bits:#x} outside the {len(enum_values)} enum values"
+    tags = [enum_values[i] for i in range(len(enum_values)) if bits >> i & 1]
+    return ",".join(sorted(tags, key=natural_key))
+
+def new_entity_id():
+    return "1" + ''.join(random.choice("0123456789abcdef") for _ in range(14))
+
+
+#Props, VFX, point lights and composite scenes also carry a u32 season mask; bit i is the i-th season listed at the top
+#of the same fastbin (ha, au, wi, sp, su). All five seasons means no mask.
+season_names = {"sp": "season_spring", "su": "season_summer", "ha": "season_harvest", "au": "season_autumn", "wi": "season_winter"}
+
+def season_mask_string(season_values, bits):
+    seasons = [season_names.get(season_values[i], season_values[i]) for i in range(len(season_values)) if bits >> i & 1]
+    if len(set(seasons)) == len(season_names):
+        return ""
+    return ",".join(seasons)
+
+def read_trailing_season_mask(file, season_values):
+    #the 12 bytes after a point light's / composite scene's meta tags: 5 unknown, u16 version, u32 season mask, 1 unknown
+    file.read(5)
+    version, bits = struct.unpack("<HL", file.read(6))
+    assert version == 1, f"unexpected season block version {version} at {file.tell() - 6}"
+    file.read(1)
+    return season_mask_string(season_values, bits)
+
 def read_null_terminated_string(file):
     string = b''
 
@@ -111,6 +183,9 @@ class BMDObjectTransform:
     
 
 class BMDProp:
+    tags = "" #comma-separated meta tags, see read_meta_tags
+    season_mask = "" #see season_mask_string
+
     def __init__(self, path, object_transform, culture_mask, is_decal, apply_to_terrain, apply_to_objects, has_height_patch, apply_height_patch, visible_inside_snow_region, visible_outside_snow_region, visible_inside_destruction_region, visible_outside_destruction_region, visible_in_unseen_shroud, visible_in_seen_shroud, no_culling):
         self.path = path
         self.object_transform = object_transform
@@ -129,7 +204,7 @@ class BMDProp:
         self.no_culling = no_culling
         
     def __eq__(self, other):
-        return (self.path == other.path and self.object_transform == other.object_transform)
+        return (self.path == other.path and self.object_transform == other.object_transform and self.tags == other.tags and self.season_mask == other.season_mask)
     
     #Combine the masks of two props
     def combine(self, other):
@@ -140,6 +215,9 @@ class BMDProp:
         self.culture_mask = self.culture_mask | other.culture_mask
         
 class BMDVFX:
+    tags = "" #comma-separated meta tags, see read_meta_tags
+    season_mask = "" #see season_mask_string
+
     def __init__(self, vfx_name, object_transform, culture_mask, visible_inside_snow_region, visible_outside_snow_region, visible_inside_destruction_region, visible_outside_destruction_region, visible_in_unseen_shroud, visible_in_seen_shroud, no_culling):
         self.vfx_name = vfx_name
         self.object_transform = object_transform
@@ -153,7 +231,7 @@ class BMDVFX:
         self.no_culling = no_culling
         
     def __eq__(self, other):
-        return (self.vfx_name == other.vfx_name and self.object_transform == other.object_transform)
+        return (self.vfx_name == other.vfx_name and self.object_transform == other.object_transform and self.tags == other.tags and self.season_mask == other.season_mask)
     
     #Combine the masks of two vfx
     def combine(self, other):
@@ -169,6 +247,9 @@ class BMDLightProbe:
         self.radius = radius
 
 class BMDPointLight:
+    tags = "" #comma-separated meta tags, see read_meta_tags
+    season_mask = "" #see season_mask_string
+
     def __init__(self, object_transform, culture_mask, r, g, b, anim_type, anim_scale1, anim_scale2, color_min, rand_offset, falloff_type, light_probes_only, color_scale, radius):
         self.object_transform = object_transform
         self.culture_mask = culture_mask
@@ -193,7 +274,7 @@ class BMDPointLight:
         self.no_culling = False
         
     def __eq__(self, other):
-        return (self.r == other.r and self.g == other.g and self.b == other.b and self.object_transform == other.object_transform)
+        return (self.r == other.r and self.g == other.g and self.b == other.b and self.object_transform == other.object_transform and self.tags == other.tags and self.season_mask == other.season_mask)
     
     #Combine the masks of two point lights
     def combine(self, other):
@@ -259,6 +340,9 @@ class BMDSoundEmitter:
         
         
 class BMDCompositeScene:
+    tags = "" #comma-separated meta tags, see read_meta_tags
+    season_mask = "" #see season_mask_string
+
     def __init__(self, csc_name, object_transform, culture_mask, visible_inside_snow_region, visible_outside_snow_region, visible_inside_destruction_region, visible_outside_destruction_region, visible_in_unseen_shroud, visible_in_seen_shroud, no_culling):
         self.csc_name = csc_name
         self.object_transform = object_transform
@@ -273,7 +357,7 @@ class BMDCompositeScene:
         
     def __eq__(self, other):
         #Don't worry about the boolean fields... maybe....
-        return (self.csc_name == other.csc_name and self.object_transform == other.object_transform)
+        return (self.csc_name == other.csc_name and self.object_transform == other.object_transform and self.tags == other.tags and self.season_mask == other.season_mask)
     
     
     #Combine the masks of two props
@@ -325,7 +409,18 @@ with open(binary_file_path, 'rb') as binary_file:
     
     
     
+    tagged_entities = defaultdict(list) #tags -> entity ids, for the file being written
+
+    def open_entity(xml_file, thing):
+        entity_id = new_entity_id()
+        tags = getattr(thing, "tags", "")
+        if tags:
+            tagged_entities[tags].append(entity_id)
+        xml_file.write("\n\t\t<entity id=\"" + entity_id + "\">")
+
+
     def write_xml_file(compiled_bmd, region_name, id):
+        tagged_entities.clear()
         xml_filepath = xml_output_folder + map_name + "." + id + ".layer"
         with open(xml_filepath, 'w') as xml_file:
             print("Writing " + region_name)
@@ -361,7 +456,29 @@ with open(binary_file_path, 'rb') as binary_file:
             for composite_scene in compiled_bmd.composite_scene_list:
                 write_composite_scene(xml_file, composite_scene)                    
             
-            xml_file.write("\n\t</entities>\n\t<associations>\n\t\t<Logical/>\n\t\t<Transform/>\n\t</associations>\n</layer>")
+            #One Terry layer per distinct tag set, holding the tagged objects (like building_level_5 in CA's prefab layers)
+            tag_layer_ids = {}
+            for tags in sorted(tagged_entities, key=natural_key):
+                tag_layer_ids[tags] = new_entity_id()
+                xml_file.write("\n\t\t<entity id=\"" + tag_layer_ids[tags] + "\" name=\"" + tags + "\">")
+                xml_file.write("\n\t\t\t<ECLayerInternal/>")
+                xml_file.write("\n\t\t\t<ECLayer/>")
+                xml_file.write("\n\t\t\t<ECLayerExport export=\"true\" export_as_separate_file_if_not_meta_tagged=\"false\" buildings_have_linked_destruction=\"false\"/>")
+                xml_file.write("\n\t\t\t<ECLayerExportTags tags=\"" + tags + "\"/>")
+                xml_file.write("\n\t\t</entity>")
+
+            xml_file.write("\n\t</entities>\n\t<associations>")
+            if tag_layer_ids:
+                xml_file.write("\n\t\t<Logical>")
+                for tags, layer_id in tag_layer_ids.items():
+                    xml_file.write("\n\t\t\t<from id=\"" + layer_id + "\">")
+                    for entity_id in tagged_entities[tags]:
+                        xml_file.write("\n\t\t\t\t<to id=\"" + entity_id + "\"/>")
+                    xml_file.write("\n\t\t\t</from>")
+                xml_file.write("\n\t\t</Logical>")
+            else:
+                xml_file.write("\n\t\t<Logical/>")
+            xml_file.write("\n\t\t<Transform/>\n\t</associations>\n</layer>")
             
             
             
@@ -374,7 +491,7 @@ with open(binary_file_path, 'rb') as binary_file:
         
         
     def write_campaign_properties(xml_file, prop):
-        xml_file.write(f"\n\t\t\t<ECCampaignProperties visible_inside_snow_region=\"{prop.visible_inside_snow_region}\" visible_outside_snow_region=\"{prop.visible_outside_snow_region}\" visible_inside_destruction_region=\"{prop.visible_inside_destruction_region}\" visible_outside_destruction_region=\"{prop.visible_outside_destruction_region}\" visible_in_unseen_shroud=\"{prop.visible_in_unseen_shroud}\" visible_in_seen_shroud=\"{prop.visible_in_seen_shroud}\" no_culling=\"{prop.no_culling}\" culture_mask=\"{parse_culture_mask(prop.culture_mask)}\" season_mask=\"\"/>")
+        xml_file.write(f"\n\t\t\t<ECCampaignProperties visible_inside_snow_region=\"{prop.visible_inside_snow_region}\" visible_outside_snow_region=\"{prop.visible_outside_snow_region}\" visible_inside_destruction_region=\"{prop.visible_inside_destruction_region}\" visible_outside_destruction_region=\"{prop.visible_outside_destruction_region}\" visible_in_unseen_shroud=\"{prop.visible_in_unseen_shroud}\" visible_in_seen_shroud=\"{prop.visible_in_seen_shroud}\" no_culling=\"{prop.no_culling}\" culture_mask=\"{parse_culture_mask(prop.culture_mask)}\" season_mask=\"{getattr(prop, 'season_mask', '')}\"/>")
             
             
             
@@ -386,7 +503,7 @@ with open(binary_file_path, 'rb') as binary_file:
             prop.path = prop.path.replace(vanilla_map_name, map_name)
         
         #Write
-        xml_file.write("\n\t\t<entity id=\"" + "1" + ''.join(random.choice("01234567890abcdef") for _ in range(14)) + "\">")
+        open_entity(xml_file, prop)
                         
         if (prop.is_decal):
             xml_file.write(f"\n\t\t\t<ECDecal model_path=\"{prop.path}\" parallax_scale=\"0\" tiling=\"0\" tiling_affects_alpha=\"false\" normal_mode=\"DNM_DECAL_OVERRIDE\""
@@ -406,7 +523,7 @@ with open(binary_file_path, 'rb') as binary_file:
         
         
     def write_vfx(xml_file, vfx):
-        xml_file.write("\n\t\t<entity id=\"" + "1" + ''.join(random.choice("01234567890abcdef") for _ in range(14)) + "\">")
+        open_entity(xml_file, vfx)
         
         xml_file.write(f"\n\t\t\t<ECVFX vfx=\"{vfx.vfx_name}\" autoplay=\"true\" scale=\"1\" instance_name=\"\"/>")
         
@@ -420,7 +537,7 @@ with open(binary_file_path, 'rb') as binary_file:
     
     
     def write_light_probe(xml_file, light_probe):
-        xml_file.write("\n\t\t<entity id=\"" + "1" + ''.join(random.choice("01234567890abcdef") for _ in range(14)) + "\">")
+        open_entity(xml_file, light_probe)
         
         xml_file.write(f"\n\t\t\t<ECLightProbe/>")
         
@@ -435,7 +552,7 @@ with open(binary_file_path, 'rb') as binary_file:
     
     
     def write_point_light(xml_file, point_light):
-        xml_file.write("\n\t\t<entity id=\"" + "1" + ''.join(random.choice("01234567890abcdef") for _ in range(14)) + "\">")
+        open_entity(xml_file, point_light)
         
         xml_file.write(f"\n\t\t\t<ECPointLight colour=\"{int(point_light.r*255)} {int(point_light.g*255)} {int(point_light.b*255)} 255\" colour_scale=\"{point_light.color_scale}\" radius=\"{point_light.radius}\" animation_type=\"{point_light.anim_type}\" animation_speed_scale=\"{point_light.anim_scale1} {point_light.anim_scale2}\" colour_min=\"{point_light.color_min}\" random_offset=\"{point_light.rand_offset}\" falloff_type=\"{point_light.falloff_type}\" for_light_probes_only=\"{point_light.light_probes_only}\"/>")
 
@@ -449,7 +566,7 @@ with open(binary_file_path, 'rb') as binary_file:
     
     
     def write_polymesh(xml_file, polymesh):
-        xml_file.write("\n\t\t<entity id=\"" + "1" + ''.join(random.choice("01234567890abcdef") for _ in range(14)) + "\">")
+        open_entity(xml_file, polymesh)
                         
         xml_file.write(f"\n\t\t\t<ECPolygonMesh material=\"{polymesh.material}\" affects_mesh_optimization=\"false\"/>")
 
@@ -470,7 +587,7 @@ with open(binary_file_path, 'rb') as binary_file:
     
     
     def write_sound_emitter(xml_file, sound_emitter):
-        xml_file.write("\n\t\t<entity id=\"" + "1" + ''.join(random.choice("01234567890abcdef") for _ in range(14)) + "\">")
+        open_entity(xml_file, sound_emitter)
                         
         xml_file.write(f"\n\t\t\t<ECSoundMarker key=\"{sound_emitter.sound_name}\" />")
 
@@ -501,7 +618,7 @@ with open(binary_file_path, 'rb') as binary_file:
     
     
     def write_composite_scene(xml_file, composite_scene):
-        xml_file.write("\n\t\t<entity id=\"" + "1" + ''.join(random.choice("01234567890abcdef") for _ in range(14)) + "\">")
+        open_entity(xml_file, composite_scene)
         
         xml_file.write(f"\n\t\t\t<ECCompositeScene path=\"{composite_scene.csc_name}\" script_id=\"\" autoplay=\"true\"/>")
 
@@ -525,20 +642,29 @@ with open(binary_file_path, 'rb') as binary_file:
         
         
         def do_thing(thing_list):
-            end = False
+            #Objects are bucketed on a 0.01 grid in x/z (checking the neighbouring cells an epsilon away too), so only
+            #nearby objects get compared; the full scan was O(n^2) and took over 10 minutes on the 3K map
+            def cell(v):
+                return math.floor(v * 100)
+
             new_thing_list = []
+            buckets = defaultdict(list)
             for thing in thing_list:
-                for new_thing in new_thing_list:
-                    if (thing == new_thing):
-                        new_thing.combine(thing)
-                        end = True
-                        break
-                if end == True:
-                    end = False
-                    continue
+                t = thing.object_transform
+                name = (getattr(thing, "path", None) or getattr(thing, "vfx_name", None) or getattr(thing, "csc_name", None)
+                        or getattr(thing, "sound_name", None) or getattr(thing, "material", None))
+                match = None
+                for cx in {cell(t.x_pos - 0.00001), cell(t.x_pos + 0.00001)}:
+                    for cz in {cell(t.z_pos - 0.00001), cell(t.z_pos + 0.00001)}:
+                        for new_thing in buckets.get((name, cx, cz), []):
+                            if match is None and thing == new_thing:
+                                match = new_thing
+                if match is not None:
+                    match.combine(thing)
                 else:
+                    buckets[(name, cell(t.x_pos), cell(t.z_pos))].append(thing)
                     new_thing_list.append(thing)
-                    
+
             return new_thing_list
         
         
@@ -678,7 +804,7 @@ with open(binary_file_path, 'rb') as binary_file:
             #Don't need to merge out here because.... I think that's how the quadtree is stuctured
             
             #write the xml file
-            id = "1" + ''.join(random.choice("01234567890abcdef") for _ in range(14))
+            id = new_entity_id()
             region_to_layer[region_name] = id
             write_xml_file(regional_bmd_object, region_name, id)
             
@@ -722,6 +848,7 @@ with open(binary_file_path, 'rb') as binary_file:
         #Enums (building_level/time_of_day)
         binary_file.read(2)
         binary_file.read(4) #some float
+        enum_values = [] #every enum value in order; meta tag bits index into this
         num_enum_types = struct.unpack("<L", binary_file.read(4))[0]
         for _ in range(num_enum_types):
             binary_file.read(2) #version
@@ -732,13 +859,16 @@ with open(binary_file_path, 'rb') as binary_file:
             for _ in range(num_enums):
                 enum_name_length = struct.unpack("<H", binary_file.read(2))[0]
                 enum_name = binary_file.read(enum_name_length).decode('UTF-8')
+                enum_values.append(enum_name)
         
         #Seasons
+        season_values = [] #season codes in order; season mask bits index into this
         binary_file.read(2)
         num_seasons = struct.unpack("<L", binary_file.read(4))[0]
         for _ in range(num_seasons):
             season_name_length = struct.unpack("<H", binary_file.read(2))[0]
             season_name = binary_file.read(season_name_length).decode('UTF-8')
+            season_values.append(season_name)
         
         #Unknown/Irrelevent
         binary_file.read(47)
@@ -807,8 +937,8 @@ with open(binary_file_path, 'rb') as binary_file:
             path = prop_types[index]
             
             
-            #Unknown stuff
-            binary_file.read(18) 
+            #Meta tags (building_level_x, settlement_level_x, ...)
+            tags = read_meta_tags(binary_file, enum_values)
             
             
             #3x3 matrix for rotation/scale
@@ -853,7 +983,7 @@ with open(binary_file_path, 'rb') as binary_file:
             
             binary_file.read(3)#three unknown booleans?
             
-            binary_file.read(4) #possibly bit-wise seasons mask?
+            season_mask = season_mask_string(season_values, struct.unpack("<L", binary_file.read(4))[0])
             
             visible_in_seen_shroud = struct.unpack("<B", binary_file.read(1))[0] == 1
             visible_in_unseen_shroud = struct.unpack("<B", binary_file.read(1))[0] == 1
@@ -886,6 +1016,8 @@ with open(binary_file_path, 'rb') as binary_file:
             
             bmd_prop = BMDProp(path, object_trans, 0, is_decal, apply_to_terrain, apply_to_objects, has_height_patch, apply_height_patch, visible_inside_snow_region, visible_outside_snow_region, visible_inside_destruction_region, visible_outside_destruction_region, visible_in_unseen_shroud, visible_in_seen_shroud, False)
             
+            bmd_prop.tags = tags
+            bmd_prop.season_mask = season_mask
             compiled_bmd.prop_list.append(bmd_prop)
         
         
@@ -934,7 +1066,7 @@ with open(binary_file_path, 'rb') as binary_file:
             
             binary_file.read(3)#three unknown booleans?
             
-            binary_file.read(4) #possibly bit-wise seasons mask?
+            season_mask = season_mask_string(season_values, struct.unpack("<L", binary_file.read(4))[0])
             
             #One of these can't be here?
             visible_in_seen_shroud = struct.unpack("<B", binary_file.read(1))[0] == 1
@@ -945,13 +1077,17 @@ with open(binary_file_path, 'rb') as binary_file:
                 
             autoplay = struct.unpack("<B", binary_file.read(1))[0] == 1
             
-            binary_file.read(27)
+            binary_file.read(3)
+            tags = read_meta_tags(binary_file, enum_values)
+            binary_file.read(6)
             
             
             object_trans = BMDObjectTransform(x_pos, y_pos, z_pos, x_rot, y_rot, z_rot, x_scale, y_scale, z_scale)
             
             bmd_vfx = BMDVFX(vfx_name, object_trans, 0, True, True, True, True, False, True, False)
             
+            bmd_vfx.tags = tags
+            bmd_vfx.season_mask = season_mask
             compiled_bmd.vfx_list.append(bmd_vfx)
         
         
@@ -1029,14 +1165,18 @@ with open(binary_file_path, 'rb') as binary_file:
             
             light_probes_only = struct.unpack("<B", binary_file.read(1))[0] == 1
             
-            #unknown
-            binary_file.read(34)
+            #unknown, with the meta tags in the middle
+            binary_file.read(4)
+            tags = read_meta_tags(binary_file, enum_values)
+            season_mask = read_trailing_season_mask(binary_file, season_values)
             
             
             object_trans = BMDObjectTransform(x, y, z)
             
             bmd_point_light = BMDPointLight(object_trans, 0, r, g, b, anim_type, anim_scale1, anim_scale2, color_min, rand_offset, falloff_type, light_probes_only, color_scale, radius)
             
+            bmd_point_light.tags = tags
+            bmd_point_light.season_mask = season_mask
             compiled_bmd.point_light_list.append(bmd_point_light)
             
 
@@ -1174,13 +1314,17 @@ with open(binary_file_path, 'rb') as binary_file:
             bhm_name_length = struct.unpack("<H", binary_file.read(2))[0]
             bhm_name = binary_file.read(bhm_name_length).decode('UTF-8')
             
-            binary_file.read(35)
+            binary_file.read(5)
+            tags = read_meta_tags(binary_file, enum_values)
+            season_mask = read_trailing_season_mask(binary_file, season_values)
             
                         
             object_trans = BMDObjectTransform(x_pos, y_pos, z_pos, x_rot, y_rot, z_rot, x_scale, y_scale, z_scale)
             
             bmd_composite_scene = BMDCompositeScene(csc_name, object_trans, 0, True, True, True, True, False, True, False)
             
+            bmd_composite_scene.tags = tags
+            bmd_composite_scene.season_mask = season_mask
             compiled_bmd.composite_scene_list.append(bmd_composite_scene)
             
             
```

</details>
