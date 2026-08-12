from pathlib import Path
import unittest


class DailyScraperWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = Path(".github/workflows/daily-scraper.yml")

    def test_runs_daily_and_manually(self):
        text = self.workflow.read_text()
        self.assertIn("cron: '0 6 * * *'", text)
        self.assertIn("workflow_dispatch:", text)

    def test_runs_scraper_with_required_secrets(self):
        text = self.workflow.read_text()
        self.assertIn("python scraper/main.py", text)
        self.assertIn("DATABASE_URL: ${{ secrets.DATABASE_URL }}", text)
        self.assertIn("SCRAPER_API_KEY: ${{ secrets.SCRAPER_API_KEY }}", text)
        self.assertIn("timeout-minutes: 10", text)


if __name__ == "__main__":
    unittest.main()
