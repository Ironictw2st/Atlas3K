// Frida: get_height_worker calls (race-free, as frida_gheight2.js) only while BOB builds the height grid of one mesh:
// the worker hook is attached on entry to tooldatabuilder FUN_180147cf0 (the grid lambda driver, once per mesh in loop
// order: land k = 0.., then sea) for call TARGET and detached on exit, so the rest of the run is not slowed.
'use strict';
const WS = 'warscape.modder.x64.dll', TDB = 'tooldatabuilder.modder.x64.dll';
const TARGET = 170, BATCH = 8192;
let hooked = false, grids = 0, n = 0, fill = 0, buf = new ArrayBuffer(BATCH * 32), view = new DataView(buf), listener = null;
function flush() { if (fill) { send({ kind: 'calls', count: fill, upto: n }, buf.slice(0, fill * 32)); fill = 0; } }
function setup() {
  const ws = Process.findModuleByName(WS), tdb = Process.findModuleByName(TDB);
  if (!ws || !tdb || hooked) return;
  const addr = ws.base.add(0x371030);
  const fn = new NativeFunction(addr, 'float', ['pointer', 'pointer', 'pointer', 'pointer', 'pointer', 'pointer', 'uint8']);
  Interceptor.attach(tdb.base.add(0x147cf0), {
    onEnter() {
      this.idx = grids++;
      if (this.idx !== TARGET) return;
      send({ kind: 'target_start', idx: this.idx });
      listener = Interceptor.attach(addr, {
        onEnter(a) {
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
        }
      });
    },
    onLeave() {
      if (this.idx !== TARGET || !listener) return;
      listener.detach(); listener = null; flush();
      send({ kind: 'target_end', idx: this.idx, calls: n });
    }
  });
  hooked = true;
  send({ kind: 'hooked' });
}
setup();
let polls = 0;
const iv = setInterval(() => { polls++; setup(); if (hooked || polls > 4000) clearInterval(iv); }, 250);
send({ kind: 'loaded' });
