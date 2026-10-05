"""Does the C# MsvcSort port (transcribed below 1:1) turn BOB's pass-sort input into BOB's output?
Keys (valid sub-tiles v, link targets t) come from the simulator's --pass-order exports (sim_order_<p>.txt lines:
'<file> v<n> t<n> l<n> r<n>'). usage: sort_check.py <frida jsonl> [order dir]"""
import json, re, sys
from pathlib import Path
src = Path(sys.argv[1]); d = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent
msgs = [json.loads(l) for l in open(src, encoding="utf-8")]

def msvc_sort(a, less):
    def med3(f, m, l):
        if less(a[m], a[f]): a[m], a[f] = a[f], a[m]
        if less(a[l], a[m]):
            a[l], a[m] = a[m], a[l]
            if less(a[m], a[f]): a[m], a[f] = a[f], a[m]
    def guess(f, m, l):
        c = l - f
        if c > 40:
            s = (c + 1) >> 3; t = s << 1
            med3(f, f + s, f + t); med3(m - s, m, m + s); med3(l - t, l - s, l); med3(f + s, m, l - s)
        else: med3(f, m, l)
    def partition(first, last):
        mid = first + ((last - first) >> 1)
        guess(first, mid, last - 1)
        pf, pl = mid, mid + 1
        while first < pf and not less(a[pf - 1], a[pf]) and not less(a[pf], a[pf - 1]): pf -= 1
        while pl < last and not less(a[pl], a[pf]) and not less(a[pf], a[pl]): pl += 1
        gf, gl = pl, pf
        while True:
            while gf < last:
                if less(a[pf], a[gf]): gf += 1; continue
                if less(a[gf], a[pf]): break
                if pl != gf: a[pl], a[gf] = a[gf], a[pl]
                pl += 1; gf += 1
            while first < gl:
                if less(a[gl - 1], a[pf]): gl -= 1; continue
                if less(a[pf], a[gl - 1]): break
                pf -= 1
                if pf != gl - 1: a[pf], a[gl - 1] = a[gl - 1], a[pf]
                gl -= 1
            if gl == first and gf == last: return pf, pl
            if gl == first:
                if pl != gf: a[pf], a[pl] = a[pl], a[pf]
                pl += 1; a[pf], a[gf] = a[gf], a[pf]; pf += 1; gf += 1
            elif gf == last:
                gl -= 1; pf -= 1
                if gl != pf: a[gl], a[pf] = a[pf], a[gl]
                pl -= 1; a[pf], a[pl] = a[pl], a[pf]
            else:
                gl -= 1; a[gf], a[gl] = a[gl], a[gf]; gf += 1
    def ins(first, last):
        for mid in range(first + 1, last):
            v = a[mid]
            if less(v, a[first]): a[first + 1:mid + 1] = a[first:mid]; a[first] = v
            else:
                h = mid
                while less(v, a[h - 1]): a[h] = a[h - 1]; h -= 1
                a[h] = v
    def rng(first, last, ideal):
        while True:
            if last - first <= 32: ins(first, last); return
            if ideal <= 0: raise RuntimeError("heap path not ported here")
            mf, ms = partition(first, last)
            ideal = (ideal >> 1) + (ideal >> 2)
            if mf - first < last - ms: rng(first, mf, ideal); first = ms
            else: rng(ms, last, ideal); last = mf
    rng(0, len(a), len(a))
    return a

for p, kind in ((1, "sort"), (2, "sort"), (3, "sort_junction"), (4, "sort"), (5, "sort"), (0, "sort")):
    bef = next((m["tiles"] for m in msgs if m["kind"] == kind + "_before" and m.get("pass") == p), None)
    aft = next((m["tiles"] for m in msgs if m["kind"] == kind + "_after" and m.get("pass") == p), None)
    of = d / f"sim_order_{p}.txt"
    if bef is None or not of.exists(): print(f"pass {p}: no data"); continue
    keys = {}
    for l in open(of, encoding="utf-8"):
        m = re.match(r"(\S+) v(\d+) t(\d+)", l.strip())
        if m: keys[m.group(1).lower()] = (int(m.group(2)), int(m.group(3)))
    f = lambda t: t.split("|")[0].lower()
    if p == 3: less = lambda x, y: keys[f(x)][1] < keys[f(y)][1]
    else: less = lambda x, y: keys[f(x)] != keys[f(y)] and ((keys[f(x)][0] > keys[f(y)][0]) if keys[f(x)][0] != keys[f(y)][0] else keys[f(x)][1] > keys[f(y)][1])
    out = msvc_sort(list(bef), less)
    ok = [f(x) for x in out] == [f(x) for x in aft]
    bad = next((i for i, (x, y) in enumerate(zip(out, aft)) if f(x) != f(y)), None)
    print(f"pass {p}: n {len(bef)}  port(BOB input) == BOB output: {ok}" + ("" if ok else f"  first diff at {bad}: port {f(out[bad])} / bob {f(aft[bad])}"))
    sorted_ok = all(not less(aft[i + 1], aft[i]) for i in range(len(aft) - 1))
    print(f"         BOB output is sorted by these keys: {sorted_ok}")
