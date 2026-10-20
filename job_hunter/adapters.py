import asyncio
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
import os
from urllib.parse import urlsplit, urljoin, quote
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import httpx
from pydantic import ValidationError

from .safe_web import canonical_url, fetch_public, WebError

ROOT = Path(os.getenv("HUNTER_RESOURCE_DIR", str(Path(__file__).resolve().parent.parent)))
if not (ROOT / "prompts").is_dir():
    ROOT = Path(sys.prefix) / "share" / "ai-job-hunter"


class AdapterError(ValueError):
    """Codice pubblico privo di body HTTP, credenziali o contenuti del CV."""


def haversine(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return round(6371.0088 * 2 * math.asin(min(1, math.sqrt(value))), 2)


def host(url):
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def is_portal(url):
    name = host(url)
    return any(name == d or name.endswith("."+d) for d in (
        "linkedin.com", "indeed.com", "indeed.it", "glassdoor.com", "facebook.com", "instagram.com",
        "paginegialle.it", "paginebianche.it", "wikipedia.org", "kompass.com", "crunchbase.com",
        "youtube.com", "google.com", "bing.com", "europages.it", "infojobs.it", "monster.it"))


def normalize(value):
    return " ".join(value.lower().split())


def evidence_valid(item, pages):
    page = next((p for p in pages if p["url"] == item.source_url), None)
    return page is not None and normalize(item.quote) in normalize(page["text"])


def _parse_pdf(data):
    try:
        proc = subprocess.run([sys.executable, "-m", "job_hunter.pdf_worker"], input=data,
                              capture_output=True, timeout=30, check=False)
        value = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, ValueError) as exc:
        raise AdapterError("pdf_parse_timeout_or_invalid") from exc
    if "error" in value:
        raise AdapterError(value["error"])
    return value["text"]


class Adapters:
    def __init__(self, settings, store, client=None):
        self.s, self.store = settings, store
        self.client = client or httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False)
        self.last_public = 0.0
        self.last_search = 0.0
        self.last_geo = 0.0
        self.retries = 0

    async def request(self, method, url, **kwargs):
        for attempt in range(3):
            try:
                # Stream and cap every response, including trusted LAN adapters.
                async with self.client.stream(method, url, **kwargs) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt < 2:
                            self.retries += 1
                            await asyncio.sleep(2 ** attempt)
                            continue
                    if not 200 <= response.status_code < 300:
                        raise AdapterError(f"service_http_{response.status_code}")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > max(20_000_000, self.s.max_upload_mb * 1024 * 1024):
                            raise AdapterError("service_response_too_large")
                    return httpx.Response(response.status_code, headers=response.headers, content=bytes(body), request=response.request)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 2:
                    raise AdapterError("service_unreachable_or_timeout") from exc
                self.retries += 1
                await asyncio.sleep(2 ** attempt)
        raise AdapterError("service_retry_exhausted")

    async def llm(self, prompt, data, schema, writing=False):
        system = (ROOT / "prompts" / (prompt + ".md")).read_text(encoding="utf-8")
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": json.dumps({"untrusted_data": data}, ensure_ascii=False)}]
        for attempt in range(2):
            response = await self.request("POST", self.s.ollama_url.rstrip("/") + "/api/chat",
                json={"model": self.s.writing_model if writing else self.s.research_model,
                      "stream": False, "think": False, "format": schema.model_json_schema(),
                      "options": {"temperature": 0, "num_ctx": self.s.num_ctx, "num_predict": 2200},
                      "keep_alive": "2m", "messages": messages}, timeout=self.s.ollama_timeout)
            try:
                content = response.json()["message"]["content"]
                return schema.model_validate_json(content)
            except (ValueError, KeyError, ValidationError):
                if attempt == 0:
                    messages.append({"role": "user", "content": "Output non conforme. Riprova una sola volta con JSON valido nello schema, senza aggiungere dati."})
        raise AdapterError("llm_invalid_json_after_repair")

    async def pdf_text(self, data):
        try:
            return await asyncio.to_thread(_parse_pdf, data)
        except AdapterError as exc:
            if str(exc) != "ocr_required":
                raise
            if not self.s.stirling_enabled:
                raise AdapterError("ocr_required_enable_stirling_or_upload_text_pdf") from exc
        base = self.s.stirling_url.rstrip("/")
        headers = {"X-API-KEY": self.s.stirling_key} if self.s.stirling_key else {}
        spec = (await self.request("GET", base + "/v1/api-docs", headers=headers)).json()
        if "/api/v1/misc/ocr-pdf" not in spec.get("paths", {}):
            raise AdapterError("stirling_ocr_endpoint_unavailable")
        response = await self.request("POST", base + "/api/v1/misc/ocr-pdf", headers=headers,
            files=[("fileInput", ("cv.pdf", data, "application/pdf"))] +
                  [("languages", (None, lang.strip())) for lang in self.s.ocr_languages.split(",")],
            data={"ocrType": "skip-text"}, timeout=120)
        return await asyncio.to_thread(_parse_pdf, response.content)

    async def search(self, query, language="it"):
        await asyncio.sleep(max(0, 1.1 - (time.monotonic() - self.last_search)))
        self.last_search = time.monotonic()
        response = await self.request("GET", self.s.searx_url.rstrip("/") + "/search",
                                     params={"q": query, "format": "json", "language": language})
        return response.json().get("results", [])[:10]

    async def geocode(self, address):
        key = "geo:" + hashlib.sha256(address.lower().encode()).hexdigest()
        cached = self.store.cache_get(key)
        if cached is not None:
            return cached
        await asyncio.sleep(max(0, 1.1 - (time.monotonic() - self.last_geo)))
        self.last_geo = time.monotonic()
        response = await self.request("GET", self.s.geocode_url.rstrip("/") + "/search",
            params={"q": address, "format": "jsonv2", "limit": 1}, headers={"User-Agent": self.s.user_agent})
        values = response.json()
        result = {"coordinates": [float(values[0]["lat"]), float(values[0]["lon"])],
                  "label": values[0].get("display_name"), "provider": self.s.geocode_url,
                  "checked_at": time.time(), "attribution": "© OpenStreetMap contributors, ODbL; https://www.openstreetmap.org/copyright"} if values else {}
        self.store.cache_put(key, result, 24 * 30)
        return result

    async def public_fetch(self, url):
        await asyncio.sleep(max(0, 1.1 - (time.monotonic() - self.last_public)))
        self.last_public = time.monotonic()
        for attempt in range(3):
            try:
                return await asyncio.to_thread(fetch_public, url, self.s.user_agent)
            except WebError as exc:
                if attempt == 2 or exc.status not in (429, 500, 502, 503, 504):
                    raise
                self.retries += 1
                await asyncio.sleep(2 ** attempt)

    async def crawl(self, url):
        url = canonical_url(url)
        key = "page:" + hashlib.sha256(url.encode()).hexdigest()
        cached = self.store.cache_get(key)
        if cached is not None:
            return cached
        p = urlsplit(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        robots_key = "robots:" + robots_url
        robots = self.store.cache_get(robots_key)
        if robots is None:
            try:
                robots = {"text": (await self.public_fetch(robots_url)).text}
            except WebError as exc:
                if exc.status == 404:
                    robots = {"text": ""}
                else:
                    raise AdapterError("robots_unavailable_refused") from exc
            self.store.cache_put(robots_key, robots, self.s.cache_hours)
        parser = RobotFileParser()
        parser.parse(robots["text"].splitlines())
        if not parser.can_fetch("AIJobHunter", url):
            raise AdapterError("robots_disallowed")
        delay = parser.crawl_delay("AIJobHunter") or parser.crawl_delay("*") or 0
        if delay > 60:
            raise AdapterError("robots_crawl_delay_above_budget")
        await asyncio.sleep(max(0, delay - (time.monotonic() - self.last_public)))
        page = await self.public_fetch(url)
        # Refuse a cross-origin redirect: its robots policy has not been read.
        if urlsplit(page.url).netloc != p.netloc:
            raise AdapterError("cross_origin_redirect_refused")
        soup = BeautifulSoup(page.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            try:
                link = canonical_url(urljoin(page.url, a["href"]))
                if host(link) == host(page.url) and link not in links:
                    links.append(link)
            except ValueError:
                pass
        # Defense in depth: no active elements, fetchable attributes or JSON-LD scripts go to the raw processor.
        jsonld = [t.string for t in soup.find_all("script", type="application/ld+json") if t.string]
        for node in soup(["script", "style", "iframe", "object", "embed", "link", "img", "video", "audio", "source", "base", "meta"]):
            node.decompose()
        for node in soup.find_all(True):
            node.attrs = {}
        response = await self.request("POST", self.s.crawl_url.rstrip("/") + "/crawl",
            headers={"Authorization": "Bearer " + self.s.crawl_token},
            json={"urls": ["raw:" + str(soup)],
                  "browser_config": {"type": "BrowserConfig", "params": {"headless": True, "java_script_enabled": False}},
                  "crawler_config": {"type": "CrawlerRunConfig", "params": {
                      "stream": False, "cache_mode": "bypass", "word_count_threshold": 1,
                      "verbose": False}}}, timeout=60)
        result = response.json().get("results", [])
        if not result or not result[0].get("success"):
            raise AdapterError("crawl4ai_extraction_failed")
        markdown = result[0].get("markdown") or ""
        if isinstance(markdown, dict):
            markdown = markdown.get("raw_markdown", "")
        if not isinstance(markdown, str):
            raise AdapterError("crawl4ai_invalid_markdown")
        value = {"url": page.url, "text": markdown[:10000], "links": links[:80],
                 "jsonld": jsonld[:10], "checked_at": time.time()}
        self.store.cache_put(key, value, self.s.cache_hours)
        return value

    def dav_path(self, path):
        if not self.s.nextcloud_enabled:
            raise AdapterError("nextcloud_disabled")
        # Base URL is the administrator's allowed folder. No deletion, listing or overwrite API.
        if not path or path.startswith("/") or "\\" in path or "%" in path or any(p in (".", "..") for p in path.split("/")):
            raise AdapterError("nextcloud_path_outside_allowed_folder")
        return self.s.nextcloud_url.rstrip("/") + "/" + quote(str(PurePosixPath(path)), safe="/")

    async def dav_import(self, path):
        response = await self.request("GET", self.dav_path(path),
            auth=(self.s.nextcloud_user, self.s.nextcloud_password))
        if not response.content.startswith(b"%PDF-") or len(response.content) > self.s.max_upload_mb * 1024 * 1024:
            raise AdapterError("nextcloud_invalid_pdf_or_size")
        return response.content

    async def dav_export(self, path, content, content_type):
        # If-None-Match avoids replacing an existing user document.
        await self.request("PUT", self.dav_path(path), content=content,
            headers={"Content-Type": content_type, "If-None-Match": "*"},
            auth=(self.s.nextcloud_user, self.s.nextcloud_password))
