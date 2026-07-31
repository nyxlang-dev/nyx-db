# Makefile — nyx-db-stack
# El toolchain Nyx vive fuera de este repo; se apunta vía NYX_HOME.

NYX_HOME ?= /home/admin/nyx/lang
export NYX_HOME

.PHONY: build test-db test-units test-server clean

build:
	nyx build

# Suite completa: 7 unit tests .nx + test Python del server
test-db: test-units test-server

test-units:
	bash scripts/run_unit_tests.sh

test-server: build
	bash scripts/run_server_tests.sh

clean:
	rm -f nyx-db script.nx script.ll nyx.lock *.ndb *.wal
