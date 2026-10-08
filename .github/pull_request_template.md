## Summary
<!-- One paragraph, plain English: what guardrail changes and why. -->

## Fleet
<!-- Policies, scripts, or settings that change in fleet/. -->

## Okta Workflows
<!-- What changes in which flow, and what the flow now does. -->

## How they connect
<!-- Which Fleet policy names now gate Okta sign-in. -->

## After merge
- [ ] GitHub Actions applies the Fleet changes (`fleetctl gitops`).
- [ ] Import `okta/workflows/device-compliance/restore.flopack` in the Workflows Console, reselect connections, turn the previous Restore flows off, then turn the new flows on (the plan allows only 5 active flows).

## Validation
- [ ] `tools/validate-flopack okta/workflows/device-compliance/*.flopack`
