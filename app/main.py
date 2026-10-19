from pathlib import Path
from dotenv import load_dotenv

# Load .env FIRST — before any app.* import reads os.getenv()
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import razorpay
import uuid
from datetime import datetime, timezone
from app.ledger import Ledger, load_private_key
from app.db import get_conn, init_db
from app.rules import evaluate

client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET"),
))

LEDGER_PATH = Path(__file__).parent.parent / "data" / "ledger.jsonl"
KEY_PATH = Path(__file__).parent.parent / "keys" / "ledger.key"
ledger = Ledger(LEDGER_PATH, load_private_key(KEY_PATH))

app = FastAPI(title="Arbiter Guard", version="0.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()
ARBITER_MODE = os.getenv("ARBITER_MODE", "enforce")


@app.get("/")
def checkout_page():
    return FileResponse(Path(__file__).parent.parent / "checkout.html")


class RefundRequest(BaseModel):
    payment_id: str
    amount: int
    idempotency_key: str
    agent_id: str
    task_id: str
    payee: str | None = None


class RefundResponse(BaseModel):
    decision: str
    reason: str | None
    refund_id: str | None
    arbiter_ref: str


@app.get("/health")
def health():
    return {"status": "ok"}


class OrderRequest(BaseModel):
    amount: int = 50000


@app.post("/v1/create_order")
def create_order(req: OrderRequest):
    order = client.order.create({
        "amount": req.amount,
        "currency": "INR",
        "receipt": f"arbiter_pay_{uuid.uuid4().hex[:8]}"
    })
    return {"order_id": order["id"], "amount": order["amount"]}


@app.post("/v1/refunds", response_model=RefundResponse)
def refund(req: RefundRequest):
    arbiter_ref = f"ks_{uuid.uuid4().hex[:12]}"
    payee = req.payee or req.payment_id
    now = datetime.now(timezone.utc).isoformat()

    conn = get_conn()
    verdict = evaluate(req, conn)

    ledger.append({
        "action": "refund_proposed",
        "arbiter_ref": arbiter_ref,
        "agent_id": req.agent_id,
        "task_id": req.task_id,
        "payment_id": req.payment_id,
        "payee": payee,
        "amount": req.amount,
        "idempotency_key": req.idempotency_key,
        "verdict": verdict.decision,
        "rule": verdict.rule,
        "reason": verdict.reason,
        "mode": ARBITER_MODE,
    })

    should_execute = verdict.decision == "allow" or (
        verdict.decision == "block" and ARBITER_MODE == "shadow"
    )

    def record(decision, rule, reason, executed):
        conn.execute(
            "INSERT INTO actions (arbiter_ref, agent_id, task_id, payment_id, payee, amount, "
            "idempotency_key, decision, rule, reason, executed, mode, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (arbiter_ref, req.agent_id, req.task_id, req.payment_id, payee, req.amount,
             req.idempotency_key, decision, rule, reason, executed, ARBITER_MODE, now),
        )
        conn.commit()

    if not should_execute:
        record(verdict.decision, verdict.rule, verdict.reason, 0)
        ledger.append({
            "action": "refund_result", "arbiter_ref": arbiter_ref,
            "status": verdict.decision, "rule": verdict.rule,
        })
        raise HTTPException(
            status_code=202 if verdict.decision == "escalate" else 403,
            detail={
                "arbiter_ref": arbiter_ref,
                "decision": verdict.decision,
                "rule": verdict.rule,
                "reason": verdict.reason,
            },
        )

    try:
        r = client.payment.refund(req.payment_id, {"amount": req.amount})
    except razorpay.errors.BadRequestError as e:
        record("error", None, str(e), 0)
        ledger.append({"action": "refund_result", "arbiter_ref": arbiter_ref,
                       "status": "error", "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

    record(verdict.decision, verdict.rule, verdict.reason, 1)
    ledger.append({
        "action": "refund_result", "arbiter_ref": arbiter_ref,
        "status": "success", "refund_id": r["id"],
        "shadow_blocked": verdict.decision == "block",
    })

    return RefundResponse(
        decision=verdict.decision,
        reason=verdict.reason,
        refund_id=r["id"],
        arbiter_ref=arbiter_ref,
    )
