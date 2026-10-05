// Tree height internals for BOB "Campaign Trees": per tree (QTU::TerrainSurface::Object::height_split) the (x, z)
// asked for, the returned (hf, lf), and every call of warscape's bilinear compressed-map sampler FUN_18039eea0
// (RVA 0x39eea0) made inside it: the COMPRESSED_MAP* and the (u, v) it samples. Rows: ['T', x, z, hf, lf] then
// ['S', map, u, v] for the samples belonging to that tree (in call order).
'use strict';
let hooked = 0, inTree = false, n = 0;
const seenMaps = new Set();
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
  Interceptor.attach(m.base.add(0x39eea0), {
    onEnter(a) {
      if (!inTree) return;
      const k = a[0].toString();
      if (!seenMaps.has(k)) {                       // header floats of each COMPRESSED_MAP once (lo +0x4c, hi +0x58)
        seenMaps.add(k);
        const fl = []; for (let o = 0x30; o < 0x70; o += 4) fl.push(a[0].add(o).readFloat());
        const ints = []; for (let o = 0x0; o < 0x30; o += 4) ints.push(a[0].add(o).readU32());
        send({ kind: 'map', map: k, floats_0x30: fl, u32_0x00: ints });
      }
      buf.push(['S', k, a[1].readFloat(), a[1].add(4).readFloat()]);
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
