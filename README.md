# Arbiter Guard v0.1

**Arbiter assumes your AI agent will eventually be tricked, and makes that cheap.**

It is a runtime control layer that sits between an AI agent and a payment gateway (Razorpay). It holds the credentials, enforces deterministic rules, and writes a hash-chained, cryptographically verifiable evidence log that a third party (like an insurer) can trust.

## Architecture

1. **The Proxy** (`app/main.py`): The agent calls Arbiter, not Razorpay. The agent holds no credentials.
2. **The Rules** (`app/rules.py`): Deterministic limits on velocity, duplicate payments, payee caps, and refund loops. No AI hallucinations.
3. **The Ledger** (`app/ledger.py`): Every proposed action and every result is signed with Ed25519 and appended to a hash chain before the payment gateway is called.
4. **The Verifier** (`scripts/verify.py`): A 60-line, dependency-light script that proves the ledger has not been tampered with. 

## What it catches that payment limits miss:
- **Refund Loops**: 40 valid $5 refunds is a loop. Limits see 40 valid transactions.
- **Idempotency**: The agent retries a failed request. Limits see two valid payments.
- **Credential Laundering**: Sub-agents bypassing parent limits.
- **Read-then-Exfiltrate**: (Partially handled in v0.1 via strict payload logging).

## Quickstart

1. `pip install -r requirements.txt`
2. `playwright install chromium` (Needed for the test payment generator)
3. Copy `.env.example` to `.env` and add your Razorpay Test Keys.
4. Generate the signing keys: `python scripts/genkey.py`
5. Start the server: `uvicorn app.main:app --reload`
6. Open `http://127.0.0.1:8000/` in your browser to test a manual payment.

## The Replay Demo (How to prove it works)

To generate the automated evidence report:

1. Generate 7 captured test payments: 
   `python scripts/seed_payments.py 7`
2. Fire the 5 attack scenarios at the guard: 
   `python scripts/replay.py`
3. Generate the HTML report: 
   `python scripts/report.py`
4. Verify the evidence log is untampered: 
   `python scripts/verify.py`

## Honest Limits (Tier C)
In v0.1, we demonstrate Tier C enforcement. The agent *could* technically bypass the proxy if it had the raw Razorpay keys. Tier A (credential broker + Hardware Security Module) eliminates this risk but requires production deployment. We ship Tier C first because it is installable without re-architecting a company's entire payment path.
