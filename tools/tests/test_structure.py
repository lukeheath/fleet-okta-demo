import glob
import os
import unittest

from helpers import card, make_flopack, methods, clone, FLO_ID
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

    # Okta's importer fails with 500 "TypeError: flo.id is not a function" when a value has
    # collection: true but its data isn't a list. Across the 127 templates, such data is
    # always a list or null.
    def _with_list_value(self, io, data):
        doc = make_flopack()
        methods(doc)[1]["node"]["model"][io]["data"]["listVal001"] = {
            "id": "listVal001", "key": "hosts", "value": {"type": "object", "collection": True, "data": data}}
        return doc

    def _collection_errors(self, doc):
        errors, _ = validate(doc)
        return [e for e in errors if "collection" in e]

    def test_list_value_with_string_data_is_error(self):
        for io in ("inputs", "outputs"):
            with self.subTest(io=io):
                errors = self._collection_errors(self._with_list_value(io, ""))
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("[]", errors[0])
                self.assertIn("assignCrd1", errors[0])
                self.assertIn("root:kernel:object:0.0.1:assign", errors[0])
                self.assertIn("hosts", errors[0])

    def test_list_value_with_object_data_is_error(self):
        for io in ("inputs", "outputs"):
            with self.subTest(io=io):
                errors = self._collection_errors(self._with_list_value(io, {}))
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("[]", errors[0])

    def test_list_value_with_list_or_null_data_is_valid(self):
        for io in ("inputs", "outputs"):
            for data in ([], ["x"], None):
                with self.subTest(io=io, data=data):
                    errors, _ = validate(self._with_list_value(io, data))
                    self.assertEqual(errors, [])

    def test_list_value_with_string_data_in_inline_flow_is_error(self):
        doc = make_flopack()
        inner = card("innerCrd01", "object", "get",
                     outputs={"innerOut01": {"id": "innerOut01", "key": "hosts",
                                             "value": {"type": "object", "collection": True, "data": ""}}})
        inline = {"id": "44444444-4444-4444-8444-444444444444", "uuid": "44444444-4444-4444-8444-444444444444",
                  "methods": [inner], "orderings": {}}
        methods(doc)[1]["node"]["model"]["inputs"]["data"]["inlineFlo1"] = {
            "id": "inlineFlo1", "key": "flo", "value": {"type": "flo", "data": inline}}
        errors = self._collection_errors(doc)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("innerCrd01", errors[0])

    @unittest.skipUnless(os.environ.get("OKTA_TEMPLATES_DIR"), "set OKTA_TEMPLATES_DIR to run the corpus check")
    def test_all_okta_templates_have_no_errors(self):
        import json
        paths = glob.glob(os.path.join(os.environ["OKTA_TEMPLATES_DIR"], "workflows", "*", "*.flopack"))
        self.assertGreater(len(paths), 100)
        for p in paths:
            with open(p) as f:
                errors, _ = validate(json.load(f))
            self.assertEqual(errors, [], p)
