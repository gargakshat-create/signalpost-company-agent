import unittest
from signalpost.parsers import parse_html_document, pick_company_description


class ParserTest(unittest.TestCase):
    def test_meta_description(self):
        html = b'''<html><head><title>Acme</title><meta name="description" content="A fictional company for a local unit test."></head><body><h1>Acme</h1></body></html>'''
        parsed = parse_html_document(html, "https://example.test")
        self.assertEqual(parsed["title"], "Acme")
        self.assertEqual(pick_company_description(parsed), "A fictional company for a local unit test.")


if __name__ == "__main__":
    unittest.main()
