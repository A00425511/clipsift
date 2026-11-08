"""Portable inference adapter for the experimental ClipSift RF-DETR Small checkpoint."""

from .detector import FishDetector, tile_origins

__all__ = ["FishDetector", "tile_origins"]
