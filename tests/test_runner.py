import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from signalpost.runner import process_one
from signalpost.storage import StateStore
from signalpost.http import RequestBudget


class FakeResp:
    def __init__(self, body: bytes, status: int = 200, url: str = "https://example.test"):
        self.body = body
        self.status = status
        self.url = url
        self.retrieved_at = "2026-09-27T00:00:00Z"
        self.headers = {"content-type": "application/json"}


class FakeHttp:
    def __init__(self):
        self.budget = RequestBudget(99)
        self.calls = []

    def get(self, url, allowed_hostname=None):
        self.calls.append(url)
        if "/enheter/999999998" in url and not url.endswith("roller"):
            payload = {
                "organisasjonsnummer": "999999998",
                "navn": "Fixture AS",
                "organisasjonsform": {"kode": "AS", "beskrivelse": "Aksjeselskap"},
                "registreringsdatoEnhetsregisteret": "2020-01-02",
                "stiftelsesdato": "2019-12-01",
                "forretningsadresse": [{"adresse": ["Testgata 1"], "postnummer": "0001", "poststed": "Oslo", "landkode": "NO", "kommune": "Oslo"}],
                "postadresse": [{"adresse": ["Postboks 1"], "postnummer": "0001", "poststed": "Oslo", "landkode": "NO"}],
                "naeringskode1": {"kode": "62010", "beskrivelse": "Computer programming activities"},
                "hjemmeside": "https://example.test",
                "antallAnsatte": 7,
            }
            return FakeResp(json.dumps(payload).encode(), url=url)
        if url.endswith("/roller"):
            return FakeResp(json.dumps({"rollegrupper": []}).encode(), url=url)
        if "/kopi/999999998/aar" in url:
            return FakeResp(json.dumps([2025]).encode(), url=url)
        if "/kopi/999999998/2025" in url:
            return FakeResp(b"not a pdf", url=url)
        return FakeResp(b"<html><head><title>Fixture</title><meta name='description' content='A fictional company for testing only and not a real company.'></head><body><a href='/careers'>Careers</a></body></html>", url=url)


class RunnerTest(unittest.TestCase):
    def test_process_one(self):
        path = tempfile.mktemp(suffix=".sqlite3")
        store = StateStore(path)
        http = FakeHttp()
        result = process_one("999999998", http, store)
        self.assertEqual(result.state, "available")
        self.assertEqual(result.profile["employees"]["value"], 7)
        self.assertEqual(result.profile["legal_name"], "Fixture AS")
        store.close()


if __name__ == "__main__":
    unittest.main()
