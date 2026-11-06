import json,glob,time,sys,numpy as np,cv2
from PIL import Image
from rfdetr import from_checkpoint
L='/Users/jacobhalloran/Claude Cowork/RBC HubHacks/clipsift/labels/verified/T1-STAT2_411_t1320.303'
base=cv2.imread(L+'.png'); H,W=base.shape[:2]
P=np.array([(p['x'],p['y']) for p in json.load(open(L+'.json'))['points']]); YMAX=P[:,1].max()+80
src=open('run/evalcfd.py').read(); s=src.index('def run('); e=src.index('out={}'); exec(src[s:e])
def enh(kind):
    b=base.copy()
    if kind=='clahe':
        l=cv2.cvtColor(b,cv2.COLOR_BGR2LAB); l[:,:,0]=cv2.createCLAHE(3.0,(8,8)).apply(l[:,:,0]); b=cv2.cvtColor(l,cv2.COLOR_LAB2BGR)
    if kind=='flat':  # divide out slow background, then stretch
        f=b.astype(np.float32); bg=cv2.GaussianBlur(f,(0,0),80); d=f/(bg+1); d=(d-0.82)/(1.18-0.82); b=np.clip(d*255,0,255).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(b,cv2.COLOR_BGR2RGB))
for name,f in (('nano','weights/cfd-rf-detr-nano*'),('small','weights/cfd-rf-detr-small*'),('medium','weights/cfd-rf-detr-medium*')):
    m=from_checkpoint(glob.glob(f)[0])
    if name=='small':
        for t in glob.glob('testimgs/*'):
            d=m.predict(Image.open(t).convert('RGB'),threshold=0.3); print('SANITY',t[9:34],len(d.xyxy),[round(float(c),2) for c in d.confidence][:6],flush=True)
    for kind in ('raw','clahe','flat'):
        img=enh(kind)
        for tile in (768,512):
            B,S,t,n=run(m,tile,0.02)
            r=[]
            for thr in (0.03,0.05,0.1,0.2):
                k,tp,rc,pr=score(B,S,thr); r.append(f'{thr}: {k}/{tp} R{rc:.2f} P{pr:.2f}')
            print(name,kind,tile,f'{t:.0f}s',' | '.join(r),flush=True)
            json.dump(dict(B=B.tolist(),S=S.tolist()),open(f'run/p_{name}_{kind}_{tile}.json','w'))
