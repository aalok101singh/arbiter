import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "arbiter.db"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                arbiter_ref TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                payment_id TEXT NOT NULL,
                payee TEXT NOT NULL,
                amount INTEGER NOT NULL,
                idempotency_key TEXT NOT NULL,
                decision TEXT NOT NULL,
                rule TEXT,
                reason TEXT,
                executed INTEGER NOT NULL,
                mode TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_idem ON actions(agent_id, idempotency_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payment ON actions(agent_id, payment_id, decision)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_time ON actions(agent_id, created_at, decision)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payee_time ON actions(payee, created_at, decision)")
        conn.commit()
