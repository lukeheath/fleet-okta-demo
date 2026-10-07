# Device compliance flows

`workflow.flopack` holds two flows exported from the `fleetdmdev` Okta Workflows Console:

- **Fail flow** (API endpoint trigger): called by Fleet's failing-policy webhook. Adds the host's user to `Quarantine` and clears their Okta sessions.
- **Recover flow** (scheduled): removes users from `Quarantine` once their host passes all gating policies again.

## Deploying

Okta has no API for importing flows. To deploy a change, drag `workflow.flopack` into the Workflows Console, select the Okta and Fleet API connections, and turn the flows on.

<!-- TODO: after import, document whether re-importing changes the API endpoint URL. Fleet's webhook URL points at it. -->
