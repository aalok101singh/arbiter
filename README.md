# Arbiter Guard v0.1

**Arbiter assumes your AI agent will eventually be tricked, and makes that cheap.**

It is a runtime control layer that sits between an AI agent and a payment gateway (Razorpay). It holds the credentials, enforces deterministic rules, and writes a hash-chained, cryptographically verifiable evidence log that a third party (like an insurer) can trust.

## Architecture

1. **The Proxy** (`app/main.py`): The agent calls Arbiter, not Razorpay. The agent holds no credentials.
2. **The Rules** (`app/rules.py`): Deterministic limits on velocity, duplicate payments, payee caps, and refund loops. No AI hallucinations.
3. **The Ledger** (`app/ledger.py`): Every proposed action and every result is signed with Ed25519 and appended to a hash chain before the payment gateway is called.
4. **The Verifier** (`scripts/verify.py`): A 60-line, dependency-light script that proves the ledger has not been tampered with. 

## What it catches (Tested in v0.1)
- **Refund Loops**: An agent tries to refund the same payment multiple times.
- **Idempotency (Duplicates)**: An agent retries a failed request with the same key.
- **Velocity Spikes**: Too many refunds in a short window (scoped per agent).
- **New Payee Escalation**: Blocking a large transfer to an unknown destination until human review.
- **Payee Cap Bypass**: Blocking cumulative refunds to a single merchant that exceed a daily threshold.

## What is NOT yet covered (Roadmap for v0.2+)
- **Credential Laundering**: Sub-agents bypassing parent limits (requires nested delegation tracking).
- **Read-then-Exfiltrate**: Detecting data exfiltration in payload memos (requires NLP analysis).

## Honest Limits: Tier Definitions
- **Tier C (Current v0.1)**: The enforcing proxy holds the payment gateway API keys. It is safe against the *agent*, but if the operator gives the agent the raw API keys, it can bypass the guard.
- **Tier A (Manifesto Vision)**: A production deployment where a customer-controlled HSM brokers task-scoped, short-lived tokens so the agent never even sees the keys.

## Quickstart

1. `pip install -r requirements.txt`
2. `playwright install chromium` (Needed for the test payment generator)
3. Copy `.env.example` to `.env` and add your Razorpay Test Keys.
4. Generate the signing keys: `python scripts/genkey.py`
5. Start the server: `uvicorn app.main:app --reload`
6. Open `http://127.0.0.1:8000/` in your browser.

## The Replay Demo

To generate the automated evidence report:
1. `python scripts/seed_payments.py 7`
2. `python scripts/replay.py`
3. `python scripts/report.py`
4. `python scripts/verify.py`
