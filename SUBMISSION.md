# Signalpost submission checklist

**Project:** NordicTrace

**Repository:** push this folder to the participant's Git host and paste the resulting repository URL here.

**Exact commit:** see `GIT_COMMIT.txt`. After pushing, submit that commit hash.

**One command:**

```bash
python -m pip install -r requirements.txt && python -m signalpost.run /path/to/companies.jsonl > output.jsonl
```

**Model/API disclosure:** no LLM is required; official Brønnøysund Register Centre public APIs plus company websites.

**Expected external API cost:** USD 0 per 100-company run under the default configuration.

**Code licence:** MIT. See `LICENSE`.

**Contact:** replace the placeholders below before sending.

- Participant name: `AKSHAT`
- Email: `<YOUR_EMAIL>`
- Repository URL: `<YOUR_REPOSITORY_URL>`

## Required seed artifacts

Before submission, run `scripts/build_seed_profiles.py` against Builderr's supplied eligible-company universe and verify that:

- `profiles/profiles.jsonl` contains at least 1,000 completed profiles;
- `profiles/organisation_numbers.txt` contains the same organisation numbers, one per line;
- no profile contains fabricated values;
- each available fact has evidence and retrieval/period dates;
- missing information is represented explicitly.

The package intentionally does not manufacture a fake 1,000-company corpus.
