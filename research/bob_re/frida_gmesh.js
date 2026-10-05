// Frida hook for BOB "Global Mesh" (tooldatabuilder FUN_180124ed0): per mesh, the height grid that goes into the
// normals pass FUN_180147860 (arg0: float[N*N], -20 = hole; arg2: N), the 0x94-byte vertex records after the normals
// pass (normals at +0x44; full records for the first FULL calls, else +0x40..+0x54 only), and the merged index list
// TRIANGLE_MERGER process FUN_1800d0140 leaves at this+0x30 ({u32 cap, u32 count, ptr}). Binary data goes out as the
// message's data buffer (frida_bob.py writes it next to the jsonl).
'use strict';
const TDB = 'tooldatabuilder.modder.x64.dll';
const FULL = 2;
let hooked = false, calls = 0, merges = 0;
function setup() {
  const tdb = Process.findModuleByName(TDB);
  if (!tdb || hooked) return;
  Interceptor.attach(tdb.base.add(0x147860), {
    onEnter(a) {
      this.h = a[0]; this.vec = a[1]; this.n = a[2].toInt32();
      const n = this.n;
      send({ kind: 'heights', call: calls, n: n }, this.h.readByteArray(n * n * 4));
    },
    onLeave() {
      const cnt = this.vec.add(4).readU32(), p = this.vec.add(8).readPointer();
      if (calls < FULL) send({ kind: 'verts_full', call: calls, count: cnt }, p.readByteArray(cnt * 0x94));
      else {
        const buf = new Uint8Array(cnt * 0x14);
        for (let i = 0; i < cnt; i++) buf.set(new Uint8Array(p.add(i * 0x94 + 0x40).readByteArray(0x14)), i * 0x14);
        send({ kind: 'verts_n', call: calls, count: cnt }, buf.buffer);
      }
      calls++;
    }
  });
  Interceptor.attach(tdb.base.add(0xd0140), {
    onEnter(a) { this.m = a[0]; },
    onLeave() {
      const v = this.m.add(0x30), cnt = v.add(4).readU32(), p = v.add(8).readPointer();
      send({ kind: 'merged', merge: merges, count: cnt }, p.readByteArray(cnt * 4));
      merges++;
    }
  });
  hooked = true;
  send({ kind: 'hooked', tdb: tdb.base.toString() });
}
setup();
let polls = 0;
const iv = setInterval(() => { polls++; setup(); if (hooked || polls > 4000) clearInterval(iv); }, 250);
send({ kind: 'loaded' });
