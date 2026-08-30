-- Bootstraps the local Sokoni development database on an existing PostgreSQL server.
-- Run once as a superuser (usually "postgres"):
--   psql -U postgres -h localhost -p 5432 -f scripts/create_local_db.sql
-- Credentials here must match POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB in .env.

DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sokoni') THEN
        CREATE ROLE sokoni WITH LOGIN PASSWORD 'sokoni' CREATEDB;
    END IF;
END
$$;

SELECT 'CREATE DATABASE sokoni OWNER sokoni'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sokoni')
\gexec

GRANT ALL PRIVILEGES ON DATABASE sokoni TO sokoni;
