// Frida: dump BOB's height-patch objects (warscape FUN_180350320, RVA 0x350320, scene height query) on its first call.
// Object array: param_1[0x17] (0xb0 bytes each), count u32 at param_1 + 0xb4 (CA_STD::VECTOR {cap?, size, data}).
// Per object: +0 COMPRESSED_MAP*, +8 minX +0xc minZ +0x10 maxX +0x14 maxZ (world AABB), +0x18/+0x1c/+0x20/+0x24
// local minX/minZ/maxX/maxZ, +0x28.. 4x4 world matrix (row-major), +0x68.. 4x4 inverse, +0xa8 enabled, +0xa9 add-lf.
// Also: the global-mesh block AABBs (FUN_180350620: keys at scene+0x30 / count +0x2c, AABB from vtable +0x178 of the
// object FUN_1801a5430(scene+0x48)) are dumped via a hook on FUN_180350620's first call.
'use strict';
const MOD = 'warscape.modder.x64.dll';
let hooked = false, donePatch = false; const sums = {};
function setup(m) {
  if (hooked) return;
  const exp = n => m.getExportByName(n);
  const cmW = new NativeFunction(exp('?width@COMPRESSED_MAP@WARSCAPE@@QEBAIXZ'), 'uint', ['pointer']);
  const cmH = new NativeFunction(exp('?height@COMPRESSED_MAP@WARSCAPE@@QEBAIXZ'), 'uint', ['pointer']);
  const cmLo = new NativeFunction(exp('?min_height@COMPRESSED_MAP@WARSCAPE@@QEBAMXZ'), 'float', ['pointer']);
  const cmHi = new NativeFunction(exp('?max_height@COMPRESSED_MAP@WARSCAPE@@QEBAMXZ'), 'float', ['pointer']);
  const cmV = new NativeFunction(exp('?value_float@COMPRESSED_MAP@WARSCAPE@@QEBAMII@Z'), 'float', ['pointer', 'uint', 'uint']);
  Interceptor.attach(m.base.add(0x350320), {
    onEnter(a) {
      if (donePatch) return; donePatch = true;
      const s = a[0];
      const n = s.add(0xb4).readU32(); const base = s.add(0xb8).readPointer();
      const objs = [];
      for (let i = 0; i < n; i++) {
        const o = base.add(i * 0xb0);
        const cm = o.readPointer();
        const f = k => o.add(k).readFloat();
        const rec = { i: i, en: o.add(0xa8).readU8(), addlf: o.add(0xa9).readU8(),
          aabb: [f(8), f(0xc), f(0x10), f(0x14)], local: [f(0x18), f(0x1c), f(0x20), f(0x24)],
          m: [...Array(16).keys()].map(k => f(0x28 + 4 * k)), inv: [...Array(16).keys()].map(k => f(0x68 + 4 * k)) };
        if (!cm.isNull()) {
          const w = cmW(cm), h = cmH(cm);
          rec.cm = { w: w, h: h, lo: cmLo(cm), hi: cmHi(cm), ptr: cm.toString(),
                     // checksum-ish fingerprint of the map to identify the model: a few sampled values
                     probe: [[0, 0], [w >> 1, h >> 1], [w - 1, h - 1], [w >> 2, (3 * h) >> 2]].map(p => cmV(cm, p[0], p[1])) };
          const key = cm.toString();
          if (!sums[key]) {                                  // whole-map fingerprint: count of valid samples and their sum
            let n = 0, sum = 0; const st = (w * h > 4096) ? 2 : 1;
            for (let y = 0; y < h; y += st) for (let x = 0; x < w; x += st) { const v = cmV(cm, x, y); if (v > -49.999) { n++; sum += v * ((x * 7 + y * 13) % 17 + 1); } }
            sums[key] = [n, sum];
          }
          rec.cm.sum = sums[key];
        }
        objs.push(rec);
      }
      send({ kind: 'patches', n: n, objs: objs });
    }
  });
  hooked = true;
  send({ kind: 'hooked', base: m.base.toString() });
}
const m0 = Process.findModuleByName(MOD);
if (m0) setup(m0);
let polls = 0;
const iv = setInterval(() => { polls++; if (!hooked) { const mm = Process.findModuleByName(MOD); if (mm) setup(mm); } if (hooked || polls > 4000) clearInterval(iv); }, 250);
send({ kind: 'loaded', already: !!m0 });
