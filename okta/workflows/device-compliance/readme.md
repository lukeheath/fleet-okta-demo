# Device compliance

| Flow file | What it does |
|---|---|
| `quarantine.flopack` | Fleet calls it when a Mac fails a gating policy. It adds the Mac's user to the `Quarantine` group and ends their Okta sessions. |
| `restore.flopack` | Runs every 5 minutes. It removes users from `Quarantine` once their Mac passes every policy listed in `gating_policies`. |

A Fleet policy gates Okta access when it has `webhooks_and_tickets_enabled: true` and its name is in `gating_policies`. `tools/validate-flopack` checks that the two lists match.

## Deploying a change

Okta has no API for importing flows, so this part is manual:

1. In the Workflows Console, turn off and delete the two Restore flows.
2. Import the new `restore.flopack`.
3. Turn both flows on.
