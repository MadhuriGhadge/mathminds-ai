from playwright.sync_api import sync_playwright

def run():
    print("Starting sync_playwright...")
    try:
        with sync_playwright() as p:
            print("Launching browser...")
            browser = p.chromium.launch(headless=True)
            print("Browser launched.")
            page = browser.new_page()
            page.goto("http://example.com")
            print("Title:", page.title())
            browser.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run()
