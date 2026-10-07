import json
import unittest

from helpers import make_flopack, dumps_min
from flopack.fmt import format_text, is_formatted


class FmtTest(unittest.TestCase):
    def test_format_is_idempotent_and_indented(self):
        text = format_text(make_flopack())
        self.assertTrue(text.endswith("}\n"))
        self.assertIn('\n  "version": "1.6.0"', text)
        self.assertEqual(format_text(json.loads(text)), text)

    def test_minified_is_not_formatted(self):
        self.assertFalse(is_formatted(dumps_min(make_flopack())))
        self.assertTrue(is_formatted(format_text(make_flopack())))

    def test_key_order_is_preserved(self):
        text = format_text(make_flopack())
        self.assertLess(text.index('"type"'), text.index('"version"'))
        self.assertLess(text.index('"version"'), text.index('"data"'))

    def test_non_ascii_is_kept_literal(self):
        doc = make_flopack()
        doc["data"]["flos"][next(iter(doc["data"]["flos"]))]["description"] = "Okta → Fleet"
        self.assertIn("Okta → Fleet", format_text(doc))
