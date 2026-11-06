import json,numpy as np,cv2
L='/Users/jacobhalloran/Claude Cowork/RBC HubHacks/clipsift/labels/verified/T1-STAT2_411_t1320.303'
P=np.array([(p['x'],p['y']) for p in json.load(open(L+'.json'))['points']]); YMAX=P[:,1].max()+80; W,H=3840,2160
def score(B,rad=60,pad=20):
    used=set();tp=0;C=np.c_[(B[:,0]+B[:,2])/2,(B[:,1]+B[:,3])/2]
    for p in P:
        best=None;bd=1e9
        for j,(b,c) in enumerate(zip(B,C)):
            if j in used: continue
            ins=b[0]-pad<=p[0]<=b[2]+pad and b[1]-pad<=p[1]<=b[3]+pad; d=np.hypot(*(c-p))
            if (ins or d<rad) and d<bd: best=j;bd=d
        if best is not None: used.add(best);tp+=1
    return tp
rng=np.random.default_rng(1)
print('config thr n boxH boxW | real R P | strict(25px,pad0) R P | chance R P (30 random placements in same area)')
for f,thr in (('nano_raw_512',.03),('nano_raw_512',.05),('medium_clahe_512',.03),('medium_clahe_512',.05),('medium_clahe_512',.1),('medium_raw_768',.05),('nano_raw_768',.1)):
    d=json.load(open(f'run/p_{f}.json'));B=np.array(d['B']);S=np.array(d['S']);B=B[S>=thr];B=B[(B[:,1]+B[:,3])/2<YMAX]
    w=B[:,2]-B[:,0];h=B[:,3]-B[:,1];n=len(B);t=score(B);ts=score(B,25,0)
    y0=max(0,P[:,1].min()-80);rs=[]
    for _ in range(30):
        cx=rng.uniform(0,W,n);cy=rng.uniform(y0,YMAX,n);R=np.c_[cx-w/2,cy-h/2,cx+w/2,cy+h/2];rs.append(score(R))
    c=np.mean(rs)
    print(f'{f} {thr} n={n} h~{np.median(h):.0f} w~{np.median(w):.0f} | R{t/103:.2f} P{t/n:.2f} | R{ts/103:.2f} P{ts/n:.2f} | R{c/103:.2f} P{c/n:.2f}')
im=cv2.imread(L+'.png')
d=json.load(open('run/p_medium_clahe_512.json'));B=np.array(d['B']);S=np.array(d['S']);B=B[S>=.05]
for b in B: cv2.rectangle(im,(int(b[0]),int(b[1])),(int(b[2]),int(b[3])),(0,0,255),3)
for x,y in P: cv2.drawMarker(im,(int(x),int(y)),(0,255,255),cv2.MARKER_CROSS,30,3)
cv2.imwrite('run/ov.jpg',cv2.resize(im[300:1450,:2000],(1300,748)),[cv2.IMWRITE_JPEG_QUALITY,84])
