"""Download pubblici con IP fissato al socket e nuova verifica per ogni redirect."""
from dataclasses import dataclass
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit, urlunsplit, urljoin


class WebError(ValueError):
    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)


def canonical_url(url):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise WebError("invalid_url")
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise WebError("invalid_url")
    try:
        port = p.port
    except ValueError as exc:
        raise WebError("invalid_port") from exc
    if port not in (None, 80 if p.scheme == "http" else 443):
        raise WebError("disallowed_port")
    host = p.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    if ":" in host:
        host = "[" + host + "]"
    return urlunsplit((p.scheme, host, p.path or "/", p.query, ""))


def public_addresses(host, port):
    try:
        answers = list(dict.fromkeys(a[4][0] for a in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)))
    except OSError as exc:
        raise WebError("dns_failed") from exc
    if not answers:
        raise WebError("dns_failed")
    for value in answers:
        ip = ipaddress.ip_address(value)
        # IPv4 mapped IPv6, Teredo, 6to4 and all non-global ranges are refused.
        if not ip.is_global or ip.is_multicast or ip.is_reserved or getattr(ip, "ipv4_mapped", None) or getattr(ip, "sixtofour", None) or getattr(ip, "teredo", None):
            raise WebError("ssrf_blocked")
    return answers


class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, ip, tls, timeout):
        super().__init__(host, port, timeout=timeout)
        self.ip, self.tls = ip, tls

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)
        if self.tls:
            self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)


@dataclass
class Page:
    url: str
    text: str
    content_type: str


def fetch_public(url, user_agent, timeout=20, max_bytes=2_000_000):
    deadline = time.monotonic() + timeout
    for _ in range(5):
        url = canonical_url(url)
        p = urlsplit(url)
        port = 443 if p.scheme == "https" else 80
        ips = public_addresses(p.hostname, port)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise WebError("public_request_timeout")
        conn = PinnedConnection(p.hostname, port, ips[0], p.scheme == "https", remaining)
        try:
            conn.request("GET", urlunsplit(("", "", p.path, p.query, "")),
                         headers={"User-Agent": user_agent, "Accept": "text/html,text/plain", "Accept-Encoding": "identity"})
            res = conn.getresponse()
            if res.status in (301, 302, 303, 307, 308):
                target = res.getheader("Location")
                if not target:
                    raise WebError("invalid_redirect")
                url = urljoin(url, target)
                continue
            if res.status >= 400:
                raise WebError(f"http_{res.status}", res.status)
            typ = res.getheader("Content-Type", "").lower()
            if not ("text/html" in typ or "text/plain" in typ or "application/xhtml+xml" in typ):
                raise WebError("unsupported_content_type")
            if res.getheader("Content-Encoding", "identity") not in ("identity", ""):
                raise WebError("unsupported_encoding")
            raw = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WebError("public_request_timeout")
                if conn.sock:
                    conn.sock.settimeout(remaining)
                chunk = res.read1(min(65536, max_bytes + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > max_bytes:
                    raise WebError("page_too_large")
            if len(raw) > max_bytes:
                raise WebError("page_too_large")
            return Page(url, raw.decode("utf-8", errors="replace"), typ)
        except (OSError, http.client.HTTPException) as exc:
            raise WebError("network_error") from exc
        finally:
            conn.close()
    raise WebError("too_many_redirects")
