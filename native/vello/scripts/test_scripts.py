"""Small, GPU-independent tests for evidence generation."""
import unittest

import numpy as np

from compare import stats, uniform_mask
from make_fixture import build_scene, parse_ncel, to_json


class EvidenceTests(unittest.TestCase):
    def test_uniform_mask_excludes_borders_and_nearby_edges(self):
        rgb = np.zeros((7, 7, 3), dtype=np.int16)
        rgb[3, 3] = 1
        mask = uniform_mask(rgb)
        self.assertEqual(int(mask.sum()), 16)
        self.assertFalse(mask[0].any())
        self.assertFalse(mask[3, 2])
        self.assertTrue(mask[1, 1])

    def test_stats_count_pixels_not_channels(self):
        d = np.array([[[1, -2, 0], [0, 0, 3]]], dtype=np.int16)
        result = stats(d)
        self.assertEqual(result["pixels"], 2)
        self.assertEqual(result["mae"], 1.0)
        self.assertEqual(result["max_channel_delta"], 3)
        self.assertEqual(stats(d, np.zeros((1, 2), dtype=bool))["pixels"], 0)

    def test_grain_variants_have_identical_geometry_and_colour(self):
        grain = to_json(parse_ncel(build_scene(0.008)), 0, "fixture.ncel")
        flat = to_json(parse_ncel(build_scene(0)), 0, "fixture.ncel")
        self.assertEqual(grain["layers"], flat["layers"])
        self.assertEqual(grain["paper"]["rgb"], flat["paper"]["rgb"])
        self.assertEqual((grain["width"], grain["height"]), (1920, 1080))
        self.assertEqual(sum(len(r) for p in flat["layers"] for r in p["rings"]), 2427)


if __name__ == "__main__":
    unittest.main()
