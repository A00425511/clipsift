"""Data contract for results.json (schema_version 0.2).

Plain dataclasses with to_dict / from_dict, plus validate() which checks a
plain dict (for example one loaded from disk) and returns a list of problems.
An empty list means the document is valid.

Null (None) means "not computed". Boxes are [x, y, w, h] in ORIGINAL pixels.
Counts are relative indices, not abundance.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

SCHEMA_VERSION = "0.2"
KINDS = ("active", "set_aside")
STATUSES = ("known", "fish_unknown", "unclear", "movement_unidentified", "none")
TRACK_STATUSES = ("known", "fish_unknown", "unclear")


@dataclass
class Detection:
    t: float
    box: list  # [x, y, w, h] original pixels
    score: float = 0.0
    track_id: Optional[int] = None
    source: str = ""  # which backend made it, e.g. "onnx:model.onnx" or "motion_blob"
    # Static-object filter (clipsift/static_filter.py). Rejected boxes are kept, not deleted.
    static: bool = False  # True = judged a fixed object (pipe, pole, rock) or masked; hidden and not counted
    static_reason: Optional[str] = None  # e.g. "persistent", "no_movement", "mask" (joined with "+")
    movement: Optional[float] = None  # 90th percentile of absolute difference from the background, grey levels

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.movement is not None:
            d["movement"] = round(float(self.movement), 2)
        d["box"] = [round(float(v), 1) for v in self.box]
        d["t"] = round(float(self.t), 3)
        d["score"] = round(float(self.score), 4)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Detection":
        return cls(t=float(d["t"]), box=list(d["box"]), score=float(d.get("score", 0.0)),
                   track_id=d.get("track_id"), source=d.get("source", ""),
                   static=bool(d.get("static", False)), static_reason=d.get("static_reason"),
                   movement=None if d.get("movement") is None else float(d["movement"]))


@dataclass
class SpeciesGuess:
    name: str
    score: float = 0.0
    aphia_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {"name": self.name, "aphia_id": self.aphia_id, "score": round(float(self.score), 4)}

    @classmethod
    def from_dict(cls, d: dict) -> "SpeciesGuess":
        return cls(name=d["name"], score=float(d.get("score", 0.0)), aphia_id=d.get("aphia_id"))


@dataclass
class Track:
    track_id: int
    start_s: float
    end_s: float
    n_points: int
    species_topk: list = field(default_factory=list)  # list[SpeciesGuess]
    status: str = "fish_unknown"

    def to_dict(self) -> dict:
        return {"track_id": self.track_id, "start_s": round(self.start_s, 3),
                "end_s": round(self.end_s, 3), "n_points": self.n_points,
                "species_topk": [g.to_dict() for g in self.species_topk],
                "status": self.status}

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        return cls(track_id=int(d["track_id"]), start_s=float(d["start_s"]), end_s=float(d["end_s"]),
                   n_points=int(d.get("n_points", 0)),
                   species_topk=[SpeciesGuess.from_dict(g) for g in d.get("species_topk", [])],
                   status=d.get("status", "fish_unknown"))


@dataclass
class Counts:
    maxn: Optional[int] = None
    maxn_time_s: Optional[float] = None
    mean_count: Optional[float] = None
    unique_tracks: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Counts":
        d = d or {}
        return cls(maxn=d.get("maxn"), maxn_time_s=d.get("maxn_time_s"),
                   mean_count=d.get("mean_count"), unique_tracks=d.get("unique_tracks"))


@dataclass
class Flags:
    shake: bool = False
    low_visibility: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Flags":
        d = d or {}
        return cls(shake=bool(d.get("shake", False)), low_visibility=bool(d.get("low_visibility", False)))


@dataclass
class Segment:
    segment_id: str
    start_s: float
    end_s: float
    kind: str = "active"
    audit_sample: bool = False
    motion_score: float = 0.0
    flags: Flags = field(default_factory=Flags)
    visibility_score: float = 0.0
    status: str = "movement_unidentified"
    still_time_s: float = 0.0
    detections: list = field(default_factory=list)  # list[Detection]
    tracks: list = field(default_factory=list)  # list[Track]
    counts: Counts = field(default_factory=Counts)
    review_priority: float = 0.0

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "start_s": round(self.start_s, 3), "end_s": round(self.end_s, 3),
            "kind": self.kind, "audit_sample": self.audit_sample,
            "motion_score": round(float(self.motion_score), 5),
            "flags": self.flags.to_dict(),
            "visibility_score": round(float(self.visibility_score), 4),
            "status": self.status,
            "still_time_s": round(float(self.still_time_s), 3),
            "detections": [d.to_dict() for d in self.detections],
            "tracks": [t.to_dict() for t in self.tracks],
            "counts": self.counts.to_dict(),
            "review_priority": round(float(self.review_priority), 4),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(segment_id=d["segment_id"], start_s=float(d["start_s"]), end_s=float(d["end_s"]),
                   kind=d.get("kind", "active"), audit_sample=bool(d.get("audit_sample", False)),
                   motion_score=float(d.get("motion_score", 0.0)), flags=Flags.from_dict(d.get("flags")),
                   visibility_score=float(d.get("visibility_score", 0.0)),
                   status=d.get("status", "none"), still_time_s=float(d.get("still_time_s", d["start_s"])),
                   detections=[Detection.from_dict(x) for x in d.get("detections", [])],
                   tracks=[Track.from_dict(x) for x in d.get("tracks", [])],
                   counts=Counts.from_dict(d.get("counts")),
                   review_priority=float(d.get("review_priority", 0.0)))


def empty_auto() -> dict:
    return {"fish_count": None, "invertebrate_count": None, "detections": [], "points": [],
            "motion_near_point": False, "movement_unidentified": 0, "visibility_score": 0.0}


@dataclass
class Subsample:
    """One systematic subsample point: the main unit of review."""
    subsample_id: str
    t_s: float
    context_start_s: float
    context_end_s: float
    auto: dict = field(default_factory=empty_auto)  # suggestions only, never final counts
    qc_sample: bool = False
    review_priority: float = 0.0

    def to_dict(self) -> dict:
        a = dict(self.auto)
        a["detections"] = [x.to_dict() if isinstance(x, Detection) else x for x in a.get("detections", [])]
        a["points"] = [[round(float(v), 2) for v in pt] for pt in a.get("points", [])]
        a["visibility_score"] = round(float(a.get("visibility_score", 0.0)), 4)
        return {"subsample_id": self.subsample_id, "t_s": round(self.t_s, 3),
                "context_start_s": round(self.context_start_s, 3),
                "context_end_s": round(self.context_end_s, 3), "auto": a,
                "qc_sample": self.qc_sample, "review_priority": round(float(self.review_priority), 4)}

    @classmethod
    def from_dict(cls, d: dict) -> "Subsample":
        a = empty_auto()
        a.update(d.get("auto") or {})
        return cls(subsample_id=d["subsample_id"], t_s=float(d["t_s"]),
                   context_start_s=float(d.get("context_start_s", d["t_s"])),
                   context_end_s=float(d.get("context_end_s", d["t_s"])), auto=a,
                   qc_sample=bool(d.get("qc_sample", False)),
                   review_priority=float(d.get("review_priority", 0.0)))


@dataclass
class Recording:
    recording_id: str
    source_files: list = field(default_factory=list)
    duration_s: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    site: Optional[str] = None
    date: Optional[str] = None
    video_id: Optional[str] = None  # must match the Coastal Action spreadsheet; editable
    transect: Optional[str] = None
    stat: Optional[str] = None
    year: Optional[int] = None
    season: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_s"] = round(self.duration_s, 3)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Recording":
        return cls(recording_id=d["recording_id"], source_files=list(d.get("source_files", [])),
                   duration_s=float(d.get("duration_s", 0.0)), fps=float(d.get("fps", 0.0)),
                   width=int(d.get("width", 0)), height=int(d.get("height", 0)),
                   site=d.get("site"), date=d.get("date"), video_id=d.get("video_id"),
                   transect=d.get("transect"), stat=d.get("stat"), year=d.get("year"),
                   season=d.get("season"))


@dataclass
class Run:
    layer: int = 0
    model_version: Optional[str] = None
    config_hash: str = ""
    created_at: str = ""
    sample_fps: float = 2.0
    runtime_s: float = 0.0
    stage_runtimes_s: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["runtime_s"] = round(self.runtime_s, 3)
        d["stage_runtimes_s"] = {k: round(v, 3) for k, v in self.stage_runtimes_s.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Run":
        return cls(layer=int(d.get("layer", 0)), model_version=d.get("model_version"),
                   config_hash=d.get("config_hash", ""), created_at=d.get("created_at", ""),
                   sample_fps=float(d.get("sample_fps", 2.0)), runtime_s=float(d.get("runtime_s", 0.0)),
                   stage_runtimes_s=dict(d.get("stage_runtimes_s", {})))


@dataclass
class Summary:
    n_segments: int = 0
    n_active: int = 0
    n_set_aside: int = 0
    n_audit: int = 0
    maxn: Optional[int] = None
    mean_count: Optional[float] = None
    unique_tracks: Optional[int] = None
    mean_count_auto: Optional[float] = None  # mean of model/stand-in fish counts over subsamples
    mean_count_reviewed: Optional[float] = None  # filled from subsample_reviews.jsonl by export
    n_subsamples: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Summary":
        d = d or {}
        return cls(**{k: d.get(k, getattr(cls(), k)) for k in cls().__dict__})


@dataclass
class Results:
    recording: Recording
    run: Run
    segments: list = field(default_factory=list)
    summary: Summary = field(default_factory=Summary)
    schema_version: str = SCHEMA_VERSION
    protocol: dict = field(default_factory=dict)  # config used + window_start_s, window_end_s
    subsamples: list = field(default_factory=list)  # list[Subsample]

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "recording": self.recording.to_dict(),
                "run": self.run.to_dict(), "protocol": self.protocol,
                "subsamples": [x.to_dict() for x in self.subsamples],
                "segments": [s.to_dict() for s in self.segments],
                "summary": self.summary.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "Results":
        return cls(recording=Recording.from_dict(d["recording"]), run=Run.from_dict(d["run"]),
                   segments=[Segment.from_dict(s) for s in d.get("segments", [])],
                   summary=Summary.from_dict(d.get("summary")),
                   schema_version=d.get("schema_version", SCHEMA_VERSION),
                   protocol=dict(d.get("protocol", {})),
                   subsamples=[Subsample.from_dict(x) for x in d.get("subsamples", [])])

    def compute_summary(self) -> Summary:
        """Fill the summary from the segments. Counts stay None if never computed."""
        active = [s for s in self.segments if s.kind == "active"]
        maxn = [s.counts.maxn for s in active if s.counts.maxn is not None]
        means = [s.counts.mean_count for s in active if s.counts.mean_count is not None]
        uniq = [s.counts.unique_tracks for s in active if s.counts.unique_tracks is not None]
        self.summary = Summary(
            n_segments=len(self.segments), n_active=len(active),
            n_set_aside=len(self.segments) - len(active),
            n_audit=sum(1 for s in self.segments if s.audit_sample),
            maxn=max(maxn) if maxn else None,
            mean_count=round(sum(means) / len(means), 4) if means else None,
            unique_tracks=sum(uniq) if uniq else None,
            mean_count_auto=self._mean_auto(), mean_count_reviewed=None,
            n_subsamples=len(self.subsamples))
        return self.summary

    def _mean_auto(self):
        v = [x.auto.get("fish_count") for x in self.subsamples if x.auto.get("fish_count") is not None]
        return round(sum(v) / len(v), 4) if v else None


# ---------------------------------------------------------------- validation
def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _opt_num(v) -> bool:
    return v is None or _num(v)


def validate(d: Any) -> list:
    """Check a results dict against the contract. Returns a list of error strings."""
    errs: list = []

    def need(obj, key, where, typ=None):
        if not isinstance(obj, dict) or key not in obj:
            errs.append(f"{where}: missing '{key}'")
            return None
        v = obj[key]
        if typ is not None and not typ(v):
            errs.append(f"{where}.{key}: wrong type ({type(v).__name__})")
        return v

    if not isinstance(d, dict):
        return ["results is not an object"]
    if d.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version should be '{SCHEMA_VERSION}', got {d.get('schema_version')!r}")
    rec = need(d, "recording", "results")
    for k, t in (("recording_id", lambda v: isinstance(v, str)), ("source_files", lambda v: isinstance(v, list)),
                 ("duration_s", _num), ("fps", _num), ("width", _num), ("height", _num)):
        need(rec, k, "recording", t)
    run = need(d, "run", "results")
    for k, t in (("layer", lambda v: v in (0, 1, 2)), ("config_hash", lambda v: isinstance(v, str)),
                 ("created_at", lambda v: isinstance(v, str)), ("sample_fps", _num),
                 ("runtime_s", _num), ("stage_runtimes_s", lambda v: isinstance(v, dict))):
        need(run, k, "run", t)
    if isinstance(run, dict) and run.get("model_version") is not None and not isinstance(run["model_version"], str):
        errs.append("run.model_version must be a string or null")
    need(d, "protocol", "results", lambda v: isinstance(v, dict))
    prot = d.get("protocol") if isinstance(d.get("protocol"), dict) else {}
    for k in ("window_start_s", "window_end_s"):
        need(prot, k, "protocol", _num)
    subs = need(d, "subsamples", "results", lambda v: isinstance(v, list))
    for i, x in enumerate(subs or []):
        w = f"subsamples[{i}]"
        need(x, "subsample_id", w, lambda v: isinstance(v, str))
        need(x, "t_s", w, _num)
        need(x, "context_start_s", w, _num)
        need(x, "context_end_s", w, _num)
        need(x, "qc_sample", w, lambda v: isinstance(v, bool))
        need(x, "review_priority", w, _num)
        au = need(x, "auto", w, lambda v: isinstance(v, dict))
        need(au, "fish_count", w + ".auto", _opt_num)
        need(au, "invertebrate_count", w + ".auto", _opt_num)
        need(au, "detections", w + ".auto", lambda v: isinstance(v, list))
        need(au, "motion_near_point", w + ".auto", lambda v: isinstance(v, bool))
        need(au, "movement_unidentified", w + ".auto", _num)
        need(au, "visibility_score", w + ".auto", _num)
    segs = need(d, "segments", "results", lambda v: isinstance(v, list))
    seen = set()
    for i, s in enumerate(segs or []):
        w = f"segments[{i}]"
        sid = need(s, "segment_id", w, lambda v: isinstance(v, str))
        if sid in seen:
            errs.append(f"{w}: duplicate segment_id {sid}")
        seen.add(sid)
        a = need(s, "start_s", w, _num)
        b = need(s, "end_s", w, _num)
        if _num(a) and _num(b) and b < a:
            errs.append(f"{w}: end_s before start_s")
        need(s, "kind", w, lambda v: v in KINDS)
        need(s, "audit_sample", w, lambda v: isinstance(v, bool))
        need(s, "motion_score", w, _num)
        fl = need(s, "flags", w, lambda v: isinstance(v, dict))
        for k in ("shake", "low_visibility"):
            need(fl, k, w + ".flags", lambda v: isinstance(v, bool))
        need(s, "visibility_score", w, _num)
        need(s, "status", w, lambda v: v in STATUSES)
        need(s, "still_time_s", w, _num)
        need(s, "review_priority", w, _num)
        for j, det in enumerate(need(s, "detections", w, lambda v: isinstance(v, list)) or []):
            dw = f"{w}.detections[{j}]"
            need(det, "t", dw, _num)
            need(det, "box", dw, lambda v: isinstance(v, list) and len(v) == 4 and all(_num(x) for x in v))
            need(det, "score", dw, _num)
            need(det, "source", dw, lambda v: isinstance(v, str))
            if isinstance(det, dict) and "track_id" not in det:
                errs.append(f"{dw}: missing 'track_id'")
        for j, tr in enumerate(need(s, "tracks", w, lambda v: isinstance(v, list)) or []):
            tw = f"{w}.tracks[{j}]"
            need(tr, "track_id", tw, _num)
            need(tr, "start_s", tw, _num)
            need(tr, "end_s", tw, _num)
            need(tr, "n_points", tw, _num)
            need(tr, "species_topk", tw, lambda v: isinstance(v, list))
            need(tr, "status", tw, lambda v: v in TRACK_STATUSES)
        c = need(s, "counts", w, lambda v: isinstance(v, dict))
        need(c, "maxn", w + ".counts", _opt_num)
        need(c, "maxn_time_s", w + ".counts", _opt_num)
        need(c, "mean_count", w + ".counts", _opt_num)
        need(c, "unique_tracks", w + ".counts", _opt_num)
    summ = need(d, "summary", "results", lambda v: isinstance(v, dict))
    for k in ("n_segments", "n_active", "n_set_aside", "n_audit", "n_subsamples"):
        need(summ, k, "summary", _num)
    if isinstance(summ, dict) and isinstance(segs, list) and summ.get("n_segments") != len(segs):
        errs.append("summary.n_segments does not match number of segments")
    return errs
