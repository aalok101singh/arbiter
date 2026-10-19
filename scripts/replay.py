"""
Runs five attack scenarios against the Arbiter proxy using payment IDs
from data/payments.json. Writes data/replay_results.json for report.py.
"""
import json
import sys
import uuid
from pathlib import Path
import requests

BASE = "http://127.0.0.1:8000"
PAYMENTS_FILE = Path(__file__).parent.parent / "data" / "payments.json"
RESULTS_FILE = Path(__file__).parent.parent / "data" / "replay_results.json"
LEDGER_FILE = Path(__file__).parent.parent / "data" / "ledger.jsonl"

# Define what the guard SHOULD do for each test
EXPECTED = {
    "refund_loop": {"allow": 1, "block": 4, "escalate": 0},
    "duplicate":   {"allow": 1, "block": 1, "escalate": 0},
    "velocity":    {"allow": 2, "block": 1, "escalate": 0},
    "new_payee":   {"allow": 0, "block": 0, "escalate": 1},
    "cap_bypass":  {"allow": 2, "block": 1, "escalate": 0},
}

def get_ledger_seq() -> int:
    """Returns the current number of records in the ledger."""
    if not LEDGER_FILE.exists(): return 0
    with open(LEDGER_FILE, "rb") as f:
        return sum(1 for line in f if line.strip())

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

    actual = {
        "allow": sum(1 for a in attempts if a["decision"] == "allow"),
        "block": sum(1 for a in attempts if a["decision"] == "block"),
        "escalate": sum(1 for a in attempts if a["decision"] == "escalate"),
    }

    expected = EXPECTED[name]
    passed = (actual == expected)

    return {
        "attack": name,
        "attempted": len(attempts),
        "attempts": attempts,
        "expected": expected,
        "actual": actual,
        "passed": passed
    }

def sc_refund_loop(payment_id):
    agent = f"loop-{uuid.uuid4().hex[:6]}"
    out = []
    for i in range(5):
        code, dec, rule = call_refund(payment_id, 10000, agent, f"loop-{i}")
        out.append({"i": i+1, "amount": 10000, "payee": payment_id, "http": code, "decision": dec, "rule": rule})
    return out

def sc_duplicate(payment_id):
    agent = f"dup-{uuid.uuid4().hex[:6]}"
    key = f"dup-key-{uuid.uuid4().hex[:6]}"
    out = []
    for i in range(2):
        code, dec, rule = call_refund(payment_id, 10000, agent, key)
        out.append({"i": i+1, "amount": 10000, "payee": payment_id, "http": code, "decision": dec, "rule": rule})
    return out

def sc_velocity(payments):
    agent = f"vel-{uuid.uuid4().hex[:6]}"
    out = []
    for i, pid in enumerate(payments[:3]):
        code, dec, rule = call_refund(pid, 10000, agent, f"vel-{i}")
        out.append({"i": i+1, "amount": 10000, "payee": pid, "http": code, "decision": dec, "rule": rule})
    return out

def sc_new_payee(payment_id):
    agent = f"np-{uuid.uuid4().hex[:6]}"
    payee = f"merchant-{uuid.uuid4().hex[:8]}"
    code, dec, rule = call_refund(payment_id, 100000, agent,
                                  f"np-{uuid.uuid4().hex[:6]}", payee=payee)
    return [{"i": 1, "amount": 100000, "payee": payee, "http": code, "decision": dec, "rule": rule}]

def sc_cap_bypass(payment_id):
    payee = f"capmerchant-{uuid.uuid4().hex[:6]}"
    warm_agent = f"warm-{uuid.uuid4().hex[:6]}"
    # This warmup call is NOT counted in the attempts list, but it writes 2 ledger records
    call_refund(payment_id, 10000, warm_agent, f"warm-{uuid.uuid4().hex[:6]}", payee=payee)

    out = []
    for i in range(3):
        agent = f"cap-{uuid.uuid4().hex[:6]}"
        code, dec, rule = call_refund(payment_id, 80000, agent, f"cap-{i}", payee=payee)
        out.append({"i": i+1, "amount": 80000, "payee": payee, "http": code, "decision": dec, "rule": rule})
    return out

def main() -> int:
    if not PAYMENTS_FILE.exists():
        print(f"Missing {PAYMENTS_FILE}. Run: python scripts/seed_payments.py 7")
        return 1
    pays = json.loads(PAYMENTS_FILE.read_text())
    if len(pays) < 7:
        print(f"Need 7 payment IDs, have {len(pays)}.")
        return 1

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    start_seq = get_ledger_seq() + 1

    print(f"Starting Replay {run_id}...")
    results = [
        run("refund_loop", sc_refund_loop, pays[0]),
        run("duplicate",   sc_duplicate,   pays[1]),
        run("velocity",    sc_velocity,    pays[2:5]),
        run("new_payee",   sc_new_payee,   pays[5]),
        run("cap_bypass",  sc_cap_bypass,  pays[6]),
    ]

    end_seq = get_ledger_seq()

    output = {
        "run_id": run_id,
        "ledger_start": start_seq,
        "ledger_end": end_seq,
        "results": results
    }

    RESULTS_FILE.write_text(json.dumps(output, indent=2))
    print(f"\nWrote {RESULTS_FILE}\n")

    print(f"{'Attack':<14} {'Att':>4} {'Exp (A/B/E)':>12} {'Act (A/B/E)':>12} {'Result':>8}")
    print("-" * 55)
    for r in results:
        exp = r['expected']
        act = r['actual']
        status = "✅ PASS" if r['passed'] else "❌ FAIL"
        print(f"{r['attack']:<14} {r['attempted']:>4} "
              f"{exp['allow']}/{exp['block']}/{exp['escalate']:>6} "
              f"{act['allow']}/{act['block']}/{act['escalate']:>6} "
              f"{status:>8}")

    return 0 if all(r["passed"] for r in results) else 1

if __name__ == "__main__":
    sys.exit(main())
