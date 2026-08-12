# Neon Database Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the Value Stream dashboard and scraper to Neon through `DATABASE_URL` while preserving Cloud SQL as a rollback path.

**Architecture:** Each workload will prefer a Neon URL and pass it directly to `psycopg2` with TLS required. Without that variable, each workload will keep its current Cloud SQL Unix-socket connection. Tests will replace database libraries with fakes and inspect connection arguments without contacting either database.

**Tech Stack:** Python 3.11, psycopg2, SQLAlchemy, Streamlit, unittest, Google Cloud Run, Neon PostgreSQL 18

---

### Task 1: Test connection selection

**Files:**
- Create: `tests/test_database_connections.py`
- Test: `streamlit-app/db.py`
- Test: `scraper/db.py`

- [ ] **Step 1: Write tests that load each module with fake database libraries**

Create a `unittest` suite that sets `DATABASE_URL`, calls each `get_conn()`, and asserts that `psycopg2.connect` receives the URL plus `sslmode="require"`. Add fallback cases that omit the URL and assert the existing `/cloudsql/<connection-name>` host, database, user, and password arguments.

- [ ] **Step 2: Run the tests and verify the Neon cases fail**

Run: `python3 -m unittest -v tests/test_database_connections.py`

Expected: the Neon cases fail because both modules still select the Cloud SQL socket.

### Task 2: Implement Neon URL support

**Files:**
- Modify: `streamlit-app/db.py`
- Modify: `scraper/db.py`

- [ ] **Step 1: Prefer `DATABASE_URL` in the Streamlit connection function**

Add this branch before the Cloud Run socket branch:

```python
database_url = os.getenv("DATABASE_URL")
if database_url:
    return psycopg2.connect(database_url, sslmode="require")
```

- [ ] **Step 2: Prefer `DATABASE_URL` in the scraper connection function**

Add the same branch before its existing socket connection.

- [ ] **Step 3: Run the focused tests**

Run: `python3 -m unittest -v tests/test_database_connections.py`

Expected: four tests pass.

- [ ] **Step 4: Run syntax and diff checks**

Run: `python3 -m compileall -q streamlit-app scraper tests && git diff --check`

Expected: both commands exit successfully with no output.

### Task 3: Deploy and verify the Streamlit service

**Files:**
- Deploy source: `streamlit-app/`

- [ ] **Step 1: Copy the imported Neon branch's direct connection string**

Use Neon Console's **Connect** dialog for branch `import-2026-08-12T14:01:42.714Z`, database `neondb`, and connection pooling disabled. Store it only in the deployment environment; never print it.

- [ ] **Step 2: Deploy a new `value-stream` Cloud Run revision**

Build from `streamlit-app/`, retain the current non-database environment variables, add `DATABASE_URL`, and retain the Cloud SQL attachment for rollback.

- [ ] **Step 3: Verify the dashboard**

Open the service URL and confirm the home page plus the database-backed Trends view load without connection errors. Confirm the new revision is ready before continuing.

### Task 4: Deploy and verify the scraper

**Files:**
- Deploy source: `scraper/`

- [ ] **Step 1: Deploy a new `scraper` Cloud Run job revision**

Build from `scraper/`, retain its API variables, add the same `DATABASE_URL`, and retain the Cloud SQL attachment for rollback.

- [ ] **Step 2: Execute the job once**

Expected: the execution completes successfully.

- [ ] **Step 3: Verify the Neon write**

Run this read-only query in Neon SQL Editor:

```sql
SELECT COUNT(*) AS rows,
       MAX(scraped_at) AS latest_scrape
FROM amazon_bestsellers;
```

Expected: `rows` is greater than zero and `latest_scrape` reflects the test execution.

### Task 5: Complete the cost cutover

- [ ] **Step 1: Confirm both Cloud Run workloads remain healthy**

Check the service revision and scraper execution logs for database errors.

- [ ] **Step 2: Stop the Cloud SQL instance**

Stop rather than delete `value-stream`. Keep the prior Cloud Run revisions and connection variables intact for rollback.

- [ ] **Step 3: Recheck the dashboard after Cloud SQL stops**

Expected: the dashboard and scraper still use Neon successfully.

- [ ] **Step 4: Record final verification**

Document the deployed revisions, Neon branch, verification results, and rollback procedure in the task handoff.
