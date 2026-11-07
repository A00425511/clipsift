/* ClipSift shared help v1 — standalone, no external dependencies. */
(() => {
'use strict';
const glossary = [
 ['Workflow', 'Start in Videos with an existing local video path and timestamp. Open Subsamples to inspect the center frame, protocol window and proposed tracks. Open Human Review to inspect evidence, verify the original footage, assign reviewer decisions and export the review CSV.'],
 ['Videos / local path', 'The current prototype reads a video already on the server computer. Typing a path does not upload a video from another computer.'],
 ['Subsample', 'A protocol-selected point in the original video. A sample has its own source timestamp and frames; it is not a single 10-second video frame.'],
 ['Source frame number', 'Position of the representative center frame in the ORIGINAL source video. Index is zero-based; displayed frame number is one-based.'],
 ['Center frame', 'Still image from the original video at the sample timestamp. Some detections occur on other frames within the surrounding context and will not appear here.'],
 ['Context window', 'Typically 5 seconds before and 5 seconds after the sample timestamp. Sampled frames from this region provide tracking and visual evidence.'],
 ['Count window', 'Provisional 1-second central interval (timestamp ±0.5 s). Only observations in this interval are relevant to the current candidate peak statistics. This is not a validated abundance protocol.'],
 ['Sampled context frames', 'Number of frames actually evaluated by the model in the context window (approximately 5 frames per second in the current pipeline).'],
 ['Detection event', 'A model-generated bounding box on one sampled frame, potentially including false positives and repeated observations of the same object.'],
 ['Raw tracks', 'Initial linked sequences from the tracker; some may be too short or weak to reach the review queue. Track IDs are not fish counts.'],
 ['Reviewable tracks', 'Candidate trajectories eligible for human inspection. These can include fish, background objects, equipment and duplicates.'],
 ['Confidence', 'A model score for a detection, not the probability that the object is definitively a fish. The gallery uses each track’s maximum observed confidence for ordering.'],
 ['Strong evidence', 'Review display tier: maximum track confidence at least 0.30. A strong candidate is NOT a confirmed fish.'],
 ['Additional evidence', 'Review display tier: maximum track confidence below 0.30. These candidates remain available to avoid prematurely excluding possible fish.'],
 ['HIGH / REVIEW', 'V6 trajectory priorities based on its observation rules; independent of Strong/Additional display tiers. HIGH does not mean confirmed fish.'],
 ['In count window', 'At least one observation of the track occurred in the provisional 1-second count window. Context-only tracks are useful evidence but are not count-window candidates.'],
 ['Peak HIGH', 'Largest number of simultaneous HIGH-priority candidates across sampled frames of the count window, after the current duplicate suppression. NOT confirmed fish abundance.'],
 ['Peak reviewable', 'Largest simultaneous number of reviewable candidates in the count window; not necessarily unique animals.'],
 ['Duplicate events removed', 'Potential duplicated observations suppressed by current heuristics. Other duplicates can remain and must be resolved by human review.'],
 ['Evidence crop / yellow box', 'A selected source-video frame with highlighted proposed bounding boxes. Other candidates may also be drawn. It is not an AI-confirmed fish image.'],
 ['Reviewer decisions', 'FISH, INVERTEBRATE, EQUIPMENT, BACKGROUND or UNCERTAIN. Check original video and adjacent frames; record rationale in notes. Do not use a decision alone as a unique animal count.'],
 ['Confirmed fish count', 'Pending until human verification and reconciliation of multiple tracks that may refer to the same fish. No automatic candidate-to-abundance conversion.'],
 ['Precision / Recall', 'Validation statistics comparing candidate boxes with manually annotated boxes under an explicit IoU criterion. Results on small development clips do not establish general performance.'],
 ['What to look for', 'Look for body shape and motion across adjacent frames; identify pipes, cables, shadows or fixed background; check overlapping tracks for one animal counted multiple times; confirm whether observations fall in the count window. Mark uncertain objects UNCERTAIN rather than guessing.']
];
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const css = `
#cs-help-open{margin-left:auto;cursor:pointer;border:1px solid #75b7c8;background:#163944;color:#e8fbff;padding:8px 12px;border-radius:7px;font:600 14px system-ui}
.help[role="button"],.help{cursor:pointer!important}
.help:focus-visible,#cs-help-open:focus-visible,.cs-help-close:focus-visible{outline:3px solid #ffc96b;outline-offset:2px}
#cs-help-dialog{border:1px solid #547d89;border-radius:13px;max-width:min(760px,calc(100vw - 30px));width:100%;max-height:85vh;overflow:auto;background:#172e38;color:#f1f9fa;padding:23px;font:14px/1.6 system-ui,Segoe UI,Arial,sans-serif;box-shadow:0 20px 80px #0009}
#cs-help-dialog::backdrop{background:rgba(0,0,0,.78)}
#cs-help-dialog h2{font-size:21px;margin:0 0 8px;color:#fff}#cs-help-dialog h3{margin:14px 0 5px;color:#9fe9f5}
#cs-help-dialog p{margin:6px 0 13px}#cs-help-dialog details{border-top:1px solid #3d5964;padding:9px 0}#cs-help-dialog summary{cursor:pointer;font-weight:700;color:#b9e9f7}
#cs-help-dialog .cs-help-head{display:flex;gap:15px;align-items:flex-start;justify-content:space-between}#cs-help-dialog .cs-help-close{border:1px solid #85a6b0;border-radius:7px;padding:6px 12px;background:#305666;color:white;cursor:pointer;font-size:15px}
#cs-help-dialog .cs-help-note{border-left:3px solid #f1bb66;background:#423728;padding:10px;margin:10px 0}
#cs-help-dialog .cs-help-steps{padding-left:22px}#cs-help-dialog .cs-help-steps li{margin:8px 0}
`;
function init(){
  if(document.querySelector('#cs-help-dialog'))return;
  const style=document.createElement('style');style.textContent=css;document.head.appendChild(style);
  const nav=document.querySelector('.csnav')||document.querySelector('nav');
  const open=document.createElement('button');open.type='button';open.id='cs-help-open';open.textContent='? User Guide';open.setAttribute('aria-label','Open ClipSift user guide');
  (nav||document.body).appendChild(open);
  const dialog=document.createElement('dialog');dialog.id='cs-help-dialog';dialog.setAttribute('aria-label','ClipSift help');
  document.body.appendChild(dialog);
  function show(title,body,full=false){
    dialog.innerHTML=`<div class="cs-help-head"><h2>${esc(title)}</h2><button class="cs-help-close" type="button">Close ×</button></div>${full?body:`<p>${esc(body)}</p><p class="cs-help-note">A candidate is not a confirmed fish. Check the source footage before deciding.</p>`}`;
    dialog.querySelector('.cs-help-close').onclick=()=>dialog.close();
    if(!dialog.open)dialog.showModal();
  }
  function allGuide(){
    const steps=`<h3>Quick start</h3><ol class="cs-help-steps"><li><strong>Videos:</strong> enter a video path accessible on this computer, a subsample timestamp (MM:SS), and a unique run name. Click Run local AI.</li><li><strong>Subsamples:</strong> inspect the REAL center frame and the time windows; candidate peaks are proposals, not fish counts.</li><li><strong>Gallery:</strong> filter In count window, Strong or Additional. Open a candidate to inspect evidence.</li><li><strong>Human Review:</strong> compare the proposed box with original footage and nearby frames. Record FISH, INVERTEBRATE, EQUIPMENT, BACKGROUND or UNCERTAIN and save notes.</li><li><strong>Export:</strong> export reviewer CSV for traceability. A final unique-fish count requires duplicate reconciliation.</li></ol><p class="cs-help-note"><strong>What to look for:</strong> Fish body and temporal motion, fixed pipes/cables, background patterns, multiple tracks on one object, and whether the candidate is inside the count window.</p>`;
    const items=glossary.map(([a,b])=>`<details><summary>${esc(a)}</summary><p>${esc(b)}</p></details>`).join('');
    show('ClipSift — User Guide',steps+'<h3>Glossary — click a term</h3>'+items,true);
  }
  open.addEventListener('click',allGuide);
  document.addEventListener('click',e=>{
    const tip=e.target.closest('.help');if(!tip)return;
    e.preventDefault();e.stopPropagation();
    const desc=tip.getAttribute('title')||tip.getAttribute('data-help')||'Review the candidate in the original footage.';
    const parent=tip.parentElement;let title='What does this mean?';
    if(parent){title=(parent.textContent||'').replace(/\?/g,'').trim().slice(0,110)||title;}
    show(title,desc);
  });
  document.addEventListener('keydown',e=>{
    const tip=e.target.closest&&e.target.closest('.help');if(tip&&(e.key==='Enter'||e.key===' ')){e.preventDefault();tip.click();}
  });
  // The original help marks are dynamically generated spans. Make them keyboard-accessible.
  const enhance=()=>{document.querySelectorAll('.help:not([role])').forEach(n=>{n.setAttribute('role','button');n.setAttribute('tabindex','0');n.setAttribute('aria-label','Explain: '+(n.getAttribute('title')||'this metric'));});};
  enhance();new MutationObserver(enhance).observe(document.body,{childList:true,subtree:true});
  dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
