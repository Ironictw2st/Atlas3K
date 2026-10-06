// Frida: dump every AMD_TC_ConvertTexture call (AMDCompress_MT_DLL.dll): source texture header + pixels, destination
// header, the options struct (first 96 bytes) and the compressed output. AMD_TC_Texture = { u32 size, width, height,
// pitch, format, data_size; u8* data }.
'use strict';
const MOD = 'amdcompress_mt_dll.dll';
let hooked = false, n = 0;
function tex(p) {
  return { size: p.readU32(), w: p.add(4).readU32(), h: p.add(8).readU32(), pitch: p.add(12).readU32(),
           format: p.add(16).readU32(), dataSize: p.add(20).readU32(), data: p.add(24).readPointer() };
}
function setup(m) {
  if (hooked) return;
  Interceptor.attach(m.getExportByName('AMD_TC_ConvertTexture'), {
    onEnter(a) {
      this.i = n++;
      const s = tex(a[0]); this.d = a[1];
      const d = tex(a[1]);
      const o = a[2].isNull() ? null : Array.from(new Uint8Array(a[2].readByteArray(96)));
      send({ kind: 'convert_src', i: this.i, src: { w: s.w, h: s.h, pitch: s.pitch, format: s.format, dataSize: s.dataSize },
             dst: { w: d.w, h: d.h, pitch: d.pitch, format: d.format, dataSize: d.dataSize }, options: o },
           s.data.readByteArray(s.dataSize));
    },
    onLeave(r) {
      const d = tex(this.d);
      send({ kind: 'convert_dst', i: this.i, ret: r.toInt32() }, d.data.readByteArray(d.dataSize));
    }
  });
  hooked = true;
  send({ kind: 'hooked' });
}
let polls = 0;
const iv = setInterval(() => {
  polls++;
  if (!hooked) { const mm = Process.findModuleByName(MOD) || Process.findModuleByName('AMDCompress_MT_DLL.dll'); if (mm) setup(mm); }
  if (hooked || polls > 24000) clearInterval(iv);
}, 5);
