# Fleet + Okta Workflows demo

One repo manages Fleet and Okta Workflows. An admin describes a device-to-identity guardrail in one prompt, and Claude Code opens one PR that changes both systems.

- `fleet/`: Fleet GitOps config, applied by `fleetctl gitops` when a PR is merged.
- `okta/workflows/`: Okta Workflows flows exported as `.flopack` JSON. Okta has no import API, so each flow is imported by hand in the Workflows Console.
- `tools/validate-flopack`: structural validator, run in CI on every PR.

See `CLAUDE.md` for how the systems connect.
