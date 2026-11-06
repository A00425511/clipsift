"""Configuration: default.yaml, deep-merged with a user file and overrides."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config" / "default.yaml"


def deep_merge(base: dict, new: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (new or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(path=None, overrides: dict | None = None) -> dict:
    """Load default.yaml, then an optional user YAML, then a dict of overrides."""
    with open(DEFAULT_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if path:
        with open(path, "r", encoding="utf-8") as f:
            cfg = deep_merge(cfg, yaml.safe_load(f) or {})
    if overrides:
        cfg = deep_merge(cfg, overrides)
    return cfg


def config_hash(cfg: dict) -> str:
    """Short stable hash of the settings that affect results (paths are excluded)."""
    c = {k: v for k, v in cfg.items() if k != "paths"}
    blob = json.dumps(c, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def resolve_path(p, cfg: dict | None = None):
    """Relative paths in config are relative to the project root."""
    if p is None:
        return None
    p = Path(p)
    return p if p.is_absolute() else ROOT / p
