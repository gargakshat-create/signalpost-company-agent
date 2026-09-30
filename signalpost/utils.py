from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_orgnr(raw: str) -> str:
    s = re.sub(r"\D", "", str(raw))
    if not s:
        raise ValueError("empty organisation number")
    return s.zfill(9) if len(s) < 9 else s


def stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def compact_text(value: str, limit: int = 2000) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:limit].rstrip()


def safe_http_url(url: str, allowed_hostname: str | None = None) -> str | None:
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if p.scheme not in {"http", "https"} or not p.hostname:
        return None
    host = p.hostname.rstrip(".").lower()
    if allowed_hostname:
        allowed = allowed_hostname.rstrip(".").lower()
        if host != allowed and not host.endswith("." + allowed):
            return None
    # Reject obvious non-public hostnames.
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return None
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError:
        infos = []
    for _, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
            return None
    return url


def source_host(url: str) -> str | None:
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


def absolute_url(base: str, href: str) -> str | None:
    if not href:
        return None
    return urljoin(base, href)


def text_hash(value: object) -> str:
    return sha256_text(stable_json(value))
