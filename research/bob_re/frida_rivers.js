// Frida hooks for BOB "Terry file" river meshes (tooldatabuilder.modder.x64.dll + utilitydll.modder.x64.dll):
//  - SEGMENTED_SPLINE_3(uint,uint,bool) ctor (utilitydll export)  -> marks the start of a river spline
//  - FUN_18016e440 (tooldatabuilder RVA 0x16e440) segment add       -> raw P0..P3 in, stored control points + length out
//  - SEGMENTED_SPLINE_3::optimise_spline (utilitydll export)       -> the sample parameter list out
// Floats are sent as hex bit patterns (exact).
'use strict';
const TDB = 'tooldatabuilder.modder.x64.dll', UTL = 'utilitydll.modder.x64.dll';
let hooked = false;
const hx = p => { const b = new Uint32Array(1); b[0] = p.readU32(); return b[0].toString(16); };
const v3 = p => [hx(p), hx(p.add(4)), hx(p.add(8))];
function setup() {
  const tdb = Process.findModuleByName(TDB), utl = Process.findModuleByName(UTL);
  if (!tdb || !utl || hooked) return;
  const ctor = utl.getExportByName('??0SEGMENTED_SPLINE_3@UTILITYDLL@@QEAA@II_N@Z');
  Interceptor.attach(ctor, { onEnter(a) { send({ kind: 'spline', self: a[0].toString(), a1: a[1].toInt32(), a2: a[2].toInt32() }); } });
  Interceptor.attach(tdb.base.add(0x16e440), {
    onEnter(a) {
      this.s = a[0];
      this.in = [v3(a[1]), v3(a[2]), v3(a[3]), v3(a[4])];
    },
    onLeave() {
      const s = this.s, n = s.add(4).readU32(), data = s.add(8).readPointer().add((n - 1) * 0x30);
      const ctrl = [0, 0xc, 0x18, 0x24].map(o => v3(data.add(o)));
      // param_1 + 4 (uint idx 4 -> byte 0x10): lengths vector {cap, count, ptr}
      const lc = s.add(0x14).readU32(), lp = s.add(0x18).readPointer();
      const len = hx(lp.add((lc - 1) * 4));
      const total = hx(s.add(0x30));
      send({ kind: 'seg', self: s.toString(), in: this.in, ctrl: ctrl, len: len, total: total });
    }
  });
  const opt = utl.getExportByName('?optimise_spline@SEGMENTED_SPLINE_3@UTILITYDLL@@QEBAXAEAV?$VECTOR@MV?$ALLOCATOR@M@CA_STD@@UVECTOR_TRAITS@DETAIL@2@@CA_STD@@MAEBV34@M@Z');
  Interceptor.attach(opt, {
    onEnter(a) { this.self = a[0]; this.out = a[1]; this.extra = a[3]; },
    onLeave() {
      const n = this.out.add(4).readU32(), p = this.out.add(8).readPointer();
      const ts = []; for (let i = 0; i < n; i++) ts.push(hx(p.add(4 * i)));
      send({ kind: 'opt', self: this.self.toString(), n: n, ts: ts });
    }
  });
  hooked = true;
  send({ kind: 'hooked', tdb: tdb.base.toString(), utl: utl.base.toString() });
}
setup();
let polls = 0;
const iv = setInterval(() => { polls++; setup(); if (hooked || polls > 4000) clearInterval(iv); }, 250);
send({ kind: 'loaded' });
