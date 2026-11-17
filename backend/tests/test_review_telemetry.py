from datetime import datetime, timezone, timedelta
import unittest
from app.core.platform_registry import resolve_resource_url
from app.services.scheduler import calculate_decayed_retention, calculate_mastery_delta

class TestReviewTelemetryAndFormatting(unittest.TestCase):
    def test_platform_registry_null_safety(self):
        """Verify resolve_resource_url safely handles None platform and query without throwing AttributeError."""
        # Video with None platform
        url_video = resolve_resource_url("video", None, "TCP Handshake")
        self.assertIn("youtube.com", url_video)
        self.assertIn("TCP+Handshake", url_video)

        # Docs with None platform and None query
        url_docs = resolve_resource_url("docs", None, None)
        self.assertIn("google.com", url_docs)

        # Standard known platform
        url_wiki = resolve_resource_url("article", "wikipedia", "Dijkstra algorithm")
        self.assertIn("wikipedia.org/wiki/Dijkstra_algorithm", url_wiki)

    def test_srs_last_reviewed_at_retention_recovery(self):
        """Verify that updating last_reviewed_at resets retention decay properly."""
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(days=20)
        
        # Stale last_reviewed_at causes decay
        decayed = calculate_decayed_retention(old_time, interval_days=5, current_mastery=90.0)
        self.assertLess(decayed, 70.0)

        # Fresh review resets retention decay
        refreshed = calculate_decayed_retention(now, interval_days=5, current_mastery=90.0)
        self.assertEqual(refreshed, 90.0)

    def test_mastery_delta_calculations(self):
        """Verify mastery deltas for all rating scale values."""
        self.assertEqual(calculate_mastery_delta(5), 15.0)
        self.assertEqual(calculate_mastery_delta(4), 10.0)
        self.assertEqual(calculate_mastery_delta(3), 5.0)
        self.assertEqual(calculate_mastery_delta(2), -10.0)
        self.assertEqual(calculate_mastery_delta(1), -15.0)

if __name__ == "__main__":
    unittest.main()
