from __future__ import annotations

import logging
from collections import deque
from urllib.parse import urljoin, urlparse

from .constants import DEFAULT_MAX_PAGE_LINKS
from .http import HttpClient
from .models import Fact, Profile, Source
from .parsers import classify_links, extract_activity, extract_jobs, parse_html_document, pick_company_description
from .utils import absolute_url, safe_http_url, source_host

log = logging.getLogger(__name__)


class WebsiteCrawler:
    def __init__(self, http: HttpClient, max_pages: int = DEFAULT_MAX_PAGE_LINKS) -> None:
        self.http = http
        self.max_pages = max_pages

    def crawl(self, website: str, profile: Profile) -> None:
        website = safe_http_url(website)
        if not website:
            return
        host = source_host(website)
        if not host:
            return
        # Try the canonical website and only same-site links.
        queue = deque([website])
        seen: set[str] = set()
        pages = []
        while queue and len(pages) < self.max_pages:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            try:
                r = self.http.get(url, allowed_hostname=host)
            except Exception as exc:
                log.debug("website fetch failed %s: %s", url, exc)
                continue
            ctype = r.headers.get("content-type", "")
            if "text/html" not in ctype and not r.body.lstrip().startswith(b"<"):
                continue
            parsed = parse_html_document(r.body, r.url)
            src = Source(url=r.url, retrieved_at=r.retrieved_at, source_type="company_website", title=parsed.get("title"))
            pages.append((parsed, src, r.url))
            classified = classify_links(parsed.get("links", []))
            for bucket in ("about", "jobs", "activity"):
                for link in classified[bucket][:4]:
                    absu = absolute_url(r.url, link.get("href", ""))
                    if not absu:
                        continue
                    if safe_http_url(absu, allowed_hostname=host) and absu not in seen and absu not in queue:
                        queue.append(absu)
                    if len(queue) > self.max_pages * 2:
                        break

        # Prefer homepage/about as the description source.
        for parsed, src, page_url in pages:
            desc = pick_company_description(parsed)
            if desc and not profile.description:
                profile.description = desc
                profile.facts.append(Fact("description", desc, src))
            for job in extract_jobs(parsed, page_url):
                job["source"] = src.url
                job["retrieved_at"] = src.retrieved_at
                profile.jobs.append(job)
            for item in extract_activity(parsed, page_url):
                item["source"] = src.url
                item["retrieved_at"] = src.retrieved_at
                profile.public_activity.append(item)

        # De-duplicate by URL/title to keep refreshes clean.
        profile.jobs = _dedupe_items(profile.jobs)
        profile.public_activity = _dedupe_items(profile.public_activity)


def _dedupe_items(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple] = set()
    for item in items:
        key = (item.get("url"), item.get("title"), item.get("date"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
