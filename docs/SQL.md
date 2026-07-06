# nyx-db — SQL Reference

All SQL is sent as plain text via RESP. Multi-word statements are joined into a single string by the RESP protocol layer.

---

## CREATE TABLE

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT,
    score REAL
)
```

Column types: `INTEGER`, `TEXT`, `REAL`, `BLOB`. Only one `PRIMARY KEY` per table.

---

## DROP TABLE

```sql
DROP TABLE users
→ +OK
```

Deletes the table and all its data. Error if table doesn't exist.

---

## CREATE INDEX

```sql
-- HASH (default): O(1) exact-match lookups, no range scans
CREATE INDEX idx_users_email ON users (email)
CREATE INDEX idx_users_email ON users (email) USING HASH
→ +OK

-- BTREE: real B-tree (order t=3) — supports exact match + range queries
CREATE INDEX idx_users_score ON users (score) USING BTREE
→ +OK
```

HASH indexes accelerate `WHERE col = val`. BTREE indexes also accelerate
`>`, `<`, `>=`, `<=`, and `BETWEEN` via index range scans. The query
planner hoists the most selective indexed predicate automatically; a
pair of range predicates on the same BTREE column (e.g.
`age > 10 AND age < 20`) is fused into a single range lookup.

---

## INSERT

```sql
INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')
→ +OK

-- Multiple rows
INSERT INTO users (id, name) VALUES (2, 'Bob'), (3, 'Carol')
→ +OK
```

String values must be quoted with single quotes.

---

## SELECT

### Basic

```sql
SELECT * FROM users
SELECT id, name FROM users
SELECT name FROM users WHERE id = 1
```

### WHERE

```sql
-- Comparison operators: =, !=, <, >, <=, >=
SELECT * FROM users WHERE score > 9.5

-- LIKE (% wildcard)
SELECT * FROM users WHERE name LIKE 'A%'

-- IS NULL / IS NOT NULL
SELECT * FROM users WHERE email IS NULL

-- AND / OR
SELECT * FROM users WHERE score > 5 AND name LIKE 'A%'
```

### ORDER BY

```sql
SELECT * FROM users ORDER BY score DESC
SELECT * FROM users ORDER BY name ASC
```

### LIMIT / OFFSET

```sql
SELECT * FROM users LIMIT 10
SELECT * FROM users LIMIT 10 OFFSET 20
```

### JOIN

```sql
SELECT users.name, orders.total
FROM users
JOIN orders ON users.id = orders.user_id
WHERE orders.total > 100
```

Basic inner join on equality condition. `LEFT JOIN` is also supported
(rows from the left table without a match produce NULL columns on the
right).

### GROUP BY + aggregates

```sql
SELECT name, COUNT(*), SUM(score), AVG(score), MIN(score), MAX(score)
FROM scores
GROUP BY name
```

Aggregates supported: `COUNT(*)`, `SUM(col)`, `AVG(col)`, `MIN(col)`,
`MAX(col)`. `AVG` returns a float; others return the same type as the
underlying column.

### HAVING

Filters groups after aggregation. The predicate may reference any
aggregate or the grouped column:

```sql
-- Students with more than one exam
SELECT name, COUNT(*) FROM scores
GROUP BY name HAVING COUNT(*) > 1

-- Students whose average exceeds 85
SELECT name, AVG(score) FROM scores
GROUP BY name HAVING AVG(score) >= 85

-- Combined WHERE + HAVING
SELECT name, COUNT(*) FROM scores
WHERE subject = 'math'
GROUP BY name HAVING COUNT(*) > 0
```

### DISTINCT

```sql
SELECT DISTINCT name FROM scores
```

---

## UPDATE

```sql
UPDATE users SET score = 10.0 WHERE id = 1
→ +OK

UPDATE users SET name = 'Alicia', email = 'alicia@example.com' WHERE id = 1
→ +OK
```

---

## DELETE

```sql
DELETE FROM users WHERE id = 1
→ +OK

DELETE FROM users WHERE score < 1.0
→ +OK
```

---

## Transactions

```sql
BEGIN
→ +OK

INSERT INTO users (id, name) VALUES (5, 'Eve')
UPDATE accounts SET balance = balance - 100 WHERE user_id = 5

COMMIT
→ +OK

-- Or rollback
ROLLBACK
→ +OK
```

Within a transaction, all statements execute against a snapshot. On COMMIT, changes are applied atomically. On ROLLBACK, all changes are discarded.

---

## Meta Commands

### TABLES

```
TABLES
→ 1) "users"
   2) "orders"
   3) "products"
```

### SCHEMA

```
SCHEMA users
→ "id INTEGER PK, name TEXT, email TEXT, score REAL"
```

### INFO

```
INFO
→ "# nyx-db v0.1.0\r\ntables:3\r\ntotal_rows:1500\r\n"
```

---

## Limitations

- No `ALTER TABLE` (redesign the table, migrate data manually).
- No subqueries, CTEs, or window functions.
- `JOIN` supports `INNER JOIN` and `LEFT JOIN` only (no RIGHT/FULL OUTER).
- String comparisons are case-sensitive.
- `LIKE` supports only `%` wildcard (not `_`).
- BTREE deletes leave tombstones; a future VACUUM will compact them.
- No foreign key constraints.
- No auto-increment — manage IDs in the application.
- Transactions (`BEGIN`/`COMMIT`/`ROLLBACK`) are stubs — no rollback.
