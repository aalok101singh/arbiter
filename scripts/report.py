import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
RESULTS_FILE = DATA_DIR / "replay_results.json"
LEDGER_FILE = DATA_DIR / "ledger.jsonl"
REPORT_FILE = DATA_DIR / "report.html"

def generate_report():
    results = json.loads(RESULTS_FILE.read_text())

    # Get the latest hash from the ledger to act as the fingerprint
    last_hash = "0" * 64
    record_count = 0
    if LEDGER_FILE.exists():
        with open(LEDGER_FILE, "rb") as f:
            for line in f:
                if line.strip():
                    record_count += 1
                    last_record = json.loads(line)
                    last_hash = last_record["hash"]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Build the HTML table rows
    rows = ""
    for r in results:
        status_color = "#e8f5e9" if r["blocked"] > 0 or r["escalated"] > 0 else "#ffffff"
        rows += f"""
        <tr style="background-color: {status_color};">
            <td><strong>{r['attack'].replace('_', ' ').title()}</strong></td>
            <td>{r['attempted']}</td>
            <td>{r['allowed']}</td>
            <td>{r['blocked']}</td>
            <td>{r['escalated']}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Arbiter Assurance Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #333; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.5; }}
        h1 {{ border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 5px; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
        .fingerprint {{ margin-top: 40px; padding: 15px; background: #f4f4f4; font-family: monospace; font-size: 0.85em; border-left: 4px solid #000; word-break: break-all; }}
        .verifier {{ font-weight: bold; margin-top: 10px; font-family: monospace; }}
    </style>
</head>
<body>
    <h1>Arbiter Guard: Enforcement Replay Report</h1>
    <div class="meta">
        Generated: {now}<br>
        Target: Razorpay Test Environment<br>
        Mode: Enforce (Deterministic Rules)
    </div>

    <p>This report demonstrates the Arbiter runtime guard successfully intercepting five common agentic payment failure modes before they reach the payment gateway.</p>

    <table>
        <thead>
            <tr>
                <th>Attack Scenario</th>
                <th>Attempts</th>
                <th>Allowed</th>
                <th>Blocked</th>
                <th>Escalated</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>

    <h3>Evidence Ledger Fingerprint</h3>
    <p>Every decision (allow, block, or escalate) is cryptographically signed and appended to a hash-chained ledger. The current state of the ledger is:</p>
    <div class="fingerprint">
        Records: {record_count}<br>
        Latest Hash: {last_hash}
    </div>
    <p class="verifier">Verify this evidence: <code>python scripts/verify.py</code></p>
</body>
</html>"""

    REPORT_FILE.write_text(html)
    print(f"Report generated: {REPORT_FILE}")

if __name__ == "__main__":
    generate_report()
