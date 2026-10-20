-- Local development database setup. Run with:
-- psql -d postgres -f scripts/setup_database.sql
-- (Add -U postgres or -h localhost -U postgres if your installation requires it.)

-- Windows installers create the postgres role during setup, while macOS
-- Homebrew and some Linux installations may not. Create it only when absent.
SELECT 'CREATE ROLE postgres WITH LOGIN PASSWORD ''postgres'''
WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'postgres'
)
\gexec

-- Leave an existing database in place so rerunning this script never deletes
-- data. The API creates the members and books tables on its first startup.
SELECT 'CREATE DATABASE library_management OWNER postgres'
WHERE NOT EXISTS (
  SELECT 1 FROM pg_database WHERE datname = 'library_management'
)
\gexec
