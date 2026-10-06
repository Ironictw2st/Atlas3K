// Frida: trace EDITOR_TILE_MAP::links_match for one tile file at one point (battle Tilemap). Inside that call it logs
// every TILE_MAP::tile_at_point (x, y, returned id) and link_target_state (point). Set FILTER below.
'use strict';
const MOD = 'warscape.modder.x64.dll';
const FILTER = { file: 'plains_forest_edge_straight_bb_forest0.bin', x: 31, y: 52 };
const RVA = { links: 0x397060, tileAt: 0x353260, lts: 0x3978b0 };
let hooked = false, inside = 0;

function setup(m) {
  if (hooked) return;
  const base = m.base;
  const exp = n => m.getExportByName(n);
  const cal = n => Process.getModuleByName('calibs.modder.x64.dll').getExportByName(n);
  const binName = new NativeFunction(exp('?binary_filename@TILE_DATABASE_TILE@WARSCAPE@@QEBA?AVString@CA@@XZ'), 'pointer', ['pointer', 'pointer']);
  const sData = new NativeFunction(cal('?data@String@CA@@QEBAPEBDXZ'), 'pointer', ['pointer']);
  const sLen = new NativeFunction(cal('?length@String@CA@@QEBAIXZ'), 'uint', ['pointer']);
  const str = s => { const p = sData(s); return p.isNull() ? '' : p.readUtf8String(sLen(s)); };
  const cache = new Map();
  const fileOf = t => { const k = t.toString(); if (!cache.has(k)) cache.set(k, str(binName(t, Memory.alloc(64)))); return cache.get(k); };
  Interceptor.attach(base.add(RVA.links), {
    onEnter(a) {
      this.match = a[2].toUInt32() === FILTER.x && a[3].toUInt32() === FILTER.y;
      if (this.match) { inside++; send({ kind: 'links_enter', file: fileOf(a[1]), rot: a[4].toUInt32() }); }
    },
    onLeave(r) { if (this.match) { inside--; send({ kind: 'links_leave', ret: r.toInt32() & 0xff }); } }
  });
  Interceptor.attach(base.add(RVA.tileAt), {
    onEnter(a) { if (inside) { this.on = true; this.x = a[1].toUInt32(); this.y = a[2].toUInt32(); } },
    onLeave(r) { if (this.on) send({ kind: 'tile_at', x: this.x, y: this.y, id: (r.toUInt32() >>> 0).toString(16) }); }
  });
  Interceptor.attach(base.add(RVA.lts), {
    onEnter(a) { if (inside) send({ kind: 'lts', x: a[1].readS32(), y: a[1].add(4).readS32() }); }
  });
  hooked = true;
  send({ kind: 'hooked' });
}
const m = Process.findModuleByName(MOD);
if (m) setup(m);
let polls = 0;
const iv = setInterval(() => { polls++; if (!hooked) { const mm = Process.findModuleByName(MOD); if (mm) setup(mm); } if (hooked || polls > 2400) clearInterval(iv); }, 50);
