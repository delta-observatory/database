#!/bin/sh
# Apply migrations/*.sql in name order. Each file runs once, in its own
# transaction, under an advisory lock. A changed file that already ran stops
# the run, because released migrations are immutable.
# Requires DATABASE_URL and psql.
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"
DIR="${MIGRATIONS_DIR:-$(dirname "$0")/migrations}"
LOCK=7462103

psql_q() { psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -X -q -tA "$@"; }

psql_q -c "SET client_min_messages = warning; CREATE TABLE IF NOT EXISTS schema_migration (
    version    text PRIMARY KEY,
    sha256     text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now())"

for file in "$DIR"/[0-9]*.sql; do
    version=$(basename "$file" .sql)
    digest=$(sha256sum "$file" | cut -d' ' -f1)
    recorded=$(psql_q -c "SELECT sha256 FROM schema_migration WHERE version = '$version'")
    if [ -n "$recorded" ]; then
        if [ "$recorded" != "$digest" ]; then
            echo "error: $version changed after it was applied ($recorded != $digest)" >&2
            exit 1
        fi
        echo "skip  $version"
        continue
    fi
    {
        echo "BEGIN;"
        echo "DO \$\$ BEGIN PERFORM pg_advisory_xact_lock($LOCK); IF EXISTS (SELECT 1 FROM schema_migration WHERE version = '$version') THEN RAISE EXCEPTION 'concurrent apply of $version'; END IF; END \$\$;"
        cat "$file"
        echo "INSERT INTO schema_migration (version, sha256) VALUES ('$version', '$digest');"
        echo "COMMIT;"
    } | psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -X -q
    echo "apply $version"
done
