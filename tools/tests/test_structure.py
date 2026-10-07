import glob
import os
import unittest

from helpers import make_flopack, methods, clone, FLO_ID
from flopack.structure import validate


class StructureTest(unittest.TestCase):
    def test_minimal_flopack_is_valid(self):
        errors, warnings = validate(make_flopack())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_config_with_secret_data_is_error(self):
        doc = make_flopack()
        doc["data"]["configs"]["33333333-3333-4333-8333-333333333333"] = {
            "id": "33333333-3333-4333-8333-333333333333", "name": "Fleet API", "module": "httpfunctions",
            "data": {"token": "secret"}}
        errors, _ = validate(doc)
        self.assertTrue(any("non-null data" in e for e in errors), errors)

    def test_pin_to_missing_card_is_error(self):
        doc = make_flopack()
        methods(doc)[0]["pins"] = {"outRecord1": {"noSuchCard": [{"input": "x", "transform": None}]}}
        errors, _ = validate(doc)
        self.assertTrue(any("noSuchCard" in e for e in errors), errors)

    def test_ordering_to_unknown_card_is_error(self):
        doc = make_flopack()
        doc["data"]["flos"][FLO_ID]["data"]["orderings"]["ord2"] = ["assignCrd1", "ghostCard1"]
        errors, _ = validate(doc)
        self.assertTrue(any("ghostCard1" in e for e in errors), errors)

    def test_duplicate_card_uuid_is_error(self):
        doc = make_flopack()
        methods(doc).append(clone(methods(doc)[1]))
        errors, _ = validate(doc)
        self.assertTrue(any("duplicate method uuid" in e for e in errors), errors)

    def test_checksum_is_warning_not_error(self):
        doc = make_flopack()
        doc["checksum"] = "0" * 64
        errors, warnings = validate(doc)
        self.assertEqual(errors, [])
        self.assertTrue(any("checksum" in w for w in warnings), warnings)

    @unittest.skipUnless(os.environ.get("OKTA_TEMPLATES_DIR"), "set OKTA_TEMPLATES_DIR to run the corpus check")
    def test_all_okta_templates_have_no_errors(self):
        import json
        paths = glob.glob(os.path.join(os.environ["OKTA_TEMPLATES_DIR"], "workflows", "*", "*.flopack"))
        self.assertGreater(len(paths), 100)
        for p in paths:
            with open(p) as f:
                errors, _ = validate(json.load(f))
            self.assertEqual(errors, [], p)
