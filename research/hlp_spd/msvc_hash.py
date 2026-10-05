"""Emulation of MSVC std::unordered_multimap iteration order (xhash), identity hash.
insert: rehash first if size+1 > buckets; equal key present -> after the last equal one; bucket non-empty -> front of
the bucket; empty bucket -> list end. Rehash walks the list: a node whose new bucket is empty stays in place, otherwise
it is moved to just after that bucket's last node."""
def order(keys, hashf=lambda k: k):
    lst = []; nb = 8
    def bucket(k): return hashf(k) & (nb - 1)
    for k in keys:
        if len(lst) + 1 > nb:
            nb = nb * 8 if nb < 512 else nb * 2
            new = []; ranges = {}
            for x in lst:
                b = bucket(x)
                if b not in ranges:
                    new.append(x); ranges[b] = x
                else:
                    i = new.index(ranges[b]); new.insert(i + 1, x); ranges[b] = x
            lst = new
        b = bucket(k)
        idxs = [i for i, x in enumerate(lst) if bucket(x) == b]
        eq = [i for i in idxs if hashf(lst[i]) == hashf(k)]
        if eq: lst.insert(eq[-1] + 1, k)
        elif idxs: lst.insert(idxs[0], k)
        else: lst.append(k)
    return lst
