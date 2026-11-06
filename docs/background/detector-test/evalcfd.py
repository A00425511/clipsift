import json,glob,time,sys,numpy as np
from PIL import Image
import torch
from rfdetr import from_checkpoint
L='/Users/jacobhalloran/Claude Cowork/RBC HubHacks/clipsift/labels/verified/T1-STAT2_411_t1320.303'
img=Image.open(L+'.png').convert('RGB'); W,H=img.size
P=np.array([(p['x'],p['y']) for p in json.load(open(L+'.json'))['points']]); print('dots',len(P),'y range',P[:,1].min(),P[:,1].max(),W,H)
YMAX=P[:,1].max()+80
def run(model,tile,thr=0.05):
    B=[];S=[]; t=time.time()
    if tile is None: crops=[(0,0,W,H)]
    else:
        st=int(tile*0.75); xs=sorted(set(list(range(0,W-tile,st))+[W-tile])); ys=sorted(set(list(range(0,H-tile,st))+[H-tile])); crops=[(x,y,x+tile,y+tile) for y in ys for x in xs]
    for c in crops:
        d=model.predict(img.crop(c),threshold=thr)
        if len(d.xyxy):
            b=np.array(d.xyxy,dtype=float); b[:,[0,2]]+=c[0]; b[:,[1,3]]+=c[1]; B.append(b); S.append(np.array(d.confidence))
    if not B: return np.zeros((0,4)),np.zeros(0),time.time()-t,len(crops)
    B=np.vstack(B);S=np.hstack(S)
    o=S.argsort()[::-1];keep=[]
    while len(o):
        i=o[0];keep.append(i);r=o[1:]
        xx1=np.maximum(B[i,0],B[r,0]);yy1=np.maximum(B[i,1],B[r,1]);xx2=np.minimum(B[i,2],B[r,2]);yy2=np.minimum(B[i,3],B[r,3])
        inter=np.clip(xx2-xx1,0,None)*np.clip(yy2-yy1,0,None);a=(B[i,2]-B[i,0])*(B[i,3]-B[i,1]);ar=(B[r,2]-B[r,0])*(B[r,3]-B[r,1])
        o=r[inter/np.minimum(a,ar)<0.5]
    return B[keep],S[keep],time.time()-t,len(crops)
def score(B,S,thr):
    m=S>=thr;B=B[m];B=B[(B[:,1]+B[:,3])/2<YMAX]
    if len(B)==0: return 0,0,0,0
    used=set();tp=0
    C=np.c_[(B[:,0]+B[:,2])/2,(B[:,1]+B[:,3])/2]
    for p in P:
        best=None;bd=1e9
        for j,(b,c) in enumerate(zip(B,C)):
            if j in used: continue
            inside=b[0]-20<=p[0]<=b[2]+20 and b[1]-20<=p[1]<=b[3]+20
            d=np.hypot(*(c-p))
            if (inside or d<60) and d<bd: best=j;bd=d
        if best is not None: used.add(best);tp+=1
    return len(B),tp,tp/len(P),tp/len(B)
out={}
for name,f in (('small','weights/cfd-rf-detr-small*'),('nano','weights/cfd-rf-detr-nano*'),('medium','weights/cfd-rf-detr-medium*')):
    m=from_checkpoint(glob.glob(f)[0])
    for tile in (None,1536,1024,768):
        if name=='nano' and tile==768: pass
        B,S,t,n=run(m,tile)
        print(f'{name} tile={tile} crops={n} time={t:.1f}s raw={len(B)}',flush=True)
        for thr in (0.1,0.2,0.3,0.4,0.5):
            k,tp,r,p=score(B,S,thr); print(f'  thr {thr}: det {k} hit {tp} recall {r:.2f} precision {p:.2f}',flush=True)
        out[f'{name}_{tile}']=dict(B=B.tolist(),S=S.tolist())
json.dump(out,open('run/preds.json','w'))
