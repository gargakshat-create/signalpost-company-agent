from __future__ import annotations

from typing import Any

from .constants import BRREG_ACCOUNTS_PDF_URL, BRREG_ACCOUNTS_YEARS_URL, BRREG_ENTITY_URL, BRREG_ROLES_URL
from .http import HttpClient
from .models import Fact, Profile, Source
from .utils import now_iso


def _json(resp) -> Any:
    import json
    return json.loads(resp.body.decode("utf-8"))


def _address(payload: dict[str, Any], key: str) -> str | None:
    addr = payload.get(key) or []
    if isinstance(addr, dict):
        addr = [addr]
    if not addr:
        return None
    parts: list[str] = []
    first = addr[0] if isinstance(addr[0], dict) else {}
    for k in ("adresse", "postnummer", "poststed", "landkode"):
        v = first.get(k)
        if v:
            parts.append(str(v))
    return ", ".join(parts) if parts else None


def resolve_entity(orgnr: str, http: HttpClient) -> tuple[dict[str, Any], Source]:
    url = BRREG_ENTITY_URL.format(orgnr=orgnr)
    r = http.get(url)
    if r.status == 404:
        raise LookupError("organisation number not found")
    if r.status >= 400:
        raise RuntimeError(f"Brreg entity HTTP {r.status}")
    payload = _json(r)
    src = Source(url=r.url, retrieved_at=r.retrieved_at, source_type="brreg_entity", title="Brønnøysund Register Centre — entity")
    return payload, src


def build_profile_from_entity(orgnr: str, payload: dict[str, Any], source: Source) -> Profile:
    p = Profile(organisation_number=orgnr)
    p.legal_name = payload.get("navn")
    p.registered_address = _address(payload, "forretningsadresse")
    p.postal_address = _address(payload, "postadresse")
    p.municipality = (payload.get("forretningsadresse") or [{}])[0].get("kommune") if isinstance(payload.get("forretningsadresse"), list) else None
    p.county = (payload.get("forretningsadresse") or [{}])[0].get("kommunenummer") if isinstance(payload.get("forretningsadresse"), list) else None
    form = payload.get("organisasjonsform") or {}
    p.organization_form = form.get("beskrivelse") or form.get("kode")
    p.status = "inactive" if payload.get("registrertIFrivillighetsregisteret") is False and payload.get("slettedato") else "active"
    p.registration_date = payload.get("registreringsdatoEnhetsregisteret")
    p.establishment_date = payload.get("stiftelsesdato")
    naering = payload.get("naeringskode1") or {}
    p.industry = {"code": naering.get("kode"), "description": naering.get("beskrivelse")} if naering else None
    if payload.get("hjemmeside"):
        p.facts.append(Fact("website", payload["hjemmeside"], source, period=None))
    for key in ("forretningsadresse", "postadresse", "organisasjonsform", "registreringsdatoEnhetsregisteret", "stiftelsesdato"):
        val = payload.get(key)
        if val is not None and key not in {"forretningsadresse", "postadresse"}:
            p.facts.append(Fact(key, val, source, period=None))
    if p.registered_address:
        p.facts.append(Fact("registered_address", p.registered_address, source))
    if p.postal_address:
        p.facts.append(Fact("postal_address", p.postal_address, source))
    if p.legal_name:
        p.facts.append(Fact("legal_name", p.legal_name, source))
    if p.organization_form:
        p.facts.append(Fact("organization_form", p.organization_form, source))
    if p.registration_date:
        p.facts.append(Fact("registration_date", p.registration_date, source, period=p.registration_date))
    if p.establishment_date:
        p.facts.append(Fact("establishment_date", p.establishment_date, source, period=p.establishment_date))
    if p.industry:
        p.facts.append(Fact("industry_code", p.industry.get("code"), source))
        p.facts.append(Fact("industry_description", p.industry.get("description"), source))
    return p


def fetch_roles(orgnr: str, http: HttpClient, profile: Profile) -> list[Fact]:
    url = BRREG_ROLES_URL.format(orgnr=orgnr)
    r = http.get(url)
    if r.status >= 400:
        return []
    payload = _json(r)
    src = Source(url=r.url, retrieved_at=r.retrieved_at, source_type="brreg_roles", title="Brønnøysund Register Centre — roles")
    out: list[Fact] = []
    for group in payload.get("rollegrupper", []) or []:
        for role in group.get("roller", []) or []:
            person = role.get("person") or {}
            name = person.get("navn")
            rtype = (role.get("type") or {}).get("beskrivelse") or (role.get("type") or {}).get("kode")
            if name and rtype:
                out.append(Fact("role", {"type": rtype, "name": name}, src, period=group.get("sistEndret")))
    profile.roles = out
    return out


def newest_account_year(orgnr: str, http: HttpClient) -> int | None:
    url = BRREG_ACCOUNTS_YEARS_URL.format(orgnr=orgnr)
    r = http.get(url)
    if r.status >= 400:
        return None
    try:
        payload = _json(r)
        years = payload if isinstance(payload, list) else payload.get("aar", payload.get("years", []))
        years = [int(y) for y in years if str(y).isdigit()]
        return max(years) if years else None
    except Exception:
        return None
