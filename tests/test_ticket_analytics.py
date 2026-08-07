import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


class TicketAnalyticsTests(unittest.TestCase):
    def test_average_rating_and_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "tickets.db"
            with patch("database.db.DB_PATH", db_path):
                from database.db import create_ticket, init_db, update_ticket
                from utils.analytics import average_rating, average_resolution_seconds

                init_db()
                create_ticket(1, 10, 20, "support")
                now = int(time.time())
                update_ticket(10, status="closed", closed_at=now + 120, rating=5)

                self.assertEqual(average_rating(1), 5.0)
                self.assertGreaterEqual(average_resolution_seconds(1), 0)


if __name__ == "__main__":
    unittest.main()
