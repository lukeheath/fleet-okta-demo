"""Cross-system check: Fleet policies that report to Okta must match the Restore flow's gating list.

Fleet sends failing hosts to the Okta Fail flow for every policy with
`webhooks_and_tickets_enabled: true`. The Restore flow releases a user only when
their host passes every policy named in its `gating_policies` input. The two
lists must be identical, or users are released while still failing (or never released).
"""
from __future__ import annotations

import json
import pathlib

GATING_KEY = "gating_policies"


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _gating_inputs(flos):
    """Yield every card *input* named gating_policies, including inside inline flows.

    Outputs are skipped: Assign cards mirror each input as an output with the same key and no data.
    """
    for d in _walk(flos):
        inputs = d.get("inputs")
        if isinstance(inputs, dict) and isinstance(inputs.get("data"), dict):
            for i in inputs["data"].values():
                if isinstance(i, dict) and i.get("key") == GATING_KEY:
                    yield i


def flopack_gating_policies(doc: dict) -> list[str] | None:
    found = []
    for i in _gating_inputs(doc.get("data", {}).get("flos", {})):
        data = (i.get("value") or {}).get("data")
        if data is None:
            continue  # wired from another card, not a literal list
        if isinstance(data, str):
            data = json.loads(data)
        if not (isinstance(data, list) and all(isinstance(x, str) for x in data)):
            raise ValueError(f"{GATING_KEY} must be a list of policy names, got {data!r}")
        found.append(data)
    if not found:
        return None
    if any(sorted(f) != sorted(found[0]) for f in found):
        raise ValueError(f"{GATING_KEY} appears {len(found)} times with different values")
    return found[0]


def _load_yaml(path: pathlib.Path):
    try:
        import yaml
    except ImportError as e:
        raise SystemExit("PyYAML is required: python3 -m pip install --user pyyaml") from e
    return yaml.safe_load(path.read_text()) or {}


def fleet_gating_policies(fleet_dir: pathlib.Path) -> set[str]:
    names = set()
    for f in sorted((fleet_dir / "fleets").glob("*.yml")):
        for item in _load_yaml(f).get("policies") or []:
            items = [item]
            if "path" in item:
                loaded = _load_yaml((f.parent / item["path"]).resolve())
                items = loaded if isinstance(loaded, list) else [loaded]
            for p in items:
                if p.get("webhooks_and_tickets_enabled") is True:
                    names.add(p["name"])
    return names


def check(doc: dict, fleet_dir: pathlib.Path) -> list[str]:
    try:
        gating = flopack_gating_policies(doc)
    except ValueError as e:
        return [str(e)]
    if gating is None:
        return []
    fleet = fleet_gating_policies(fleet_dir)
    errors = []
    for name in sorted(fleet - set(gating)):
        errors.append(f'Fleet policy "{name}" sends failing hosts to Okta (webhooks_and_tickets_enabled: true) '
                      f'but is missing from {GATING_KEY}: the Restore flow would release users while it still fails.')
    for name in sorted(set(gating) - fleet):
        errors.append(f'{GATING_KEY} lists "{name}" but no Fleet policy with that name has '
                      f'webhooks_and_tickets_enabled: true: quarantined users would never be released.')
    return errors
