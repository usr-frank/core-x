from playwright.sync_api import sync_playwright

def verify_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to dashboard
        page.goto("http://localhost:5000")

        # Check fonts - this is hard to verify with playwright selectors directly without computed styles,
        # but we can take a screenshot.

        # Verify Neon Elements exist (by checking styles if possible, but visual is best)
        # We can check if title has correct font-family
        header_font = page.eval_on_selector("h1", "el => getComputedStyle(el).fontFamily")
        print(f"Header Font: {header_font}")

        # Take Dashboard Screenshot (Nether Theme)
        page.screenshot(path="/home/jules/verification/dashboard_nether.png")

        # Toggle Theme
        page.click("#themeToggle")

        # Take Dashboard Screenshot (Aether Theme)
        page.screenshot(path="/home/jules/verification/dashboard_aether.png")

        # Go to Profile (if any player exists) - We might need to mock data or insert some if DB is empty.
        # Since I just init DB, it is empty. I should insert a dummy player to verify card styles.

        browser.close()

if __name__ == "__main__":
    verify_frontend()
