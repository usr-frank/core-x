from playwright.sync_api import sync_playwright

def verify_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Verify Dashboard (Ironman Icons)
        print("Navigating to Dashboard...")
        page.goto("http://localhost:5000/")

        # Wait for content to load
        page.wait_for_selector(".player-card")

        # Take Screenshot
        page.screenshot(path="verification/dashboard.png", full_page=True)
        print("📸 Dashboard screenshot saved to verification/dashboard.png")

        # 2. Verify Leaderboard (Hall of Fame)
        print("Navigating to Leaderboard...")
        page.goto("http://localhost:5000/leaderboard")

        # Wait for grid
        page.wait_for_selector(".leaderboard-grid")

        # Take Screenshot
        page.screenshot(path="verification/leaderboard.png", full_page=True)
        print("📸 Leaderboard screenshot saved to verification/leaderboard.png")

        browser.close()

if __name__ == "__main__":
    verify_frontend()
