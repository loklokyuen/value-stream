# Value Stream Zero-Cost Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Value Stream GCP dashboard and scraper with Streamlit Community Cloud and a scheduled GitHub Actions workflow at zero monthly hosting cost.

**Architecture:** Streamlit Community Cloud deploys `streamlit-app/app.py` from `main`; GitHub Actions runs `scraper/main.py` daily and on demand. Both workloads use Neon through `DATABASE_URL`. GCP remains live until both replacements pass end-to-end checks.

**Tech Stack:** Python 3.11, Streamlit Community Cloud, GitHub Actions, Neon PostgreSQL, GitHub CLI, GCP CLI

---

### Task 1: Specify the scheduled scraper workflow

**Files:**
- Create: `tests/test_daily_scraper_workflow.py`
- Test: `tests/test_daily_scraper_workflow.py`

- [ ] **Step 1: Write the failing workflow contract test**

```python
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
```

- [ ] **Step 2: Run the test and confirm the workflow is missing**

Run: `python3 -m unittest -v tests/test_daily_scraper_workflow.py`

Expected: error because `.github/workflows/daily-scraper.yml` does not exist.

### Task 2: Add the scheduled scraper workflow

**Files:**
- Create: `.github/workflows/daily-scraper.yml`
- Test: `tests/test_daily_scraper_workflow.py`

- [ ] **Step 1: Add the workflow**

```yaml
name: Daily Amazon bestseller scraper

on:
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:

concurrency:
  group: daily-amazon-bestseller-scraper
  cancel-in-progress: false

jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      DATABASE_URL: ${{ secrets.DATABASE_URL }}
      SCRAPER_API_KEY: ${{ secrets.SCRAPER_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
          cache-dependency-path: scraper/requirements.txt
      - run: python -m pip install -r scraper/requirements.txt
      - run: python scraper/main.py
```

- [ ] **Step 2: Run the workflow contract and database tests**

Run: `python3 -m unittest -v tests/test_daily_scraper_workflow.py tests/test_database_connections.py`

Expected: six tests pass.

- [ ] **Step 3: Check syntax and whitespace**

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 4: Commit the workflow**

```bash
git add .github/workflows/daily-scraper.yml tests/test_daily_scraper_workflow.py
git commit -m "ci: run bestseller scraper daily"
```

### Task 3: Publish and test the scraper

**Files:**
- No repository file changes.

- [ ] **Step 1: Push the branch**

Run: `git push -u origin codex/neon-db-cutover`

Expected: GitHub accepts the branch.

- [ ] **Step 2: Copy the existing runtime values into GitHub Actions secrets without printing them**

Set repository secrets `DATABASE_URL` and `SCRAPER_API_KEY` from the current Cloud Run job and Secret Manager. Do not print either value.

- [ ] **Step 3: Confirm secret names**

Run: `gh secret list --repo loklokyuen/value-stream`

Expected: `DATABASE_URL` and `SCRAPER_API_KEY` appear by name.

- [ ] **Step 4: Trigger the workflow on the migration branch**

Run: `gh workflow run daily-scraper.yml --repo loklokyuen/value-stream --ref codex/neon-db-cutover`

Expected: GitHub creates a workflow run.

- [ ] **Step 5: Wait for success**

Run: `gh run watch --repo loklokyuen/value-stream <run-id> --exit-status`

Expected: the workflow completes successfully.

- [ ] **Step 6: Verify Neon received a fresh write**

Run in Neon SQL Editor:

```sql
SELECT COUNT(*) AS total_rows, MAX(scraped_at) AS latest_scrape
FROM amazon_bestsellers;
```

Expected: `latest_scrape` is later than the previous GCP test write.

### Task 4: Merge the production source

**Files:**
- No new repository file changes.

- [ ] **Step 1: Create a pull request**

Create a pull request from `codex/neon-db-cutover` to `main` describing Neon support, Streamlit source, tests, and the daily workflow.

- [ ] **Step 2: Verify the pull request diff and checks**

Confirm no secret values or unrelated user files appear. Confirm tests and the manual scraper workflow pass.

- [ ] **Step 3: Merge the pull request**

Merge with a merge commit or squash through GitHub. Do not alter the user's dirty local checkout.

- [ ] **Step 4: Confirm the schedule exists on `main`**

Run: `gh workflow view daily-scraper.yml --repo loklokyuen/value-stream --ref main`

Expected: GitHub displays the workflow from `main`.

### Task 5: Deploy Streamlit Community Cloud

**Files:**
- No repository file changes.

- [ ] **Step 1: Create the app**

In Streamlit Community Cloud, choose repository `loklokyuen/value-stream`, branch `main`, entry point `streamlit-app/app.py`, and Python 3.11.

- [ ] **Step 2: Add root-level secrets**

Add `DATABASE_URL`, `SHOPIFY_API_TOKEN`, and `OPENROUTER_API_KEY` using the existing Cloud Run values. Do not print or store them in Git.

- [ ] **Step 3: Wait for deployment**

Expected: Community Cloud reports the app running and provides a `streamlit.app` URL.

- [ ] **Step 4: Test the public app**

Verify the root page, `/Trends`, product count, Shopify-backed actions, and absence of database errors.

### Task 6: Remove Value Stream from GCP

**Files:**
- Download: `outputs/value-stream-gcp/beauty_products/*.csv`

- [ ] **Step 1: Disable the GCP scheduler**

Pause `scraper-daily` and confirm the GitHub workflow is enabled on `main`.

- [ ] **Step 2: Check for active executions**

Confirm no Cloud Run scraper execution is running.

- [ ] **Step 3: Delete the GCP workloads**

Delete scheduler job `scraper-daily`, Cloud Run job `scraper`, and Cloud Run service `value-stream` in `europe-west2`.

- [ ] **Step 4: Preserve the two product CSV files**

Download `gs://beauty_products` into `outputs/value-stream-gcp/beauty_products/` and verify both files are nonempty.

- [ ] **Step 5: Remove obsolete artifacts**

Delete the `beauty_products` bucket, source/build buckets, and Artifact Registry repositories after confirming no live workload uses them.

- [ ] **Step 6: Verify the project is empty**

Confirm no Cloud Run services, jobs, functions, schedulers, Cloud SQL instances, application buckets, or Artifact Registry repositories remain.

- [ ] **Step 7: Detach billing**

Disable billing for `value-stream-493409` and verify billing is disabled.

### Task 7: Final verification

**Files:**
- No repository file changes.

- [ ] **Step 1: Run the complete local test suite**

Run: `python3 -m unittest -v tests/test_daily_scraper_workflow.py tests/test_database_connections.py`

Expected: six tests pass.

- [ ] **Step 2: Verify production endpoints**

Confirm the Streamlit Community Cloud URL returns successfully and both pages show Neon data.

- [ ] **Step 3: Verify the scheduled workflow**

Confirm the workflow is active on `main` and the latest manual run succeeded.

- [ ] **Step 4: Verify rollback files**

Run `gzip -t` and `shasum -a 256` against `outputs/value-stream-postgres-2026-08-12.sql.gz`.

Expected: gzip passes and the checksum remains `b9ed6b835d9184a78abb93aa09423379773f9d9f91b4eaf50d810461a9aabb72`.
