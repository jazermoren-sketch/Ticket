import unittest

from utils.ranks import calculate_level, detect_promotion, rank_for_xp


class RankTests(unittest.TestCase):
    def test_rank_thresholds(self):
        self.assertEqual(rank_for_xp(0)["name"], "Trainee")
        self.assertEqual(rank_for_xp(100)["name"], "Helper")
        self.assertEqual(rank_for_xp(1500)["name"], "Manager")
        self.assertEqual(calculate_level(250), 2)
        self.assertEqual(detect_promotion(90, 100)["new_rank"]["name"], "Helper")


if __name__ == "__main__":
    unittest.main()
