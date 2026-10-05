def order(keys, hashf, nonempty="front", rehash_mode="after_hi", grow=lambda nb: nb * 8 if nb < 512 else nb * 2):
    lst = []; nb = 8
    for k in keys:
        if len(lst) + 1 > nb:
            nb = grow(nb)
            new = []; lo = {}; hi = {}
            for x in lst:
                b = hashf(x) & (nb - 1)
                if b not in lo:
                    new.append(x); lo[b] = hi[b] = x
                elif rehash_mode == "after_hi":
                    i = new.index(hi[b]); new.insert(i + 1, x); hi[b] = x
                else:
                    i = new.index(lo[b]); new.insert(i, x); lo[b] = x
            lst = new
        b = hashf(k) & (nb - 1)
        idxs = [i for i, x in enumerate(lst) if hashf(x) & (nb - 1) == b]
        eq = [i for i in idxs if hashf(lst[i]) == hashf(k)]
        if eq: lst.insert(eq[-1] + 1, k)
        elif idxs: lst.insert(idxs[0] if nonempty == "front" else idxs[-1] + 1, k)
        else: lst.append(k)
    return lst
