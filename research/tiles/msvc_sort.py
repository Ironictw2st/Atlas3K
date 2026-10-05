"""Exact port of MSVC STL std::sort (introsort) so unstable orderings of equal keys match BOB.

less(a, b) is the strict-weak-ordering predicate. Sorts the list in place.
Mirrors _Sort_unchecked / _Insertion_sort_unchecked / _Partition_by_median_guess_unchecked /
_Guess_median_unchecked / _Med3_unchecked / _Make_heap_unchecked / _Sort_heap_unchecked
(the shapes match the decompiled warscape sorts: <= 32 elements -> insertion sort, ideal <= 0 -> heap sort).
"""

ISORT_MAX = 32


def sort(a, less):
    _sort(a, 0, len(a), len(a), less)
    return a


def _sort(a, first, last, ideal, less):
    while True:
        if last - first <= ISORT_MAX:
            _insertion(a, first, last, less)
            return
        if ideal <= 0:
            _make_heap(a, first, last, less)
            _sort_heap(a, first, last, less)
            return
        mfirst, mlast = _partition(a, first, last, less)
        ideal = (ideal >> 1) + (ideal >> 2)
        if mfirst - first < last - mlast:
            _sort(a, first, mfirst, ideal, less)
            first = mlast
        else:
            _sort(a, mlast, last, ideal, less)
            last = mfirst


def _insertion(a, first, last, less):
    if first == last:
        return
    for nxt in range(first + 1, last):
        val = a[nxt]
        if less(val, a[first]):
            a[first + 1:nxt + 1] = a[first:nxt]
            a[first] = val
        else:
            hole = nxt
            while less(val, a[hole - 1]):
                a[hole] = a[hole - 1]
                hole -= 1
            a[hole] = val


def _med3(a, f, m, l, less):
    if less(a[m], a[f]):
        a[m], a[f] = a[f], a[m]
    if less(a[l], a[m]):
        a[l], a[m] = a[m], a[l]
        if less(a[m], a[f]):
            a[m], a[f] = a[f], a[m]


def _guess_median(a, f, m, l, less):
    count = l - f
    if count > 40:
        step = (count + 1) >> 3
        two = step << 1
        _med3(a, f, f + step, f + two, less)
        _med3(a, m - step, m, m + step, less)
        _med3(a, l - two, l - step, l, less)
        _med3(a, f + step, m, l - step, less)
    else:
        _med3(a, f, m, l, less)


def _partition(a, first, last, less):
    mid = first + ((last - first) >> 1)
    _guess_median(a, first, mid, last - 1, less)
    pfirst = mid
    plast = pfirst + 1
    while first < pfirst and not less(a[pfirst - 1], a[pfirst]) and not less(a[pfirst], a[pfirst - 1]):
        pfirst -= 1
    while plast < last and not less(a[plast], a[pfirst]) and not less(a[pfirst], a[plast]):
        plast += 1
    gfirst = plast
    glast = pfirst
    while True:
        while gfirst < last:
            if less(a[pfirst], a[gfirst]):
                pass
            elif less(a[gfirst], a[pfirst]):
                break
            elif plast != gfirst:
                a[plast], a[gfirst] = a[gfirst], a[plast]
                plast += 1
            else:
                plast += 1
            gfirst += 1
        while first < glast:
            if less(a[glast - 1], a[pfirst]):
                pass
            elif less(a[pfirst], a[glast - 1]):
                break
            else:
                pfirst -= 1
                if pfirst != glast - 1:
                    a[pfirst], a[glast - 1] = a[glast - 1], a[pfirst]
            glast -= 1
        if glast == first and gfirst == last:
            return pfirst, plast
        if glast == first:
            if plast != gfirst:
                a[pfirst], a[plast] = a[plast], a[pfirst]
            plast += 1
            a[pfirst], a[gfirst] = a[gfirst], a[pfirst]
            pfirst += 1
            gfirst += 1
        elif gfirst == last:
            glast -= 1
            pfirst -= 1
            if glast != pfirst:
                a[glast], a[pfirst] = a[pfirst], a[glast]
            plast -= 1
            a[pfirst], a[plast] = a[plast], a[pfirst]
        else:
            glast -= 1
            a[gfirst], a[glast] = a[glast], a[gfirst]
            gfirst += 1


def _push_heap_by_index(a, first, hole, top, val, less):
    idx = (hole - 1) >> 1
    while top < hole and less(a[first + idx], val):
        a[first + hole] = a[first + idx]
        hole = idx
        idx = (hole - 1) >> 1
    a[first + hole] = val


def _pop_heap_hole_by_index(a, first, hole, bottom, val, less):
    top = hole
    idx = hole
    max_seq_non_leaf = (bottom - 1) >> 1
    while idx < max_seq_non_leaf:
        idx = 2 * idx + 2
        if less(a[first + idx], a[first + idx - 1]):
            idx -= 1
        a[first + hole] = a[first + idx]
        hole = idx
    if idx == max_seq_non_leaf and bottom % 2 == 0:
        a[first + hole] = a[first + bottom - 1]
        hole = bottom - 1
    _push_heap_by_index(a, first, hole, top, val, less)


def _make_heap(a, first, last, less):
    bottom = last - first
    hole = bottom >> 1
    while hole > 0:
        hole -= 1
        val = a[first + hole]
        _pop_heap_hole_by_index(a, first, hole, bottom, val, less)


def _sort_heap(a, first, last, less):
    while last - first >= 2:
        last -= 1
        val = a[last]
        a[last] = a[first]
        _pop_heap_hole_by_index(a, first, 0, last - first, val, less)


if __name__ == '__main__':
    import random
    for n in [0, 1, 5, 33, 41, 100, 1000]:
        xs = [random.randrange(20) for _ in range(n)]
        ys = sort(list(xs), lambda p, q: p < q)
        assert ys == sorted(xs), n
    print('ok')
