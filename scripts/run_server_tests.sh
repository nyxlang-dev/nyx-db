#!/bin/bash
# run_server_tests.sh — corre el test Python del modo servidor (RESP2,
# incl. reinicio de persistencia). El test gestiona su propio daemon.
set -uo pipefail
STACK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$STACK"
[ -x "$STACK/nyx-db" ] || { echo "error: nyx-db not built (make build)"; exit 1; }
NYX_DB_BIN="$STACK/nyx-db" python3 tests/test_nyx_db.py
