"""Phase 2 training run (RF-DETR Nano, MPS). One epoch = whole balanced set.
  .venv/bin/python train_run.py --start stock|cfd --tag NAME [--epochs 3] [--resume auto]
Fixed: res 640, batch 2, grad accum 4 (effective 8), rfdetr default LRs (lr 1e-4, lr_encoder 1.5e-4), EMA on, num_classes=2.
Writes runs/<tag>/: checkpoint_<epoch>.ckpt (full, for resume), ema_epoch<N>.pth (EMA weights, scoreable by eval_*.py), train_log.jsonl.
Dry-run knobs: --limit-batches N, --val-batches N, --dataset. Aborts (stops the trainer) on a NaN loss."""
import sys, json, time, argparse, math, shutil
sys.dont_write_bytecode = True
from pathlib import Path
from common import *

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, choices=["cfd", "stock"]); ap.add_argument("--tag", required=True)
    ap.add_argument("--epochs", type=int, default=3); ap.add_argument("--batch", type=int, default=2); ap.add_argument("--accum", type=int, default=4)
    ap.add_argument("--res", type=int, default=640); ap.add_argument("--resume", default=None, help="path to checkpoint_<e>.ckpt or 'auto'")
    ap.add_argument("--limit-batches", type=int); ap.add_argument("--val-batches", type=int); ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--dataset", default=str(HERE/"tiles/puget_bal_root"))
    a = ap.parse_args()
    out = HERE/"runs"/a.tag; out.mkdir(parents=True, exist_ok=True)
    resume = a.resume
    if resume == "auto":
        c = sorted(out.glob("checkpoint_*.ckpt"), key=lambda p: p.stat().st_mtime); resume = str(c[-1]) if c else None
    import torch, rfdetr.training as T
    from pytorch_lightning import Callback
    from rfdetr.training.callbacks.best_model import BestModelCallback
    logf = open(out/"train_log.jsonl", "a")

    class Probe(Callback):
        def __init__(s): s.t = None
        def on_train_batch_end(s, trainer, m, outputs, batch, i):
            torch.mps.synchronize(); now = time.perf_counter()
            l = outputs["loss"] if isinstance(outputs, dict) else outputs
            l = float(l)
            if s.t is not None and i % 20 == 0:
                logf.write(json.dumps({"epoch": trainer.current_epoch, "batch": i, "gstep": trainer.global_step, "loss": l, "dt": now-s.t,
                                       "mps_driver_mb": torch.mps.driver_allocated_memory()/2**20}) + "\n"); logf.flush()
            s.t = now
            if not math.isfinite(l):
                logf.write(json.dumps({"NaN_loss_at": trainer.global_step}) + "\n"); logf.flush(); trainer.should_stop = True
        def on_train_epoch_end(s, trainer, m):
            best = [c for c in trainer.callbacks if isinstance(c, BestModelCallback)][0]
            sd = best._get_ema_model_state_dict(trainer, m)
            best._write_ema_checkpoint(trainer, m, sd, out/f"ema_epoch{trainer.current_epoch+1}.pth")
            logf.write(json.dumps({"epoch_done": trainer.current_epoch+1, "t": time.time()}) + "\n"); logf.flush()

    orig = T.build_trainer
    def patched(tc, mc, **kw):
        if a.limit_batches: kw["limit_train_batches"] = a.limit_batches
        if a.val_batches: kw["limit_val_batches"] = a.val_batches
        kw["num_sanity_val_steps"] = 0
        tr = orig(tc, mc, **kw); tr.callbacks.append(Probe()); return tr
    T.build_trainer = patched
    from rfdetr import RFDETRNano
    kw = dict(resolution=a.res, num_classes=2)
    if a.start == "cfd": kw["pretrain_weights"] = str(CFD_NANO)
    model = RFDETRNano(**kw)
    t0 = time.time()
    model.train(dataset_dir=a.dataset, epochs=a.epochs, batch_size=a.batch, grad_accum_steps=a.accum, device="mps", output_dir=str(out),
                num_workers=a.workers, tensorboard=False, progress_bar=None, use_ema=True, checkpoint_interval=1,
                class_names=["fish", "crab"], resume=resume)
    logf.write(json.dumps({"train_done_seconds": time.time()-t0}) + "\n"); logf.close()
    print("TRAIN_DONE", time.time()-t0)

if __name__ == "__main__":
    main()
