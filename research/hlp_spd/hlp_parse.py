"""Parse hlp_data.esf (CAI_TRANSITION_DATA) and print a summary.
usage: hlp_parse.py <hlp_data.esf> [-v]"""
import sys
from esf_flat import header, tokens


class R:
    def __init__(self, toks):
        self.t = toks; self.i = 0

    def v(self):
        x = self.t[self.i][2]; self.i += 1; return x


def parse(path):
    b = open(path, "rb").read()
    h = header(b)
    toks, _ = tokens(b, h["body"], h["end"])
    r = R(toks)
    n = r.v()
    nodes = []
    for _ in range(n):
        nd = {"id": r.v(), "subs": []}
        k = r.v()
        for _ in range(k):
            s = {"area": r.v(), "centre": (r.v(), r.v()), "a": r.v(), "b": r.v()}
            m = r.v()
            s["tr"] = [dict(p=(r.v(), r.v()), q=(r.v(), r.v()), cost=r.v(), to=r.v(), idx=r.v(), f1=r.v(), f2=r.v())
                       for _ in range(m)]
            s["mat"] = [r.v() for _ in range(m * (m - 1))]
            nd["subs"].append(s)
        nodes.append(nd)
    return h, nodes, toks[r.i:], toks


if __name__ == "__main__":
    h, nodes, rest, toks = parse(sys.argv[1])
    print("nodes", len(nodes), "subs", sum(len(n["subs"]) for n in nodes), "rest tokens", len(rest), "of", len(toks))
    print("rest head", [(f"{t:02x}", v) for _, t, v in rest[:80]])
    if "-v" in sys.argv:
        for nd in nodes:
            for s in nd["subs"]:
                print(nd["id"], len(nd["subs"]), s["area"], s["centre"], s["a"], s["b"], len(s["tr"]))
