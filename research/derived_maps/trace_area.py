import numpy as np, merger_proto as M
M.TRACE=[]
v_ref, idx_ref, bb = M.read_mesh(0)
valid = M.global_validity_from_coverage(); L = M.lf_heights()
xs, ys, zs, flags, nrm, tris = M.build(0, 0, L, valid)
out = M.merge(xs, ys, zs, flags, nrm, tris, np.float32(0.9999))
N=M.N
g=lambda q:(q%N,q//N)
for it,v,w,c in M.TRACE:
    i,j=g(v)
    if 8<=i<=12 and 0<=j<=4:
        print('iter',it,'v',g(v),'->',g(w),'flags',flags[v],flags[w],'cands',[g(x) for x in c])
