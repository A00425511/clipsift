#!/bin/bash
# Sequential: stock-start run, its evals, then CFD-start run, its evals. Re-runnable (resumes from latest checkpoint).
cd "$(dirname "$0")"
PY=.venv/bin/python
for start in stock cfd; do
  tag=p2_$start
  echo "$(date) TRAIN $tag" >> logs/phase2_launcher.log
  $PY train_run.py --start $start --tag $tag --epochs 3 --resume auto > logs/train_$tag.log 2>&1 || { echo "$(date) TRAIN FAILED $tag" >> logs/phase2_launcher.log; exit 1; }
  for e in 1 2 3; do
    ck=runs/$tag/ema_epoch$e.pth
    [ -f $ck ] || continue
    $PY eval_tiled.py --ckpt $ck --name ${tag}_ep$e --batch 16 > logs/eval_${tag}_ep$e.log 2>&1
    $PY eval_coastal.py --ckpt $ck --name ${tag}_ep$e --threshold-file eval_out/${tag}_ep$e/threshold.json > logs/coastal_${tag}_ep$e.log 2>&1
    echo "$(date) evals done ${tag}_ep$e" >> logs/phase2_launcher.log
  done
done
echo "$(date) ALL DONE" >> logs/phase2_launcher.log
