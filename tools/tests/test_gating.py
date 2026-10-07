import json
import tempfile
import unittest

from helpers import make_flopack, write_fleet, methods
from flopack.gating import check, flopack_gating_policies, fleet_gating_policies

GATEKEEPER = """  - name: Gatekeeper enabled
    query: SELECT 1 FROM gatekeeper WHERE assessments_enabled = 1;
    webhooks_and_tickets_enabled: true
"""
CLAUDE = """  - name: Claude Code configured to org standard
    query: SELECT 1;
    webhooks_and_tickets_enabled: true
"""
UNFLAGGED = """  - name: Disk encryption enabled
    query: SELECT 1;
"""


class GatingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_matching_lists_pass(self):
        fleet = write_fleet(self.tmp.name, GATEKEEPER + UNFLAGGED)
        self.assertEqual(check(make_flopack(), fleet), [])

    def test_fleet_policy_missing_from_flopack_fails(self):
        fleet = write_fleet(self.tmp.name, GATEKEEPER + CLAUDE)
        errors = check(make_flopack(), fleet)
        self.assertEqual(len(errors), 1)
        self.assertIn("Claude Code configured to org standard", errors[0])
        self.assertIn("release", errors[0])

    def test_flopack_policy_missing_from_fleet_fails(self):
        fleet = write_fleet(self.tmp.name, GATEKEEPER)
        doc = make_flopack(gating=("Gatekeeper enabled", "Claude Code configured to org standard"))
        errors = check(doc, fleet)
        self.assertEqual(len(errors), 1)
        self.assertIn("Claude Code configured to org standard", errors[0])

    def test_policies_from_path_files_count(self):
        fleet = write_fleet(self.tmp.name, "  - path: ../lib/claude.policies.yml\n" + GATEKEEPER)
        (fleet / "lib").mkdir()
        (fleet / "lib" / "claude.policies.yml").write_text(CLAUDE.replace("  - ", "- ", 1).replace("\n    ", "\n  "))
        doc = make_flopack(gating=("Gatekeeper enabled", "Claude Code configured to org standard"))
        self.assertEqual(check(doc, fleet), [])

    def test_flopack_without_gating_list_is_skipped(self):
        fleet = write_fleet(self.tmp.name, GATEKEEPER + CLAUDE)
        self.assertIsNone(flopack_gating_policies(make_flopack(gating=None)))
        self.assertEqual(check(make_flopack(gating=None), fleet), [])

    def test_gating_list_stored_as_json_string_is_accepted(self):
        doc = make_flopack()
        methods(doc)[1]["node"]["model"]["inputs"]["data"]["gatingIn01"]["value"] = {
            "type": "string", "data": json.dumps(["Gatekeeper enabled"])}
        self.assertEqual(flopack_gating_policies(doc), ["Gatekeeper enabled"])

    def test_unflagged_policies_are_ignored(self):
        fleet = write_fleet(self.tmp.name, GATEKEEPER + UNFLAGGED)
        self.assertEqual(fleet_gating_policies(fleet), {"Gatekeeper enabled"})

    def test_assign_output_mirror_is_ignored(self):
        doc = make_flopack()
        methods(doc)[1]["node"]["model"]["outputs"]["data"]["gatingOut1"] = {
            "id": "gatingOut1", "key": "gating_policies", "value": {"type": "list"}}
        self.assertEqual(flopack_gating_policies(doc), ["Gatekeeper enabled"])
