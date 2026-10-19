"""
Blazing fast payment generator. Runs headless and in parallel.
"""
import json
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = "http://127.0.0.1:8000/"
AMOUNT_PAISE = 200000   # ₹2000 per payment
PAYMENTS_FILE = Path(__file__).parent.parent / "data" / "payments.json"

def get_checkout_frame(page):
    for sel in [
        "iframe.razorpay-checkout-frame",
        "iframe[name='razorpay-checkout-frame']",
        "iframe[src*='checkout.razorpay.com']",
    ]:
        try:
            page.wait_for_selector(sel, timeout=5000)
            return page.frame_locator(sel)
        except PWTimeout:
            continue
    raise RuntimeError("Razorpay iframe never appeared")

def generate_one(index) -> str | None:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # Use a fresh context to ensure no cookies/sessions carry over
            context = browser.new_context()
            page = context.new_page()

            # Auto-dismiss the native alert() so it doesn't block JavaScript
            page.on("dialog", lambda dialog: dialog.accept())

            # Block images and fonts to speed up Razorpay load times
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())

            page.goto(f"{BASE_URL}?amount={AMOUNT_PAISE}")
            page.click("#pay")

            frame = get_checkout_frame(page)

            # 1. Go straight to Netbanking (Mobile number is skipped due to prefill in HTML)
            netbanking_tab = frame.locator("text=Netbanking").first
            netbanking_tab.wait_for(state="visible", timeout=10000)
            netbanking_tab.click()

            # 2. PNB & Popup
            with page.expect_popup(timeout=7000) as popup_info:
                try:
                    frame.locator("#overlay-backdrop").wait_for(state="hidden", timeout=2000)
                except PWTimeout:
                    pass

                try:
                    frame.locator("text=Punjab National Bank").first.click(timeout=3000, force=True)
                except PWTimeout:
                    frame.locator("text=Canara Bank").first.click(timeout=3000, force=True)

            mock_bank_page = popup_info.value
            mock_bank_page.wait_for_load_state()

            # 3. Success
            mock_bank_page.locator("text=Success").first.click(timeout=5000, no_wait_after=True)

            # 4. Get ID
            page.wait_for_function("() => document.getElementById('log').textContent.includes('pay_')", timeout=15000)
            log_text = page.locator("#log").text_content() or ""
            m = re.search(r"pay_[A-Za-z0-9]+", log_text)

            browser.close()
            return m.group(0) if m else None

    except Exception as e:
        print(f"    ! worker {index} failed: {e}")
        return None

def main(n: int = 7) -> int:
    print(f"Generating {n} payments in parallel (headless)...")
    start_time = time.time()

    results = []
    PAYMENTS_FILE.parent.mkdir(exist_ok=True)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(generate_one, i) for i in range(n)]
        for f in futures:
            pid = f.result()
            if pid:
                results.append(pid)
                print(f"    + {pid}")
                PAYMENTS_FILE.write_text(json.dumps(results, indent=2))

    elapsed = time.time() - start_time
    print(f"\nDone! Wrote {len(results)}/{n} IDs in {elapsed:.1f} seconds to {PAYMENTS_FILE}")
    return 0 if len(results) == n else 1

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    sys.exit(main(n))
