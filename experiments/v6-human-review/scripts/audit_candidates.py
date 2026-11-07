"""ClipSift V6 candidate evidence audit (not a fish classifier).

Reads existing subsamples_v6.json; no model/video inference needed.
Outputs candidate_audit.csv and audit_summary.json for review triage.
All signals are descriptive; no automatic fish/exclusion decisions.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
from pathlib import Path

FIELDS = [
    'subsample_index', 'subsample_timestamp_seconds', 'track_id', 'model_priority',
    'observed_in_count_window', 'observations_in_count_window', 'frames_seen',
    'max_confidence', 'mean_confidence', 'center_span_pct_diagonal',
    'median_step_pct_diagonal', 'frame_boundary_contact_pct',
    'max_simultaneous_iou_with_other_tracks', 'overlapping_track_ids',
    'evidence_flags', 'review_action', 'reviewer_decision', 'reviewer_notes',
]

def iou(a,b):
    x0=max(a[0],b[0]); y0=max(a[1],b[1]); x1=min(a[2],b[2]); y1=min(a[3],b[3])
    inter=max(0,x1-x0)*max(0,y1-y0)
    aa=max(0,a[2]-a[0])*max(0,a[3]-a[1]); ab=max(0,b[2]-b[0])*max(0,b[3]-b[1])
    return inter/(aa+ab-inter) if aa+ab-inter>0 else 0.

def center(b): return ((b[0]+b[2])/2,(b[1]+b[3])/2)

def distance(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])

def inspect(sample, sample_index, width, height):
    diagonal=math.hypot(width,height)
    tracks=[t for t in sample.get('candidate_tracks',[]) if t.get('status') != 'low_priority_candidate']
    at_frame={}
    for t in tracks:
        for o in t.get('observations') or []:
            if o.get('bbox') and 'frame_index' in o:
                at_frame.setdefault(int(o['frame_index']),[]).append((int(t['track_id']),o['bbox']))
    pair_peak={}
    for boxes in at_frame.values():
        for i,(a,box_a) in enumerate(boxes):
            for b,box_b in boxes[i+1:]:
                key=tuple(sorted((a,b)))
                pair_peak[key]=max(pair_peak.get(key,0),iou(box_a,box_b))
    rows=[]
    for t in tracks:
        tid=int(t['track_id']); obs=[o for o in (t.get('observations') or []) if o.get('bbox')]
        c=[center(o['bbox']) for o in obs]
        # Position span describes image-space stability, not biological motion.
        span=max((distance(c[0],p) for p in c),default=0)/diagonal*100
        steps=[distance(a,b)/diagonal*100 for a,b in zip(c,c[1:])]
        median_step=statistics.median(steps) if steps else 0
        contacts=sum(1 for o in obs if (o['bbox'][0]<=0 or o['bbox'][1]<=0 or o['bbox'][2]>=width-2 or o['bbox'][3]>=height-2))
        boundary=100*contacts/len(obs) if obs else 0
        overlaps={b if a==tid else a: v for (a,b),v in pair_peak.items() if (a==tid or b==tid) and v>=0.35}
        max_overlap=max(overlaps.values(),default=0)
        in_count=sum(bool(o.get('in_count_window')) for o in obs)
        flags=[]
        if len(obs)>=10 and span<=2:
            flags.append('LOW_IMAGE_POSITION_VARIATION')
        if boundary>=70 and len(obs)>=3:
            flags.append('REPEATED_FRAME_BOUNDARY_CONTACT')
        if overlaps:
            flags.append('OVERLAPPING_TRACKS')
        if not obs:
            flags.append('MISSING_FRAME_OBSERVATIONS')
        if in_count==0:
            flags.append('OUTSIDE_COUNT_WINDOW')
        # These flags are not a biological classification or automatic veto.
        rows.append({
            'subsample_index':sample_index,
            'subsample_timestamp_seconds':sample.get('subsample_timestamp_seconds'),
            'track_id':tid,
            'model_priority':t.get('status','').replace('_priority_candidate','').replace('_candidate','').upper(),
            'observed_in_count_window':bool(in_count) if obs else '',
            'observations_in_count_window':in_count,
            'frames_seen':t.get('frames_seen'),
            'max_confidence':t.get('max_confidence'),
            'mean_confidence':t.get('mean_confidence'),
            'center_span_pct_diagonal':round(span,3),
            'median_step_pct_diagonal':round(median_step,3),
            'frame_boundary_contact_pct':round(boundary,1),
            'max_simultaneous_iou_with_other_tracks':round(max_overlap,3),
            'overlapping_track_ids':';'.join(map(str,sorted(overlaps))),
            'evidence_flags':';'.join(flags),
            'review_action':'CHECK_VISUAL_CONTEXT' if flags else 'STANDARD_REVIEW',
            'reviewer_decision':'',
            'reviewer_notes':'',
        })
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('json_file',type=Path)
    parser.add_argument('--width',type=int,default=3840,help='Source frame width')
    parser.add_argument('--height',type=int,default=2160,help='Source frame height')
    parser.add_argument('--out-dir',type=Path,default=None)
    a=parser.parse_args()
    if a.width<=0 or a.height<=0: parser.error('width and height must be positive')
    data=json.loads(a.json_file.read_text(encoding='utf-8'))
    out=a.out_dir or a.json_file.parent/'audit'
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,sample in enumerate(data['subsamples'],1):
        rows.extend(inspect(sample,i,a.width,a.height))
    with (out/'candidate_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    summary={
        'source_file':str(a.json_file),'reviewable_candidates':len(rows),
        'observed_in_count_window':sum(r['observed_in_count_window'] is True for r in rows),
        'low_image_variation_flags':sum('LOW_IMAGE_POSITION_VARIATION' in r['evidence_flags'] for r in rows),
        'frame_boundary_flags':sum('REPEATED_FRAME_BOUNDARY_CONTACT' in r['evidence_flags'] for r in rows),
        'overlapping_track_flags':sum('OVERLAPPING_TRACKS' in r['evidence_flags'] for r in rows),
        'automatic_fish_labels':0,'confirmed_fish_count':None,
        'warning':'Evidence flags only. Stationary animals and camera motion mean these are not fish/non-fish labels. Human review and duplicate resolution required.'}
    (out/'audit_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    print('Files:',out/'candidate_audit.csv',out/'audit_summary.json')

if __name__=='__main__':main()
