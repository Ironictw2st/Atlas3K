// Frida hook for BOB "Global Mesh": warscape TERRAIN_RENDER_SETUP::get_height_worker(pos, TILE_INSTANCE, bool& valid,
// float* lf, float* hf, bool) at RVA 0x371030, as FUN_18016ae30 calls it through get_height. Out pointers that are null
// get scratch buffers, so every call reports the lf part and the hf raw/mesh value. Records of 32 bytes:
// f32 x, f32 z, i16 tile x, i16 tile y, u16 orientation, u8 valid, u8 had_lf_ptr, f32 lf, f32 hf_out, u32 variation ptr
// low bits, u32 call index. Batched as binary messages; stops after LIMIT calls.
'use strict';
const WS = 'warscape.modder.x64.dll';
const LIMIT = 3000000, BATCH = 8192;
let hooked = false, n = 0, buf = new ArrayBuffer(BATCH * 32), view = new DataView(buf), fill = 0;
const scratch = Memory.alloc(16);
function flush() {
  if (fill === 0) return;
  send({ kind: 'calls', count: fill, upto: n }, buf.slice(0, fill * 32));
  fill = 0;
}
function setup() {
  const ws = Process.findModuleByName(WS);
  if (!ws || hooked) return;
  Interceptor.attach(ws.base.add(0x371030), {
    onEnter(a) {
      if (n >= LIMIT) { this.skip = true; return; }
      this.pos = a[1]; this.ti = a[2]; this.valid = a[3];
      this.lfp = a[4]; this.hfp = a[5];
      this.hadLf = !this.lfp.isNull();
      if (this.lfp.isNull()) { a[4] = scratch; this.lfp = scratch; }
      if (this.hfp.isNull()) { a[5] = scratch.add(8); this.hfp = scratch.add(8); }
      this.lfp.writeFloat(NaN); this.hfp.writeFloat(NaN);
    },
    onLeave() {
      if (this.skip) return;
      const o = fill * 32;
      view.setFloat32(o, this.pos.readFloat(), true);
      view.setFloat32(o + 4, this.pos.add(4).readFloat(), true);
      view.setInt16(o + 8, this.ti.add(8).readS16(), true);
      view.setInt16(o + 10, this.ti.add(10).readS16(), true);
      view.setUint16(o + 12, this.ti.add(12).readU16(), true);
      view.setUint8(o + 14, this.valid.readU8());
      view.setUint8(o + 15, this.hadLf ? 1 : 0);
      view.setFloat32(o + 16, this.lfp.readFloat(), true);
      view.setFloat32(o + 20, this.hfp.readFloat(), true);
      view.setUint32(o + 24, this.ti.readPointer().and(0xffffffff).toUInt32(), true);
      view.setUint32(o + 28, n, true);
      fill++; n++;
      if (fill === BATCH) flush();
      if (n === LIMIT) flush();
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
