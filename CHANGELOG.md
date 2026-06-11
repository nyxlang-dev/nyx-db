# nyx-db — Changelog

All notable changes to `nyx-db` (the library and its reference daemon).
Follows [Semantic Versioning](https://semver.org/). Dates are ISO-8601.

---

## [0.5.0] — 2026-04-23 · "Durability"

### Added
- **WAL (Write-Ahead Log)** — new `src/wal.nx` (~400 LOC). Every
  mutator (`INSERT`/`UPDATE`/`DELETE`/`CREATE TABLE`/`DROP TABLE`/
  `CREATE INDEX`) appends a binary record to `<data>.wal` before the
  in-memory change is applied. On restart the replay path rebuilds
  state from snapshot + WAL.
  - Format: `NYXW` header + per-record `MAGIC/LSN/TYPE/LEN/PAYLOAD/CRC32`.
  - CRC-verified; torn-write detection truncates cleanly at the first
    corrupt record.
  - Checkpoint on `db_save` emits a `CHECKPOINT` marker and truncates
    the WAL to just the header.
  - Flags: `--wal <path>` (default `<data>.wal`), `--no-wal` to disable.
- **`VACUUM` command** — compacts tombstones accumulated by deletes in
  BTREE secondary indices. Rebuilds the affected tree(s) and releases
  the old nodes. `VACUUM` with no argument scans every index; `VACUUM
  <table>` restricts to a single table. Reports the number of
  tombstones removed.
- **`HAVING` clause** (carried forward from the v0.4.x timeline) —
  post-`GROUP BY` predicate filtering, accepting aggregate expressions
  (`COUNT(*)`, `SUM(col)`, `AVG(col)`, `MIN(col)`, `MAX(col)`) and
  grouped columns.

### Changed
- Default behaviour of the reference daemon now activates the WAL at
  startup. Earlier snapshots remain loadable; the WAL is born empty
  on first run and grows with mutations.
- `persist.nx` binary encoders (`push_i32_le` / `push_i64_le` /
  `push_string_bin` etc.) are now `pub` so the WAL module can share them.

### Deferred / explicitly out of scope
- Aggregates in the raw `WHERE` clause — not standard SQL
  (PostgreSQL / Oracle prohibit it: `WHERE` runs pre-group, so
  aggregates have no defined value there). Use `HAVING` for post-group
  filtering.

### Known limitations (unchanged from v0.4)
- BTREE range scan still walks the full tree (O(n)); descent-optimised
  iterator planned for v0.6.
- BTREE delete leaves tombstones until `VACUUM` runs; no automatic
  compaction.
- Transactions (`BEGIN`/`COMMIT`/`ROLLBACK`) remain stubs — MVCC is a
  v0.8 target.
- Cost-based planner (statistics, histograms, join reorder) is a v0.7
  target.

### Tests
- New `tests/products/test_db_vacuum.nx` (13 cases).
- New `tests/products/test_db_wal.nx` (11 cases covering append,
  replay, torn-write, checkpoint, BTREE backfill via WAL).
- Regression: 7 product-level suites (`test_db_embedded`,
  `test_db_planner`, `test_db_btree`, `test_db_having`,
  `test_db_vacuum`, `test_db_wal`, `test_btree`) all green.

---

## [0.4.0] — 2026-04-23 · "BTREE secondary indices"

### Added
- Real B-tree (order `t=3`) in `src/btree.nx` with Cormen-style
  preemptive split, range scans, tombstone deletes.
- `CREATE INDEX ... USING HASH|BTREE` syntax (default HASH for
  back-compat).
- Planner hoists range predicates (`>`, `<`, `>=`, `<=`, `BETWEEN`) and
  fuses two range predicates on the same BTREE-indexed column into a
  single `RANGE` hoist.
- Snapshot v2 serialises index `kind` alongside each definition.

## [0.3.0] — 2026-04-23 · "Query planner"

### Added
- `src/planner.nx`: predicate reorder, static selectivity scoring,
  stable sort, indexed-equality hoist.
- `NYX_DB_EXPLAIN=1` debug output.

## [0.2.0] — 2026-03

Prior history tracked in the top-level `CHANGELOG.md`. v0.2 shipped
the library refactor, SQL parser, RESP2 server, flat-Map storage,
HASH indices, GROUP BY + aggregates, snapshot persistence with CRC32.
