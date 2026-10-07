# Device compliance flows

Two flopacks, one per Workflows folder. Each one imports on its own.

These are seed files: they were assembled from cards copied out of Okta's published workflow templates, not exported from a live org. Once they're imported and working in `fleetdmdev`, we'll replace them with Okta's own exports.

## `quarantine.flopack`: folder "Device compliance - Quarantine"

| Flow | Trigger | What it does |
|---|---|---|
| Fleet failing policy → Quarantine | API Endpoint (client token) | Fleet's failing-policy webhook calls it. It parses `hosts[]` and runs "Quarantine host's user" for each host under **For Each - Ignore Errors**, then always returns `200 {"ok":true}`, so Fleet never retries. |
| Quarantine host's user | Helper | `GET /api/v1/fleet/hosts/:id` → `host.end_users[0].idp_username`. If it's empty, the helper stops. Otherwise it runs Okta Read User → Add User to Group (`Quarantine`) → Clear User Sessions (also revokes OAuth tokens). |
| Fleet GET | Helper | `GET {fleet_url}{path}` with the API Connector Raw Request, then parses the JSON body. It's the only card that calls Fleet. |

The Fail flow answers non-2xx only if parsing the request body fails before Return Raw runs, which needs a malformed body. Fleet never sends one.

## `restore.flopack`: folder "Device compliance - Restore"

| Flow | Trigger | What it does |
|---|---|---|
| Restore compliant users | Scheduled, every 5 minutes | Streams each member of `Quarantine` to "Restore if compliant". |
| Restore if compliant | Helper (`Record`, `State`) | `GET /api/v1/fleet/hosts?query=<login>&populate_policies=true&populate_end_users=true`, then finds the host whose `end_users[0].idp_username` equals the user's Okta login. It removes the user from `Quarantine` only if every policy in `gating_policies` reports `pass` on that host. |
| Fleet GET | Helper | Same as in the Quarantine folder. Flows can't call across flopacks, so each folder has its own copy. |

The Restore flow fails closed. The user stays in `Quarantine` if the stream record has no Okta login, if no Fleet host maps to them, or if a gating policy is failing or missing from that host's results.

## Configuration

Each folder's main flow begins with an Assign card named **Configuration** that holds `fleet_url` and `quarantine_group_id`. Neither is secret. The helpers receive both values from that card; the Restore helper reads them from `State`.

The Fleet API token is never in these files. It lives in the **Fleet API** connection: an API Connector with Auth Type **Custom** and the header `Authorization: Bearer <token>`.

## Gating contract

The "Gating policies" Assign card in "Restore if compliant" holds `gating_policies`, a list of Fleet policy names. It must list exactly the policies in `fleet/` that have `webhooks_and_tickets_enabled: true`:

- If a webhook policy is missing from the list, users get released while that policy is still failing.
- If the list names a policy that doesn't send webhooks, Restore still requires it to pass:
  - If that policy doesn't exist in Fleet (for example, a typo), it's missing from every host's results, so nobody gets released.
  - If it exists, users are released only once it passes, even though failing it never quarantined anyone.

`tools/validate-flopack` checks the two lists against each other, and so does `tools/tests/test_repo_flopacks.py` in CI. When you add or remove a gating policy in Fleet, update this list in the same PR.

## Known limitations

- Restore checks only the first host whose IdP user matches. A user with a second Mac that's failing can still be released.

## Importing

Okta has no API for importing flows. Every import creates new flows, with a new Invoke URL and client token. It never overwrites existing flows.

1. In the Workflows Console, import `quarantine.flopack` and then `restore.flopack` (drag each file in, or use **Import** on the folder menu).
2. Reselect connections. Connections aren't exported, so each connector card needs one:
   - **Okta**: Read User, Add User to Group, and Clear User Sessions in "Quarantine host's user"; List Group Members in "Restore compliant users"; and Remove User from Group in "Restore if compliant".
   - **Fleet API**: the Raw Request card in each folder's "Fleet GET".
3. Check each **Configuration** card: `fleet_url` and `quarantine_group_id`.
4. On the API Endpoint card of "Fleet failing policy → Quarantine", leave security on the client token. Copy the Invoke URL, which includes `?clientToken=`. Set it as `OKTA_WEBHOOK_URL` in `.env` and in the repo's GitHub secrets, then run GitOps so Fleet's failing-policy webhook points at the new flow.
5. Turn on all six flows: the helpers first, then "Fleet failing policy → Quarantine" and "Restore compliant users". Confirm that the scheduled flow shows "every 5 minutes".
6. Turn off or delete the flows from any previous import. A stale Restore flow keeps running with its old gating list.
