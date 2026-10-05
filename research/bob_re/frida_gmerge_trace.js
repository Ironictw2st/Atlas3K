// Frida trace of BOB's TRIANGLE_MERGER for selected merge calls (tooldatabuilder): FUN_1800d0140 process (this+0x50
// factor, +0x54 span, +0x58 step, +0x5c pass limit); while a traced call runs, FUN_1800cfdb0 (pass start),
// FUN_1800cf400 (removable: v, result) and FUN_1800cfa40 (v, result, target, candidates at this+0x70 / count
// this+0x6c) are hooked, so other merges run at full speed. Text records, batched.
'use strict';
const TDB = 'tooldatabuilder.modder.x64.dll';
const TRACE = [7, 134, 184];
let hooked = false, calls = 0, cur = -1, lines = [], inner = [];
function out(s) { lines.push(s); if (lines.length >= 4000) { send({ kind: 'trace', call: cur, text: lines.join('\n') }); lines = []; } }
function setup() {
  const tdb = Process.findModuleByName(TDB);
  if (!tdb || hooked) return;
  function attachInner() {
    inner.push(Interceptor.attach(tdb.base.add(0xcfdb0), {
      onEnter(a) { out(`pass limit ${a[0].add(0x5c).readFloat()} factor ${a[0].add(0x50).readFloat()} tris ${a[0].add(0x1c).readU32()}`); }
    }));
    inner.push(Interceptor.attach(tdb.base.add(0xcfa40), {
      onEnter(a) { this.m = a[0]; this.v = a[1].toUInt32(); this.t = a[2]; },
      onLeave(r) {
        const n = this.m.add(0x6c).readU32(), p = this.m.add(0x70).readPointer();
        const c = [];
        for (let i = 0; i < n && i < 64; i++) c.push(p.add(i * 4).readU32());
        out(`cand v ${this.v} ok ${r.toUInt32() & 0xff} target ${this.t.readU32()} n ${n} [${c.join(',')}]`);
      }
    }));
    inner.push(Interceptor.attach(tdb.base.add(0xcf400), {
      onEnter(a) { this.v = a[1].toUInt32(); },
      onLeave(r) { out(`rem v ${this.v} ${r.toUInt32() & 0xff}`); }
    }));
  }
  Interceptor.attach(tdb.base.add(0xd0140), {
    onEnter(a) {
      cur = calls++; this.active = TRACE.indexOf(cur) >= 0; this.m = a[0];
      if (this.active) { out(`process ${cur}`); attachInner(); }
    },
    onLeave() {
      if (!this.active) return;
      inner.forEach(l => l.detach()); inner = [];
      const m = this.m;
      out(`end factor ${m.add(0x50).readFloat()} span ${m.add(0x54).readFloat()} step ${m.add(0x58).readFloat()} limit ${m.add(0x5c).readFloat()} out ${m.add(0x34).readU32()}`);
      send({ kind: 'trace', call: cur, text: lines.join('\n') }); lines = [];
    }
  });
  hooked = true;
  send({ kind: 'hooked', tdb: tdb.base.toString() });
}
setup();
let polls = 0;
const iv = setInterval(() => { polls++; setup(); if (hooked || polls > 4000) clearInterval(iv); }, 250);
send({ kind: 'loaded' });
