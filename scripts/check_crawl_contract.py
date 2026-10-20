"""Smoke test del contratto raw HTML con il crawler reale, nessun sito esterno."""
import os
import time
import httpx

base = os.getenv("CRAWL_TEST_URL", "http://127.0.0.1:11235")
with httpx.Client(timeout=60) as client:
    for attempt in range(40):
        try:
            if client.get(base+"/health").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(2)
    else:
        raise SystemExit("Crawl4AI non pronto")
    response = client.post(base+"/crawl", headers={"Authorization": "Bearer "+os.environ["CRAWL_TEST_TOKEN"]},
        json={"urls": ["raw:<html><body><h1>Impresa Fittizia</h1><p>Software dimostrativo senza dati reali.</p></body></html>"],
              "browser_config": {"type": "BrowserConfig", "params": {"headless": True, "java_script_enabled": False}},
              "crawler_config": {"type": "CrawlerRunConfig", "params": {"stream": False, "cache_mode": "bypass",
                  "process_in_browser": False, "base_url": "https://example.org/", "verbose": False}}})
    response.raise_for_status()
    result = response.json()["results"][0]
    assert result["success"] is True
    markdown = result["markdown"]
    if isinstance(markdown, dict):
        markdown = markdown["raw_markdown"]
    assert "Impresa Fittizia" in markdown
    print("Contratto Crawl4AI raw HTML verificato, senza fetch di siti esterni.")
