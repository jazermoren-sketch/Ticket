import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class StaffXPMultiplierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "tickets.db"
        self.patch_db = patch("database.db.DB_PATH", self.db_path)
        self.patch_db.start()
        self.addCleanup(self.patch_db.stop)

        from database.db import init_db

        init_db()

    def test_base_xp_with_default_multiplier(self):
        from database.staff import add_staff_xp, get_staff

        add_staff_xp(1001, 10, guild_id=1)
        self.assertEqual(get_staff(1001)["xp"], 10)

    def test_multiplier_two(self):
        from database.db import set_staff_xp_multiplier
        from database.staff import add_staff_xp, get_staff

        set_staff_xp_multiplier(1, 2)
        add_staff_xp(1002, 10, guild_id=1)
        self.assertEqual(get_staff(1002)["xp"], 20)

    def test_multiplier_three(self):
        from database.db import set_staff_xp_multiplier
        from database.staff import add_staff_xp, get_staff

        set_staff_xp_multiplier(1, 3)
        add_staff_xp(1003, 10, guild_id=1)
        self.assertEqual(get_staff(1003)["xp"], 30)

    def test_zero_resets_to_normal(self):
        from database.db import get_staff_xp_multiplier, set_staff_xp_multiplier
        from database.staff import add_staff_xp, get_staff

        set_staff_xp_multiplier(1, 3)
        set_staff_xp_multiplier(1, 0)
        add_staff_xp(1004, 10, guild_id=1)
        self.assertEqual(get_staff_xp_multiplier(1), 1)
        self.assertEqual(get_staff(1004)["xp"], 10)

    def test_negative_multiplier_rejected(self):
        from database.db import set_staff_xp_multiplier

        with self.assertRaises(ValueError):
            set_staff_xp_multiplier(1, -1)

    def test_multiplier_above_ten_rejected(self):
        from database.db import set_staff_xp_multiplier

        with self.assertRaises(ValueError):
            set_staff_xp_multiplier(1, 11)

    def test_multiplier_persists_after_restart(self):
        from database.db import get_staff_xp_multiplier, init_db, set_staff_xp_multiplier

        set_staff_xp_multiplier(1, 5)
        init_db()
        self.assertEqual(get_staff_xp_multiplier(1), 5)

    def test_staff_points_multiplier_applied_once(self):
        from database.db import add_staff_points, get_staff_points, set_staff_xp_multiplier

        set_staff_xp_multiplier(1, 2)
        add_staff_points(1, 1005, 10, source="ticket")
        self.assertEqual(get_staff_points(1, 1005)["points"], 20)


if __name__ == "__main__":
    unittest.main()
