# nyx-db — Architecture

## Overview

nyx-db is a single-binary, in-memory SQL database. It speaks RESP and has a custom SQL engine written entirely in Nyx.

```
Client (redis-cli / any RESP client)
    │  TCP :6382
    ▼
main.nx  ──  one goroutine per connection
    │
    ▼
commands.nx  ──  join RESP tokens into SQL string
    │
    ▼
sql_lexer.nx  ──  tokenize SQL string
    │
    ▼
sql_parser.nx  ──  recursive descent → AST
    │
    ▼
executor.nx  ──  evaluate AST against store
    │
    ├── planner.nx     (reorder AND by selectivity, hoist indexed)
    ├── store.nx       (tables, indexes, row storage, WHERE eval)
    ├── btree.nx       (real B-tree for BTREE-kind indexes)
    ├── persist.nx     (save/load .ndb snapshots)
    └── limits.nx      (rate limiting)
```

## SQL Engine

### Lexer (`sql_lexer.nx`)

Tokenizes the SQL string into a flat array of `[type, value]` pairs:
- `KW` — SQL keywords (`SELECT`, `FROM`, `WHERE`, ...)
- `ID` — identifiers (table names, column names)
- `STR` — single-quoted string literals
- `NUM` — numeric literals
- `OP` — operators (`=`, `!=`, `<`, `>`, `*`, `,`, `(`, `)`)

### Parser (`sql_parser.nx`)

Recursive descent parser. Produces typed AST nodes:

| Node | Shape |
|------|-------|
| `CREATE_TABLE` | `[name, [[col, type, is_pk], ...]]` |
| `CREATE_INDEX` | `[idx_name, table, col, kind]` (kind = `"HASH"` or `"BTREE"`) |
| `INSERT` | `[table, [cols], [[vals], ...]]` |
| `SELECT` | `[cols, table, where_ast, order_ast, limit, offset, join_ast, group_col, is_distinct, having_ast]` |
| `UPDATE` | `[table, [[col, val], ...], where_ast]` |
| `DELETE` | `[table, where_ast]` |
| `BEGIN` / `COMMIT` / `ROLLBACK` | `[]` |

WHERE AST uses prefix notation: `["AND", left, right]`, `["=", col, val]`, `["LIKE", col, pattern]`, etc. HAVING reuses the WHERE grammar; the executor builds a virtual schema for the synthesized group row so aggregates (`COUNT(*)`, `SUM(col)`, ...) are valid operands.

### Planner (`planner.nx`)

Between the parser and `db_select`/`db_update`/`db_delete`, the planner rewrites the WHERE tree:

1. Flattens left-heavy AND chains (OR/NOT stay opaque).
2. Scores each conjunct statically — indexed `=` → 1, BETWEEN on BTREE → 3, range on BTREE → 5, regular `=` → 10, IN → 5×len, LIKE prefix → 40, open range → 50, LIKE `%x%` → 85, OR/NOT → 95.
3. Stable-sorts ascending and hoists the most selective indexed predicate (`=` for HASH, `=`/range/BETWEEN for BTREE; two same-column ranges fuse into a single `RANGE`). The hoist becomes an `index_lookup` or `index_range_lookup` call; the residual AND tree feeds `eval_where` per row.

### Executor (`executor.nx`)

Walks the AST and performs operations against `store.nx`.

- **SELECT**: scans rows (or uses index if available), evaluates WHERE predicate, applies ORDER BY and LIMIT/OFFSET.
- **INSERT**: appends rows to `g_tables[table]`, updates indexes.
- **UPDATE**: scans rows, applies SET to matching rows.
- **DELETE**: removes matching rows, updates indexes.
- **Transactions**: on BEGIN, a snapshot of affected tables is taken. COMMIT atomically replaces the live tables; ROLLBACK discards the snapshot.

## Storage

### `store.nx`

- `g_tables: Map` — presence set of table names (`name → 1`)
- `g_schema: Map` — `table → "col:TYPE,col:TYPE:PK,..."`
- `g_rows: Map` — flat `"table::rowid" → "v1\x1Fv2\x1F..."` (US as column separator). Flat keys avoid nested Maps.
- `g_row_ids: Map` — `table → "id1,id2,id3,..."` (ordered CSV for iteration)
- `g_index_def: Map` — `"table::col" → 1` (presence of an index)
- `g_index_kind: Map` — `"table::col" → "HASH"|"BTREE"`
- `g_index_data: Map` — `"idx::table::col::value" → "rowid_csv"` (HASH only)
- `g_index_btree_id: Map` — `"table::col" → tree_id_string` (BTREE only; tree itself lives in `btree.nx`'s `g_bti_*` maps)

### `btree.nx`

Real B-tree of order t=3 (nodes hold 2..5 keys, 1..5 for root). Nodes are serialised as strings with leading-separator encoding so empty/tombstoned slots round-trip. Insert uses Cormen-style preemptive split; delete tombstones (no merge — a future VACUUM compacts).

### Why in-memory?

All data fits in RAM for the use cases nyx-db targets: configuration, user sessions, small structured datasets. The `.ndb` snapshots provide durability across restarts.

## Persistence

On SAVE or SIGTERM, `persist.nx` serialises all tables, schemas, and row data into a binary `.ndb` file (same format as nyx-kv). On startup, `nyx.db` is loaded automatically if it exists.

## Concurrency

One goroutine per connection, protected by a global store mutex. Transactions use a per-connection snapshot during BEGIN/COMMIT, released on COMMIT or ROLLBACK.
