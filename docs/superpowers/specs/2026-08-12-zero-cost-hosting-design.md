# Value Stream Zero-Cost Hosting Design

## Goal

Move the Value Stream dashboard and daily scraper out of GCP without adding a monthly hosting charge. Preserve Neon as the production database and accept short wake-up delays after inactivity.

## Current State

- Cloud Run serves the Streamlit dashboard from `streamlit-app/app.py`.
- A Cloud Run job runs `scraper/main.py` each day at 06:00 UTC.
- Cloud Scheduler triggers that job.
- Both workloads use the imported Neon branch through `DATABASE_URL`.
- The former Cloud SQL instance and image-similarity homework are deleted.
- The current GCP deployment remains the rollback target until the replacement passes verification.

## Target Architecture

Streamlit Community Cloud will deploy the dashboard from the public `loklokyuen/value-stream` repository. The app entry point will remain `streamlit-app/app.py`, and its dependency file will remain beside it at `streamlit-app/requirements.txt`.

GitHub Actions will run the scraper on the existing `0 6 * * *` UTC schedule and on manual dispatch. The workflow will install `scraper/requirements.txt` and run `python scraper/main.py` from the repository root.

Neon will remain the single production database. The dashboard will read and write through `DATABASE_URL`; the scraper will write through the same connection.

## Configuration

The Community Cloud app will receive these root-level secrets, which Streamlit exposes as environment variables:

- `DATABASE_URL`
- `SHOPIFY_API_TOKEN`
- `OPENROUTER_API_KEY`

The GitHub Actions repository will receive:

- `DATABASE_URL`
- `SCRAPER_API_KEY`

The migration will not rotate credentials because the user excluded rotation from this work. No secret value will enter Git history, workflow logs, or documentation.

## Source Control

The existing `codex/neon-db-cutover` branch contains the deployed Neon support, tests, dashboard source, and scraper source. The migration will add the scheduled workflow and deployment documentation to that branch, push it to GitHub, and deploy Community Cloud from the same branch. A pull request will preserve a reviewable path to `main` without altering the user's dirty local checkout.

## Cutover and Rollback

The replacement will be deployed before GCP changes. Verification will cover dashboard startup, the Overview and Trends pages, a Neon-backed product count, and a manually triggered scraper run that creates a fresh Neon timestamp.

After those checks pass, the migration will disable the GCP schedule, wait for any active scraper execution to finish, and then delete the Cloud Run job, scheduler job, and dashboard service. If the replacement fails before deletion, traffic remains on GCP. If it fails after deletion, the tagged container images can recreate the Cloud Run workloads until GCP artifacts are removed at the final cleanup gate.

## GCP Cleanup

After the replacement remains healthy:

1. Delete obsolete Artifact Registry images and repositories.
2. Download any unique application data from `beauty_products`, then delete that bucket if its CSV files are redundant.
3. Delete Cloud Build and Cloud Run source buckets when no live workload needs them.
4. Verify the project has no Cloud Run services, jobs, functions, scheduler jobs, Cloud SQL instances, or application buckets.
5. Detach the billing account from the empty project.

## Success Criteria

- The Community Cloud dashboard loads both pages and reads Neon data.
- The scheduled workflow has a successful manual run and retains the 06:00 UTC schedule.
- Neon records the test scraper write.
- The migration branch is pushed and reviewable.
- The Value Stream GCP project has no billable application workloads or retained application data.
- The local PostgreSQL rollback archive remains unchanged.

## Out of Scope

- Credential rotation.
- Changes to dashboard features or appearance.
- Changes to the scraper's extraction logic or schedule.
- Changes to the Neon schema.
