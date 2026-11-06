#!/bin/bash
cd "$(dirname "$0")"; PY=.venv/bin/python; SNAP=label_snapshot_20261106/points.csv
CFD="$PWD/../clipsift/models/cfd-rf-detr-nano-640-2026.02.02.cp-011.20260706-release.pth"
run(){ $PY eval_coastal.py --ckpt "$1" --name "$2" $3 --team-csv $SNAP --out-name coastal_snapshot.json --threshold-file eval_out/$2/threshold.json > logs/coastal_snapshot_$2.log 2>&1; }
run "$CFD" cfd_nano_baseline; run ~/.roboflow/models/rf-detr-nano.pth stock_untrained --agnostic
for s in stock cfd; do for e in 1 2 3; do run runs/p2_$s/ema_epoch$e.pth p2_${s}_ep$e; done; done
echo done > logs/snapshot_done.txt
