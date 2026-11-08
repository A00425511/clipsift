"""Tests independent of model weights; run with python -m unittest discover -s tests."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clipsift_finetuned.detector import tile_starts, tile_origins


class TestTiling(unittest.TestCase):
    def test_small_image(self):
        self.assertEqual(tile_starts(480, 1024, 256), [0])

    def test_4k_coverage(self):
        self.assertEqual(len(tile_origins(3840, 2160, 1024, 256)), 15)
        self.assertEqual(tile_starts(3840, 1024, 256)[-1], 3840-1024)
        self.assertEqual(tile_starts(2160, 1024, 256)[-1], 2160-1024)

    def test_invalid_overlap(self):
        with self.assertRaises(ValueError):
            tile_starts(2000, 1024, 1024)


if __name__ == "__main__":
    unittest.main()
