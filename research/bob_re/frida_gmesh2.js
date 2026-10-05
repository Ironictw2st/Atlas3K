// Frida hook for BOB "Global Mesh": TRIANGLE_MERGER::process (tooldatabuilder FUN_1800d0140; this, factor, span,
// tolerance, flags*). On entry, for the first FULL calls: every vertex (this[0] = vector of 0x94-byte record pointers)
// as f32 x, y, z, nx, ny, nz (+0x4, +0x8, +0xc, +0x44, +0x48, +0x4c), the flag bytes (5th argument, {u32 cap, u32 count,
// ptr}) and the input index list (this[1]); on exit the merged index list (this + 0x30), for every call.
'use strict';
const TDB = 'tooldatabuilder.modder.x64.dll';
const FULL = 24;
let hooked = false, calls = 0;
function vec(p) { return { count: p.add(4).readU32(), data: p.add(8).readPointer() }; }
function setup() {
  const tdb = Process.findModuleByName(TDB);
  if (!tdb || hooked) return;
  Interceptor.attach(tdb.base.add(0xd0140), {
    onEnter(a) {
      this.m = a[0]; this.call = calls++;
      if (this.call >= FULL) return;
      const verts = vec(this.m.readPointer()), tris = vec(this.m.add(8).readPointer()), flags = vec(a[4]);
      const out = new ArrayBuffer(verts.count * 24), v = new DataView(out);
      for (let i = 0; i < verts.count; i++) {
        const r = verts.data.add(i * 8).readPointer();
        v.setFloat32(i * 24, r.add(4).readFloat(), true);
        v.setFloat32(i * 24 + 4, r.add(8).readFloat(), true);
        v.setFloat32(i * 24 + 8, r.add(12).readFloat(), true);
        v.setFloat32(i * 24 + 12, r.add(0x44).readFloat(), true);
        v.setFloat32(i * 24 + 16, r.add(0x48).readFloat(), true);
        v.setFloat32(i * 24 + 20, r.add(0x4c).readFloat(), true);
      }
      send({ kind: 'verts', call: this.call, count: verts.count }, out);
      send({ kind: 'flags', call: this.call, count: flags.count }, flags.data.readByteArray(flags.count));
      send({ kind: 'tris', call: this.call, count: tris.count }, tris.data.readByteArray(tris.count * 4));
    },
    onLeave() {
      const r = vec(this.m.add(0x30));
      if (r.count > 0) send({ kind: 'merged', call: this.call, count: r.count }, r.data.readByteArray(r.count * 4));
      else send({ kind: 'merged', call: this.call, count: 0 });
    }
  });
  hooked = true;
  send({ kind: 'hooked', tdb: tdb.base.toString() });
}
setup();
let polls = 0;
const iv = setInterval(() => { polls++; setup(); if (hooked || polls > 4000) clearInterval(iv); }, 250);
send({ kind: 'loaded' });
