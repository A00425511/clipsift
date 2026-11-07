#!/usr/bin/env python3
"""Create a local, browser-based fish-box validation set from ClipSift V6 runs.

No detector calls, no dependency beyond cv2 (already in ClipSift env).
"""
import argparse
import json
import hashlib
from pathlib import Path
import cv2

HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ClipSift | Fish-box validation</title><style>
:root{font-family:system-ui,Segoe UI,Arial,sans-serif;color:#eaf0fa;background:#101824}body{margin:0 auto;padding:22px;max-width:1300px}h1{margin:0 0 6px}p{color:#aabbd0;line-height:1.5}.toolbar{display:flex;flex-wrap:wrap;gap:9px;margin:14px 0}button,select{font:inherit;border:1px solid #51627e;color:#f0f6ff;background:#25344c;padding:10px 13px;border-radius:8px;cursor:pointer}button:hover{background:#355071}button:disabled{opacity:.4}.active{background:#0b715c;border-color:#27b99b}.layout{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:15px}.imagebox{background:#03080d;border:1px solid #384b64;border-radius:10px;padding:6px}canvas{display:block;max-width:100%;height:auto;cursor:crosshair;touch-action:none}.side{padding:14px;background:#1b2839;border-radius:10px}.hint{font-size:13px;color:#bfcfe0}.stat{background:#1c2c41;padding:12px;border-radius:8px;margin:9px 0}code{font-size:12px}a{color:#74bbff}#frameList button{font-size:12px;padding:8px;margin:3px}#results{white-space:pre-wrap;font:13px/1.65 ui-monospace,Consolas,monospace;color:#dce9fc}#status{color:#9cdecf}.key{display:inline-block;width:12px;height:12px;margin-right:5px} @media(max-width:850px){.layout{grid-template-columns:1fr}}
</style></head><body>
<h1>ClipSift — Manual Fish Annotation</h1>
<p>Draw <strong>one rectangle around each clearly visible fish</strong>. Orange boxes are ClipSift's tracked candidate proposals; green boxes are your independent fish annotations. Annotate every visible fish, including fish the model missed. Do not label equipment as fish. Mark a frame unusable if the image cannot be judged reliably.</p>
<div class="toolbar"><button id="prev">← Previous frame</button><select id="frameSelect"></select><button id="next">Next frame →</button><button id="showPred" class="active">Show model boxes</button><button id="undo">Undo fish box</button><button id="clear">Clear fish boxes</button><button id="toggleSkip">Mark frame unusable</button><button id="done">Confirm frame annotation complete</button></div>
<div class="layout"><div><div class="imagebox"><canvas id="canvas"></canvas></div><div class="toolbar"><button id="export">Export annotations JSON</button><button id="importBtn">Import saved JSON</button><input id="importFile" type="file" accept="application/json" hidden></div><p id="status">Ready. Draw fish rectangles with your mouse.</p><div id="frameList"></div></div><div class="side"><div class="stat" id="info"></div><div class="stat"><span class="key" style="background:#f8a537"></span> Model candidates<br><span class="key" style="background:#52e7a0"></span> Human fish boxes</div><p class="hint">Boxes represent tracked candidates from the V6 JSON, not all raw RF-DETR detections. This evaluates candidate localization on these sampled frames, not whole-video fish counts.</p><div class="stat" id="progress"></div><div class="stat" id="results"></div><p class="hint">IoU ≥ 0.30 used for a provisional match; each prediction and annotation can match only once. Final metrics are valid only after every usable frame is fully annotated. This is a development sample, not a blind benchmark. Confirm each frame with the button after drawing all fish (including zero-fish frames).</p></div></div>
<script id="manifest" type="application/json">__MANIFEST__</script>
<script>
const D=JSON.parse(document.getElementById('manifest').textContent), C=document.getElementById('canvas'), X=C.getContext('2d');
const KEY='clipsift_fish_validation_'+D.id;let labels={};try{labels=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){};let ix=0,img=new Image(),showPred=true,drag=null;
const $=id=>document.getElementById(id);const entry=()=>D.frames[ix], mark=()=>labels[entry().key]||(labels[entry().key]={boxes:[],skip:false,done:false});
function save(){try{localStorage.setItem(KEY,JSON.stringify(labels))}catch(e){$('status').textContent='Browser storage unavailable: use Export annotations JSON often.'}}
function ioU(a,b){const x=Math.max(0,Math.min(a[2],b[2])-Math.max(a[0],b[0])),y=Math.max(0,Math.min(a[3],b[3])-Math.max(a[1],b[1]));const inter=x*y,aa=(a[2]-a[0])*(a[3]-a[1]),bb=(b[2]-b[0])*(b[3]-b[1]);return inter/(aa+bb-inter||1)}
function score(f,m){const available=[];for(const p of f.predictions)for(const g of m.boxes)if(ioU(p.bbox,g)>=.3)available.push({p:p.id,g:JSON.stringify(g),iou:ioU(p.bbox,g)});available.sort((a,b)=>b.iou-a.iou);let matched=0,ps=new Set(),gs=new Set();for(const a of available){if(!ps.has(a.p)&&!gs.has(a.g)){ps.add(a.p);gs.add(a.g);matched++}}return {tp:matched,fp:f.predictions.length-matched,fn:m.boxes.length-matched}}
function renderStats(){let done=0,usable=0,total={tp:0,fp:0,fn:0},group={};for(const f of D.frames){const m=labels[f.key];if(!m||!m.done)continue;done++;if(m.skip)continue;usable++;const s=score(f,m);for(const k of Object.keys(s))total[k]+=s[k];const t=group[f.scene]||(group[f.scene]={tp:0,fp:0,fn:0,frames:0});t.frames++;for(const k of Object.keys(s))t[k]+=s[k]}
const precision=total.tp+total.fp?total.tp/(total.tp+total.fp):null,recall=total.tp+total.fn?total.tp/(total.tp+total.fn):null;
const fmt=x=>x===null?'N/A':(x*100).toFixed(1)+'%';$('progress').innerHTML=`Annotated: <b>${done}/${D.frames.length}</b><br>Usable: ${usable}<br>Excluded: ${done-usable}`;
$('results').textContent=`Provisional candidate-box metrics\nTP: ${total.tp}  FP: ${total.fp}  FN: ${total.fn}\nPrecision: ${fmt(precision)}\nRecall: ${fmt(recall)}\n`+Object.entries(group).map(([n,s])=>`\n${n}: ${s.frames} frames\nTP ${s.tp} / FP ${s.fp} / FN ${s.fn}`).join('')+(done===D.frames.length?'\n\nAll frames visited. Check annotations carefully.':'\n\nINCOMPLETE — annotate all frames first.');
$('toggleSkip').textContent=mark().skip?'Restore usable frame':'Mark frame unusable';$('done').textContent=mark().done?'✓ Annotation confirmed (click to reopen)':'Confirm frame annotation complete';$('frameList').innerHTML='';D.frames.forEach((f,i)=>{const b=document.createElement('button');b.textContent=(labels[f.key]?.done?'✓ ':'')+(labels[f.key]?.skip?'× ':'')+(i+1);if(i===ix)b.className='active';b.onclick=()=>load(i);$('frameList').appendChild(b)})}
function rect(b,col){X.strokeStyle=col;X.lineWidth=Math.max(2,C.width/520);X.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1])}
function paint(){if(!img.complete||!img.naturalWidth)return;X.clearRect(0,0,C.width,C.height);X.drawImage(img,0,0,C.width,C.height);const f=entry();if(showPred)f.predictions.forEach(p=>{rect(p.bbox,'#f8a537');X.fillStyle='#f8a537';X.font=`bold ${Math.max(14,C.width/72)}px sans-serif`;X.fillText('P'+p.id,p.bbox[0]+3,Math.max(18,p.bbox[1]-5))});mark().boxes.forEach((b,i)=>{rect(b,'#52e7a0');X.fillStyle='#52e7a0';X.font=`bold ${Math.max(14,C.width/72)}px sans-serif`;X.fillText('F'+(i+1),b[0]+3,Math.max(18,b[1]-5))});if(drag)rect([Math.min(drag.x,drag.x2),Math.min(drag.y,drag.y2),Math.max(drag.x,drag.x2),Math.max(drag.y,drag.y2)],'#52e7a0');if(mark().skip){X.fillStyle='#ffcccc';X.font='bold 28px sans-serif';X.fillText('EXCLUDED',20,40)}}
function load(i){ix=Math.max(0,Math.min(D.frames.length-1,i));const f=entry();$('frameSelect').value=String(ix);img=new Image();img.onload=()=>{C.width=f.width;C.height=f.height;paint()};img.onerror=()=>{$('status').textContent='Cannot load '+f.image+'. Open validation.html inside its original folder.'};img.src=f.image;$('info').innerHTML=`<strong>${f.scene}</strong><br>Video time: ${f.timestamp.toFixed(2)} s<br>Frame #${f.frame_index}<br>Model boxes: ${f.predictions.length}<br>Human fish boxes: ${mark().boxes.length}`;renderStats()}
function pos(e){const r=C.getBoundingClientRect();return {x:Math.max(0,Math.min(C.width,(e.clientX-r.left)*C.width/r.width)),y:Math.max(0,Math.min(C.height,(e.clientY-r.top)*C.height/r.height))}}
C.addEventListener('pointerdown',e=>{if(mark().skip)return;C.setPointerCapture(e.pointerId);const p=pos(e);drag={x:p.x,y:p.y,x2:p.x,y2:p.y}});C.addEventListener('pointermove',e=>{if(!drag)return;const p=pos(e);drag.x2=p.x;drag.y2=p.y;paint()});C.addEventListener('pointerup',e=>{if(!drag)return;const p=pos(e),a=[Math.min(drag.x,p.x),Math.min(drag.y,p.y),Math.max(drag.x,p.x),Math.max(drag.y,p.y)];drag=null;if(a[2]-a[0]>5&&a[3]-a[1]>5){mark().boxes.push(a.map(x=>Math.round(x)));mark().done=false;save()}paint();loadMeta()});
function loadMeta(){$('info').innerHTML=`<strong>${entry().scene}</strong><br>Video time: ${entry().timestamp.toFixed(2)} s<br>Frame #${entry().frame_index}<br>Model boxes: ${entry().predictions.length}<br>Human fish boxes: ${mark().boxes.length}`;renderStats()}
$('prev').onclick=()=>load(ix-1);$('next').onclick=()=>load(ix+1);$('showPred').onclick=()=>{showPred=!showPred;$('showPred').classList.toggle('active',showPred);paint()};$('undo').onclick=()=>{mark().boxes.pop();mark().done=false;save();paint();loadMeta()};$('clear').onclick=()=>{if(confirm('Remove all fish boxes from this frame?')){mark().boxes=[];mark().done=false;save();paint();loadMeta()}};$('toggleSkip').onclick=()=>{mark().skip=!mark().skip;mark().done=false;save();paint();loadMeta()};$('done').onclick=()=>{mark().done=!mark().done;save();loadMeta();$('status').textContent=mark().done?'Frame annotation confirmed. Continue to the next frame.':'Frame reopened for annotation.'};
$('export').onclick=()=>{const data={format:'clipsift_validation_v1',dataset_id:D.id,frames:D.frames.map(f=>({key:f.key,scene:f.scene,frame_index:f.frame_index,timestamp:f.timestamp,predictions:f.predictions,annotation:labels[f.key]||{boxes:[],skip:false,done:false}}))};const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='clipsift_validation_annotations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);$('status').textContent='Annotations exported. Save this file for reproducibility.'};
$('importBtn').onclick=()=>$('importFile').click();$('importFile').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{const data=JSON.parse(await file.text());if(data.dataset_id!==D.id)throw new Error('This annotation file belongs to another dataset.');for(const f of data.frames||[])if(f.annotation)labels[f.key]=f.annotation;save();load(ix);$('status').textContent='Annotations imported.'}catch(err){alert(err.message)}};
D.frames.forEach((f,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i+1}. ${f.scene} @ ${f.timestamp.toFixed(2)}s`;$('frameSelect').appendChild(o)});$('frameSelect').onchange=e=>load(Number(e.target.value));load(0);
</script></body></html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--equipment-json', required=True)
    ap.add_argument('--fish-json', required=True)
    ap.add_argument('--output-dir', default='outputs/validation_set')
    args = ap.parse_args()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for scene, jp in [('Equipment 10:00', args.equipment_json), ('Fish school 00:16', args.fish_json)]:
        data = json.loads(Path(jp).read_text(encoding='utf-8'))
        video = Path(data['video'])
        if not video.exists():
            raise FileNotFoundError(f'Video not found: {video}')
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            raise RuntimeError(f'Unable to open video {video}')
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f'{scene}: {video}, {width}x{height}')
        for si, sub in enumerate(data['subsamples']):
            for cf in sub.get('count_window_frames', []):
                fid = int(cf['frame_index'])
                stamp = float(cf['timestamp'])
                cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
                ok, img = cap.read()
                if not ok:
                    print(f'WARNING: cannot read frame {fid} from {video}')
                    continue
                # Preserve original coordinates and aspect ratio with uniform scaling.
                scale = min(1., 1280. / img.shape[1])
                dw = round(img.shape[1]*scale)
                dh = round(img.shape[0]*scale)
                if scale < 1:
                    img = cv2.resize(img, (dw,dh), interpolation=cv2.INTER_AREA)
                key = f'{scene.replace(" ","_")}_s{si+1}_f{fid}'
                name = f'{key}.jpg'
                if not cv2.imwrite(str(out/name), img, [int(cv2.IMWRITE_JPEG_QUALITY), 86]):
                    raise RuntimeError(f'Cannot save {out/name}')
                preds = []
                for tr in sub.get('candidate_tracks', []):
                    if tr.get('status') not in ('high_priority_candidate','review_candidate'):
                        continue
                    obs = [o for o in tr.get('observations',[]) if int(o.get('frame_index',-1))==fid]
                    if not obs:
                        continue
                    o=max(obs, key=lambda x:x.get('confidence',0))
                    b=[round(float(v)*scale) for v in o['bbox']]
                    preds.append({'id':str(tr['track_id']),'bbox':b,'confidence':round(float(o['confidence']),4),'priority':tr['status']})
                frames.append({'key':key,'scene':scene,'frame_index':fid,'timestamp':stamp,'image':name,'width':dw,'height':dh,'predictions':preds})
        cap.release()
    if not frames:
        raise RuntimeError('No count-window frames extracted. Check the two V6 JSON inputs.')
    dataset_id=hashlib.sha256(json.dumps([(f['key'],f['predictions']) for f in frames],sort_keys=True).encode()).hexdigest()[:12]
    manifest={'id':dataset_id,'frames':frames,'note':'Provisional V6 tracked-candidate boxes; hand-drawn fish GT on count-window frames.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    html=HTML.replace('__MANIFEST__',json.dumps(manifest).replace('<','\\u003c'))
    (out/'validation.html').write_text(html,encoding='utf-8')
    print(f'Created {len(frames)} validation frames, dataset {dataset_id}.')
    print(f'Open in browser: {out / "validation.html"}')
    print('Label all actual fish with green boxes. Export annotations JSON when finished.')

if __name__=='__main__':
    main()
