"""Compare the raw 32-byte river vertices/indices that FUN_18015e9e0 emits (Frida dump, frida_rivers2.js) with the
prototype sections (exact_cmp.build_world) and with BOB's final file.
usage: raw_cmp.py <frida jsonl> [river]"""
import json, sys, collections, numpy as np
sys.path.insert(0, '.')
import exact_cmp as E
F = np.float32


def load(path):
    out = []
    for l in open(path, encoding='utf-8'):
        m = json.loads(l)
        if m['kind'] != 'mesh': continue
        raw = bytes.fromhex(m['verts']); v = np.frombuffer(raw, np.uint8).reshape(-1, 32)
        idx = np.frombuffer(bytes.fromhex(m['idx']), np.uint32)
        out.append(dict(raw=v, h=v[:, :12].copy().view(np.float16).astype(np.float32), idx=idx))
    return out


if __name__ == "__main__":
    D = load(sys.argv[1])
    for d in D:
        p = d['h'][:, :3]
        d['k'] = min(range(len(E.rs)), key=lambda k: np.abs(E.build_world(k)[2].min(0) - p.min(0)).sum() + np.abs(E.build_world(k)[2].max(0) - p.max(0)).sum()) if False else None
    worlds = {k: E.build_world(k) for k in range(len(E.rs))}
    tot = eq = 0
    for i, d in enumerate(D):
        p = d['h'][:, :3]
        k = min(worlds, key=lambda k: np.abs(worlds[k][2].min(0) - p.min(0)).sum() + np.abs(worlds[k][2].max(0) - p.max(0)).sum())
        name, ts, v = worlds[k]
        n = min(len(v), len(p)); same = (v[:n] == p[:n]).all(1)
        tot += len(p); eq += same.sum()
        print(f"dump {i:2d} {name:9s} raw {len(p):4d} ours {len(v):4d} ordered-equal {same.sum():4d} x {int((v[:n,0]!=p[:n,0]).sum())} y {int((v[:n,1]!=p[:n,1]).sum())} z {int((v[:n,2]!=p[:n,2]).sum())} idx {len(d['idx'])}")
    print(f"raw vs prototype ordered: {eq}/{tot} = {eq/tot:.1%}")
