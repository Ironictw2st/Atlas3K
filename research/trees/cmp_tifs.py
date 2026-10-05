import numpy as np, os, glob
from PIL import Image
hexpng=np.array(Image.open('research/trees/vanilla_trees_hex.png'))[::-1]
hexc=(hexpng[...,0].astype(np.uint32)<<16)|(hexpng[...,1].astype(np.uint32)<<8)|hexpng[...,2]
AK='C:/Program Files (x86)/Steam/steamapps/common/Total War THREE KINGDOMS/assembly_kit/raw_data/terrain/campaigns/3k_dlc07_main_map'
for p in glob.glob(AK+'/*tree*.tif')+['Vanilla/3k_dlc07_main_map/3k_dlc07_main_map.tree.191fd7dc12fe7e4.tif']:
    im=Image.open(p); a=np.array(im); pal=np.array(im.getpalette()).reshape(-1,3); H=a.shape[0]
    match=tot=0; ex=0
    for r in range(702):
        for c in range(hexc.shape[1]):
            y=H-2*r-1-(c&1); idx=a[y,2*c]
            col=0 if idx==19 else int(pal[idx][0])<<16|int(pal[idx][1])<<8|int(pal[idx][2])
            match+= col==hexc[r,c]; tot+=1; ex+= hexc[r,c]!=0
    print(os.path.basename(p), a.shape, 'agree', round(match/tot,5), 'mismatch', tot-match)
