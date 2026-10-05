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

### Changes
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

I also cross-checked it entity by entity against an independent C# reader, and tags and season masks agree for every object. The only difference is 3 near-identical duplicate roof tiles, which one reader merges and the other keeps because of float precision.

### Unrelated things I noticed (not in this PR)
- Light probes are written as `<ECDoubleSphere radius=…/>`, which Terry drops on load; they come back as
  `<ECSphere radius="1"/>`. Writing `<ECSphere radius=…/>` keeps the radius.
- The `SST_SPHERE` sound line is missing its `f` prefix and newline:
  `xml_file.write("<ECSphere radius=\"{sound_emitter.radius}\"/>")`.
- `SST_LINE_LIST` sounds are written as `ECPolyline3D`, which Terry also drops for campaign sound markers.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
