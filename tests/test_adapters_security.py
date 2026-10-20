import asyncio
import io
import json
import socket
import time
import httpx
import pytest

from job_hunter.adapters import Adapters, AdapterError, evidence_valid, haversine
from job_hunter.models import Draft, Contact, Fit
from job_hunter.safe_web import canonical_url, public_addresses, fetch_public, WebError, Page
from job_hunter.store import Store
from job_hunter.exports import safe_cell
from conftest import pdf_bytes


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.org", "http://user:pass@example.org", "http://example.org:8080/", "https://example.org/\nsecret", "http://example.org:bad/"])
def test_url_schemes_credentials_ports(url):
    with pytest.raises(ValueError):
        canonical_url(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "192.168.1.1", "10.0.0.1", "172.16.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1", "0.0.0.0", "224.0.0.1", "100.64.0.1", "fd00::1"])
def test_private_and_special_addresses_blocked(monkeypatch, ip):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, 1, 6, "", (ip, 80))])
    with pytest.raises(WebError):
        public_addresses("example.org", 80)


def test_mixed_dns_answers_and_pin(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, 1, 6, "", ("93.184.216.34", 443)), (socket.AF_INET, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(WebError):
        public_addresses("example.org", 443)


def test_redirect_to_internal_is_revalidated(monkeypatch):
    from job_hunter import safe_web
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: [
        (socket.AF_INET, 1, 6, "", ("127.0.0.1" if host == "internal.test" else "93.184.216.34", 80))])
    calls = []
    class FakeConnection:
        def __init__(self, hostname, port, ip, tls, timeout):
            calls.append((hostname, ip))
        def request(self, *a, **k): pass
        def close(self): pass
        def getresponse(self):
            class Redirect:
                status = 302
                def getheader(self, name): return "http://internal.test/secret"
            return Redirect()
    monkeypatch.setattr(safe_web, "PinnedConnection", FakeConnection)
    with pytest.raises(WebError, match="ssrf_blocked"):
        fetch_public("http://example.org/", "Fixture")
    assert calls == [("example.org", "93.184.216.34")]


async def test_ollama_structured_output_one_repair(settings):
    requests = []
    def mock(req):
        data = json.loads(req.content)
        requests.append(data)
        return httpx.Response(200, json={"message": {"content": "not json"}})
    adapter = Adapters(settings, Store(settings.data_dir), httpx.AsyncClient(transport=httpx.MockTransport(mock)))
    with pytest.raises(AdapterError, match="llm_invalid_json_after_repair"):
        await adapter.llm("draft-email", {"test": "fixture"}, Draft, writing=True)
    assert len(requests) == 2 and requests[0]["format"]["properties"]["status"]["const"] == "draft"
    assert requests[0]["stream"] is False and requests[0]["think"] is False
    await adapter.client.aclose()


@pytest.mark.parametrize("status", [401, 402, 403])
async def test_non_retryable_service_errors(settings, status):
    calls = []
    def mock(req):
        calls.append(req)
        return httpx.Response(status, text="Sensitive remote body")
    adapter = Adapters(settings, Store(settings.data_dir), httpx.AsyncClient(transport=httpx.MockTransport(mock)))
    with pytest.raises(AdapterError, match=f"service_http_{status}"):
        await adapter.request("GET", "http://service.test")
    assert len(calls) == 1
    await adapter.client.aclose()


async def test_retry_429_then_success(settings, monkeypatch):
    requests = []
    async def no_delay(*a): pass
    monkeypatch.setattr(asyncio, "sleep", no_delay)
    def mock(req):
        requests.append(req)
        return httpx.Response(429 if len(requests) == 1 else 200, json={"ok": True})
    adapter = Adapters(settings, Store(settings.data_dir), httpx.AsyncClient(transport=httpx.MockTransport(mock)))
    assert (await adapter.request("GET", "http://service.test")).json()["ok"]
    assert adapter.retries == 1
    await adapter.client.aclose()


async def test_stirling_off_text_pdf_and_scan(settings):
    adapter = Adapters(settings, Store(settings.data_dir))
    assert "Python" in await adapter.pdf_text(pdf_bytes())
    with pytest.raises(AdapterError, match="ocr_required_enable_stirling_or_upload_text_pdf"):
        await adapter.pdf_text(pdf_bytes(""))
    await adapter.client.aclose()


async def test_stirling_enabled_openapi_multipart_and_reextract(settings):
    settings.stirling_enabled = True
    settings.stirling_url = "http://stirling.local"
    settings.stirling_key = "fake-key-not-a-secret"
    requests = []
    def mock(req):
        requests.append(req)
        if req.method == "GET":
            return httpx.Response(200, json={"paths": {"/api/v1/misc/ocr-pdf": {}}})
        assert req.headers["X-API-KEY"] == settings.stirling_key
        assert b'name="fileInput"' in req.content and req.content.count(b'name="languages"') == 2
        return httpx.Response(200, content=pdf_bytes())
    adapter = Adapters(settings, Store(settings.data_dir), httpx.AsyncClient(transport=httpx.MockTransport(mock)))
    assert "Python" in await adapter.pdf_text(pdf_bytes(""))
    assert len(requests) == 2
    await adapter.client.aclose()


async def test_nextcloud_off_and_safe_paths(settings):
    adapter = Adapters(settings, Store(settings.data_dir))
    with pytest.raises(AdapterError, match="nextcloud_disabled"):
        await adapter.dav_import("cv.pdf")
    settings.nextcloud_enabled = True
    settings.nextcloud_url = "http://nextcloud.local/allowed"
    for path in ("../private/cv.pdf", "/cv.pdf", "%2e%2e/secret", "a\\..\\secret", "a/./cv.pdf"):
        with pytest.raises(AdapterError):
            adapter.dav_path(path)
    assert adapter.dav_path("CV prova.pdf") == "http://nextcloud.local/allowed/CV%20prova.pdf"
    await adapter.client.aclose()


async def test_webdav_get_put_no_overwrite(settings):
    settings.nextcloud_enabled, settings.nextcloud_url = True, "http://nextcloud.local/allowed"
    requests = []
    def mock(req):
        requests.append(req)
        if req.method == "GET": return httpx.Response(200, content=pdf_bytes())
        assert req.method == "PUT" and req.headers["If-None-Match"] == "*"
        return httpx.Response(201)
    adapter = Adapters(settings, Store(settings.data_dir), httpx.AsyncClient(transport=httpx.MockTransport(mock)))
    assert (await adapter.dav_import("cv.pdf")).startswith(b"%PDF-")
    await adapter.dav_export("report.json", b"{}", "application/json")
    assert [r.method for r in requests] == ["GET", "PUT"]
    await adapter.client.aclose()


async def test_crawl_sanitizes_raw_html_and_cache(settings):
    requests = []
    def mock(req):
        payload = json.loads(req.content)
        requests.append(payload)
        raw = payload["urls"][0]
        assert raw.startswith("raw:") and "<script" not in raw and "<iframe" not in raw and "src=" not in raw
        # 0.9.5 defaults raw HTML to the non-browser path, and refuses these knobs over HTTP.
        assert "process_in_browser" not in payload["crawler_config"]["params"]
        assert "base_url" not in payload["crawler_config"]["params"]
        return httpx.Response(200, json={"results": [{"success": True, "markdown": {"raw_markdown": "Azienda fittizia"}}]})
    adapter = Adapters(settings, Store(settings.data_dir), httpx.AsyncClient(transport=httpx.MockTransport(mock)))
    async def public(url):
        if url.endswith("robots.txt"): return Page(url, "User-agent: *\nAllow: /", "text/plain")
        return Page(url, '<h1>Azienda fittizia</h1><script>bad()</script><iframe src="http://127.0.0.1"></iframe><img src="http://10.0.0.1"><a href="/contatti">Contatti</a>', "text/html")
    adapter.public_fetch = public
    page = await adapter.crawl("https://example.org/")
    assert page["links"] == ["https://example.org/contatti"]
    assert await adapter.crawl("https://example.org/") == page
    assert len(requests) == 1
    await adapter.client.aclose()


async def test_robots_refused(settings):
    adapter = Adapters(settings, Store(settings.data_dir))
    async def public(url): return Page(url, "User-agent: *\nDisallow: /", "text/plain")
    adapter.public_fetch = public
    with pytest.raises(AdapterError, match="robots_disallowed"):
        await adapter.crawl("https://example.org/")
    await adapter.client.aclose()


@pytest.mark.parametrize("value", ["=HYPERLINK(\"http://example.org\")", "+SUM(1,1)", "-1+2", "@cmd", "\t =1"])
def test_csv_formula_escape(value):
    assert safe_cell(value).startswith("'")


def test_distance_and_evidence():
    assert haversine([45.07, 7.69], [45.07, 7.69]) == 0
    assert 120 < haversine([45.07, 7.69], [45.46, 9.19]) < 130
    item = Contact(person_name=None, role=None, email="inventata@example.org", category="general",
                   source_url="https://wrong.example/", quote="Una citazione reale")
    assert not evidence_valid(item, [{"url": "https://example.org/", "text": "Una citazione reale"}])
