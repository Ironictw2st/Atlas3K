import struct, numpy as np, tifffile, collections
p='Vanilla/Map/campaign_maps/3k_dlc07_main_map/display/trees/trees.campaign_tree_list'
d=open(p,'rb').read()
ver,a,b,W,H,n=struct.unpack_from('<IIIffI',d,0); o=24
print(ver,a,b,W,H,n)
types=[]
for t in range(n):
    L,=struct.unpack_from('<H',d,o);o+=2; name=d[o:o+L].decode();o+=L
    c,=struct.unpack_from('<I',d,o);o+=4
    inst=[]
    for i in range(c):
        x,y,z,f,v,sc=struct.unpack_from('<fffBBI',d,o);o+=18
        s=struct.unpack_from('<%dI'%sc,d,o);o+=4*sc
        inst.append((x,y,z,f,v,s))
    types.append((name,inst))
import pickle; pickle.dump((W,H,types),open('research/trees/vanilla.pkl','wb'))
for name,inst in types:
    xs=np.array([i[0] for i in inst]);zs=np.array([i[2] for i in inst])
    print(name,len(inst),collections.Counter(i[5] for i in inst).most_common(3),collections.Counter(i[4] for i in inst).most_common(6), inst[0][:3])
t=tifffile.TiffFile('Vanilla/3k_dlc07_main_map/3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif')
pg=t.pages[0]; img=pg.asarray(); print(img.shape,img.dtype, pg.photometric, np.unique(img,return_counts=True))
cm=pg.colormap
if cm is not None:
    for i in np.unique(img): print(i, cm[:,i]>>8)
