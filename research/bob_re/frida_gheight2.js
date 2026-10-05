// Frida hook for BOB "Global Mesh", race-free version of frida_gheight.js: on entry to warscape
// TERRAIN_RENDER_SETUP::get_height_worker (RVA 0x371030; this, pos, TILE_INSTANCE, bool* valid, float* lf, float* hf,
// bool) it calls the function itself with its own out buffers, so it gets the float result, the valid flag and the lf
// part of the same call. Records of 32 bytes: f32 x, f32 z, i16 tile x, i16 tile y, u16 orientation, u8 valid, u8 flag
// arg, f32 lf, f32 result, f32 hf_out, u32 call index. After LIMIT calls it detaches so BOB runs at full speed.
'use strict';
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
