import sys, numpy as np, merger_proto as M
v_ref, idx_ref, bb = M.read_mesh(0)
valid = M.global_validity(); L = M.lf_heights()
N=M.N; C=float(M.CELL)
gi=np.round(v_ref[:,0]/C).astype(int); gj=np.round(v_ref[:,2]/C).astype(int)
p=v_ref[idx_ref].astype(float)
area=np.abs((p[:,1,0]-p[:,0,0])*(p[:,2,2]-p[:,0,2])-(p[:,2,0]-p[:,0,0])*(p[:,1,2]-p[:,0,2]))
ref=set(gj[q]*N+gi[q] for t in idx_ref[area>1e-9] for q in t)
for k in [float(a) for a in sys.argv[1:]]:
    M.NZ_SCALE=k
    xs, ys, zs, flags, nrm, tris = M.build(0, 0, L, valid)
    out = M.merge(xs, ys, zs, flags, nrm, tris, np.float32(0.9999))
    ours=set(q for t in out for q in t)
    print(f'nz scale {k}: {len(out)} tris, {len(ours)} verts, common with vanilla {len(ours&ref)} / {len(ref)}', flush=True)
