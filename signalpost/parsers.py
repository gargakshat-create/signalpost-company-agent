from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from .utils import compact_text


def parse_html_document(body: bytes, base_url: str) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = compact_text(soup.title.get_text(" ", strip=True) if soup.title else "", 300)
    meta_desc = ""
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    std_desc = soup.find("meta", attrs={"name": "description"})
    if og_desc and og_desc.get("content"):
        meta_desc = compact_text(og_desc["content"], 1200)
    elif std_desc and std_desc.get("content"):
        meta_desc = compact_text(std_desc["content"], 1200)
    body_text = compact_text(soup.get_text(" ", strip=True), 12000)
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        label = compact_text(a.get_text(" ", strip=True), 300)
        if href:
            links.append({"href": href, "label": label})
    return {"title": title, "description": meta_desc, "text": body_text, "links": links}


def extract_date(text: str) -> str | None:
    m = re.search(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b", text)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def pick_company_description(parsed: dict[str, Any]) -> str | None:
    desc = parsed.get("description")
    if desc and len(desc) >= 40:
        return desc
    text = parsed.get("text", "")
    # Prefer a short leading sentence instead of claiming an entire page is a description.
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences[:12]:
        s = compact_text(sentence, 700)
        if 60 <= len(s) <= 700:
            return s
    return None


def classify_links(links: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    result = {"jobs": [], "activity": [], "about": []}
    job_words = re.compile(r"job|career|careers|vacanc|ledig|stilling|work with us|join us", re.I)
    activity_words = re.compile(r"news|nyhet|aktuelt|press|blog|insight|article|media", re.I)
    about_words = re.compile(r"about|om oss|who we are|what we do", re.I)
    for link in links:
        hay = f"{link.get('label','')} {link.get('href','')}"
        if job_words.search(hay):
            result["jobs"].append(link)
        if activity_words.search(hay):
            result["activity"].append(link)
        if about_words.search(hay):
            result["about"].append(link)
    return result


def extract_jobs(parsed: dict[str, Any], page_url: str) -> list[dict[str, Any]]:
    matches = []
    lower = parsed.get("text", "").lower()
    if any(term in lower for term in ["job", "career", "vacancy", "stilling", "ledig"]):
        matches.append({"title": parsed.get("title") or "Careers", "url": page_url, "summary": pick_company_description(parsed)})
    return matches


def extract_activity(parsed: dict[str, Any], page_url: str) -> list[dict[str, Any]]:
    lower = parsed.get("text", "").lower()
    date = extract_date(parsed.get("text", ""))
    if any(term in lower for term in ["news", "nyhet", "press", "aktuelt", "blog"]):
        return [{"title": parsed.get("title") or "Public activity", "url": page_url, "date": date, "summary": pick_company_description(parsed)}]
    return []
