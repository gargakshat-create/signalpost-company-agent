from __future__ import annotations

import json
import sqlite3
from typing import Any

from .models import Fact
from .utils import now_iso, stable_json, text_hash


class StateStore:
    def __init__(self, path: str) -> None:
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS facts (
                organisation_number TEXT NOT NULL,
                field TEXT NOT NULL,
                value_json TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_type TEXT NOT NULL,
                period TEXT,
                retrieved_at TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                PRIMARY KEY (organisation_number, field, source_url, period, value_hash)
            )"""
        )
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS current_facts (
                organisation_number TEXT NOT NULL,
                field TEXT NOT NULL,
                value_json TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_type TEXT NOT NULL,
                period TEXT,
                retrieved_at TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                PRIMARY KEY (organisation_number, field)
            )"""
        )
        self.db.commit()

    def record_fact(self, orgnr: str, fact: Fact) -> dict[str, Any] | None:
        value_json = stable_json(fact.value)
        vhash = text_hash(fact.value)
        current = self.db.execute(
            "SELECT value_json, source_url, period, retrieved_at, value_hash FROM current_facts WHERE organisation_number=? AND field=?",
            (orgnr, fact.field),
        ).fetchone()
        change = None
        if current and current[4] != vhash:
            change = {
                "field": fact.field,
                "old_value": json.loads(current[0]),
                "new_value": fact.value,
                "previous_source": current[1],
                "previous_period": current[2],
                "new_source": fact.source.url,
                "new_period": fact.period,
            }
        self.db.execute(
            """INSERT OR IGNORE INTO facts(organisation_number,field,value_json,source_url,source_type,period,retrieved_at,value_hash)
               VALUES(?,?,?,?,?,?,?,?)""",
            (orgnr, fact.field, value_json, fact.source.url, fact.source.source_type, fact.period, fact.source.retrieved_at, vhash),
        )
        self.db.execute(
            """INSERT INTO current_facts(organisation_number,field,value_json,source_url,source_type,period,retrieved_at,value_hash)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(organisation_number,field) DO UPDATE SET
                 value_json=excluded.value_json, source_url=excluded.source_url, source_type=excluded.source_type,
                 period=excluded.period, retrieved_at=excluded.retrieved_at, value_hash=excluded.value_hash""",
            (orgnr, fact.field, value_json, fact.source.url, fact.source.source_type, fact.period, fact.source.retrieved_at, vhash),
        )
        self.db.commit()
        return change

    def close(self) -> None:
        self.db.close()
