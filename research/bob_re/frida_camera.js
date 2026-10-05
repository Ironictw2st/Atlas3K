// Frida hooks for BOB "Generate Camera Height Map" (tooldatabuilder.modder.x64.dll, image base 0x180000000).
// generate_camera_height_map (0x69e80) runs the per-pixel pass FUN_1800a7cc0(range, &ctx) with
//   ctx[0] = &W (u32; H follows at +4), ctx[1] = &stepX (stepZ at +4), ctx[2] = &halfX (halfZ at +4), ctx[3] = TW_SCENE*,
//   ctx[4] = CAMERA_HEIGHT_MAP_SETTINGS* (+0 u32 samples per unit, +4 f32 resolution, +8 u8 blur, +0xc kernel, +0x10 sigma),
//   ctx[5] = &{u32 n, u32 cap, float* pixels}, ctx[6] = &{u32 n, u32 cap, float* per-thread max}.
// On leave the float pixel buffer (row-major, W per row, row j = z index j) is sent as binary data.
// The height provider: scene+0x10 object, vtable slot 0xd0: float get(this, const VECTOR_2*, int) - reported, and
// probe() lets the host call it at chosen points.
'use strict';
const MOD = 'tooldatabuilder.modder.x64.dll';
let hooked = false, provider = null, getH = null, probePts = null, gotBlocks = false;
recv('points', function onPts(m) { probePts = m.points; });
function setup(m) {
  if (hooked) return;
  const pass = m.base.add(0x1800a7cc0 - 0x180000000);
  Interceptor.attach(pass, {
    onEnter(a) { this.ctx = a[1]; },
    onLeave() {
      const c = this.ctx;
      const pW = c.readPointer(), pStep = c.add(8).readPointer(), pHalf = c.add(16).readPointer();
      const scene = c.add(24).readPointer(), st = c.add(32).readPointer(), pix = c.add(40).readPointer();
      const W = pW.readU32(), H = pW.add(4).readU32();
      const info = {
        kind: 'pass', W: W, H: H, stepX: pStep.readFloat(), stepZ: pStep.add(4).readFloat(),
        halfX: pHalf.readFloat(), halfZ: pHalf.add(4).readFloat(),
        samplesPerUnit: st.readU32(), resolution: st.add(4).readFloat(), blur: st.add(8).readU8(),
        kernel: st.add(12).readU32(), sigma: st.add(16).readFloat(), n: pix.readU32()
      };
      provider = scene.add(0x10).readPointer();
      if (!provider.isNull()) {
        const fn = provider.readPointer().add(0xd0).readPointer();
        const mod = Process.findModuleByAddress(fn);
        info.provider = mod ? `${mod.name}+0x${fn.sub(mod.base).toString(16)}` : fn.toString();
        info.providerVtable = (() => { const v = provider.readPointer(); const mm = Process.findModuleByAddress(v); return mm ? `${mm.name}+0x${v.sub(mm.base).toString(16)}` : v.toString(); })();
        getH = new NativeFunction(fn, 'float', ['pointer', 'pointer', 'int']);
      }
      const data = pix.add(8).readPointer().readByteArray(W * H * 4);
      send(info, data);
      if (probePts && getH) {                               // BOB's own height at chosen points, inside the pass
        const v = Memory.alloc(8); const out = [];
        for (const pt of probePts) { v.writeFloat(pt[0]); v.add(4).writeFloat(pt[1]); out.push(getH(provider, v, 0)); }
        send({ kind: 'probe', heights: out });
        // quadtree query (warscape FUN_1803f32e0) for the first points: object indices BOB considers at each point
        const ws = Process.findModuleByName('warscape.modder.x64.dll');
        const q = new NativeFunction(ws.base.add(0x3f32e0), 'void', ['pointer', 'pointer', 'pointer', 'pointer']);
        const hobj = provider.add(0x1b50);
        const tree = hobj.readPointer().add(0x20); const root = tree.readPointer().add(0x18).readPointer();   // *(*(*p1 + 0x20) + 0x18)
        const box = Memory.alloc(16); const res = hobj.add(0x70).readPointer(); const lists = [];   // BOB's per-thread result slot 0 (param_1[0xe])
        let offx = 0, offz = 0; try { offx = provider.add(0x1b08).readFloat(); offz = provider.add(0x1b0c).readFloat(); } catch (e) {}
        for (let i = 0; i < Math.min(probePts.length, 3000); i++) {
          const x = probePts[i][0] - offx, z = probePts[i][1] - offz;
          box.writeFloat(x); box.add(4).writeFloat(z); box.add(8).writeFloat(x); box.add(12).writeFloat(z);
          res.add(4).writeU32(0);
          q(tree, root, box, res);
          const n = res.add(4).readU32(), data = res.add(8).readPointer(); const ids = [];
          for (let k = 0; k < n; k++) {
            const cell = data.add(8 * k).readPointer();
            if (cell.isNull() || cell.compare(ptr('0x10000')) < 0 || cell.equals(ptr('0xffffffffffffffff'))) continue;
            let cnt = 0, idx = null;
            try { cnt = cell.add(0x1c).readU32(); idx = cell.add(0x20).readPointer(); } catch (e) { continue; }
            try { for (let t = 0; t < cnt; t++) ids.push(idx.add(4 * t).readU32()); } catch (e) { ids.push(-1); }
          }
          lists.push(ids);
        }
        send({ kind: 'qtree', offx: offx, offz: offz, lists: lists });
        // whole tree: node bounds (+0x28..+0x3c), object indices (+0x1c count, +0x20 u32*), +0xc count, children +0x40..+0x58
        const nodes = []; const stack = [[root, 0]];
        while (stack.length) {
          const [nd, depth] = stack.pop();
          if (nd.isNull()) continue;
          const b = [0x28, 0x2c, 0x30, 0x34, 0x38, 0x3c].map(k => nd.add(k).readFloat());
          const cnt = nd.add(0x1c).readU32(); const idx = nd.add(0x20).readPointer(); const ids = [];
          for (let t = 0; t < cnt; t++) ids.push(idx.add(4 * t).readU32());
          const c0 = nd.add(0xc).readU32(); const tiles = [];
          if (c0 > 0) { const tp = nd.add(0x10).readPointer(); for (let t = 0; t < c0; t++) tiles.push(tp.add(4 * t).readU32()); }
          nodes.push({ d: depth, b: b, c0: c0, ids: ids, tiles: tiles });
          for (let c = 0; c < 4; c++) { const ch = nd.add(0x40 + 8 * c).readPointer(); if (!ch.isNull()) stack.push([ch, depth + 1]); }
        }
        send({ kind: 'qnodes', n: nodes.length, nodes: nodes });
        // tile instances (BATTLE_TILE_MAP at param_1[0xb]; 0xb8-byte TILE_INSTANCE: +8 x, +10 y (i16), +0xc u16 flags)
        try {
          const btm = hobj.add(0x58).readPointer();
          const tcount = new NativeFunction(ws.getExportByName('?tile_count@BATTLE_TILE_MAP@WARSCAPE@@QEBAIXZ'), 'uint', ['pointer'])(btm);
          const base = btm.add(8).readPointer(); const inst = [];
          for (let t = 0; t < tcount; t++) { const ti = base.add(0xb8 * t); inst.push([ti.add(8).readS16(), ti.add(10).readS16(), ti.add(0xc).readU16()]); }
          send({ kind: 'tileinst', n: tcount, inst: inst });
        } catch (e) { send({ kind: 'tileinst_error', err: String(e) }); }
      }
    }
  });
  hooked = true;
  send({ kind: 'hooked', base: m.base.toString() });
  const ws = Process.findModuleByName('warscape.modder.x64.dll');
  if (ws) {
    const getObj = new NativeFunction(ws.base.add(0x1a5430), 'pointer', ['pointer']);
    Interceptor.attach(ws.base.add(0x350620), {
      onEnter(a) {
        if (gotBlocks) return; gotBlocks = true;
        const s = a[0]; const obj = getObj(s.add(0x48).readPointer());
        const n = s.add(0x2c).readU32(); const keys = s.add(0x30).readPointer();
        const fn = new NativeFunction(obj.readPointer().add(0x178).readPointer(), 'pointer', ['pointer', 'pointer']);
        const out = []; const kp = Memory.alloc(8);
        for (let i = 0; i < n; i++) {
          kp.writeU32(keys.add(4 * i).readU32());
          const bb = fn(obj, kp);
          out.push({ key: keys.add(4 * i).readFloat(), keyu: keys.add(4 * i).readU32(), bb: [0, 4, 8, 12, 16, 20].map(k => bb.add(k).readFloat()) });
        }
        send({ kind: 'blocks', n: n, blocks: out });
      }
    });
  }
}
rpc.exports = {
  probe(points) {               // points: [[x, z], ...] -> heights from the scene height provider
    if (!getH) return null;
    const v = Memory.alloc(8);
    return points.map(p => { v.writeFloat(p[0]); v.add(4).writeFloat(p[1]); return getH(provider, v, 0); });
  }
};
const m0 = Process.findModuleByName(MOD);
if (m0) setup(m0);
let polls = 0;
const iv = setInterval(() => {
  polls++;
  if (!hooked) { const mm = Process.findModuleByName(MOD); if (mm) setup(mm); }
  if (hooked || polls > 4000) clearInterval(iv);
}, 250);
send({ kind: 'loaded', already: !!m0 });
