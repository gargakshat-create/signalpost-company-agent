from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .constants import DEFAULT_DB, DEFAULT_MAX_REQUESTS, TERMINAL_STATES
from .finance import enrich_financials
from .http import HttpClient, RequestBudget
from .models import Fact, Profile, ResultEnvelope, Source
from .registry import build_profile_from_entity, fetch_roles, newest_account_year, resolve_entity
from .storage import StateStore
from .utils import now_iso, normalize_orgnr, safe_http_url, source_host
from .web_crawler import WebsiteCrawler

log = logging.getLogger(__name__)


def _read_inputs(path: str) -> list[str]:
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    suffix = Path(path).suffix.lower()
    values: list[Any] = []
    if suffix == ".csv":
        import csv, io
        rows = csv.DictReader(io.StringIO(text))
        for row in rows:
            values.append(row.get("organisation_number") or row.get("orgnr") or row.get("organization_number"))
    elif suffix == ".json":
        data = json.loads(text)
        values = data if isinstance(data, list) else [data]
    elif suffix in {".jsonl", ".ndjson"}:
        for line in text.splitlines():
            if not line.strip():
                continue
            values.append(json.loads(line))
    else:
        values = [line.strip() for line in text.splitlines() if line.strip()]
    orgnrs = []
    for item in values:
        if isinstance(item, dict):
            item = item.get("organisation_number") or item.get("orgnr") or item.get("organization_number")
        if item:
            orgnrs.append(normalize_orgnr(str(item)))
    return orgnrs


def _profile_dict(profile: Profile) -> dict[str, Any]:
    def fact_obj(f: Fact) -> dict[str, Any]:
        return {
            "value": f.value,
            "period": f.period,
            "confidence": f.confidence,
            "source": f.source.to_dict(),
        }

    d: dict[str, Any] = {
        "organisation_number": profile.organisation_number,
        "legal_name": profile.legal_name,
        "description": profile.description,
        "registered_address": profile.registered_address,
        "postal_address": profile.postal_address,
        "municipality": profile.municipality,
        "county": profile.county,
        "organization_form": profile.organization_form,
        "status": profile.status,
        "registration_date": profile.registration_date,
        "establishment_date": profile.establishment_date,
        "industry": profile.industry,
        "employees": fact_obj(profile.employees) if profile.employees else None,
        "financials": {k: fact_obj(v) for k, v in profile.financials.items()},
        "roles": [fact_obj(v) for v in profile.roles],
        "jobs": profile.jobs,
        "public_activity": profile.public_activity,
        "facts": [
            {"field": f.field, **fact_obj(f)} for f in profile.facts
        ],
    }
    return d


def _collect_sources(profile: Profile) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen = set()
    for fact in profile.all_facts():
        key = fact.source.url
        if key not in seen:
            seen.add(key)
            sources.append(fact.source.to_dict())
    for item in profile.jobs + profile.public_activity:
        if item.get("source") and item["source"] not in seen:
            seen.add(item["source"])
            sources.append({"url": item["source"], "retrieved_at": item.get("retrieved_at"), "source_type": "company_website"})
    return sources


def _record_profile(store: StateStore, profile: Profile) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for fact in profile.all_facts():
        if fact.value is None:
            continue
        c = store.record_fact(profile.organisation_number, fact)
        if c:
            changes.append(c)
    return changes


def process_one(orgnr: str, http: HttpClient, store: StateStore) -> ResultEnvelope:
    generated = now_iso()
    try:
        payload, src = resolve_entity(orgnr, http)
    except LookupError as exc:
        return ResultEnvelope(orgnr, "not_available", None, [], ["company_identity"], [], generated)
    except ValueError as exc:
        return ResultEnvelope(orgnr, "blocked", None, [], ["company_identity"], [], generated, str(exc))
    except Exception as exc:
        return ResultEnvelope(orgnr, "failed", None, [], ["company_identity"], [], generated, str(exc))

    profile = build_profile_from_entity(orgnr, payload, src)

    try:
        fetch_roles(orgnr, http, profile)
    except Exception as exc:
        log.debug("roles failed %s: %s", orgnr, exc)

    # Employees may be supplied by the entity API under the current API schema.
    employee_value = payload.get("antallAnsatte")
    if employee_value is not None:
        profile.employees = Fact("employees", employee_value, src, period=payload.get("oppdateringsdato"), confidence=1.0)

    website_value = payload.get("hjemmeside")
    if website_value:
        try:
            website_url = website_value if website_value.startswith("http") else "https://" + website_value
            if safe_http_url(website_url):
                WebsiteCrawler(http).crawl(website_url, profile)
        except Exception as exc:
            log.debug("website failed %s: %s", orgnr, exc)

    try:
        year = newest_account_year(orgnr, http)
        if year:
            enrich_financials(orgnr, year, http, profile)
    except Exception as exc:
        log.debug("finance failed %s: %s", orgnr, exc)

    # Identity lock for website-derived facts: the page must have been reached on the registry-declared host.
    # The crawler enforces this; we additionally verify the stored website source host here.
    if website_value:
        declared = source_host(website_value if str(website_value).startswith("http") else "https://" + str(website_value))
        for fact in profile.facts:
            if fact.field == "description" and source_host(fact.source.url) not in {declared}:
                profile.facts.remove(fact)
                profile.description = None
                break

    changes = _record_profile(store, profile)
    unknown = []
    for field, value in {
        "legal_name": profile.legal_name,
        "registered_address": profile.registered_address,
        "industry": profile.industry,
        "description": profile.description,
        "employees": profile.employees.value if profile.employees else None,
        "financial_revenue": profile.financials.get("revenue").value if profile.financials.get("revenue") else None,
        "financial_profit_or_loss": profile.financials.get("profit_or_loss").value if profile.financials.get("profit_or_loss") else None,
    }.items():
        if value is None:
            unknown.append(field)

    state = "available" if profile.legal_name else "not_available"
    summary_parts = []
    if profile.legal_name:
        summary_parts.append(profile.legal_name)
    if profile.industry and profile.industry.get("description"):
        summary_parts.append(f"operates in {profile.industry['description'].lower()}")
    if profile.description:
        summary_parts.append(profile.description[:350].strip())
    summary = ". ".join(summary_parts).strip()
    if summary and not summary.endswith("."):
        summary += "."
    if changes:
        summary += (" Changes detected: " + ", ".join(c["field"] for c in changes[:6]) + ".")
    if unknown:
        summary += (" Unknown or unavailable: " + ", ".join(unknown[:6]) + ".")
    envelope = ResultEnvelope(orgnr, state, _profile_dict(profile), changes, unknown, _collect_sources(profile), generated)
    result = envelope.to_dict()
    result["summary"] = summary or "Company identity resolved; no additional verified summary was available."
    return ResultEnvelope(orgnr, state, {**(envelope.profile or {}), "summary": result["summary"]}, changes, unknown, envelope.sources, generated, envelope.error)


def run(input_path: str) -> int:
    max_requests = int(os.environ.get("SIGNALPOST_MAX_REQUESTS", DEFAULT_MAX_REQUESTS))
    db_path = os.environ.get("SIGNALPOST_DB", DEFAULT_DB)
    orgnrs = _read_inputs(input_path)
    if not orgnrs:
        print(json.dumps({"error": "empty input"}, ensure_ascii=False), file=sys.stderr)
        return 2

    # De-duplicate only for processing, but emit one result for each input row.
    unique = list(dict.fromkeys(orgnrs))
    store = StateStore(db_path)
    budget = RequestBudget(max_requests=max_requests)
    http = HttpClient(budget, store.db)
    results: dict[str, ResultEnvelope] = {}
    try:
        for orgnr in unique:
            result = process_one(orgnr, http, store)
            results[orgnr] = result
            print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")), flush=True)
    finally:
        store.close()
    return 0
