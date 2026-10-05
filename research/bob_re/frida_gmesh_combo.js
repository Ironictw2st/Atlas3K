'use strict';
// frida_gheight2.js + frida_gmesh2.js in one script (one BOB run).
(function gheight() {
// Frida hook for BOB "Global Mesh", race-free version of frida_gheight.js: on entry to warscape
// TERRAIN_RENDER_SETUP::get_height_worker (RVA 0x371030; this, pos, TILE_INSTANCE, bool* valid, float* lf, float* hf,
// bool) it calls the function itself with its own out buffers, so it gets the float result, the valid flag and the lf
// part of the same call. Records of 32 bytes: f32 x, f32 z, i16 tile x, i16 tile y, u16 orientation, u8 valid, u8 flag
// arg, f32 lf, f32 result, f32 hf_out, u32 call index. After LIMIT calls it detaches so BOB runs at full speed.

const WS = 'warscape.modder.x64.dll';
const LIMIT = 1500000, BATCH = 8192;
let hooked = false, n = 0, done = false, buf = new ArrayBuffer(BATCH * 32), view = new DataView(buf), fill = 0;
let fn = null;
function flush() {
  if (fill === 0) return;
  send({ kind: 'calls', count: fill, upto: n }, buf.slice(0, fill * 32));
  fill = 0;
}
function setup() {
  const ws = Process.findModuleByName(WS);
  if (!ws || hooked) return;
  const addr = ws.base.add(0x371030);
  fn = new NativeFunction(addr, 'float', ['pointer', 'pointer', 'pointer', 'pointer', 'pointer', 'pointer', 'uint8']);
  const listener = Interceptor.attach(addr, {
    onEnter(a) {
      if (done) return;
      const out = Memory.alloc(16);
      out.writeU8(0); out.add(4).writeFloat(NaN); out.add(8).writeFloat(NaN);
      const flag = a[6].toUInt32() & 0xff;
      const r = fn(a[0], a[1], a[2], out, out.add(4), out.add(8), flag);
      const o = fill * 32;
      view.setFloat32(o, a[1].readFloat(), true);
      view.setFloat32(o + 4, a[1].add(4).readFloat(), true);
      view.setInt16(o + 8, a[2].add(8).readS16(), true);
      view.setInt16(o + 10, a[2].add(10).readS16(), true);
      view.setUint16(o + 12, a[2].add(12).readU16(), true);
      view.setUint8(o + 14, out.readU8());
      view.setUint8(o + 15, flag);
      view.setFloat32(o + 16, out.add(4).readFloat(), true);
      view.setFloat32(o + 20, r, true);
      view.setFloat32(o + 24, out.add(8).readFloat(), true);
      view.setUint32(o + 28, n, true);
      fill++; n++;
      if (fill === BATCH) flush();
      if (n >= LIMIT && !done) { done = true; flush(); send({ kind: 'detaching', n: n }); listener.detach(); }
    }
  });
  hooked = true;
  send({ kind: 'hooked', ws: ws.base.toString() });
}
setup();
let polls = 0;
const iv = setInterval(() => { polls++; setup(); if (hooked || polls > 4000) clearInterval(iv); }, 250);
recv('flush', () => flush());
send({ kind: 'loaded' });

})();
(function gmesh() {
// Frida hook for BOB "Global Mesh": TRIANGLE_MERGER::process (tooldatabuilder FUN_1800d0140; this, factor, span,
// tolerance, flags*). On entry, for the first FULL calls: every vertex (this[0] = vector of 0x94-byte record pointers)
// as f32 x, y, z, nx, ny, nz (+0x4, +0x8, +0xc, +0x44, +0x48, +0x4c), the flag bytes (5th argument, {u32 cap, u32 count,
// ptr}) and the input index list (this[1]); on exit the merged index list (this + 0x30), for every call.

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
      if (this.call === 0) send({ kind: 'globals', d_6b2c04: Process.findModuleByName(TDB).base.add(0x6b2c04).readFloat() });
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

})();
