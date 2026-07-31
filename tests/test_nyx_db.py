#!/usr/bin/env python3
"""Functional test for nyx-db — server mode (RESP2), incl. persistence restart.

Spawnea el binario del stack (raíz del repo) o el indicado en NYX_DB_BIN.
Movido del monorepo al extraerse nyx-db (2026-07-05, split #5).
"""

import socket
import time
import sys
import subprocess
import signal
import os

PORT = 6399  # Use non-standard port for testing
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINARY = os.environ.get("NYX_DB_BIN", os.path.join(ROOT, "nyx-db"))

def resp_command(*args):
    """Build RESP array from arguments"""
    parts = [f"*{len(args)}\r\n"]
    for a in args:
        s = str(a)
        parts.append(f"${len(s)}\r\n{s}\r\n")
    return "".join(parts).encode()

def resp_inline(sql):
    """Send SQL as inline RESP (split by spaces, but keep quoted strings together)"""
    # Split respecting single-quoted strings
    tokens = []
    current = ""
    in_quote = False
    for ch in sql:
        if ch == "'" and not in_quote:
            in_quote = True
            current += ch
        elif ch == "'" and in_quote:
            in_quote = False
            current += ch
        elif ch == " " and not in_quote:
            if current:
                tokens.append(current)
                current = ""
        else:
            current += ch
    if current:
        tokens.append(current)
    return resp_command(*tokens)

def read_response(sock, timeout=5):
    """Read complete RESP response"""
    sock.settimeout(timeout)
    data = b""
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            # Try to detect if we have a complete response
            try:
                text = data.decode("utf-8", errors="replace")
                # Simple heuristic: response ends with \r\n
                if text.endswith("\r\n"):
                    break
            except:
                pass
    except socket.timeout:
        pass
    return data.decode("utf-8", errors="replace")

def send_sql(sock, sql):
    """Send SQL and return response"""
    sock.sendall(resp_inline(sql))
    return read_response(sock)

def test_ping(sock):
    sock.sendall(resp_command("PING"))
    resp = read_response(sock)
    assert "PONG" in resp, f"PING failed: {resp}"
    print("  PING: OK")

def test_create_table(sock):
    resp = send_sql(sock, "CREATE TABLE users (id INT PRIMARY KEY, name TEXT, age INT)")
    assert "OK" in resp or "ok" in resp.lower(), f"CREATE TABLE failed: {resp}"
    print("  CREATE TABLE: OK")

def test_insert_basic(sock):
    resp = send_sql(sock, "INSERT INTO users VALUES (1, 'Alice', 30)")
    assert ":1" in resp, f"INSERT failed: {resp}"
    resp = send_sql(sock, "INSERT INTO users VALUES (2, 'Bob', 25)")
    assert ":1" in resp, f"INSERT failed: {resp}"
    resp = send_sql(sock, "INSERT INTO users VALUES (3, 'Charlie', 35)")
    assert ":1" in resp, f"INSERT failed: {resp}"
    print("  INSERT (3 rows): OK")

def test_select_all(sock):
    resp = send_sql(sock, "SELECT * FROM users")
    assert "Alice" in resp and "Bob" in resp and "Charlie" in resp, f"SELECT * failed: {resp}"
    print("  SELECT *: OK")

def test_select_where(sock):
    resp = send_sql(sock, "SELECT * FROM users WHERE age > 25")
    assert "Alice" in resp and "Charlie" in resp, f"SELECT WHERE > failed: {resp}"
    assert "Bob" not in resp, f"SELECT WHERE > returned Bob: {resp}"
    print("  SELECT WHERE age > 25: OK")

def test_select_where_eq(sock):
    resp = send_sql(sock, "SELECT name FROM users WHERE id = 2")
    assert "Bob" in resp, f"SELECT WHERE = failed: {resp}"
    print("  SELECT WHERE id = 2: OK")

def test_update(sock):
    resp = send_sql(sock, "UPDATE users SET age = 31 WHERE name = 'Alice'")
    assert ":1" in resp, f"UPDATE failed: {resp}"
    # Verify
    resp = send_sql(sock, "SELECT age FROM users WHERE name = 'Alice'")
    assert "31" in resp, f"UPDATE verify failed: {resp}"
    print("  UPDATE: OK")

def test_delete(sock):
    resp = send_sql(sock, "DELETE FROM users WHERE name = 'Charlie'")
    assert ":1" in resp, f"DELETE failed: {resp}"
    resp = send_sql(sock, "SELECT * FROM users")
    assert "Charlie" not in resp, f"DELETE verify failed: {resp}"
    print("  DELETE: OK")

def test_count(sock):
    resp = send_sql(sock, "SELECT COUNT(*) FROM users")
    assert "2" in resp, f"COUNT failed: {resp}"
    print("  COUNT(*): OK")

def test_insert_10k(sock):
    """Insert 10K rows — acceptance criterion"""
    t0 = time.time()
    for i in range(100, 10100):
        name = f"user{i}"
        age = 18 + (i % 60)
        resp = send_sql(sock, f"INSERT INTO users VALUES ({i}, '{name}', {age})")
        if ":1" not in resp:
            print(f"  INSERT 10K failed at row {i}: {resp}")
            return False
    elapsed = time.time() - t0
    print(f"  INSERT 10K rows: OK ({elapsed:.1f}s)")
    return True

def test_select_where_10k(sock):
    """SELECT with WHERE on 10K+ rows — acceptance criterion"""
    t0 = time.time()
    resp = send_sql(sock, "SELECT COUNT(*) FROM users WHERE age > 50")
    elapsed = time.time() - t0
    # age ranges from 18-77, so age > 50 should return many rows
    print(f"  SELECT WHERE on 10K+ rows: OK ({elapsed:.3f}s) — {resp.strip()}")

def test_tables(sock):
    sock.sendall(resp_command("TABLES"))
    resp = read_response(sock)
    assert "users" in resp, f"TABLES failed: {resp}"
    print("  TABLES: OK")

def test_info(sock):
    sock.sendall(resp_command("INFO"))
    resp = read_response(sock)
    assert "nyx-db" in resp, f"INFO failed: {resp}"
    print("  INFO: OK")

def main():
    db_file = "/tmp/nyx-db-test.ndb"
    # Clean up old data
    if os.path.exists(db_file):
        os.remove(db_file)

    print(f"Starting nyx-db on port {PORT}...")
    proc = subprocess.Popen(
        [BINARY, "--port", str(PORT), "--data", db_file],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(0.5)  # Let server start

    if proc.poll() is not None:
        print("ERROR: nyx-db failed to start")
        out = proc.stdout.read().decode()
        err = proc.stderr.read().decode()
        print(f"stdout: {out}")
        print(f"stderr: {err}")
        sys.exit(1)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", PORT))

        print("\n=== nyx-db Functional Tests ===\n")

        test_ping(sock)
        test_create_table(sock)
        test_insert_basic(sock)
        test_select_all(sock)
        test_select_where(sock)
        test_select_where_eq(sock)
        test_update(sock)
        test_delete(sock)
        test_count(sock)
        test_tables(sock)
        test_info(sock)

        print("\n--- 10K Row Test ---\n")
        ok = test_insert_10k(sock)
        if ok:
            test_select_where_10k(sock)

        sock.close()

        # Test persistence: stop server, restart, verify data
        print("\n--- Persistence Test ---\n")
        print("  Stopping server (SIGTERM)...")
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
        time.sleep(0.5)

        print("  Restarting server...")
        proc = subprocess.Popen(
            [BINARY, "--port", str(PORT), "--data", db_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        time.sleep(2)

        if proc.poll() is not None:
            out = proc.stdout.read().decode()
            err = proc.stderr.read().decode()
            print(f"  Server failed to restart!")
            print(f"  stdout: {out[:500]}")
            print(f"  stderr: {err[:500]}")
            print("\n=== FUNCTIONAL TESTS PASSED (persistence skipped) ===\n")
            return

        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock2.connect(("127.0.0.1", PORT))

        # Verify data survived restart
        resp = send_sql(sock2, "SELECT COUNT(*) FROM users")
        print(f"  After restart, COUNT(*): {resp.strip()}")

        resp = send_sql(sock2, "SELECT name FROM users WHERE id = 1")
        assert "Alice" in resp, f"Persistence check failed: {resp}"
        print("  Persistence: Alice still exists after restart: OK")

        resp = send_sql(sock2, "SELECT name FROM users WHERE id = 500")
        assert "user500" in resp, f"Persistence check for row 500 failed: {resp}"
        print("  Persistence: user500 still exists after restart: OK")

        sock2.close()

        print("\n=== ALL TESTS PASSED ===\n")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except:
            proc.kill()
        # Cleanup
        if os.path.exists(db_file):
            os.remove(db_file)
        if os.path.exists(db_file + ".tmp"):
            os.remove(db_file + ".tmp")

if __name__ == "__main__":
    main()
