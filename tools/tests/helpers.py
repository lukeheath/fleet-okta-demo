"""Builders for minimal, valid flopack documents used across tests."""
import copy
import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

FLO_ID = "11111111-1111-4111-8111-111111111111"
GROUP_ID = "22222222-2222-4222-8222-222222222222"


def card(uuid, fn, key, inputs=None, outputs=None):
    chan = f"root:kernel:{fn}"
    ver = f"{chan}:0.0.1"
    return {
        "uuid": uuid,
        "address": f"{ver}:{key}",
        "parents": {"channel": {"address": chan}, "version": {"address": ver}},
        "node": {"key": key, "model": {"key": key, "config": None,
                                        "inputs": {"data": inputs or {}},
                                        "outputs": {"data": outputs or {}}}},
        "pins": {}, "branches": {}, "joins": {},
    }


def make_flopack(gating=("Gatekeeper enabled",)):
    start = card("startCrd01", "control", "callable",
                 outputs={"outRecord1": {"id": "outRecord1", "key": "Record", "value": {"type": "object"}}})
    inputs = {}
    if gating is not None:
        inputs["gatingIn01"] = {"id": "gatingIn01", "key": "gating_policies",
                                "value": {"type": "list", "data": list(gating)}}
    assign = card("assignCrd1", "object", "assign", inputs=inputs)
    return {
        "type": "flopack", "version": "1.6.0", "created": "2026-10-07T00:00:00.000Z",
        "flags": {"auto-transform": True, "looseBooleans": True, "looseStrings": True, "looseNulls": True},
        "data": {
            "flos": {FLO_ID: {"id": FLO_ID, "name": "Restore compliant users", "description": "",
                              "data": {"uuid": FLO_ID, "group": GROUP_ID,
                                       "methods": [start, assign],
                                       "orderings": {"ord1": ["startCrd01", "assignCrd1"]},
                                       "display": {"preview": [{"module": "control", "name": "callable"},
                                                               {"module": "object", "name": "assign"}],
                                                   "isCallable": True},
                                       "scheduled": False, "cron": {}}}},
            "configs": {},
            "tables": {},
            "groups": {GROUP_ID: {"id": GROUP_ID, "name": "Device compliance",
                                  "data": {"name": "Device compliance", "path": ""}}},
        },
    }


def methods(doc):
    return doc["data"]["flos"][FLO_ID]["data"]["methods"]


def write_fleet(tmp, policies_yaml):
    fleets = pathlib.Path(tmp) / "fleets"
    fleets.mkdir(parents=True, exist_ok=True)
    (fleets / "workstations.yml").write_text("name: Workstations\npolicies:\n" + policies_yaml)
    return pathlib.Path(tmp)


def clone(doc):
    return copy.deepcopy(doc)


def dumps_min(doc):
    return json.dumps(doc, separators=(",", ":"))
