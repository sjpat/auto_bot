import unittest
from unittest.mock import Mock
from src.trading.correlation_manager import CorrelationManager


class TestCorrelationManager(unittest.TestCase):
    def setUp(self):
        self.config = Mock()
        self.config.MAX_EVENT_EXPOSURE_USD = 200.0
        self.position_manager = Mock()
        self.manager = CorrelationManager(self.config, self.position_manager)

    def test_get_event_group(self):
        """Test heuristic for grouping markets."""
        self.assertEqual(self.manager.get_event_group("FED-DEC-RATE"), "FED")
        self.assertEqual(self.manager.get_event_group("KX-INFL-DEC"), "KX-INFL")
        self.assertEqual(self.manager.get_event_group("NBA-LAKERS-WARRIORS"), "NBA")
        self.assertEqual(self.manager.get_event_group("SIMPLE"), "SIMPLE")

    def test_check_exposure_pass(self):
        """Test that trade passes when no exposure exists."""
        self.position_manager.get_active_positions.return_value = []

        passed, reason = self.manager.check_exposure("FED-RATE", 100.0)
        self.assertTrue(passed)
        self.assertEqual(reason, "OK")

    def test_check_exposure_fail(self):
        """Test that trade fails when exposure limit is exceeded."""
        # Existing position taking up $150 in FED group
        pos1 = Mock()
        pos1.market_id = "FED-DEC"
        pos1.entry_cost = 150.0

        self.position_manager.get_active_positions.return_value = [pos1]

        # Try to add $60 to FED group (Total $210 > $200 Limit)
        passed, reason = self.manager.check_exposure("FED-NOV", 60.0)
        self.assertFalse(passed)
        self.assertIn("Correlation limit hit", reason)

    def test_check_exposure_different_groups(self):
        """Test that exposure in one group doesn't affect another."""
        # Existing position in NBA ($150)
        pos1 = Mock()
        pos1.market_id = "NBA-GAME"
        pos1.entry_cost = 150.0

        self.position_manager.get_active_positions.return_value = [pos1]

        # Try to add $100 to FED (Should pass, different group)
        passed, reason = self.manager.check_exposure("FED-RATE", 100.0)
        self.assertTrue(passed)


if __name__ == "__main__":
    unittest.main()
