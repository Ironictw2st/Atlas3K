// Tree lf internals, run 3: replace warscape's bilinear sampler FUN_18039eea0 (RVA 0x39eea0) with a wrapper that calls
// the original and logs (map, u, v, result l) - a float return is only visible through a NativeFunction - and dump the
// TERRAIN_RENDER_SETUP scale fields once from the first get_height_worker(tile) call (RVA 0x371030).
// Rows: ['T', x, z, hf, lf] per tree, preceded by ['S', map, u, v, l] for its samples.
'use strict';
let hooked = 0, inTree = false, n = 0, setupDumped = false;
const buf = [];
function flush() { if (buf.length) send({ kind: 'rows', rows: buf.splice(0) }); }
function setupQt(m) {
  const fn = m.getExportByName('?height_split@Object@TerrainSurface@QTU@@QEBA?AU?$pair@MM@std@@VVECTOR_2@UTILITYLIB@@@Z');
  Interceptor.attach(fn, {
    onEnter(a) { this.ret = a[1]; this.x = a[2].readFloat(); this.z = a[2].add(4).readFloat(); inTree = true; },
    onLeave() { inTree = false; buf.push(['T', this.x, this.z, this.ret.readFloat(), this.ret.add(4).readFloat()]); n++; if (buf.length >= 4000) flush(); }
  });
  hooked |= 1; send({ kind: 'hooked', what: 'qt' });
}
function setupWs(m) {
  const target = m.base.add(0x39eea0);
  const orig = new NativeFunction(target, 'float', ['pointer', 'pointer']);
  Interceptor.replace(target, new NativeCallback(function (map, uv) {
    const r = orig(map, uv);
    if (inTree) buf.push(['S', map.toString(), uv.readFloat(), uv.add(4).readFloat(), r]);
    return r;
  }, 'float', ['pointer', 'pointer']));
  const ghw = Interceptor.attach(m.base.add(0x371030), {
    onEnter(a) {
      if (setupDumped || !inTree) return;
      setupDumped = true;
      const t = a[0], f = {};
      for (const o of [0x80, 0x84, 0x88, 0x8c, 0x90, 0x320, 0x324, 0x328, 0x32c, 0x330, 0x340, 0x344, 0x348, 0x34c])
        f['0x' + o.toString(16)] = t.add(o).readFloat();
      send({ kind: 'setup', fields: f });
    }
  });
  hooked |= 2; send({ kind: 'hooked', what: 'ws' });
}
let polls = 0;
const iv = setInterval(() => {
  polls++;
  if (!(hooked & 1)) { const m = Process.findModuleByName('qttoolutility.modder.x64.dll'); if (m) setupQt(m); }
  if (!(hooked & 2)) { const m = Process.findModuleByName('warscape.modder.x64.dll'); if (m) setupWs(m); }
  if (hooked) flush();
  if (hooked && polls % 40 === 0) send({ kind: 'count', n: n });
  if (polls > 40000) clearInterval(iv);
}, 250);
send({ kind: 'loaded' });
