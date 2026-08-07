import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class StaffDatabaseTests(unittest.TestCase):
    def test_staff_profile_xp_and_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "tickets.db"
            with patch("database.db.DB_PATH", db_path):
                from database.db import init_db
                from database.staff import add_staff_xp, create_staff, get_staff, update_staff_stat

                init_db()
                create_staff(123)
                add_staff_xp(123, 150)
                update_staff_stat(123, "tickets_claimed")
                profile = get_staff(123)

                self.assertEqual(profile["xp"], 150)
                self.assertEqual(profile["level"], 1)
                self.assertEqual(profile["rank"], "Helper")
                self.assertEqual(profile["tickets_claimed"], 1)


if __name__ == "__main__":
    unittest.main()
