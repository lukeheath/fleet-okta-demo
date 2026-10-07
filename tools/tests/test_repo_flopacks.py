"""Checks on the flopacks committed in this repo (not on test fixtures).

The gating check skips a flopack that has no gating_policies list, so these tests pin
down which file must carry the list: restore.flopack does, quarantine.flopack doesn't.
"""
import json
import pathlib
import unittest

import helpers  # noqa: F401  (puts tools/ on sys.path)
from flopack import gating, structure
from flopack.fmt import is_formatted

REPO = pathlib.Path(__file__).resolve().parents[2]
FLOPACKS = sorted(REPO.glob("okta/workflows/*/*.flopack"))
DEVICE_COMPLIANCE = REPO / "okta" / "workflows" / "device-compliance"


def load(path):
    return json.loads(path.read_text())


class RepoFlopacksTest(unittest.TestCase):
    def test_repo_has_flopacks(self):
        self.assertTrue(FLOPACKS, "no okta/workflows/*/*.flopack files found")

    def test_every_flopack_is_structurally_valid(self):
        for path in FLOPACKS:
            with self.subTest(flopack=str(path.relative_to(REPO))):
                errors, _ = structure.validate(load(path))
                self.assertEqual(errors, [])

    def test_every_flopack_is_formatted(self):
        for path in FLOPACKS:
            with self.subTest(flopack=str(path.relative_to(REPO))):
                self.assertTrue(is_formatted(path.read_text()), f"run tools/fmt-flopack {path.relative_to(REPO)}")

    def test_restore_has_gating_list_matching_fleet(self):
        doc = load(DEVICE_COMPLIANCE / "restore.flopack")
        self.assertIsNotNone(gating.flopack_gating_policies(doc),
                             "restore.flopack must have a literal gating_policies list")
        self.assertEqual(gating.check(doc, REPO / "fleet"), [])

    def test_quarantine_has_no_gating_list(self):
        doc = load(DEVICE_COMPLIANCE / "quarantine.flopack")
        self.assertIsNone(gating.flopack_gating_policies(doc))


if __name__ == "__main__":
    unittest.main()
