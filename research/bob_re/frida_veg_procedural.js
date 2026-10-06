// Frida: BOB Vegetation / Procedural Generation. Hooks qttoolutility QTU::ProceduralTerrainContent::generate and dumps
// its Input (compiled parameters: header, channel ends, groups, objects, object parameter structs + model strings; the
// composited height and blend Array3<float> maps; the exclusion zone; the seed) and its result (3 instance vectors).
// Run with research/battle_build/frida_run_battle.py.
'use strict';
const RVA_GENERATE = 0x85510;
const RVA_GROUP_COMPILE = 0xd7660;   // FUN_1800d7660(state, out 0x14, pair {int channel, VegetationGroupParameters*})
let sData = null, sLen = null;
function caStr(p) {
    if (sData === null) {
        const c = Process.findModuleByName('calibs.modder.x64.dll');
        sData = new NativeFunction(c.getExportByName('?data@String@CA@@QEBAPEBDXZ'), 'pointer', ['pointer']);
        sLen = new NativeFunction(c.getExportByName('?length@String@CA@@QEBAIXZ'), 'uint', ['pointer']);
    }
    const n = sLen(p);
    return n === 0 ? '' : sData(p).readUtf8String(n);
}
function vec(p, stride) {   // std::vector {begin, end, cap}
    const b = p.readPointer(), e = p.add(8).readPointer();
    return { b, n: e.sub(b).toInt32() / stride };
}
function bytes(p, n) { return n > 0 ? p.readByteArray(n) : new ArrayBuffer(0); }
let call = 0;
function attach() {
    const m = Process.findModuleByName('qttoolutility.modder.x64.dll');
    if (!m || !Process.findModuleByName('calibs.modder.x64.dll')) { setTimeout(attach, 20); return; }
    send({ kind: 'module', base: m.base.toString() });
    Interceptor.attach(m.base.add(RVA_GROUP_COMPILE), {
        onEnter(args) {
            this.out = args[1];
            const pair = args[2];
            const g = pair.add(8).readPointer();
            const probs = [];
            for (let i = 0; i < 8; i++) probs.push(caStr(g.add(0x50 + 16 * i)));
            this.info = { kind: 'group_compile', k: call, channel: pair.readS32(), name: caStr(g), texture: caStr(g.add(0x40)), probs,
                          raw: Array.from(new Uint8Array(g.add(0x10).readByteArray(0x30))) };
        },
        onLeave() { send(this.info, bytes(this.out, 0x14)); }
    });
    Interceptor.attach(m.base.add(RVA_GENERATE), {
        onEnter(args) {
            const k = call++;
            this.k = k; this.ret = args[0];
            const inp = args[1];
            send({ kind: 'input_raw', k }, bytes(inp, 0x48));
            const cp = inp.readPointer();
            send({ kind: 'compiled_header', k }, bytes(cp, 0xb8));
            const g = vec(cp.add(0x10), 0x14), o = vec(cp.add(0x28), 0xc), op = vec(cp.add(0x40), 8);
            send({ kind: 'groups', k, n: g.n }, bytes(g.b, g.n * 0x14));
            send({ kind: 'objects', k, n: o.n }, bytes(o.b, o.n * 0xc));
            const ptrs = [];
            for (let i = 0; i < op.n; i++) {
                const q = op.b.add(i * 8).readPointer();
                ptrs.push(q.toString());
                send({ kind: 'object_param', k, i, ptr: q.toString(), name: caStr(q), group: caStr(q.add(0xa0)) }, bytes(q, 0x100));
            }
            this.ptrs = ptrs;
            // mask bit vector at +0x90 (begin,end) if present
            const mb = cp.add(0x90).readPointer(), me = cp.add(0x98).readPointer();
            if (!mb.isNull()) send({ kind: 'mask', k }, bytes(mb, me.sub(mb).toInt32()));
            for (const [name, off] of [['height', 0x10], ['blend', 0x20]]) {
                const a = inp.add(off).readPointer();
                if (a.isNull()) { send({ kind: name, k, null: true }); continue; }
                const c = a.readS32(), w = a.add(4).readS32(), h = a.add(8).readS32();
                const d = a.add(0x10).readPointer();
                send({ kind: name, k, c, w, h, hdr: Array.from(new Uint32Array(a.readByteArray(0x20))) },
                     bytes(d, c * w * h * 4));
            }
            send({ kind: 'exclusion_raw', k }, bytes(inp.add(0x30), 0x10));
            const ez = inp.add(0x30).readPointer();
            if (!ez.isNull()) {
                send({ kind: 'exclusion', k }, bytes(ez, 0xb0));
                const np = ez.add(4).readS32();
                const idx = ez.add(8).readPointer();
                if (np > 0) send({ kind: 'exclusion_index', k, np }, bytes(idx, np * 2));
                const vb = ez.add(0x98).readPointer(), ve = ez.add(0xa0).readPointer();
                if (!vb.isNull()) send({ kind: 'exclusion_verts', k }, bytes(vb, ve.sub(vb).toInt32()));
            }
        },
        onLeave() {
            const outer = vec(this.ret, 0x18);
            for (let j = 0; j < outer.n; j++) {
                const v = vec(outer.b.add(j * 0x18), 0x18);
                const buf = new ArrayBuffer(v.n * 20), dv = new DataView(buf);
                const raw = v.n > 0 ? v.b.readByteArray(v.n * 0x18) : new ArrayBuffer(0);
                const rv = new DataView(raw);
                for (let i = 0; i < v.n; i++) {
                    const lo = rv.getUint32(i * 0x18, true), hi = rv.getUint32(i * 0x18 + 4, true);
                    const ptr = ptr64(hi, lo);
                    dv.setInt32(i * 20, this.ptrs.indexOf(ptr), true);
                    for (let f = 0; f < 4; f++) dv.setUint32(i * 20 + 4 + f * 4, rv.getUint32(i * 0x18 + 8 + f * 4, true), true);
                }
                send({ kind: 'instances', k: this.k, pass: j, n: v.n }, buf);
            }
        }
    });
}
function ptr64(hi, lo) { return '0x' + (BigInt(hi) * 4294967296n + BigInt(lo)).toString(16); }
attach();
