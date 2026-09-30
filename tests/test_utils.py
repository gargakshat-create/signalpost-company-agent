import unittest
from signalpost.utils import normalize_orgnr, safe_http_url


class UtilsTest(unittest.TestCase):
    def test_normalize_orgnr(self):
        self.assertEqual(normalize_orgnr("983890593"), "983890593")
        self.assertEqual(normalize_orgnr("12345678"), "012345678")

    def test_safe_url_blocks_non_http(self):
        self.assertIsNone(safe_http_url("file:///etc/passwd"))
        self.assertIsNone(safe_http_url("http://localhost/foo"))


if __name__ == "__main__":
    unittest.main()
