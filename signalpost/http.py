from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests

from .constants import DEFAULT_MAX_BYTES, DEFAULT_MAX_REQUESTS, DEFAULT_TIMEOUT, USER_AGENT
from .utils import now_iso, safe_http_url, sha256_text

log = logging.getLogger(__name__)


class RequestBudgetExceeded(RuntimeError):
    pass


@dataclass
class HttpResponse:
    status: int
    url: str
    headers: dict[str, str]
    body: bytes
    retrieved_at: str
    from_cache: bool = False


class RequestBudget:
    def __init__(self, max_requests: int = DEFAULT_MAX_REQUESTS) -> None:
        self.max_requests = max_requests
        self.used = 0

    def charge(self) -> None:
        if self.used >= self.max_requests:
            raise RequestBudgetExceeded(f"request budget exceeded ({self.max_requests})")
        self.used += 1


class HttpClient:
    def __init__(self, budget: RequestBudget, db: sqlite3.Connection, timeout: int = DEFAULT_TIMEOUT, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self.budget = budget
        self.db = db
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en,nb;q=0.8,no;q=0.7"})
        self._init_cache()

    def _init_cache(self) -> None:
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS http_cache (
                url TEXT PRIMARY KEY,
                status INTEGER NOT NULL,
                final_url TEXT NOT NULL,
                headers_json TEXT NOT NULL,
                body BLOB NOT NULL,
                retrieved_at TEXT NOT NULL,
                sha256 TEXT NOT NULL
            )"""
        )
        self.db.commit()

    def _cache_get(self, url: str) -> Optional[HttpResponse]:
        row = self.db.execute(
            "SELECT status, final_url, headers_json, body, retrieved_at FROM http_cache WHERE url = ?", (url,)
        ).fetchone()
        if not row:
            return None
        import json
        return HttpResponse(row[0], row[1], json.loads(row[2]), row[3], row[4], True)

    def _cache_put(self, url: str, response: HttpResponse) -> None:
        import json
        self.db.execute(
            """INSERT INTO http_cache(url,status,final_url,headers_json,body,retrieved_at,sha256)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(url) DO UPDATE SET status=excluded.status, final_url=excluded.final_url,
                 headers_json=excluded.headers_json, body=excluded.body, retrieved_at=excluded.retrieved_at,
                 sha256=excluded.sha256""",
            (
                url,
                response.status,
                response.url,
                json.dumps(response.headers, ensure_ascii=False),
                response.body,
                response.retrieved_at,
                sha256_text(response.body.decode("utf-8", errors="replace")),
            ),
        )
        self.db.commit()

    def get(self, url: str, allowed_hostname: str | None = None, allow_cached: bool = True) -> HttpResponse:
        normalized = safe_http_url(url, allowed_hostname=allowed_hostname)
        if not normalized:
            raise ValueError(f"unsafe URL blocked: {url}")
        cached = self._cache_get(normalized) if allow_cached else None
        if cached:
            return cached
        self.budget.charge()
        response = self.session.get(normalized, timeout=self.timeout, allow_redirects=True, stream=True)
        final_url = response.url
        # Validate the final destination after redirects.
        if not safe_http_url(final_url, allowed_hostname=allowed_hostname):
            response.close()
            raise ValueError(f"unsafe redirect blocked: {final_url}")
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > self.max_bytes
            except (TypeError, ValueError):
                too_large = False
            if too_large:
                response.close()
                raise ValueError("response too large")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=32_768):
            if chunk:
                body.extend(chunk)
                if len(body) > self.max_bytes:
                    response.close()
                    raise ValueError("response too large")
        response.close()
        result = HttpResponse(response.status_code, final_url, dict(response.headers), bytes(body), now_iso(), False)
        self._cache_put(normalized, result)
        return result

    def get_text(self, url: str, allowed_hostname: str | None = None) -> HttpResponse:
        return self.get(url, allowed_hostname=allowed_hostname)
