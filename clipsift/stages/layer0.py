"""Layer 0: motion segments by temporal median background. No detections, no ML."""
from __future__ import annotations

import random
from dataclasses import dataclass

import cv2
import numpy as np

from ..schema import Segment, Flags
from .base import SegmentProposer, register


@dataclass
class SampleStat:
    t: float
    active: bool = False       # blob big enough in this sample
    confirmed: bool = False    # part of a run of min_consecutive active samples
    motion: float = 0.0        # share of the frame covered by qualifying blobs
    visibility: float = 0.0    # 0..1 from contrast and sharpness
    shift_px: float = 0.0      # global shift away from the window's typical position (shake)


def _align(gray, ref):
    """Return (aligned gray, (dx, dy)) using phase correlation. Small shifts only."""
    try:
        (dx, dy), _ = cv2.phaseCorrelate(np.float32(ref), np.float32(gray))
    except cv2.error:
        return gray, (0.0, 0.0)
    if abs(dx) > 15 or abs(dy) > 15:
        return gray, (0.0, 0.0)
    m = np.float32([[1, 0, -dx], [0, 1, -dy]])
    out = cv2.warpAffine(gray, m, (gray.shape[1], gray.shape[0]), borderMode=cv2.BORDER_REPLICATE)
    return out, (dx, dy)


@register("proposer", "median_background")
class MedianBackgroundProposer(SegmentProposer):
    """Median background over windows of samples; blobs in the difference are 'motion'.

    Known limit: something that sits still for a whole window becomes background.
    Runs on downscaled grayscale frames for speed (see proxy_width in config).
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.pc = cfg["proposer"]
        self.dt = 1.0 / cfg["sample_fps"]
        self.stats: list = []

    # ---- sample statistics -------------------------------------------------
    def analyse(self, frames) -> list:
        """Stream frames in windows; return a SampleStat per sample."""
        W = self.pc["window_samples"]
        stats, buf, context = [], [], []
        for t, g in frames:
            buf.append((t, g))
            if len(buf) >= W:
                stats += self._process(buf, context, W)
                context = [x for _, x in buf]
                buf = []
        if buf:
            stats += self._process(buf, context, W)
        self._confirm(stats)
        self.stats = stats
        return stats

    def _process(self, buf, context, W):
        grays = [g for _, g in buf]
        allf = (context + grays)[-W:] if len(grays) < W else grays
        ref = allf[0]
        aligned, shifts = [], []
        for g in allf:
            a, s = _align(g, ref)
            aligned.append(a)
            shifts.append(s)
        stack = np.stack(aligned).astype(np.float32)
        bg = np.median(stack, axis=0)
        bg_med = float(np.median(bg))
        k = self.pc["blur_ksize"] | 1
        bg_blur = cv2.GaussianBlur(bg, (k, k), 0)
        sx, sy = np.median([s[0] for s in shifts]), np.median([s[1] for s in shifts])
        out = []
        n_new = len(grays)
        for i in range(len(allf) - n_new, len(allf)):
            t = buf[i - (len(allf) - n_new)][0]
            f = aligned[i].astype(np.float32)
            f += bg_med - float(np.median(f))  # ignore slow global brightness change
            diff = np.abs(cv2.GaussianBlur(f, (k, k), 0) - bg_blur)
            mask = (diff > self.pc["diff_threshold"]).astype(np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            n, _, st, _ = cv2.connectedComponentsWithStats(mask, 8)
            areas = [int(st[j, cv2.CC_STAT_AREA]) for j in range(1, n)
                     if st[j, cv2.CC_STAT_AREA] >= self.pc["min_blob_area"]]
            s = SampleStat(t=t, active=bool(areas), motion=sum(areas) / mask.size)
            g = grays[i - (len(allf) - n_new)]
            s.visibility = self._visibility(g)
            s.shift_px = float(np.hypot(shifts[i][0] - sx, shifts[i][1] - sy))
            out.append(s)
        return out

    def _visibility(self, g) -> float:
        contrast = min(1.0, float(g.std()) / self.pc["contrast_scale"])
        sharp = min(1.0, float(cv2.Laplacian(g, cv2.CV_64F).var()) / self.pc["sharpness_scale"])
        return 0.5 * contrast + 0.5 * sharp

    def _confirm(self, stats):
        n = self.pc["min_consecutive"]
        i = 0
        while i < len(stats):
            if not stats[i].active:
                i += 1
                continue
            j = i
            while j < len(stats) and stats[j].active:
                j += 1
            if j - i >= n:
                for s in stats[i:j]:
                    s.confirmed = True
            i = j

    # ---- segments ------------------------------------------------------------
    def propose(self, frames, start_s: float = 0.0, end_s: float | None = None) -> list:
        stats = self.analyse(frames)
        if not stats:
            return []
        t0 = start_s
        t1 = end_s if end_s is not None else stats[-1].t + self.dt
        return self.segments_from_stats(stats, t0, t1)

    def segments_from_stats(self, stats, t0, t1) -> list:
        pc = self.pc
        runs = []
        i = 0
        while i < len(stats):
            if stats[i].confirmed:
                j = i
                while j + 1 < len(stats) and stats[j + 1].confirmed:
                    j += 1
                runs.append([max(t0, stats[i].t - pc["pad_s"]), min(t1, stats[j].t + self.dt + pc["pad_s"])])
                i = j + 1
            else:
                i += 1
        merged = []
        for r in runs:
            if merged and r[0] - merged[-1][1] < pc["merge_gap_s"]:
                merged[-1][1] = max(merged[-1][1], r[1])
            else:
                merged.append(r)
        active = [(a, b) for a, b in merged]
        pieces = []  # (start, end, kind)
        for a, b in active:
            pieces += [(x, y, "active") for x, y in self._split(a, b, pc["max_segment_s"])]
        cur = t0
        for a, b in active + [(t1, t1)]:
            if a - cur > 1e-6:
                pieces += [(x, y, "set_aside") for x, y in self._split(cur, a, pc["max_set_aside_s"])]
            cur = max(cur, b)
        pieces.sort()
        segs = [self._make(i + 1, a, b, kind, stats) for i, (a, b, kind) in enumerate(pieces)]
        self._mark_audit(segs)
        return segs

    @staticmethod
    def _split(a, b, max_len):
        n = max(1, int(np.ceil((b - a) / max_len - 1e-9)))
        edges = np.linspace(a, b, n + 1)
        return [(float(edges[k]), float(edges[k + 1])) for k in range(n)]

    def _make(self, idx, a, b, kind, stats) -> Segment:
        inside = [s for s in stats if a - 1e-6 <= s.t < b + 1e-6] or stats[:1]
        peak = max(inside, key=lambda s: s.motion)
        vis = float(np.mean([s.visibility for s in inside]))
        seg = Segment(segment_id=f"seg_{idx:04d}", start_s=a, end_s=b, kind=kind,
                      motion_score=peak.motion if kind == "active" else float(np.mean([s.motion for s in inside])),
                      visibility_score=vis,
                      flags=Flags(shake=bool(np.mean([s.shift_px > self.pc["shake_px"] for s in inside]) >= 0.2),
                                  low_visibility=vis < self.pc["low_visibility_below"]),
                      status="movement_unidentified" if kind == "active" else "none",
                      still_time_s=peak.t if kind == "active" else (a + b) / 2)
        return seg

    def _mark_audit(self, segs):
        share = self.cfg["audit"]["share"]
        aside = [s for s in segs if s.kind == "set_aside"]
        if not aside or share <= 0:
            return
        target = share * sum(s.duration_s for s in aside)
        order = list(range(len(aside)))
        random.Random(self.cfg["audit"]["seed"]).shuffle(order)
        got = 0.0
        for k in order:
            if got >= target and got > 0:
                break
            aside[k].audit_sample = True
            got += aside[k].duration_s
