// Frida hook for BOB "Terry file": dump the raw 32-byte half-precision river vertices that FUN_18015e9e0
// (tooldatabuilder RVA 0x15e9e0) appends to its output vector (param_3: {u32 cap, u32 count, ptr data}), and the
// index list (param_4: same layout, u32 indices). Sent as hex strings per call.
'use strict';
const TDB = 'tooldatabuilder.modder.x64.dll';
let hooked = false;
function hexbytes(p, n) { const b = new Uint8Array(p.readByteArray(n)); let s = ''; for (const x of b) s += (x < 16 ? '0' : '') + x.toString(16); return s; }
function setup() {
  const tdb = Process.findModuleByName(TDB);
  if (!tdb || hooked) return;
  Interceptor.attach(tdb.base.add(0x15e9e0), {
    onEnter(a) { this.v = a[2]; this.i = a[3]; this.v0 = this.v.add(4).readU32(); this.i0 = this.i.add(4).readU32(); },
    onLeave() {
      const vn = this.v.add(4).readU32(), vp = this.v.add(8).readPointer();
      const inn = this.i.add(4).readU32(), ip = this.i.add(8).readPointer();
      send({ kind: 'mesh', v0: this.v0, vn: vn, i0: this.i0, inn: inn,
             verts: hexbytes(vp.add(this.v0 * 32), (vn - this.v0) * 32),
             idx: hexbytes(ip.add(this.i0 * 4), (inn - this.i0) * 4) });
    }
  });
  hooked = true;
  send({ kind: 'hooked', tdb: tdb.base.toString() });
}
setup();
let polls = 0;
const iv = setInterval(() => { polls++; setup(); if (hooked || polls > 4000) clearInterval(iv); }, 250);
send({ kind: 'loaded' });
