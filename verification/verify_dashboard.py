from playwright.sync_api import Page, expect, sync_playwright

def verify_dashboard(page: Page):
    # 1. Arrange: Go to the dashboard
    page.goto("http://localhost:5000/")

    # 2. Check for Search Bar
    expect(page.locator("input[name='q']")).to_be_visible()

    # 3. Check for Pagination (Next button should be visible on first page)
    # We populated 45 players, so there should be multiple pages.
    # Note: Text matching is case-insensitive usually, but "Next" is the text.
    expect(page.get_by_role("link", name="Next")).to_be_visible()

    # 4. Check for Accordion Chevron
    # We check if at least one chevron exists
    expect(page.locator(".chevron").first).to_be_visible()

    # 5. Interact: Search for "Crafter"
    page.fill("input[name='q']", "Crafter")
    page.press("input[name='q']", "Enter")

    # Wait for reload
    page.wait_for_load_state("networkidle")

    # Verify we see Crafter results
    expect(page.get_by_text("Crafter_003")).to_be_visible()

    # 6. Interact: Toggle Accordion
    # Click the first header
    page.locator(".header").first.click()

    # Wait for transition (approx 400ms CSS transition)
    page.wait_for_timeout(500)

    # Check if content expanded (we can check for visibility of an achievement title inside)
    # Assuming the first player has some achievements or rank info.
    # Rank info is inside .achievement-list now.
    expect(page.locator(".achievement-list").first).to_be_visible()

    # 7. Screenshot
    page.screenshot(path="verification/dashboard_verified.png", full_page=True)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_dashboard(page)
            print("Verification script ran successfully.")
        except Exception as e:
            print(f"Verification failed: {e}")
            page.screenshot(path="verification/failure.png")
        finally:
            browser.close()
