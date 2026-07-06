# nyx-db — Embedded SQL Database

nyx-db is an in-memory SQL database with a custom query engine, RESP protocol interface, and binary persistence. It provides a subset of SQL for structured data storage without external dependencies.

- **Port**: 6382 (default)
- **Protocol**: RESP2 — connect with `redis-cli -p 6382` or any Redis client
- **SQL engine**: custom recursive descent parser + executor (no SQLite dependency)
- **Persistence**: `.ndb` binary snapshots
- **Rate limiting**: 1000 req/s per IP (configurable)

---

## Quick Start

```bash
# Start server
./nyx-db

# Connect
redis-cli -p 6382

# Create a table
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)
→ +OK

# Insert
INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')
→ +OK

# Query
SELECT * FROM users WHERE id = 1
→ 1) "1"
   2) "Alice"
   3) "alice@example.com"
```

---

## SQL Dialect

nyx-db supports a subset of SQL. All statements are sent as plain text over RESP.

See [SQL.md](SQL.md) for the full SQL reference.

**Supported statements:**
- `CREATE TABLE` / `DROP TABLE`
- `CREATE INDEX ... [USING HASH|BTREE]` (default HASH)
- `INSERT INTO` (single or multi-row)
- `SELECT` (WHERE, ORDER BY, LIMIT/OFFSET, INNER JOIN, LEFT JOIN,
  GROUP BY + aggregates, HAVING, DISTINCT)
- `UPDATE` / `DELETE`
- `BEGIN` / `COMMIT` / `ROLLBACK` (stubs — no rollback)

**Meta commands:**
- `TABLES` — list all tables
- `SCHEMA <table>` — show column definitions
- `INFO` — server statistics
- `PING` / `QUIT`

---

## Response Format

SQL results are returned as RESP bulk arrays. Each row is a flat sequence of column values:

```
SELECT id, name FROM users
→ 1) "1"        ← id (row 1)
   2) "Alice"   ← name (row 1)
   3) "2"        ← id (row 2)
   4) "Bob"     ← name (row 2)
```

`NULL` values are returned as `(nil)` in RESP.

---

## Data Types

| SQL Type | Storage | Notes |
|----------|---------|-------|
| `INTEGER` | int64 | Stored as string internally |
| `TEXT` | String | UTF-8 |
| `REAL` | float64 | Stored as string |
| `BLOB` | String | Binary-safe |

All types are stored as strings in the in-memory Map structure and compared by value.

---

## CLI Flags

```bash
./nyx-db                          # default port 6382
./nyx-db --rate-limit 2000        # custom rate limit
./nyx-db --no-rate-limit          # disable rate limiting
```

---

## systemd

```bash
sudo cp deploy/nyx-db.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nyx-db
```

→ See [SQL.md](SQL.md) for query syntax and examples.
→ See [ARCHITECTURE.md](ARCHITECTURE.md) for internals.
