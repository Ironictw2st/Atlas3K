from cahash import cah
def ca_map_order(insert_seq):
    """Simulate CA_STD hash map (bucket-ordered list) insertion; returns final list order."""
    entries=2; buckets=[[]]  # entries-1 buckets
    count=0
    seen=set()
    for name in insert_seq:
        if name in seen: continue
        if (count+1)/(entries-1) > 1.0:
            old=[n for b in buckets for n in b]
            entries=entries*2  # param_2 = 2*entries-1, +1
            buckets=[[] for _ in range(entries-1)]
            for n in old: buckets[cah(n)%(entries-1)].append(n)
        buckets[cah(name)%(entries-1)].append(name); seen.add(name); count+=1
    return [n for b in buckets for n in b]
