import pathlib
import subprocess
import tempfile
import unittest

from helpers import make_flopack, write_fleet, dumps_min
from flopack.fmt import format_text

TOOLS = pathlib.Path(__file__).resolve().parents[1]
GATEKEEPER = "  - name: Gatekeeper enabled\n    query: SELECT 1;\n    webhooks_and_tickets_enabled: true\n"


def run(*args):
    return subprocess.run([str(TOOLS / args[0]), *args[1:]], capture_output=True, text=True)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.fleet = write_fleet(self.tmp / "fleet", GATEKEEPER)

    def test_valid_formatted_file_passes(self):
        f = self.tmp / "restore.flopack"
        f.write_text(format_text(make_flopack()))
        r = run("validate-flopack", "--fleet-dir", str(self.fleet), str(f))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_minified_file_fails_with_fmt_hint(self):
        f = self.tmp / "restore.flopack"
        f.write_text(dumps_min(make_flopack()))
        r = run("validate-flopack", "--fleet-dir", str(self.fleet), str(f))
        self.assertEqual(r.returncode, 1)
        self.assertIn("fmt-flopack", r.stdout)

    def test_fmt_then_validate_passes(self):
        f = self.tmp / "restore.flopack"
        f.write_text(dumps_min(make_flopack()))
        self.assertEqual(run("fmt-flopack", str(f)).returncode, 0)
        self.assertEqual(run("validate-flopack", "--fleet-dir", str(self.fleet), str(f)).returncode, 0)

    def test_gating_mismatch_fails(self):
        f = self.tmp / "restore.flopack"
        f.write_text(format_text(make_flopack(gating=("Gatekeeper enabled", "Not in Fleet"))))
        r = run("validate-flopack", "--fleet-dir", str(self.fleet), str(f))
        self.assertEqual(r.returncode, 1)
        self.assertIn("Not in Fleet", r.stdout)
