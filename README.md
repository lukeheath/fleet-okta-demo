# Fleet + Okta Workflows

Device health and Okta access, managed in one repo.

- `fleet/`: Fleet configuration. Merging to `main` applies it with `fleetctl gitops`.
- `okta/workflows/`: Okta Workflows flows, exported as `.flopack` files.
- `tools/validate-flopack`: checks every flopack on each pull request.

When a Mac fails a policy that gates Okta, Fleet tells Okta Workflows, and the user can't sign in until the Mac passes again.
