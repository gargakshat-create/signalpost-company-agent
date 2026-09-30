from __future__ import annotations

DEFAULT_MAX_REQUESTS = 1800
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_MAX_PAGE_LINKS = 8
DEFAULT_DB = "signalpost_state.sqlite3"
TERMINAL_STATES = {
    "available",
    "not_available",
    "blocked",
    "not_applicable",
    "ambiguous",
    "failed",
}
USER_AGENT = "NordicTrace/1.0 (Signalpost challenge; evidence-first research agent)"
BRREG_BASE = "https://data.brreg.no/enhetsregisteret"
BRREG_ENTITY_URL = BRREG_BASE + "/api/enheter/{orgnr}"
BRREG_ROLES_URL = BRREG_BASE + "/api/enheter/{orgnr}/roller"
BRREG_ACCOUNTS_YEARS_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{orgnr}/aar"
BRREG_ACCOUNTS_PDF_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{orgnr}/{year}"
