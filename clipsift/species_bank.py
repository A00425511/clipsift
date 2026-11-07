"""Species bank: turn candidate tracks into a set of images for a person to identify.

Reads the JSON that Ali's V6 pipeline writes (`subsamples_v6.json`) plus the original video.
Nothing here identifies a species or a life stage. The flags only decide what a person looks at
first, and every flag says why it was raised. The bank never changes a count, MeanCount or the
species list recorded in the watch window.

What each flag means:
  fixed_object    Barely moved, or the same box turns up at several separate points, AND the spot
                  looks the way it normally does across the video. Usually the pipe, a cable tie
                  or a seabed hollow, so it is hidden by default, never deleted. The second test
                  keeps an animal that sits beside the pipe or rests on the seabed.
  unusual         Looks least like the other candidates in this video (shape, contrast, colour).
  near_seabed     Low in the frame, where crabs and flatfish are most likely.
  small_in_frame  Among the smallest moving candidates. Small can mean young or just far away:
                  one camera gives no distance, so this is only a prompt to look for juveniles.

The thresholds are starting values, set by looking at one Coastal video. They are not validated.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

BANK_VERSION = 1
REVIEWABLE = ("high_priority_candidate", "review_candidate")
SETTINGS = {
    "still_move_ratio": 0.35,   # track moved less than this share of its own box size
    "still_min_frames": 6,      # too few sightings to judge movement, so keep the track
    "repeat_iou": 0.35,         # boxes this alike count as the same place
    "repeat_points": 3,         # same place at this many separate points means a fixed object
    "background_match": 0.75,   # at or above this, the spot looks as it normally does
    "max_frame_share": 0.5,     # a box wider or taller than this share of the frame is not an animal
    "seabed_y": 0.62,           # box centre below this share of frame height
    "small_share": 0.25,        # smallest quarter of moving candidates
    "unusual_share": 0.15,      # most different 15% of moving candidates
    "look_group_distance": 1.6,  # distance in standardised features that starts a new look group
    "same_iou": 0.25,           # two tracks seen together this alike are one animal
    "same_gap_s": 2.0,          # one track picks up this soon after another ends
    "views_to_try": 4,
    "crop_px": 480,
    "clip_half_s": 2.5,         # seconds of footage either side of the chosen view
    "clip_width": 1280,
}


def _iou(a, b) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _size(box) -> float:
    return float(max(box[2] - box[0], box[3] - box[1]))


def _centre(box):
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def movement_ratio(observations) -> float:
    """How far the box centre travelled, as a share of the box's typical long side."""
    if len(observations) < 2:
        return 0.0
    centres = np.array([_centre(o["bbox"]) for o in observations], dtype=float)
    spread = float(np.hypot(*(centres.max(axis=0) - centres.min(axis=0))))
    return spread / max(1.0, float(np.median([_size(o["bbox"]) for o in observations])))


def read_tracks(v6: dict) -> list:
    """One record per reviewable V6 track. Low-priority tracks are left out, as they are in V6."""
    tracks = []
    for index, sample in enumerate(v6.get("subsamples") or [], 1):
        for track in sample.get("candidate_tracks") or []:
            obs = [o for o in track.get("observations") or [] if len(o.get("bbox") or []) == 4]
            if track.get("status") not in REVIEWABLE or not obs:
                continue
            tracks.append({
                "id": f"p{index:03d}_t{int(track['track_id']):04d}",
                "point_s": float(sample.get("subsample_timestamp_seconds") or 0.0),
                "point_index": index,
                "v6_status": track["status"],
                "frames_seen": int(track.get("frames_seen") or len(obs)),
                "max_confidence": round(float(track.get("max_confidence") or 0.0), 3),
                "observations": obs,
            })
    return tracks


def mark_fixed(tracks: list, width: int, height: int, cfg: dict = SETTINGS) -> None:
    """Set `fixed_reason` on tracks that look like fixed objects or whole-frame artefacts."""
    place = [max(t["observations"], key=lambda o: o["confidence"])["bbox"] for t in tracks]
    for i, track in enumerate(tracks):
        reason = None
        box = place[i]
        usual_spot = track.get("background_match", 1.0) >= cfg["background_match"]
        points = {t["point_index"] for j, t in enumerate(tracks)
                  if _iou(box, place[j]) >= cfg["repeat_iou"]}
        moved = movement_ratio(track["observations"])
        track["moved"] = round(moved, 2)
        if box[2] - box[0] > cfg["max_frame_share"] * width or box[3] - box[1] > cfg["max_frame_share"] * height:
            reason = "Box covers too much of the frame"
        elif usual_spot and len(points) >= cfg["repeat_points"]:
            reason = f"Same place at {len(points)} separate points"
        elif usual_spot and moved < cfg["still_move_ratio"] and len(track["observations"]) >= cfg["still_min_frames"]:
            reason = "Barely moved during the clip"
        track["fixed_reason"] = reason


def same_animal(a: dict, b: dict, cfg: dict = SETTINGS) -> bool:
    """True when two tracks at one point look like one animal followed twice.

    Fish in a school pass close to each other, so seen-together tracks must overlap for most of the
    time they share, not just once.
    """
    if a["point_index"] != b["point_index"]:
        return False
    boxes_a = {o["frame_index"]: o["bbox"] for o in a["observations"]}
    boxes_b = {o["frame_index"]: o["bbox"] for o in b["observations"]}
    shared = boxes_a.keys() & boxes_b.keys()
    if shared:
        return float(np.median([_iou(boxes_a[f], boxes_b[f]) for f in shared])) >= cfg["same_iou"]
    first, second = sorted((a, b), key=lambda t: t["observations"][0]["timestamp"])
    end, start = first["observations"][-1], second["observations"][0]
    if start["timestamp"] - end["timestamp"] > cfg["same_gap_s"]:
        return False
    big, small = sorted((_size(end["bbox"]), _size(start["bbox"])), reverse=True)
    (x1, y1), (x2, y2) = _centre(end["bbox"]), _centre(start["bbox"])
    return small >= 0.5 * big and float(np.hypot(x2 - x1, y2 - y1)) <= big


def merge_views(items: list, cfg: dict = SETTINGS) -> list:
    """Return one item per animal. The clearest track leads and the others become `other_views`.

    A merged item only counts as a fixed object when every track in it does, so an animal is never
    hidden because one of its tracks touched the pipe.
    """
    parent = list(range(len(items)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if same_animal(items[i], items[j], cfg):
                parent[root(j)] = root(i)
    groups = {}
    for i, item in enumerate(items):
        groups.setdefault(root(i), []).append(item)
    merged = []
    for group in groups.values():
        live = [t for t in group if not t["fixed_reason"]] or group
        lead = max(live, key=lambda t: t.get("view_score", 0.0))
        lead["other_views"] = [{"id": t["id"], "crop": t["images"]["crop"], "time_s": t["time_s"]}
                               for t in group if t is not lead]
        merged.append(lead)
    return merged


def write_clip(video: Path, item: dict, out_dir: Path, cfg: dict) -> None:
    """Save a short clip around the chosen view. Skipped without ffmpeg: the frame still works."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return
    half = cfg["clip_half_s"]
    start = max(0.0, item["time_s"] - half)
    name = f"{item['id']}_clip.mp4"
    done = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{item['time_s'] - start + half:.2f}",
         "-i", str(video), "-an", "-vf", f"scale={cfg['clip_width']}:-2", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_dir / name)],
        capture_output=True, check=False)
    if done.returncode == 0:
        item["images"]["clip"] = name
        item["clip_offset_s"] = round(item["time_s"] - start, 2)


def video_background(cap, times_s, width: int = 960):
    """Median grey frame across the points: what each spot normally looks like in this video."""
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    for t in times_s:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, frame = cap.read()
        if ok:
            small = cv2.resize(frame, (width, int(width * frame.shape[0] / frame.shape[1])), interpolation=cv2.INTER_AREA)
            frames.append(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
    return np.median(np.array(frames), axis=0).astype(np.uint8) if len(frames) >= 3 else None


def background_match(frame, box, background) -> float:
    """How closely this box matches the normal view of that spot: 1 is identical, 0 is unrelated."""
    if background is None:
        return 1.0
    scale = background.shape[1] / frame.shape[1]
    x1, y1, x2, y2 = (int(v * scale) for v in box)
    x1, y1 = max(0, x1), max(0, y1)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return 1.0
    small = cv2.resize(frame, (background.shape[1], background.shape[0]), interpolation=cv2.INTER_AREA)
    now = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (0, 0), 1.0)[y1:y2, x1:x2]
    usual = cv2.GaussianBlur(background, (0, 0), 1.0)[y1:y2, x1:x2]
    if now.shape != usual.shape or now.size == 0:
        return 1.0
    return float(cv2.matchTemplate(now, usual, cv2.TM_CCOEFF_NORMED)[0][0])


def _sharpness(gray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def appearance(frame, box) -> np.ndarray:
    """Simple look features: shape, contrast against the nearby water, colour shift, edges."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (int(v) for v in box)
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    pad = max(8, int(0.3 * max(x2 - x1, y2 - y1)))
    inside = frame[y1:y2, x1:x2]
    around = frame[max(0, y1 - pad):min(h, y2 + pad), max(0, x1 - pad):min(w, x2 + pad)]
    if inside.size == 0 or around.size == 0:
        return np.zeros(6)
    lab_in = cv2.cvtColor(inside, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(float)
    lab_out = cv2.cvtColor(around, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(float)
    diff = lab_in.mean(axis=0) - lab_out.mean(axis=0)
    gray = cv2.cvtColor(inside, cv2.COLOR_BGR2GRAY)
    return np.array([
        np.log((x2 - x1) / max(1, y2 - y1)),   # long and thin, or tall
        diff[0], diff[1], diff[2],             # lighter or darker, colour shift
        float(gray.std()),                     # pattern inside the box
        np.log1p(_sharpness(gray)),
    ])


def assign_looks(items: list, cfg: dict = SETTINGS) -> None:
    """Group alike candidates and set `oddness`. Fixed objects are left out of both."""
    live = [t for t in items if not t["fixed_reason"]]
    for t in items:
        t["look_group"], t["oddness"] = None, 0.0
    if not live:
        return
    x = np.array([t["features"] for t in live], dtype=float)
    x = (x - x.mean(axis=0)) / np.where(x.std(axis=0) > 1e-6, x.std(axis=0), 1.0)
    leaders = []
    order = sorted(range(len(live)), key=lambda i: -live[i]["view_score"])
    for i in order:
        dist = [float(np.linalg.norm(x[i] - x[j])) for j in leaders]
        if dist and min(dist) <= cfg["look_group_distance"]:
            live[i]["look_group"] = int(np.argmin(dist)) + 1
        else:
            leaders.append(i)
            live[i]["look_group"] = len(leaders)
    for i, t in enumerate(live):
        d = np.sort(np.linalg.norm(x - x[i], axis=1))[1:4]
        t["oddness"] = round(float(d.mean()) if d.size else 0.0, 2)


def assign_flags(items: list, height: int, cfg: dict = SETTINGS) -> None:
    live = [t for t in items if not t["fixed_reason"]]
    small_cut = np.quantile([_size(t["bbox"]) for t in live], cfg["small_share"]) if live else 0
    odd_cut = np.quantile([t["oddness"] for t in live], 1 - cfg["unusual_share"]) if live else 0
    for t in items:
        flags, why = [], []
        if t["fixed_reason"]:
            flags.append("fixed_object")
            why.append(t["fixed_reason"])
        else:
            if len(live) >= 8 and t["oddness"] >= odd_cut:
                flags.append("unusual")
                why.append("Looks least like the other candidates in this video")
            if _centre(t["bbox"])[1] >= cfg["seabed_y"] * height:
                flags.append("near_seabed")
                why.append("Low in the frame, so check for crabs and flatfish")
            if len(live) >= 8 and _size(t["bbox"]) <= small_cut:
                flags.append("small_in_frame")
                why.append("Small in the frame. It could be young, or just far away")
        t["flags"], t["reasons"] = flags, why


def _write_views(cap, track, out_dir: Path, cfg: dict, background=None) -> dict:
    """Pick the clearest view of a track and save a close crop and a marked frame."""
    obs = track["observations"]
    best_first = sorted(obs, key=lambda o: -o["confidence"] * (_size(o["bbox"]) ** 0.5))
    tried = []
    for o in best_first[:cfg["views_to_try"]]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(o["frame_index"]))
        ok, frame = cap.read()
        if not ok:
            continue
        x1, y1, x2, y2 = (max(0, int(v)) for v in o["bbox"])
        gray = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY) if x2 > x1 and y2 > y1 else None
        score = o["confidence"] * np.log1p(_sharpness(gray)) if gray is not None else 0.0
        tried.append((float(score), o, frame))
    if not tried:
        return {}
    score, best, frame = max(tried, key=lambda t: t[0])
    h, w = frame.shape[:2]
    box = [int(v) for v in best["bbox"]]
    pad = max(24, int(0.35 * _size(box)))
    left, top, right, bottom = max(0, box[0] - pad), max(0, box[1] - pad), min(w, box[2] + pad), min(h, box[3] + pad)
    crop = frame[top:bottom, left:right]
    scale = min(3.0, cfg["crop_px"] / max(crop.shape[:2]))
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)
    marked = frame.copy()
    cv2.rectangle(marked, (box[0], box[1]), (box[2], box[3]), (0, 220, 255), max(2, w // 800))
    marked = cv2.resize(marked, (1280, int(1280 * h / w)), interpolation=cv2.INTER_AREA)
    names = {"crop": f"{track['id']}_crop.jpg", "frame": f"{track['id']}_frame.jpg"}
    cv2.imwrite(str(out_dir / names["crop"]), crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(str(out_dir / names["frame"]), marked, [cv2.IMWRITE_JPEG_QUALITY, 82])
    track.update(bbox=box, time_s=round(float(best["timestamp"]), 2), frame_index=int(best["frame_index"]),
                 view_score=round(score, 3), features=appearance(frame, box).tolist(),
                 background_match=round(background_match(frame, box, background), 2))
    return names


def _sort_key(item: dict):
    fixed = "fixed_object" in item["flags"]
    return (fixed, -len(item["flags"]), -item["oddness"], -item["max_confidence"])


def build_bank(v6_path, out_dir, video_path=None, cfg: dict = SETTINGS) -> dict:
    """Write bank.json and the images into out_dir, and return the bank."""
    v6_path, out_dir = Path(v6_path), Path(out_dir)
    v6 = json.loads(v6_path.read_text(encoding="utf-8"))
    video = Path(video_path or v6.get("video") or "")
    if not video.is_file():
        raise FileNotFoundError(f"The original video is needed for clean images. Cannot find: {video}")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video}")
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    files_dir = out_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    tracks = read_tracks(v6)
    items = []
    try:
        background = video_background(cap, [s.get("subsample_timestamp_seconds") or 0 for s in v6.get("subsamples") or []])
        for track in tracks:
            names = _write_views(cap, track, files_dir, cfg, background)
            if names:
                track["images"] = names
                items.append(track)
    finally:
        cap.release()
    mark_fixed(items, width, height, cfg)
    raw_tracks = len(items)
    items = merge_views(items, cfg)
    assign_looks(items, cfg)
    assign_flags(items, height, cfg)
    for item in items:
        write_clip(video, item, files_dir, cfg)
        if item["other_views"]:
            item["reasons"].append(f"{len(item['other_views']) + 1} overlapping tracks merged into this one")
        for key in ("observations", "features", "view_score", "fixed_reason", "point_index"):
            item.pop(key, None)
    items.sort(key=_sort_key)
    bank = {
        "version": BANK_VERSION,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"type": "v6_subsamples", "file": v6_path.name, "video": video.name,
                   "points": len(v6.get("subsamples") or []), "width": width, "height": height},
        "note": "Candidates for a person to identify. Nothing here is a species, life stage or count.",
        "counts": {"tracks": raw_tracks, "candidates": len(items),
                   "to_review": sum("fixed_object" not in i["flags"] for i in items),
                   "fixed_objects": sum("fixed_object" in i["flags"] for i in items)},
        "items": items,
    }
    tmp = out_dir / "bank.json.tmp"
    tmp.write_text(json.dumps(bank, indent=1), encoding="utf-8")
    tmp.replace(out_dir / "bank.json")
    return bank
