"""
pipeline/checkpointer.py
================================================================================
Persistent LangGraph checkpointer for TaxSathi (Supabase PostgreSQL).

WHAT IT GIVES YOU
-----------------
  * Chat sessions survive a server restart (same session_id -> history reloads).
  * A paused ITR run (PAN-mismatch / CBDT-error interrupt) can be resumed later
    with the same thread_id, even after a restart.

HOW graph.py USES IT
--------------------
    from pipeline.checkpointer import get_checkpointer
    return g.compile(checkpointer=get_checkpointer())

BEHAVIOUR
---------
  * DATABASE_URL not set  -> falls back to in-memory MemorySaver and logs a
    WARNING (nothing persists). Fine for local smoke tests.
  * DATABASE_URL set      -> PostgresSaver on a connection pool. If the database
    cannot be reached this RAISES. It never silently falls back, because that
    would make you believe sessions are being saved when they are not.

SUPABASE CONNECTION STRING
--------------------------
Dashboard -> "Connect" -> copy the URI, then:
  * Use the "Session pooler" string (works over IPv4, full session semantics).
    The "Direct connection" host is IPv6-only unless you buy the IPv4 add-on.
  * Avoid the "Transaction pooler" (port 6543) for the one-off setup step:
    the table migrations are not guaranteed to run through it.
  * URL-encode special characters in the password (@ -> %40, / -> %2F, ...).

REQUIRED PACKAGES
-----------------
    langgraph-checkpoint-postgres, psycopg[binary], psycopg-pool
(psycopg v3 - NOT psycopg2.)

ONE-TIME TABLE CREATION
-----------------------
    python -c "from pipeline.checkpointer import setup_checkpointer; setup_checkpointer()"
================================================================================
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

log = logging.getLogger(__name__)

_lock = threading.Lock()
_pool: Any = None    # psycopg_pool.ConnectionPool when Postgres is in use
_saver: Any = None   # PostgresSaver or MemorySaver singleton


def _database_url() -> Optional[str]:
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None


def get_checkpointer():
    """
    Return the process-wide checkpointer, creating it on first use.

    Thread-safe. Safe to call from build_graph() at import time, but note that
    DATABASE_URL must already be in the environment when `pipeline` is imported.
    """
    global _pool, _saver

    with _lock:
        if _saver is not None:
            return _saver

        url = _database_url()
        if url is None:
            from langgraph.checkpoint.memory import MemorySaver

            log.warning(
                "DATABASE_URL is not set - using in-memory MemorySaver. "
                "Sessions and paused ITR runs are lost on restart."
            )
            _saver = MemorySaver()
            return _saver

        # Imported lazily so the package still imports without psycopg when
        # running purely in-memory.
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=int(os.getenv("DB_POOL_MAX", "5")),
            # PostgresSaver requirements for caller-supplied connections:
            #   autocommit=True      - it manages its own transactions
            #   row_factory=dict_row - it reads rows by column name
            #   prepare_threshold=0  - no server-side prepared statements, which
            #                          break behind pgbouncer-style poolers
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            open=True,
        )
        try:
            pool.wait(timeout=20)  # fail fast with a clear error if unreachable
        except Exception:
            pool.close()
            raise

        _pool = pool
        _saver = PostgresSaver(pool)
        log.info("Using PostgresSaver (persistent checkpoints).")
        return _saver


def is_persistent() -> bool:
    """True when checkpoints are going to PostgreSQL rather than memory."""
    return _pool is not None


def setup_checkpointer() -> None:
    """
    Create the LangGraph tables (checkpoints, checkpoint_blobs,
    checkpoint_writes, checkpoint_migrations) in the database.

    Run once per database. Safe to run again - migrations are idempotent.
    """
    if _database_url() is None:
        raise EnvironmentError(
            "DATABASE_URL is not set - nothing to set up. "
            "Set it to your Supabase connection string first."
        )
    get_checkpointer().setup()
    print("LangGraph checkpoint tables are ready.")


def close_checkpointer() -> None:
    """Close the connection pool. Call from the server's shutdown hook."""
    global _pool, _saver
    with _lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _saver = None
