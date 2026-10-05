def order(keys, hashf, rehash_first=False, rehash_eq=True):
    lst = []; nb = 8
    def rehash():
        nonlocal lst, nb
        nb = nb * 8 if nb < 512 else nb * 2
        new = []
        for x in lst:
            b = hashf(x) & (nb - 1)
            idxs = [i for i, y in enumerate(new) if hashf(y) & (nb - 1) == b]
            eq = [i for i in idxs if hashf(new[i]) == hashf(x)] if rehash_eq else []
            if not idxs: new.append(x)
            elif eq: new.insert(eq[-1] + 1, x)
            else: new.insert(idxs[0], x)
        lst = new
    for k in keys:
        if rehash_first and len(lst) + 1 > nb: rehash()
        b = hashf(k) & (nb - 1)
        idxs = [i for i, x in enumerate(lst) if hashf(x) & (nb - 1) == b]
        eq = [i for i in idxs if hashf(lst[i]) == hashf(k)]
        if eq: lst.insert(eq[-1] + 1, k)
        elif idxs: lst.insert(idxs[0], k)
        else: lst.append(k)
        if not rehash_first and len(lst) > nb: rehash()
    return lst
