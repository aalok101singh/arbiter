import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env FIRST — before reading any env vars below
load_dotenv(Path(__file__).parent.parent / ".env")

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

VELOCITY_LIMIT = int(os.getenv("ARBITER_VELOCITY_LIMIT", "10"))
PAYEE_CAP = int(os.getenv("ARBITER_PAYEE_CAP", "500000"))                      # ₹5,000
NEW_PAYEE_THRESHOLD = int(os.getenv("ARBITER_NEW_PAYEE_THRESHOLD", "100000"))  # ₹1,000


@dataclass
class Verdict:
    decision: str   # "allow" | "block" | "escalate"
    rule: str | None
    reason: str | None


def evaluate(req, conn) -> Verdict:
    now = datetime.now(timezone.utc)

    # Rule 1 — idempotency
    row = conn.execute(
        "SELECT id FROM actions WHERE agent_id=? AND idempotency_key=? LIMIT 1",
        (req.agent_id, req.idempotency_key),
    ).fetchone()
    if row:
        return Verdict("block", "idempotency",
                       f"idempotency_key '{req.idempotency_key}' already used by {req.agent_id}")

    # Rule 2 — refund-loop
    row = conn.execute(
        "SELECT id FROM actions WHERE agent_id=? AND payment_id=? AND decision='allow' LIMIT 1",
        (req.agent_id, req.payment_id),
    ).fetchone()
    if row:
        return Verdict("block", "refund_loop",
                       f"payment {req.payment_id} already refunded by {req.agent_id}")

    # Rule 3 — velocity cap
    cutoff_1h = (now - timedelta(hours=1)).isoformat()
    count = conn.execute(
        "SELECT COUNT(*) FROM actions WHERE agent_id=? AND decision='allow' AND created_at>?",
        (req.agent_id, cutoff_1h),
    ).fetchone()[0]
    if count >= VELOCITY_LIMIT:
        return Verdict("block", "velocity_cap",
                       f"{count} refunds in last hour (limit {VELOCITY_LIMIT})")

    # Rule 4 — payee cap + new-payee escalation
    payee = req.payee or req.payment_id
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount),0), COUNT(*) FROM actions "
        "WHERE payee=? AND decision='allow' AND created_at>?",
        (payee, cutoff_24h),
    ).fetchone()
    prior_sum, prior_count = row[0], row[1]

    if prior_sum + req.amount > PAYEE_CAP:
        return Verdict("block", "payee_cap",
                       f"₹{(prior_sum + req.amount)/100:.2f} would exceed ₹{PAYEE_CAP/100:.2f} cap for {payee}")

    if prior_count == 0 and req.amount > NEW_PAYEE_THRESHOLD:
        return Verdict("escalate", "new_payee",
                       f"first refund to {payee} at ₹{req.amount/100:.2f}")

    return Verdict("allow", None, None)
