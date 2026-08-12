# Neon Database Cutover Design

## Goal

Move the Value Stream dashboard and scraper from Cloud SQL to the imported Neon PostgreSQL 18 database while keeping Cloud Run unchanged.

## Connection design

Both workloads will accept a `DATABASE_URL`. When it exists, they will connect through that URL with TLS. When it is absent, they will retain the current Cloud SQL Unix-socket path. This fallback supports an immediate rollback without another code deployment.

The implementation will pass the URL directly to `psycopg2`. It will not split or log the credential. The Streamlit SQLAlchemy engine will continue to call the shared connection function.

## Deployment sequence

1. Add automated tests for Neon URL selection and Cloud SQL fallback.
2. Update the Streamlit app and scraper connection modules.
3. Build and deploy new Cloud Run revisions with `DATABASE_URL` set to the imported Neon branch's direct connection string.
4. Verify the dashboard's database-backed views and run the scraper once.
5. Keep Cloud SQL available during verification. Stop it only after both workloads pass, and retain it briefly for rollback before deletion.

## Failure handling

A failed Neon connection will fail visibly instead of silently reading from Cloud SQL. Rollback consists of routing traffic to the prior Cloud Run revision or removing `DATABASE_URL`, which restores the existing socket connection.

## Acceptance criteria

- Tests prove both connection paths.
- The dashboard loads data from Neon.
- A scraper execution succeeds and writes to Neon.
- Cloud SQL receives no further application traffic before it is stopped.
