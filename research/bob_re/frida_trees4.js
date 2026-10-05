// Campaign Trees height provider (qttoolutility FUN_18011f1d0, RVA 0x11f1d0): per tree the world point, the cell
// ws_tile_instance_indices_at (RVA 0x11be90) is asked for and the candidate instance indices it returns; once, the
// TileMapProcessed inverse world transform (Transform2, 6 floats at *(provider + 0x18) + 0x48) and the z divisor at
// provider + 0x28. Rows: ['T', x, z, cx, cy, [indices...]].
'use strict';
const MOD = 'qttoolutility.modder.x64.dll';
let hooked = false, n = 0, cur = null, dumped = false;
const buf = [];
function flush() { if (buf.length) send({ kind: 'rows', rows: buf.splice(0) }); }
function setup(m) {
  if (hooked) return;
  Interceptor.attach(m.base.add(0x11f1d0), {
    onEnter(a) {
      const p = a[2];
      cur = { x: p.readFloat(), z: p.add(4).readFloat(), cell: null, idx: null };
      if (!dumped) {
        dumped = true;
        const tmp = a[0].add(0x18).readPointer();
        const inv = tmp.add(0x48), fwd = tmp.add(0x30);
        const rd = q => [0, 4, 8, 12, 16, 20].map(o => q.add(o).readFloat());
        const bits = q => [0, 4, 8, 12, 16, 20].map(o => q.add(o).readU32());
        send({ kind: 'transform', inv: rd(inv), inv_bits: bits(inv), fwd: rd(fwd), fwd_bits: bits(fwd),
               zdiv: a[0].add(0x28).readFloat(), zdiv_bits: a[0].add(0x28).readU32() });
      }
    },
    onLeave() { if (cur) { buf.push(['T', cur.x, cur.z, cur.cell ? cur.cell[0] : null, cur.cell ? cur.cell[1] : null, cur.idx]); n++; } cur = null; if (buf.length >= 5000) flush(); }
  });
  Interceptor.attach(m.base.add(0x11be90), {
    onEnter(a) { this.ret = a[1]; if (cur) cur.cell = [a[2].readS32(), a[2].add(4).readS32()]; },
    onLeave() {
      if (!cur) return;
      const b = this.ret.readPointer(), e = this.ret.add(8).readPointer();
      const out = [];
      for (let p = b; !p.isNull() && p.compare(e) < 0; p = p.add(4)) out.push(p.readS32());
      cur.idx = out;
    }
  });
  hooked = true;
  send({ kind: 'hooked', base: m.base.toString() });
}
const m0 = Process.findModuleByName(MOD);
if (m0) setup(m0);
let polls = 0;
const iv = setInterval(() => {
  polls++;
  if (!hooked) { const mm = Process.findModuleByName(MOD); if (mm) setup(mm); }
  if (hooked) flush();
  if (polls > 20000) clearInterval(iv);
}, 250);
send({ kind: 'loaded', already: !!m0 });
