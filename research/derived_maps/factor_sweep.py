import sys, numpy as np, merger_proto as M
v_ref, idx_ref, bb = M.read_mesh(0)
valid = M.global_validity(); L = M.lf_heights()
xs, ys, zs, flags, nrm, tris = M.build(0, 0, L, valid)
for f in [float(a) for a in sys.argv[1:]]:
    out = M.merge(xs, ys, zs, flags, nrm, tris, np.float32(f))
    print('factor', f, '->', len(out), 'triangles (vanilla 7191)', flush=True)
