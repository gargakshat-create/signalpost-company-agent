from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Source:
    url: str
    retrieved_at: str
    source_type: str
    published_at: str | None = None
    title: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Fact:
    field: str
    value: Any
    source: Source
    period: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.to_dict()
        return d


@dataclass
class Profile:
    organisation_number: str
    legal_name: str | None = None
    description: str | None = None
    registered_address: str | None = None
    postal_address: str | None = None
    municipality: str | None = None
    county: str | None = None
    organization_form: str | None = None
    status: str | None = None
    registration_date: str | None = None
    establishment_date: str | None = None
    industry: dict[str, Any] | None = None
    employees: Fact | None = None
    financials: dict[str, Fact] = field(default_factory=dict)
    roles: list[Fact] = field(default_factory=list)
    jobs: list[dict[str, Any]] = field(default_factory=list)
    public_activity: list[dict[str, Any]] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)

    def all_facts(self) -> list[Fact]:
        facts = list(self.facts)
        if self.employees:
            facts.append(self.employees)
        facts.extend(self.financials.values())
        facts.extend(self.roles)
        return facts


@dataclass
class ResultEnvelope:
    organisation_number: str
    state: str
    profile: dict[str, Any] | None
    changes: list[dict[str, Any]]
    unknown: list[str]
    sources: list[dict[str, Any]]
    generated_at: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.error is None:
            d.pop("error", None)
        return d
