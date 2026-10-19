import sys
from pathlib import Path
import pytest
import sqlite3
from dataclasses import dataclass

# Adjust path so we can import from app
sys.path.append(str(Path(__file__).parent.parent))
from app.rules import evaluate, Verdict

@dataclass
class MockReq:
    payment_id: str = "pay_123"
    amount: int = 10000
    idempotency_key: str = "idem_1"
    agent_id: str = "agent_1"
    task_id: str = "task_1"
    payee: str = "merchant_1"

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE actions (
            id INTEGER PRIMARY KEY,
            keystone_ref TEXT, agent_id TEXT, task_id TEXT, payment_id TEXT,
            payee TEXT, amount INTEGER, idempotency_key TEXT,
            decision TEXT, rule TEXT, reason TEXT, executed INTEGER, mode TEXT, created_at TEXT
        )
    """)
    return conn

def test_idempotency(db):
    # Insert a prior attempt
    db.execute("INSERT INTO actions (agent_id, idempotency_key) VALUES ('agent_1', 'idem_1')")
    
    req = MockReq()
    result = evaluate(req, db)
    assert result.decision == "block"
    assert result.rule == "idempotency"

def test_refund_loop(db):
    # Insert a prior allowed refund
    db.execute("INSERT INTO actions (agent_id, payment_id, decision) VALUES ('agent_1', 'pay_123', 'allow')")
    
    req = MockReq(idempotency_key="idem_2")
    result = evaluate(req, db)
    assert result.decision == "block"
    assert result.rule == "refund_loop"

def test_allow_clean_action(db):
    req = MockReq()
    result = evaluate(req, db)
    assert result.decision == "allow"
    assert result.rule is None