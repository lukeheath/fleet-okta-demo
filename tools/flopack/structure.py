"""Structural validator for Okta Workflows .flopack documents.

validate(doc) returns (errors, warnings). Errors are conditions the Workflows Console import rejects.
Warnings are deviations seen in some published templates (import likely still works).
Rules derived empirically from 127 templates in github.com/okta/workflows-templates (all pass ERROR rules).
"""
from __future__ import annotations

import json, re

UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
SHORT = re.compile(r'^[A-Za-z0-9_-]{6,14}$')
PH = re.compile(r'\{\{\{([^}]+)\}\}\}')


def validate(doc: dict) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    E = lambda m: errs.append(m)
    W = lambda m: warns.append(m)
    d = doc
    if d.get('type') != 'flopack': E('top.type must be "flopack"')
    if not re.match(r'^1\.\d+\.\d+$', str(d.get('version', ''))): E('top.version must look like 1.x.y')
    for k in ('created', 'flags', 'data'):
        if k not in d: E(f'top.{k} missing')
    if 'checksum' in d: W('top.checksum present: hand edits may invalidate it (1.5.0/1.6.0 exports omit it)')
    D = d.get('data', {})
    for k in ('flos', 'configs', 'tables', 'groups'):
        if not isinstance(D.get(k), dict): E(f'data.{k} must be an object')
    flos, configs, tables, groups = (D.get(k, {}) for k in ('flos', 'configs', 'tables', 'groups'))
    for coll, name in ((flos, 'flo'), (configs, 'config'), (tables, 'table'), (groups, 'group')):
        for k, v in coll.items():
            if v.get('id') != k: E(f'{name} key {k} != .id')
            if not UUID.match(k): W(f'{name} id {k} is not a lowercase UUID')
    for c in configs.values():
        if c.get('data') is not None: E(f'config {c["id"]} has non-null data (secrets must not be exported)')
    for g in groups.values():
        p = g['data'].get('path')
        if p and p not in groups: W(f'group {g["id"]} path {p} not in groups')
    for t in tables.values():
        if t['data'].get('group_id') not in groups: W(f'table {t["name"]} group_id not in groups')

    def walk_flo(fd, where, inline):
        ms = {}
        for m in fd.get('methods', []):
            if m.get('uuid') in ms: E(f'{where}: duplicate method uuid {m.get("uuid")}')
            ms[m.get('uuid')] = m
        io_seen = set()
        for m in ms.values():
            a = m.get('address', '')
            ap = a.split(':')
            mw = f'{where} [{m.get("uuid")} {a}]'
            if not SHORT.match(m.get('uuid', '')): W(f'{mw}: unusual method uuid format')
            try:
                if a != m['parents']['version']['address'] + ':' + m['node']['key']: E(f'{mw}: address != parents.version.address:node.key')
                if not m['parents']['version']['address'].startswith(m['parents']['channel']['address'] + ':'): E(f'{mw}: parents.channel/version mismatch')
                if m['node']['key'] != m['node']['model'].get('key'): E(f'{mw}: node.key != node.model.key')
            except (KeyError, TypeError):
                E(f'{mw}: missing parents/node structure'); continue
            mod = m['node']['model']
            ins = mod.get('inputs', {}).get('data', {}) or {}
            outs = mod.get('outputs', {}).get('data', {}) or {}
            for side, coll in (('input', ins), ('output', outs)):
                for k, v in coll.items():
                    if v.get('id') != k: E(f'{mw}: io key {k} != .id')
                    if k in io_seen: E(f'{mw}: input/output id {k} not unique within flo')
                    io_seen.add(k)
                    # Okta's importer fails with 500 "TypeError: flo.id is not a function" on list values
                    # whose data isn't a list. In all 127 templates such data is a list or null.
                    val = v.get('value') if isinstance(v.get('value'), dict) else {}
                    data = val.get('data')
                    if val.get('collection') is True and data is not None and not isinstance(data, list):
                        E(f'{mw}: {side} {v.get("key")!r} has collection: true but data is '
                          f'{type(data).__name__} {json.dumps(data)[:40]}; use [] (non-list data crashes the Okta importer)')
            for oid, tg in (m.get('pins') or {}).items():
                if oid not in outs: E(f'{mw}: pin source {oid} is not an output of this card')
                for tu, lst in tg.items():
                    if tu not in ms: E(f'{mw}: pin target card {tu} not in same flo scope'); continue
                    tin = ms[tu]['node']['model'].get('inputs', {}).get('data', {}) or {}
                    for p in lst:
                        if p.get('input') not in tin: E(f'{mw}: pin target input {p.get("input")} not on card {tu}')
                        tr = p.get('transform')
                        if tr and set(tr) != {oid}: W(f'{mw}: transform keys {list(tr)} != [{oid}]')
            for bu in m.get('branches') or {}:
                if bu not in ms: E(f'{mw}: branch head {bu} not in flo')
            for jk, lst in (m.get('joins') or {}).items():
                if jk not in ins: W(f'{mw}: join key {jk} not an input of this card')
            # connections
            if len(ap) > 3 and ap[1] == 'channels':
                cref = mod.get('config')
                if cref is not None and cref not in configs: E(f'{mw}: model.config {cref} not in data.configs')
                if cref in configs and configs[cref]['module'] != ap[3]: E(f'{mw}: config module {configs[cref]["module"]} != channel {ap[3]}')
                if ap[3] == 'stash':
                    for i in ins.values():
                        if i.get('key') == 'stash' and i['value'].get('data') not in tables:
                            E(f'{mw}: table ref {i["value"].get("data")} not in data.tables')
            if a.endswith(':compose'):
                keys = {i.get('key') for i in ins.values()}
                for i in ins.values():
                    if i.get('key') == '_text_' and isinstance(i['value'].get('data'), str):
                        for ph in PH.findall(i['value']['data']):
                            if ph not in keys: E(f'{mw}: Compose placeholder {{{{{{{ph}}}}}}} has no input with that key')
            # flow references
            for i in ins.values():
                v = i.get('value') or {}
                if v.get('type') != 'flo': continue
                dd = v.get('data')
                if isinstance(dd, dict) and 'methods' in dd:
                    if dd.get('id') != dd.get('uuid'): E(f'{mw}: inline flo id != uuid')
                    walk_flo(dd, f'{mw} > inline', True)
                elif isinstance(dd, str) and dd:
                    if dd not in flos: E(f'{mw}: references flo {dd} not in data.flos (import will demand a replacement)')
                    else:
                        tgt = flos[dd]['data']
                        starts = [x for x in tgt['methods'] if x['address'].endswith(':callable')]
                        if not starts and not a.endswith(':exportFlo'): E(f'{mw}: referenced flo "{flos[dd]["name"]}" has no Helper Flow (callable) start card')
                        elif starts:
                            hin = {x.get('key') for x in starts[0]['node']['model']['inputs']['data'].values() if x.get('group') != 'context'}
                            args = {x.get('key') for x in ins.values() if x.get('group') in (None, 'context', 'Streaming') and (x.get('value') or {}).get('type') != 'flo'
                                    and x.get('key') not in ('list', 'concurrency', 'object', 'initial', 'memo', 'times', 'count')}
                            if not args <= hin: W(f'{mw}: args {sorted(args - hin)} not inputs of helper "{flos[dd]["name"]}"')
        # orderings: edges [from, to] between cards of this scope; exactly one root
        inc = set()
        for k, pair in (fd.get('orderings') or {}).items():
            if not (isinstance(pair, list) and len(pair) == 2): E(f'{where}: ordering {k} not a [from,to] pair'); continue
            for x in pair:
                if x not in ms: E(f'{where}: ordering {k} endpoint {x} not in flo')
            inc.add(pair[1])
        heads = set()
        for m in ms.values(): heads |= set(m.get('branches') or {})
        roots = [u for u in ms if u not in inc and u not in heads]
        if ms and len(roots) != 1: E(f'{where}: expected exactly 1 start card (no incoming ordering), got {len(roots)}')
        if len(ms) > 1:
            linked = {x for p in (fd.get('orderings') or {}).values() if isinstance(p, list) for x in p}
            if set(ms) - linked: E(f'{where}: cards not linked by orderings: {sorted(set(ms) - linked)}')
        return roots, ms

    for fid, fl in flos.items():
        fd = fl.get('data', {})
        where = f'flo "{fl.get("name")}"'
        if fd.get('uuid') != fid: E(f'{where}: data.uuid != id')
        if fd.get('group') not in groups: W(f'{where}: data.group not in data.groups')
        roots, ms = walk_flo(fd, where, False)
        if roots:
            start = ms[roots[0]]['address']
            if fd.get('scheduled') and not start.endswith(':callable'): E(f'{where}: scheduled flo must start with callable card')
            if fd.get('scheduled') and not fd.get('cron'): E(f'{where}: scheduled=true but cron empty')
            if fd.get('cron') and not fd.get('scheduled'): W(f'{where}: cron set but scheduled=false')
            if start.endswith(':http:0.0.1:accept') and fd.get('security_level') not in ('medium', 'open'):
                W(f'{where}: API Endpoint with security_level {fd.get("security_level")!r} (templates use medium=client token, open=public)')
        prev = [(p.get('module'), p.get('name')) for p in fd.get('display', {}).get('preview', [])]
        mine = [((m['address'].split(':')[2] if m['address'].split(':')[1] == 'kernel' else m['address'].split(':')[3]), m['address'].split(':')[-1]) for m in fd.get('methods', [])]
        if prev != mine: W(f'{where}: display.preview out of sync with methods (cosmetic)')
    return errs, warns

