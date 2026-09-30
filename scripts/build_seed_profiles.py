from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def read_orgnrs(path: Path, limit: int) -> list[str]:
    out: list[str] = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if len(out) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                value = obj.get("organisation_number") or obj.get("orgnr") or obj.get("organization_number")
            else:
                value = obj
            if value:
                out.append(str(value).zfill(9))
    return list(dict.fromkeys(out))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/build_seed_profiles.py /path/to/signalpost-company-universe-2025.jsonl.gz [limit]", file=sys.stderr)
        print("   or: python scripts/build_seed_profiles.py --download [limit]", file=sys.stderr)
        return 2
    if sys.argv[1] == "--download":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
        url = "https://www.builderr.ai/signalpost-company-universe-2025.jsonl.gz"
        target = ROOT / "data" / "signalpost-company-universe-2025.jsonl.gz"
        print(f"downloading {url} -> {target}", file=sys.stderr)
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        with target.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
        source = target
    else:
        source = Path(sys.argv[1])
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    orgnrs = read_orgnrs(source, limit)
    tmp = ROOT / "data" / "seed_input.jsonl"
    tmp.write_text("".join(json.dumps({"organisation_number": o}) + "\n" for o in orgnrs), encoding="utf-8")
    profiles = ROOT / "profiles"
    profiles.mkdir(exist_ok=True)
    out_jsonl = profiles / "profiles.jsonl"
    with out_jsonl.open("w", encoding="utf-8") as out:
        subprocess.run([sys.executable, "-m", "signalpost.run", str(tmp)], stdout=out, cwd=ROOT, check=True)
    (profiles / "organisation_numbers.txt").write_text("\n".join(orgnrs) + "\n", encoding="utf-8")
    manifest = {
        "count": len(orgnrs),
        "source_universe": source.name,
        "profiles": out_jsonl.name,
        "organisation_numbers": "organisation_numbers.txt",
        "generated_by": "scripts/build_seed_profiles.py",
    }
    (profiles / "profile_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"generated {len(orgnrs)} profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
