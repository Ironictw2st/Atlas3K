import re, sys, collections
c=collections.Counter()
for l in open(sys.argv[1],encoding='utf-8',errors='replace'):
    m=re.match(r'(Error|Warning|Info): (\w[\w ]*?) validation: (.*)',l)
    if m and not (m.group(2)=='Regions' and 'does not have any hexes' in l):
        c[(m.group(1),m.group(2),re.sub(r'\d+','#',re.sub(r'Hex\(\d+, \d+\)','Hex',re.sub(r"3k_\w+","REG",m.group(3))))[:95])]+=1
for k,n in sorted(c.items(), key=lambda x:(x[0][0]!='Error', x[0][0]!='Warning', x[0][1])):
    if k[0]!='Info' or 'three-way' not in k[2]: print(f"{k[0]:7s} {k[1]:12s} {n:6d} {k[2]}")
