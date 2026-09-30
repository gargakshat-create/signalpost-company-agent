from __future__ import annotations

import re
from typing import Any

from pypdf import PdfReader

from .constants import BRREG_ACCOUNTS_PDF_URL
from .http import HttpClient
from .models import Fact, Profile, Source
from .utils import compact_text


def extract_pdf_text(body: bytes) -> str:
    import io
    reader = PdfReader(io.BytesIO(body))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    return compact_text("\n".join(chunks), 120_000)


def _parse_number(token: str) -> int | float | None:
    t = token.replace("\u00a0", " ").strip()
    # Norwegian/European style and plain accounting values.
    t = re.sub(r"[^0-9,.-]", "", t)
    if not t or t in {"-", ".", ","}:
        return None
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        parts = t.split(",")
        t = "".join(parts) if len(parts[-1]) == 3 else t.replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        n = float(t)
        return int(n) if n.is_integer() else n
    except ValueError:
        return None


def _find_metric(text: str, labels: list[str]) -> int | float | None:
    # Keep extraction deliberately narrow: a label followed nearby by the first plausible accounting number.
    for label in labels:
        m = re.search(rf"{re.escape(label)}[^0-9-]{{0,160}}([-\d][\d .\u00a0,]*)", text, flags=re.I)
        if m:
            return _parse_number(m.group(1))
    return None


def enrich_financials(orgnr: str, year: int, http: HttpClient, profile: Profile) -> list[Fact]:
    url = BRREG_ACCOUNTS_PDF_URL.format(orgnr=orgnr, year=year)
    r = http.get(url)
    if r.status >= 400:
        return []
    try:
        text = extract_pdf_text(r.body)
    except Exception:
        return []
    if not text:
        return []
    src = Source(url=r.url, retrieved_at=r.retrieved_at, source_type="brreg_annual_accounts", title=f"Brønnøysund Register Centre — annual accounts {year}")
    period = f"{year}-12-31"
    definitions: dict[str, list[str]] = {
        "revenue": ["Driftsinntekter", "Operating income", "Revenue"],
        "operating_profit": ["Driftsresultat", "Operating profit"],
        "profit_or_loss": ["Årsresultat", "Årsresultat før skatt", "Resultat etter skatt", "Profit for the year", "Profit/(loss)"],
        "equity": ["Sum egenkapital", "Total equity"],
        "assets": ["Sum eiendeler", "Total assets"],
        "liabilities": ["Sum gjeld", "Total liabilities"],
    }
    facts: list[Fact] = []
    for field, labels in definitions.items():
        value = _find_metric(text, labels)
        if value is not None:
            fact = Fact(field, value, src, period=period, confidence=0.85)
            profile.financials[field] = fact
            facts.append(fact)
    return facts
