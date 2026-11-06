import json,glob,sys,numpy as np,cv2,re
from PIL import Image
sys.path.insert(0,'.')
from rfdetr import from_checkpoint
sp=sys.argv[1]
L='labels/verified/T1-STAT2_411_t1320.303'
P=np.array([(p['x'],p['y']) for p in json.load(open(L+'.json'))['points']]); YMAX=P[:,1].max()+80
m=from_checkpoint(glob.glob('models/cfd-rf-detr-nano*')[0])
def det(path,thr=.05,tile=512):
    img=Image.open(path).convert('RGB');W,H=img.size;st=int(tile*.75);B=[];S=[]
    xs=sorted(set(list(range(0,W-tile,st))+[W-tile]));ys=sorted(set(list(range(0,H-tile,st))+[H-tile]))
    for y in ys:
        for x in xs:
            d=m.predict(img.crop((x,y,x+tile,y+tile)),threshold=thr)
            if len(d.xyxy):
                b=np.array(d.xyxy,float);b[:,[0,2]]+=x;b[:,[1,3]]+=y;B.append(b);S.append(np.array(d.confidence))
    B=np.vstack(B);S=np.hstack(S);o=S.argsort()[::-1];k=[]
    while len(o):
        i=o[0];k.append(i);r=o[1:];w=np.clip(np.minimum(B[i,2],B[r,2])-np.maximum(B[i,0],B[r,0]),0,None);h=np.clip(np.minimum(B[i,3],B[r,3])-np.maximum(B[i,1],B[r,1]),0,None);a=(B[i,2]-B[i,0])*(B[i,3]-B[i,1]);ar=(B[r,2]-B[r,0])*(B[r,3]-B[r,1]);o=r[w*h/np.minimum(a,ar)<.5]
    return B[k],S[k]
def score(B):
    B=B[(B[:,1]+B[:,3])/2<YMAX]
    if not len(B): return 0,0
    used=set();tp=0;C=np.c_[(B[:,0]+B[:,2])/2,(B[:,1]+B[:,3])/2]
    for p in P:
        best=None;bd=1e9
        for j,(b,c) in enumerate(zip(B,C)):
            if j in used: continue
            ins=b[0]<=p[0]<=b[2] and b[1]<=p[1]<=b[3];dd=np.hypot(*(c-p))
            if (ins or dd<25) and dd<bd: best=j;bd=dd
        if best is not None: used.add(best);tp+=1
    return tp,len(B)
print('STRICT match; dots from 1320.303')
for f in sorted(glob.glob(sp+'/ctrl/f*.jpg'),key=lambda s:float(re.search(r'f([\d.]+)\.jpg',s).group(1))):
    t=float(re.search(r'f([\d.]+)\.jpg',f).group(1));B,S=det(f)
    for thr in (.05,.1):
        Bb=B[S>=thr];tp,n=score(Bb);print(f'dt={t-1320.303:+6.1f}s thr {thr} boxes {n:3d} hits {tp:3d} R{tp/103:.2f} P{(tp/n if n else 0):.2f}',flush=True)
    if abs(t-1320.303)<.01: B0,S0=B,S
rng=np.random.default_rng(3)
for thr in (.05,.1):
    Bb=B0[S0>=thr];rs=[]
    for _ in range(40):
        a=rng.uniform(0,6.283);r=rng.uniform(150,400);dx,dy=r*np.cos(a),r*np.sin(a);rs.append(score(Bb+[dx,dy,dx,dy]))
    print(f'shifted same boxes thr {thr}: hits mean {np.mean([x[0] for x in rs]):.1f} range {min(x[0] for x in rs)}-{max(x[0] for x in rs)} boxes {np.mean([x[1] for x in rs]):.0f} real hits {score(Bb)[0]}')
