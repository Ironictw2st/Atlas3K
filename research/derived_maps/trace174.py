import numpy as np, merger_proto as M
v_ref, idx_ref, bb = M.read_mesh(0)
N=M.N; C=float(M.CELL)
gi=np.round(v_ref[:,0]/C).astype(int); gj=np.round(v_ref[:,2]/C).astype(int)
for q in (8,10,228,229): print('vanilla vert',q,'grid',(gi[q],gj[q]), 'y',v_ref[q,1])
print('vanilla tris 170..178:', idx_ref[170:178].tolist())
for t in idx_ref[170:178]: print('   ', [(gi[q],gj[q]) for q in t])
