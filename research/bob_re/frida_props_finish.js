// Frida hooks for BOB "Terry file" (global_props parity, 2026-10-05):
//  - bob_terrain FUN_18005e050 (RVA 0x5e050): the x/z box BOB computes per entity for the quadtree (logged near the
//    two water lilies at x 718..731, z 438..452, plus every box whose call returns into the mesh path)
//  - tooldatabuilder process_river_spline: call order, output path (river_N) and the AABB_3 it gets
'use strict';
const TERR = 'bob_terrain.modder.x64.dll', TDB = 'tooldatabuilder.modder.x64.dll';
const done = {};
let sData = null, sLen = null, nBox = 0;
function strOf(p) {
  try {
    if (!sData) {
      const c = Process.getModuleByName('calibs.modder.x64.dll');
      sData = new NativeFunction(c.getExportByName('?data@String@CA@@QEBAPEBDXZ'), 'pointer', ['pointer']);
      sLen = new NativeFunction(c.getExportByName('?length@String@CA@@QEBAIXZ'), 'uint', ['pointer']);
    }
    const d = sData(p); return d.isNull() ? '' : d.readUtf8String(sLen(p));
  } catch (e) { return 'ERR:' + e; }
}
function hookTerr(m) {
  Interceptor.attach(m.base.add(0x5e050), {
    onEnter(a) { this.out = a[0]; },
    onLeave() {
      nBox++;
      try {
        const o = this.out; const v = [o.readFloat(), o.add(4).readFloat(), o.add(8).readFloat(), o.add(12).readFloat()];
        if (v[0] < 731 && v[2] > 718 && v[1] < 452 && v[3] > 438) send({ kind: 'box', v: v, n: nBox });
      } catch (e) { }
    }
  });
  done[TERR] = true; send({ kind: 'hooked', mod: TERR });
}
function hookTdb(m) {
  const fn = m.getExportByName('?process_river_spline@TOOLDATABUILDER@@YA_NAEBURIVER_SPLINE_ARRAY_PLUS_MATERIAL@WS_SCENE_NODE_DYNAMIC@WARSCAPE@@AEBVString@CA@@1AEBVAABB_3@UTILITYLIB@@@Z');
  Interceptor.attach(fn, {
    onEnter(a) {
      const b = a[3]; let box = [];
      try { for (let i = 0; i < 6; i++) box.push(b.add(4 * i).readFloat()); } catch (e) { }
      send({ kind: 'river', p2: strOf(a[1]), p3: strOf(a[2]), aabb: box });
    }
  });
  done[TDB] = true; send({ kind: 'hooked', mod: TDB });
}
let polls = 0;
const iv = setInterval(() => {
  polls++;
  if (!done[TERR]) { const m = Process.findModuleByName(TERR); if (m) hookTerr(m); }
  if (!done[TDB]) { const m = Process.findModuleByName(TDB); if (m) hookTdb(m); }
  if (polls % 40 === 0) send({ kind: 'count', boxes: nBox });
  if (polls > 40000) clearInterval(iv);
}, 250);
send({ kind: 'loaded' });
