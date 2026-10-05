import pickle,sys,math,itertools,numpy as np
from PIL import Image
f32=np.float32
W,H,types=pickle.load(open('research/trees/vanilla.pkl','rb'))
tif=np.array(Image.open('Vanilla/3k_dlc07_main_map/3k_dlc07_main_map.height.191fd803c1a801d.tif')).astype(np.uint16)
print(tif.shape, tif.dtype)
pts=[(x,y,z) for n,i in types for (x,y,z,*_) in i[::401]]
ts=f32(f32(595.1)/f32(1784)); fp=f32(ts/f32(128))
Hh,Ww=tif.shape
vals=(tif.astype(np.float32)*f32(1/65535)).astype(np.float32)
def samp(px,py,flip):
    ix=math.floor(px); iy=math.floor(py); tx=f32(px-f32(ix)); ty=f32(py-f32(iy))
    g=lambda c,r: vals[min(max((Hh-1-r) if flip else r,0),Hh-1), min(max(c,0),Ww-1)]
    a=g(ix,iy); b=g(ix+1,iy); c=g(ix,iy+1); d=g(ix+1,iy+1)
    top=f32(f32(f32(b-a)*tx)+a); bot=f32(f32(f32(d-c)*tx)+c); return f32(f32(f32(bot-top)*ty)+top)
def yv(l): return f32(fp*f32(f32(l*f32(5500))-f32(1200)))
def yv2(l): return f32(f32(f32(l*f32(5500))*fp)-f32(fp*f32(1200)))
for nm,(sx,sz) in {'W/Ww':(f32(f32(W)/f32(Ww)),f32(f32(H)/f32(Hh))),'W/(Ww-1)':(f32(f32(W)/f32(Ww-1)),f32(f32(H)/f32(Hh-1)))}.items():
  for flip in (0,1):
    for half in (0,0.5):
      res=[0,0]
      for x,y,z in pts:
        px=f32(f32(x)/sx)-f32(half); pz=f32(f32(z)/sz)-f32(half)
        l=samp(px,pz,flip)
        res[0]+=yv(l)==f32(y); res[1]+=yv2(l)==f32(y)
      d=np.median([abs(float(yv(samp(f32(f32(x)/sx)-f32(half),f32(f32(z)/sz)-f32(half),flip)))-y) for x,y,z in pts[:300]])
      print(nm,flip,half,res[0]/len(pts),res[1]/len(pts),'med',d)
