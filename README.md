# NordicTrace — Signalpost Company Intelligence Agent

NordicTrace is a submission-ready, evidence-first agent for the Builderr **Signalpost** challenge. It accepts Norwegian organisation numbers in a batch, retrieves public company information, validates exact-company identity, attaches source URLs and dates to every fact, detects changes across refreshes, and always emits one terminal result per input company.

## Why this design

The Signalpost evaluator requires the agent to handle a runtime-supplied batch (currently 100 organisation numbers), including companies it has not seen before. It also requires source/date evidence, current updates, clear missing states, deterministic execution, pinned dependencies, and a single reproducible run command.

NordicTrace therefore uses a low-cost, evidence-first pipeline with no paid third-party API dependency:

1. Resolve the company from the official Brønnøysund Register Centre API.
2. Fetch official public roles from the same registry.
3. Fetch the newest available annual-account PDF from the official Register of Accounts and extract only text-backed financial facts.
4. Crawl a small, bounded portion of the company's own website for description, careers/jobs and public activity.
5. Apply identity locks before publishing any web-derived fact.
6. Persist facts and snapshots in SQLite; refreshes are idempotent and create changes only when the normalized value actually changes.
7. Emit an NDJSON terminal envelope for every input organisation number.

## Reproducible run

```bash
python -m pip install -r requirements.txt
python -m signalpost.run input/companies.jsonl > output.jsonl
```

At evaluation time, Builderr can pass the runtime company-number file as the first argument:

```bash
python -m signalpost.run /path/to/companies.jsonl > output.jsonl
```

Or use `SIGNALPOST_INPUT`:

```bash
SIGNALPOST_INPUT=/path/to/companies.jsonl python -m signalpost.run > output.jsonl
```

The program writes machine-readable results only to stdout. Diagnostics go to stderr.

## Input formats

The runner accepts:

- one organisation number per line (`.txt` / `.list`)
- CSV with an `organisation_number`/`orgnr` column
- JSON array of strings or objects
- JSONL with an `organisation_number`/`orgnr` field

## Terminal states

Every input gets exactly one of:

`available`, `not_available`, `blocked`, `not_applicable`, `ambiguous`, `failed`

A missing value is **never** converted to zero.

## Output shape

Each line is one JSON object:

```json
{
  "organisation_number": "983890593",
  "state": "available",
  "profile": {
    "legal_name": "...",
    "registered_address": "...",
    "industry": {"code": "...", "description": "..."},
    "employees": {"value": 42, "period": "2025-12-31", "source": {"url": "...", "retrieved_at": "..."}}
  },
  "changes": [],
  "unknown": ["financial_profit"],
  "sources": [...],
  "generated_at": "..."
}
```

The schema is deliberately evidence-centric: each published fact carries a value, a source URL, retrieval timestamp, and reporting/effective period where known.

## Source policy

The implementation is intentionally conservative and uses:

- Brønnøysund Register Centre Open Data APIs for registry identity and roles.
- Brønnøysund Register Centre Register of Accounts for annual-account PDFs.
- The company's own public website, restricted to the host declared by the registry.

No personal-ID endpoints, credentialed role endpoints, paid company-data vendors, or arbitrary third-party pages are used by the default agent.

## Cost and model disclosure

**Model:** no LLM is required for the core run. Extraction and validation are deterministic.

**External APIs:** official Brønnøysund public APIs only; no paid API key required.

**Expected third-party API cost:** USD 0 per 100-company run under the default configuration, excluding ordinary network/hosting costs.

**Licensing:** source data remains under the terms of its publishers. NordicTrace code is MIT-licensed. See `LICENSE`.

## Security and operational controls

- URL fetching is SSRF-aware: local/private/link-local/multicast/loopback IPs are blocked.
- Website crawl is limited to the registry-declared hostname.
- Requests are bounded by a global per-run budget (`SIGNALPOST_MAX_REQUESTS`, default 1800).
- HTTP timeouts, body-size limits and retry limits are enforced.
- Redirect destinations are revalidated.
- Server-side secrets are never required by the default run and are never printed.
- A persistent SQLite cache reduces duplicate source fetches on refresh.

## 1,000-profile seed requirement

The challenge requires at least 1,000 completed profiles from the supplied eligible company universe. The runtime agent itself is fully batch-capable and does not depend on a fixed company list. Because the Builderr universe is delivered as a downloadable compressed artifact that is not accessible in this offline build environment, this package **does not fabricate 1,000 companies**. Use `scripts/build_seed_profiles.py` with Builderr's supplied company-universe file to produce the required 1,000 evidence-backed profiles:

```bash
python scripts/build_seed_profiles.py /path/to/signalpost-company-universe-2025.jsonl.gz --limit 1000
```

The script produces:

- `profiles/profiles.jsonl`
- `profiles/organisation_numbers.txt`
- `profiles/profile_manifest.json`

It is intentionally impossible for this script to invent financial or company facts: every profile is fetched from the same evidence pipeline, and unavailable fields stay unavailable.

## Local smoke test

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

The test suite uses mocked local fixtures and never claims that fixture values are real companies.

## Submission metadata

See `SUBMISSION.md` for the repository/commit checklist and the information to send to Builderr.
