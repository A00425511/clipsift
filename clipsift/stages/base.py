"""Stage interfaces and the backend registry.

Stages: SegmentProposer, Detector, Tracker, Classifier, Counter, plus the optional CountingModel.
Config picks one backend per stage by name (config `stages:`).
To add a backend: write ONE class, decorate it with @register("<stage>", "<name>"),
and set the name in config. Constructors receive the whole config dict.
"""
from __future__ import annotations

REGISTRY: dict = {"proposer": {}, "detector": {}, "tracker": {}, "classifier": {}, "counter": {}, "counting_model": {}}


def register(stage: str, name: str, requires_2b: bool = False):
    def deco(cls):
        cls.stage, cls.backend_name, cls.requires_2b = stage, name, requires_2b
        REGISTRY[stage][name] = cls
        return cls
    return deco


def list_backends() -> dict:
    return {s: sorted(b) for s, b in REGISTRY.items()}


def get_backend(stage: str, name: str, cfg: dict):
    if name not in REGISTRY.get(stage, {}):
        raise KeyError(f"No {stage} backend named '{name}'. Available: {sorted(REGISTRY[stage])}")
    cls = REGISTRY[stage][name]
    # Layer 2b (cloud) is never selectable unless the config explicitly enables it.
    if cls.requires_2b and not (cfg.get("cloud") or {}).get("enable_2b", False):
        raise PermissionError(f"Backend '{name}' is Layer 2b (cloud). It is off by default. "
                              "Set cloud.enable_2b: true in the config to allow it.")
    return cls(cfg)


class SegmentProposer:
    """frames: iterable of (t_seconds, grayscale uint8 frame). Returns list[Segment]."""
    model_version = None

    def propose(self, frames, start_s: float = 0.0, end_s: float | None = None) -> list:
        raise NotImplementedError


class Detector:
    """detect(frame, t) -> list[Detection] with boxes in the pixel space of `frame`."""
    model_version = None

    def prepare(self, frames) -> None:
        """Optional hook: called once with the BGR frames of a window before detect()."""

    def detect(self, frame, t: float) -> list:
        raise NotImplementedError


class Tracker:
    """track(detections_per_frame) -> list[Track]; also sets Detection.track_id."""

    def track(self, detections_per_frame: list) -> list:
        raise NotImplementedError


class Classifier:
    """classify(crop) -> list[SpeciesGuess], best first."""

    def classify(self, crop) -> list:
        raise NotImplementedError


class Counter:
    """count(tracks, detections, sample_times=None) -> Counts. Counts are relative indices."""

    def count(self, tracks: list, detections: list, sample_times=None):
        raise NotImplementedError


class CountingModel:
    """Point or density counting for schools of small fish a box detector may miss.
    count_points(frame, t) -> list of [x, y, score] in the pixel space of `frame`.
    Optional stage: leave stages.counting_model null to skip it."""
    model_version = None

    def count_points(self, frame, t: float) -> list:
        raise NotImplementedError
