"""SMOKE TEST ONLY: <=100 optimiser steps of RF-DETR Nano fine-tuning on tiles/puget_v1 (MPS). Scores mean nothing.
  .venv/bin/python smoke_train.py --start cfd|stock --steps 100 --batch 4 --res 640 [--device mps]
Uses rfdetr's own trainer; one 'epoch' is capped to --steps batches (limit_train_batches) so epoch-end checkpoint+val hooks fire.
Per-step times, loss and MPS memory are written to runs/<tag>/smoke_metrics.json."""
import sys, json, time, argparse
sys.dont_write_bytecode = True
from pathlib import Path
import torch
from common import *

def main():
    global log
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, choices=["cfd", "stock"]); ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--batch", type=int, default=4); ap.add_argument("--res", type=int, default=640)
    ap.add_argument("--device", default="mps"); ap.add_argument("--val-batches", type=int, default=15)
    ap.add_argument("--tag"); ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    tag = a.tag or f"smoke_{a.start}_b{a.batch}_r{a.res}_{a.device}"
    out = HERE / "runs" / tag; out.mkdir(parents=True, exist_ok=True)

    import rfdetr.training as T
    from pytorch_lightning import Callback
    log = {"step_end_t": [], "loss": [], "mps_alloc_mb": [], "mps_driver_mb": []}

    class Probe(Callback):
        def on_train_batch_end(self, trainer, pl_module, outputs, batch, batch_idx):
            if self.dev == "mps": torch.mps.synchronize()
            log["step_end_t"].append(time.perf_counter())
            l = outputs["loss"] if isinstance(outputs, dict) and "loss" in outputs else outputs
            try: log["loss"].append(float(l))
            except Exception: log["loss"].append(float(trainer.callback_metrics.get("train/loss", float("nan"))))
            if self.dev == "mps":
                log["mps_alloc_mb"].append(torch.mps.current_allocated_memory()/2**20); log["mps_driver_mb"].append(torch.mps.driver_allocated_memory()/2**20)
        dev = a.device

    _orig = T.build_trainer
    def patched(tc, mc, **kw):
        kw.update(limit_train_batches=a.steps, limit_val_batches=a.val_batches, num_sanity_val_steps=0)
        tr = _orig(tc, mc, **kw); tr.callbacks.append(Probe()); return tr
    T.build_trainer = patched

    from rfdetr import RFDETRNano
    if a.start == "cfd":
        weights = str(CFD_NANO)
    else:
        weights = None   # rfdetr downloads its own official stock nano (rf-detr-nano.pth) into ~/.roboflow/models
    kw = dict(resolution=a.res, num_classes=2)   # explicit: new 2-class head (fish, crab); otherwise rfdetr keeps the checkpoint class count
    if weights: kw["pretrain_weights"] = weights
    model = RFDETRNano(**kw)
    log["t_start"] = time.perf_counter()
    status = "ok"
    try:
        model.train(dataset_dir=str(HERE/"tiles/puget_v1"), epochs=1, batch_size=a.batch, grad_accum_steps=1, device=a.device,
                    output_dir=str(out), num_workers=a.workers, tensorboard=False, progress_bar=None, use_ema=True, checkpoint_interval=1,
                    class_names=["fish", "crab"])
    except Exception as e:
        import traceback; traceback.print_exc(); status = f"FAILED: {type(e).__name__}: {e}"
    t = log["step_end_t"]; d = [t[i+1]-t[i] for i in range(len(t)-1)]
    summ = dict(tag=tag, status=status, steps=len(t), batch=a.batch, res=a.res, device=a.device, start=a.start,
                first_step_s=(t[0]-log["t_start"]) if t else None,
                sec_per_step_median=float(sorted(d)[len(d)//2]) if d else None, sec_per_step_mean_last50=float(sum(d[-50:])/max(1, len(d[-50:]))) if d else None,
                loss_first10_mean=sum(log["loss"][:10])/max(1, len(log["loss"][:10])), loss_last10_mean=sum(log["loss"][-10:])/max(1, len(log["loss"][-10:])),
                mps_alloc_mb_max=max(log["mps_alloc_mb"]) if log["mps_alloc_mb"] else None, mps_driver_mb_max=max(log["mps_driver_mb"]) if log["mps_driver_mb"] else None,
                files=sorted(p.name for p in out.iterdir()))
    json.dump({"summary": summ, "loss": log["loss"], "step_dt": d}, open(out/"smoke_metrics.json", "w"), indent=1)
    print("SMOKE_SUMMARY", json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
