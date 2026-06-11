# nyx-db

Embedded SQL database library written in Nyx. v0.5.0 adds a
write-ahead log (WAL) for crash recovery and a `VACUUM` command that
compacts B-tree tombstones. Previously shipped: recursive-descent SQL
parser, flat-map storage with hash and real B-tree secondary indexes
(`USING HASH|BTREE`), JOIN, GROUP BY, aggregates, `HAVING`, binary
`.ndb` snapshots, and transactions (BEGIN/COMMIT/ROLLBACK as stubs).
Queries go through a selectivity-aware planner that reorders AND
conjuncts and hoists indexed equality or range predicates to index
lookups. Accessible as a RESP2 server or imported directly into any
Nyx project as a library.

Motor de base de datos SQL embebido escrito en Nyx. v0.5.0 agrega
write-ahead log (WAL) con crash recovery y un comando `VACUUM` que
compacta tombstones de índices B-tree. Heredado: parser SQL recursivo
descendente, almacenamiento por mapas planos con índices secundarios
hash y B-tree real (`USING HASH|BTREE`), JOIN, GROUP BY, agregados,
`HAVING` y persistencia `.ndb`. Incluye un query planner que reordena
AND por selectividad y hoistea predicados indexados (`=`, rangos,
`BETWEEN`). Disponible como servidor RESP2 o como librería PM
embebida.

---

## Install

Install the Nyx toolchain:

```bash
curl -sSf https://nyxlang.com/install.sh | sh
```

## Quick start

```bash
git clone https://github.com/nyxlang-dev/nyx-db
cd nyx-db
nyx build
./nyx-db [flags]
```

## Usage

### Server mode (RESP2 over TCP)

```bash
make build       # compiles examples/standalone.nx
./nyx-db         # listens on :6382

redis-cli -p 6382
> CREATE TABLE users (id INT PRIMARY KEY, name TEXT, age INT)
OK
> INSERT INTO users VALUES (1, 'Alice', 30)
OK
> INSERT INTO users VALUES (2, 'Bob', 25)
OK
> SELECT * FROM users WHERE age > 25
1) "id"    "name"    "age"
2) "1"     "Alice"   "30"
> SELECT COUNT(*) FROM users
(integer) 2
```

### Embedded mode (library import)

```toml
# nyx.toml
[dependencies]
nyx-db = "*"
```

```nyx
import "std/resp"
import "nyx-db/src/sql_lexer"
import "nyx-db/src/sql_parser"
import "nyx-db/src/store"
import "nyx-db/src/executor"
import "nyx-db/src/query"

fn main() {
    db_query("CREATE TABLE users (id INT PRIMARY KEY, name TEXT, age INT)")
    db_query("INSERT INTO users VALUES (1, 'Alice', 30)")

    let rows: Array = db_query_rows("SELECT * FROM users")
    // rows = [["id", "name", "age"], ["1", "Alice", "30"]]
}
```

### API

| Function | Returns | Description |
|----------|---------|-------------|
| `db_query(sql)` | `["OK", count]` / `["ROWS", [[header], ...]]` / `["ERROR", msg]` | Execute any SQL statement |
| `db_query_rows(sql)` | `[[header], [row1], ...]` or `[]` | Execute SELECT, return rows directly |

## SQL support

**DDL**: `CREATE TABLE`, `DROP TABLE`, `CREATE INDEX`

**DML**: `INSERT` (multi-row), `SELECT`, `UPDATE`, `DELETE`

**SELECT**: `DISTINCT`, `JOIN` / `LEFT JOIN`, `WHERE` (`=`, `!=`, `<`, `>`, `<=`, `>=`, `LIKE`, `IS NULL`, `IS NOT NULL`, `IN`, `BETWEEN`, `AND`, `OR`, `NOT`), `GROUP BY`, `ORDER BY [ASC|DESC]`, `LIMIT` / `OFFSET`

**Aggregates**: `COUNT(*)`, `SUM`, `AVG` (float), `MIN`, `MAX`

**Transactions**: `BEGIN`, `COMMIT`, `ROLLBACK` — accepted, not enforced yet

**Meta**: `PING`, `INFO`, `TABLES`, `SCHEMA <table>`, `QUIT`

## Configuration

| Flag | Default | Description |
|------|---------|-------------|
| `--port N` | `6382` | TCP port to listen on |
| `--data FILE` | `nyx.ndb` | Path for binary persistence snapshots |
| `--rate-limit N` | `1000` | Max requests per second per IP |
| `--no-rate-limit` | — | Disable rate limiting entirely |

```bash
./nyx-db --port 6392 --data mydata.ndb --rate-limit 2000
./nyx-db --no-rate-limit   # for development / testing
```

## Documentation

See [docs/](./docs/) for full reference:

- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — storage engine, index format, concurrency model
- [docs/SQL.md](./docs/SQL.md) — complete SQL syntax reference

## Limitations

- Transactions are stubs — `BEGIN`/`COMMIT`/`ROLLBACK` return `OK` but no rollback mechanism is implemented
- No complex JOINs beyond `INNER JOIN` and `LEFT JOIN` (no `RIGHT JOIN`, subqueries, or CTEs)
- No secondary index enforcement on `UPDATE`/`DELETE` (index may become stale)
- Default rate limit of 1 000 req/s interferes with bulk-insert tests — use `--no-rate-limit` for large workloads
- Persistence on restart is unreliable in some configurations (known pre-existing issue)
- No `ALTER TABLE`, window functions, subqueries, or CTEs
- BTREE delete uses tombstones without merge/rotation; heavy-delete
  workloads leave empty slots until a future VACUUM compacts them

## License

Apache 2.0 — see [LICENSE](../../LICENSE)
