import sys, numpy as np
sys.path.insert(0, '.')
import bob_spline as S
for wf in (False, True):
    for cm in ('local', 'localf32', 'world'):
        S.WORLD_F32 = wf; S.CTRL_MODE = cm
        import importlib, exact_cmp as E
        importlib.reload(E); E.PAIR = None
        ag = []; ex = 0; counts = 0
        for bk in range(len(E.rs)):
            name, nv, nb, common, same = E.compare(bk)
            ag.append(common / nb); ex += same; counts += (nv == nb)
        print(f"world_f32={wf!s:5} ctrl={cm:8s} exact rivers {ex}/24  equal counts {counts}/24  mean exact vertices {np.mean(ag):.1%}", flush=True)
