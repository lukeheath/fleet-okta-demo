# CLAUDE.md

<!-- STUB: finished in Phase 3 of docs/plan.md once the seed flopack and Fleet config exist. -->

## How the systems connect

1. Fleet runs policies on Macs. Policies that gate Okta access have the failing-policy webhook turned on.
2. When a Mac fails a gating policy, Fleet POSTs the failing-policy webhook to the **Fail flow** (Okta Workflows API endpoint).
3. Fail flow: for each host, call Fleet `GET /api/v1/fleet/hosts/:id`, read the user's IdP username, add that Okta user to the `Quarantine` group, and clear their Okta sessions.
4. An Okta sign-on policy rule denies sign-in to members of `Quarantine`.
5. **Recover flow** (scheduled): for each `Quarantine` member, ask Fleet whether their host passes all gating policies again. If it does, remove them from `Quarantine`.

A guardrail change usually touches both systems: the Fleet policy (and its webhook) in `fleet/`, plus the list of gating policies in the flopack.

## Repo layout

- `fleet/default.yml`: global Fleet settings (GitOps).
- `fleet/fleets/workstations.yml`: the Workstations fleet's policies, scripts, and webhook.
- `fleet/lib/`: scripts and policy queries referenced from the YAML.
- `okta/workflows/device-compliance/workflow.flopack`: Fail and Recover flows (exported JSON).
- `tools/validate-flopack`: validator. Run it after every flopack edit.

## Flopack format notes

TODO

## Rules for editing

- Run `tools/validate-flopack okta/workflows/device-compliance/workflow.flopack` after any flopack edit. Don't open a PR if it fails.
- Never put secrets in the repo. Fleet YAML gets secrets from environment variables (GitHub Actions secrets).
- PR descriptions need a plain-English change summary covering both Fleet and Okta.
