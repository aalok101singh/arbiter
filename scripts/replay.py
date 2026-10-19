"""
Runs five attack scenarios against the Arbiter proxy using payment IDs
from data/payments.json. Writes data/replay_results.json for report.py.

DEMO LIMITS (set these in .env before running):
    ARBITER_VELOCITY_LIMIT=2
    ARBITER_PAYEE_CAP=200000          # ₹2000
    ARBITER_NEW_PAYEE_THRESHOLD=50000 # ₹500
"""
import json
import sys
import uuid
from pathlib import Path
import requests

BASE = "http://127.0.0.1:8000"
PAYMENTS_FILE = Path(__file__).parent.parent / "data" / "payments.json"
RESULTS_FILE = Path(__file__).parent.parent / "data" / "replay_results.json"


def call_refund(payment_id, amount, agent_id, idem_key, payee=None, task_id=None):
    body = {
        "payment_id": payment_id,
        "amount": amount,
        "idempotency_key": idem_key,
        "agent_id": agent_id,
        "task_id": task_id or f"t_{uuid.uuid4().hex[:6]}",
    }
    if payee:
        body["payee"] = payee
    r = requests.post(f"{BASE}/v1/refunds", json=body, timeout=30)
    try:
        resp = r.json()
    except Exception:
        resp = {"raw": r.text}
    detail = resp.get("detail") if isinstance(resp.get("detail"), dict) else resp
    return r.status_code, detail.get("decision"), detail.get("rule")


def run(name, fn, *args):
    print(f"  - {name}")
    attempts = fn(*args)
    return {
        "attack": name,
        "attempted": len(attempts),
        "attempts": attempts,
        "allowed": sum(1 for a in attempts if a["decision"] == "allow"),
        "blocked": sum(1 for a in attempts if a["decision"] == "block"),
        "escalated": sum(1 for a in attempts if a["decision"] == "escalate"),
    }


def sc_refund_loop(payment_id):
    agent = f"loop-{uuid.uuid4().hex[:6]}"
    out = []
    for i in range(5):
        code, dec, rule = call_refund(payment_id, 10000, agent, f"loop-{i}")
        out.append({"i": i, "http": code, "decision": dec, "rule": rule})
    return out


def sc_duplicate(payment_id):
    agent = f"dup-{uuid.uuid4().hex[:6]}"
    key = f"dup-key-{uuid.uuid4().hex[:6]}"
    out = []
    for i in range(2):
        code, dec, rule = call_refund(payment_id, 10000, agent, key)
        out.append({"i": i, "http": code, "decision": dec, "rule": rule})
    return out


def sc_velocity(payments):
    agent = f"vel-{uuid.uuid4().hex[:6]}"
    out = []
    for i, pid in enumerate(payments[:3]):
        code, dec, rule = call_refund(pid, 10000, agent, f"vel-{i}")
        out.append({"i": i, "http": code, "decision": dec, "rule": rule})
    return out


def sc_new_payee(payment_id):
    agent = f"np-{uuid.uuid4().hex[:6]}"
    payee = f"merchant-{uuid.uuid4().hex[:8]}"
    code, dec, rule = call_refund(payment_id, 100000, agent,
                                  f"np-{uuid.uuid4().hex[:6]}", payee=payee)
    return [{"i": 0, "http": code, "decision": dec, "rule": rule}]


def sc_cap_bypass(payment_id):
    payee = f"capmerchant-{uuid.uuid4().hex[:6]}"
    # warm up the payee so the new-payee rule doesn't fire
    warm_agent = f"warm-{uuid.uuid4().hex[:6]}"
    call_refund(payment_id, 10000, warm_agent,
                f"warm-{uuid.uuid4().hex[:6]}", payee=payee)
    # 3 attempts of ₹800 each → 3rd breaches ₹2000 cap
    out = []
    for i in range(3):
        agent = f"cap-{uuid.uuid4().hex[:6]}"
        code, dec, rule = call_refund(payment_id, 80000, agent,
                                      f"cap-{i}", payee=payee)
        out.append({"i": i, "http": code, "decision": dec, "rule": rule})
    return out


def main() -> int:
    if not PAYMENTS_FILE.exists():
        print(f"Missing {PAYMENTS_FILE}. Run: python scripts/seed_payments.py 7")
        return 1
    pays = json.loads(PAYMENTS_FILE.read_text())
    if len(pays) < 7:
        print(f"Need 7 payment IDs, have {len(pays)}.")
        return 1

    print("Running replay scenarios...")
    results = [
        run("refund_loop", sc_refund_loop, pays[0]),
        run("duplicate",   sc_duplicate,   pays[1]),
        run("velocity",    sc_velocity,    pays[2:5]),
        run("new_payee",   sc_new_payee,   pays[5]),
        run("cap_bypass",  sc_cap_bypass,  pays[6]),
    ]

    RESULTS_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {RESULTS_FILE}\n")

    print(f"{'Attack':<14} {'Att':>4} {'Allow':>6} {'Block':>6} {'Esc':>4}")
    print("-" * 40)
    for r in results:
        print(f"{r['attack']:<14} {r['attempted']:>4} {r['allowed']:>6} "
              f"{r['blocked']:>6} {r['escalated']:>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
