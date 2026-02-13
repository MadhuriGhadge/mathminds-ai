from app.tools.web_scraper import run_playwright_sync

query = "calculate the price of 2 kg gold according to todays gold rate"
print(f"Running scraper for: {query}")

result = run_playwright_sync(query, headless=True)

print("\n--- STATUS ---")
print(result.get("status"))

print("\n--- CONTENT SNIPPET ---")
content = result.get("content", "")
# Print first 5000 chars to be sure we see the body
print(content[:5000])

if "unusual traffic" in content.lower() or "captcha" in content.lower():
    print("\n[!] DETECTED CAPTCHA/BLOCKING")
elif "Gold Rate" in content or "Silver Rate" in content:
    print("\n[+] SUCCESS: Found Gold Rate related content")
else:
    print("\n[?] Content unclear. Check snippet above.")
