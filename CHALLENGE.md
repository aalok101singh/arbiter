# Arbiter Challenge: Break the Guard

We believe runtime enforcement is the only way to make autonomous AI agents insurable. We also believe our code is only as good as its ability to withstand adversarial pressure. 

We are inviting the security community to try and break the Arbiter Guard v0.1 prototype.

## Rules of Engagement

We are looking for logical flaws, bypass techniques, and edge cases in the **rules engine** and **ledger integrity**. 

### In-Scope (Try to bypass):
- **Refund Loops:** Can you trick the `refund_loop` rule into allowing a second refund for the same `payment_id`?
- **Velocity Limits:** Can you spoof the `agent_id` or manipulate the `created_at` timestamp to bypass the velocity cap?
- **Payee Caps:** Can you exceed the `PAYEE_CAP` by manipulating decimal places, currency codes, or payload structures?
- **Idempotency:** Can you execute a duplicate payment without triggering the `idempotency` block?
- **Ledger Tampering:** Can you modify an entry in `data/ledger.jsonl` and still pass `python scripts/verify.py`?

### Out-of-Scope (Don't bother):
- **Razorpay Infra:** Attacking Razorpay's actual API or test servers.
- **Host Compromise:** Breaking into the host machine to read the `.env` keys directly. (In Tier A production, these live in a customer-controlled HSM).
- **DDoS:** Crashing the FastAPI server with traffic.

## How to Report
If you find a bypass:
1. Open an Issue on this repository with the title `[CHALLENGE] - [Brief Description]`.
2. Provide the exact `curl` command or Python script to reproduce the bypass.
3. If we verify it's a genuine bug, we will credit you in the next release notes. (No cash bounties yet, we are a v0.1 prototype!).

Let's see if you can break it.