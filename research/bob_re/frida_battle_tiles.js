// Frida hooks for BOB "Terrain / Tilemap" on a battle map (warscape.modder.x64.dll): logs every scan pass, every
// successful EDITOR_TILE_MAP::test_final_tile_position (tile, point, chosen rotation, RNG state before the test) and
// every EDITOR_TILE_MAP::place_tile (variation location, point, rotation). Used with frida_bob.py to find the first
// divergence of the native battle tile matching (research/battle_map_files).
'use strict';
const MOD = 'warscape.modder.x64.dll';
const RVA = { scan: 0x393500, testFinal: 0x3929e0, place: 0x396020 };
let hooked = false, curPass = -1, seq = 0;

function setup(m) {
  if (hooked) return;
  const base = m.base;
  const exp = n => m.getExportByName(n);
  const cal = n => Process.getModuleByName('calibs.modder.x64.dll').getExportByName(n);
  const binName = new NativeFunction(exp('?binary_filename@TILE_DATABASE_TILE@WARSCAPE@@QEBA?AVString@CA@@XZ'), 'pointer', ['pointer', 'pointer']);
  const vLoc = new NativeFunction(exp('?location@TILE_DATABASE_TILE_VARIATION@WARSCAPE@@QEBAAEBVString@CA@@XZ'), 'pointer', ['pointer']);
  const sData = new NativeFunction(cal('?data@String@CA@@QEBAPEBDXZ'), 'pointer', ['pointer']);
  const sLen = new NativeFunction(cal('?length@String@CA@@QEBAIXZ'), 'uint', ['pointer']);
  const str = s => { const p = sData(s); return p.isNull() ? '' : p.readUtf8String(sLen(s)); };
  const cache = new Map();
  function tileFile(t) {
    const k = t.toString();
    if (!cache.has(k)) { const buf = Memory.alloc(64); cache.set(k, str(binName(t, buf))); }
    return cache.get(k);
  }
  Interceptor.attach(base.add(RVA.scan), { onEnter(a) { curPass = a[1].toInt32(); send({ kind: 'pass', pass: curPass, seq: seq++ }); } });
  Interceptor.attach(base.add(RVA.testFinal), {
    onEnter(a) {
      this.t = a[1]; this.x = a[2].toUInt32(); this.y = a[3].toUInt32(); this.rot = a[5];
      this.s0 = a[0].add(0x40).readU64().toString(16); this.s1 = a[0].add(0x48).readU64().toString(16);
    },
    onLeave(r) {
      if (r.toInt32() & 0xff)
        send({ kind: 'test', pass: curPass, seq: seq++, tile: tileFile(this.t), x: this.x, y: this.y, rot: this.rot.readU16(), s0: this.s0, s1: this.s1 });
    }
  });
  Interceptor.attach(base.add(RVA.place), {
    onEnter(a) { send({ kind: 'place', pass: curPass, seq: seq++, loc: str(vLoc(a[3])), x: a[1].toUInt32(), y: a[2].toUInt32(), rot: a[4].toUInt32() & 0xffff }); }
  });
  hooked = true;
  send({ kind: 'hooked', base: base.toString() });
}

const m = Process.findModuleByName(MOD);
if (m) setup(m);
let polls = 0;
const iv = setInterval(() => {
  polls++;
  if (!hooked) { const mm = Process.findModuleByName(MOD); if (mm) setup(mm); }
  if (hooked || polls > 2400) clearInterval(iv);
}, 50);
