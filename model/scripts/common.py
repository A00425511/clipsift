"""Shared helpers: model loading and tiled inference. Uses rfdetr.from_checkpoint (weights_only safe load)."""
import sys, warnings
from pathlib import Path
import numpy as np
from PIL import Image
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CLIPSIFT = ROOT / "clipsift"
sys.path.insert(0, str(CLIPSIFT))     # read-only import of clipsift.stages.cfd (tile_boxes, merge_boxes)
CFD_NANO = CLIPSIFT / "models" / "cfd-rf-detr-nano-640-2026.02.02.cp-011.20260706-release.pth"

def pick_device(req="auto"):
    import torch
    if req != "auto": return req
    return "mps" if torch.backends.mps.is_available() else "cpu"

def load_model(ckpt, device="auto"):
    from rfdetr import from_checkpoint
    return from_checkpoint(str(ckpt), device=pick_device(device))

def class_map(model):
    """Return {model class_id: our name} using names stored in the checkpoint. A single-class model is treated as fish."""
    names = list(getattr(model, "class_names", []) or [])
    return names

def predict_batch(model, rgb_list, thr=0.01):
    """rgb_list: list of HxWx3 uint8 RGB arrays. Returns list of (xyxy Nx4, conf N, cls N)."""
    imgs = [Image.fromarray(np.ascontiguousarray(a)) for a in rgb_list]
    res = model.predict(imgs if len(imgs) > 1 else imgs[0], threshold=thr)
    res = res if isinstance(res, list) else [res]
    return [(np.asarray(d.xyxy, float).reshape(-1, 4), np.asarray(d.confidence, float).reshape(-1),
             np.asarray(d.class_id, int).reshape(-1)) for d in res]

def iou_matrix(a, b):
    a = np.asarray(a, float).reshape(-1, 4); b = np.asarray(b, float).reshape(-1, 4)
    if not len(a) or not len(b): return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0]); y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2]); y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2-x1, 0, None)*np.clip(y2-y1, 0, None)
    aa = (a[:, 2]-a[:, 0])*(a[:, 3]-a[:, 1]); bb = (b[:, 2]-b[:, 0])*(b[:, 3]-b[:, 1])
    return inter/np.maximum(aa[:, None]+bb[None, :]-inter, 1e-9)
