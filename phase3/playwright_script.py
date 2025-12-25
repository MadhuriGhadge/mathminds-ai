from playwright.sync_api import sync_playwright

def get_stock_price(ticker="AAPL"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(
            f"https://finance.yahoo.com/quote/{ticker}",
            wait_until="domcontentloaded"
        )

        page.wait_for_timeout(3000)  # let JS settle

        price = page.locator(
            'fin-streamer[data-field="regularMarketPrice"]'
        ).first.text_content()

        browser.close()
        return price


if __name__ == "__main__":
    print("AAPL price:", get_stock_price("AAPL"))
