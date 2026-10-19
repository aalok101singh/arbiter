import json
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = Path(__file__).parent.parent / "docs"
RESULTS_FILE = DATA_DIR / "replay_results.json"
LEDGER_FILE = DATA_DIR / "ledger.jsonl"
REPORT_FILE = DATA_DIR / "report.html"
ANCHOR_FILE = DOCS_DIR / "ledger_anchor.txt"

def generate_report():
    data = json.loads(RESULTS_FILE.read_text())
    results = data["results"]
    run_id = data["run_id"]
    start_seq = data["ledger_start"]
    end_seq = data["ledger_end"]

    # Get the latest hash from the ledger
    last_hash = "0" * 64
    if LEDGER_FILE.exists():
        with open(LEDGER_FILE, "rb") as f:
            for line in f:
                if line.strip():
                    last_record = json.loads(line)
                    last_hash = last_record["hash"]

    # Write the external anchor
    DOCS_DIR.mkdir(exist_ok=True)
    anchor_text = f"Latest Ledger Hash: {last_hash}\nTimestamp: {datetime.now().isoformat()}\nRun ID: {run_id}\n"
    ANCHOR_FILE.write_text(anchor_text, encoding="utf-8")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    velocity_limit = os.getenv("ARBITER_VELOCITY_LIMIT", "2")
    payee_cap = int(os.getenv("ARBITER_PAYEE_CAP", "200000")) / 100
    new_payee_thresh = int(os.getenv("ARBITER_NEW_PAYEE_THRESHOLD", "50000")) / 100

    # Summary table rows
    summary_rows = ""
    for r in results:
        color = "#e8f5e9" if r["passed"] else "#ffebee"
        status_icon = "✅ PASS" if r["passed"] else "❌ FAIL"
        exp = r['expected']
        act = r['actual']
        summary_rows += f"""
        <tr style="background-color: {color};">
            <td><strong>{r['attack'].replace('_', ' ').title()}</strong></td>
            <td>{r['attempted']}</td>
            <td>{exp['allow']} / {exp['block']} / {exp['escalate']}</td>
            <td>{act['allow']} / {act['block']} / {act['escalate']}</td>
            <td><strong>{status_icon}</strong></td>
        </tr>
        """

    # Per-attempt detail rows
    detail_rows = ""
    for r in results:
        for a in r["attempts"]:
            amt = f"₹{a['amount']/100:.2f}"
            target = a['payee']  # Kept as 'payee' in JSON, displayed as 'Target'
            rule = a['rule'] or "-"
            dec = a['decision']

            # Color code decisions
            if dec == "allow": bg = "#ffffff"
            elif dec == "block": bg = "#ffebee"
            else: bg = "#fff3e0"

            detail_rows += f"""
            <tr style="background-color: {bg};">
                <td>{r['attack'].replace('_', ' ').title()}</td>
                <td>#{a['i']}</td>
                <td>{amt}</td>
                <td>{target}</td>
                <td>{dec.upper()}</td>
                <td>{rule}</td>
            </tr>
            """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Arbiter Regression Replay</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #333; max-width: 950px; margin: 40px auto; padding: 20px; line-height: 1.5; }}
        h1 {{ border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 5px; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
        .explain {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #000; margin-bottom: 30px; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; text-align: center; font-size: 0.9em; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
        .fingerprint {{ margin-top: 40px; padding: 15px; background: #f4f4f4; font-family: monospace; font-size: 0.85em; border-left: 4px solid #000; word-break: break-all; }}
    </style>
</head>
<body>
    <h1>Arbiter Guard: Regression Replay Report</h1>
    <div class="meta">
        <strong>Run ID:</strong> {run_id}<br>
        <strong>Generated:</strong> {now}<br>
        <strong>Target:</strong> Razorpay Test Environment (Enforce Mode)
    </div>

    <div class="explain">
        <strong>Note on Testing:</strong> This is a <em>regression replay</em> designed to test the internal consistency of the Arbiter rules engine. The attacks and expected outcomes are self-authored to ensure the guard behaves exactly as specified. (Independent adversarial audits are a v1.0 milestone).
        <br><br>
        <strong>Configured Rules & Scope:</strong>
        Velocity Limit = {velocity_limit}/hr (scoped per <code>agent_id</code>; every scenario below uses a fresh agent).
        Payee Cap = ₹{payee_cap:.2f} (scoped per <code>payee</code>).
        Refund Loop = 1 allowed per <code>payment_id</code>.
        Duplicate = 1 allowed per <code>idempotency_key</code>.
        New Payee = First transfer > ₹{new_payee_thresh:.2f} requires escalation (scoped per <code>payee</code>).
    </div>

    <h3>Summary</h3>
    <table>
        <thead>
            <tr>
                <th>Attack Scenario</th>
                <th>Attempts</th>
                <th>Expected (A / B / E)</th>
                <th>Actual (A / B / E)</th>
                <th>Result</th>
            </tr>
        </thead>
        <tbody>
            {summary_rows}
        </tbody>
    </table>

    <h3 style="margin-top: 40px;">Detailed Attempt Log</h3>
    <table>
        <thead>
            <tr>
                <th>Scenario</th>
                <th>Attempt</th>
                <th>Amount</th>
                <th>Target</th>
                <th>Decision</th>
                <th>Rule Fired</th>
            </tr>
        </thead>
        <tbody>
            {detail_rows}
        </tbody>
    </table>

    <h3 style="margin-top: 40px;">Evidence Ledger Fingerprint</h3>
    <p>Every decision is cryptographically signed and appended to a hash-chained ledger. The ledger records for this specific run range from <strong>#{start_seq} to #{end_seq}</strong>.</p>
    <p><em>Record Math:</em> 14 test attempts + 1 warmup call = 15 total requests. Each request writes a "proposed" record and a "result" record (15 × 2 = 30 records).</p>

    <div class="fingerprint">
        Total Records in Ledger: {end_seq}<br>
        Latest Hash: {last_hash}
    </div>
    <p><strong>External Anchor:</strong> A copy of this hash has been written to <code>docs/ledger_anchor.txt</code>. Once committed to a public repository, this makes a silent rewrite of the ledger history externally detectable (it does not mathematically prevent one). For a stronger guarantee, v1.0 will integrate a third-party timestamping service like OpenTimestamps or an RFC 3161 TSA.</p>
    <p><em>Verify the ledger has not been tampered with: <code>python scripts/verify.py</code></em></p>
</body>
</html>"""

    REPORT_FILE.write_text(html, encoding="utf-8")
    print(f"Report generated: {REPORT_FILE}")
    print(f"External anchor written to: {ANCHOR_FILE}")

if __name__ == "__main__":
    generate_report()
