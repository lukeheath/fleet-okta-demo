"""Checks on the flopacks committed in this repo (not on test fixtures).

The gating check skips a flopack that has no gating_policies list, so these tests pin
down which file must carry the list: restore.flopack does, quarantine.flopack doesn't.
"""
import json
import pathlib
import re
import unittest

import helpers  # noqa: F401  (puts tools/ on sys.path)
from flopack import gating, structure
from flopack.fmt import is_formatted

REPO = pathlib.Path(__file__).resolve().parents[2]
FLOPACKS = sorted(REPO.glob("okta/workflows/*/*.flopack"))
DEVICE_COMPLIANCE = REPO / "okta" / "workflows" / "device-compliance"
FLEET_URL = "https://fleet.ngrok.app"
OKTA_GROUP_ID = re.compile(r"^00g[0-9A-Za-z]{17}$")


def load(path):
    return json.loads(path.read_text())


def flow(doc, name):
    (fl,) = [f for f in doc["data"]["flos"].values() if f["name"] == name]
    return fl["data"]


def title(card):
    return card["node"]["model"]["metadata"]["name"]


def configuration(doc):
    """Literal values of the one Assign card titled "Configuration"."""
    cards = [m for f in doc["data"]["flos"].values() for m in f["data"]["methods"]
             if m["address"].endswith(":let") and title(m) == "Configuration"]
    assert len(cards) == 1, f"expected one Configuration card, found {len(cards)}"
    return {i["key"]: i["value"]["data"] for i in cards[0]["node"]["model"]["inputs"]["data"].values()}


def execution_order(fd):
    nxt = {a: b for a, b in fd["orderings"].values()}
    (cur,) = set(nxt) - set(nxt.values())
    order = []
    while cur:
        order.append(cur)
        cur = nxt.get(cur)
    return order


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

    def test_configuration_values_are_real_and_match_across_files(self):
        # Guards against the builder's REPLACE_QUARANTINE_GROUP_ID fallback reaching a commit.
        q = configuration(load(DEVICE_COMPLIANCE / "quarantine.flopack"))
        r = configuration(load(DEVICE_COMPLIANCE / "restore.flopack"))
        for name, conf in (("quarantine", q), ("restore", r)):
            with self.subTest(flopack=name):
                self.assertRegex(conf["quarantine_group_id"], OKTA_GROUP_ID)
                self.assertEqual(conf["fleet_url"], FLEET_URL)
        self.assertEqual(q["quarantine_group_id"], r["quarantine_group_id"])
        self.assertEqual(q["fleet_url"], r["fleet_url"])

    def test_restore_stops_on_empty_login_before_querying_fleet(self):
        # An empty Login makes the query "?query=", which returns every Fleet host. Find could then
        # match an unrelated host (looseNulls), whose policies would decide the release.
        fd = flow(load(DEVICE_COMPLIANCE / "restore.flopack"), "Restore if compliant")
        cards = {m["uuid"]: m for m in fd["methods"]}
        (who,) = [m for m in fd["methods"] if title(m) == "Get user"]
        login_out = [o["id"] for o in who["node"]["model"]["outputs"]["data"].values() if o["key"] == "Login"]
        guards = []
        for target, pins in who["pins"].get(login_out[0], {}).items():
            card = cards[target]
            if not card["address"].endswith(":continueIf"):
                continue
            inputs = card["node"]["model"]["inputs"]["data"]
            ops = [i["value"]["data"] for i in inputs.values() if i["key"] == "operator"]
            wired = {inputs[p["input"]]["key"] for p in pins}
            if ops == ["is not empty"] and "left-operand" in wired:
                guards.append(target)
        self.assertEqual(len(guards), 1, "Get user.Login must feed a Continue If 'is not empty'")
        order = execution_order(fd)
        (encode,) = [u for u in order if cards[u]["address"].endswith(":encodeComponent")]
        self.assertLess(order.index(guards[0]), order.index(encode))

    def test_restore_matches_host_by_device_mapping_email(self):
        # Fleet 4.92.3's list-hosts endpoint returns end_users: null for device-mapped users, even with
        # populate_end_users=true. device_mapping=true does return the mapping, so Restore matches on that.
        fd = flow(load(DEVICE_COMPLIANCE / "restore.flopack"), "Restore if compliant")

        def literal(card_title, key):
            (card,) = [m for m in fd["methods"] if title(m) == card_title]
            (value,) = [i["value"]["data"] for i in card["node"]["model"]["inputs"]["data"].values()
                        if i["key"] == key]
            return value

        self.assertIn("device_mapping=true", literal("Compose Fleet hosts URL", "_text_"))
        self.assertEqual(literal("Find the user's host", "path"), "device_mapping.0.email")


if __name__ == "__main__":
    unittest.main()
