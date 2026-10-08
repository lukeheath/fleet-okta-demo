# CLAUDE.md

This repo controls two systems that together decide who can sign in to Okta:

- **Fleet** checks Macs with policies. `fleet/` is applied by GitOps when a PR merges to `main`.
- **Okta Workflows** moves users in and out of the `Quarantine` group. Flows are stored as `.flopack` JSON and imported by hand.

Most requests are guardrails, like "only Macs that do X can sign in to Okta". A guardrail always changes both systems in one PR.

## How the systems connect

1. Fleet runs policies on Macs in the Workstations fleet (`fleet/fleets/workstations.yml`).
2. When a Mac starts failing a policy that has `webhooks_and_tickets_enabled: true`, Fleet POSTs its failing-policy webhook to the flow "Fleet failing policy - Quarantine". That flow is an API endpoint in `quarantine.flopack`.
3. For each host, that flow runs "Quarantine host's user". It reads the host's IdP username from Fleet, adds that Okta user to `Quarantine`, and clears their sessions.
4. An Okta sign-on policy denies sign-in to members of `Quarantine`. It's configured in Okta, not in this repo.
5. "Restore compliant users" in `restore.flopack` runs every 5 minutes. For each member of `Quarantine`, it runs "Restore if compliant". That flow removes the user from `Quarantine` only if their Mac passes every policy named in `gating_policies`.

Each flow, its configuration, how to import it, and known limitations are documented in `okta/workflows/device-compliance/readme.md`.

## Repo layout

- `fleet/default.yml`: org-wide Fleet settings.
- `fleet/fleets/workstations.yml`: the Workstations fleet. It holds the policies, the scripts, and the failing-policy webhook. Guardrail policies go here.
- `fleet/lib/macos/scripts/deploy-claude-settings.sh`: writes the org's Claude Code standard to each Mac.
- `okta/workflows/device-compliance/quarantine.flopack`: "Fleet failing policy - Quarantine", "Quarantine host's user", and "Fleet GET".
- `okta/workflows/device-compliance/restore.flopack`: "Restore compliant users", "Restore if compliant" (which calls Fleet itself, with no "Fleet GET" helper), and the `gating_policies` list.
- `tools/validate-flopack`, `tools/fmt-flopack`, `tools/tests/`: the flopack validator, the formatter, and their tests.
- `.github/workflows/`: `validate.yml` runs on every PR. `gitops.yml` applies `fleet/` on every push to `main`.

## Gating contract

A Fleet policy gates Okta sign-in when both of these are true:

- it has `webhooks_and_tickets_enabled: true` in `fleet/fleets/workstations.yml`, **and**
- its exact name is in `gating_policies` in `okta/workflows/device-compliance/restore.flopack`.

**Change both or neither, in the same PR.** Names must match exactly, including case, spaces, and punctuation. If the two lists drift apart:

- A policy that's in Fleet but missing from the list lets users be released while they're still failing it.
- A name in the list that's missing from Fleet means nobody is ever released.

`tools/validate-flopack` fails on either mismatch.

## Adding a guardrail

1. Create a branch from `main`: `git switch -c guardrail/<slug>`.
2. Add a policy to `policies:` in `fleet/fleets/workstations.yml`. Use "Gatekeeper enabled" as the model:
   - `name`: says what a passing Mac has, like "Gatekeeper enabled".
   - `description`: what the policy checks.
   - `resolution`: what the user or IT does to fix a failing Mac.
   - `platform: darwin`
   - `query`: returns a row only when the Mac complies.
   - `webhooks_and_tickets_enabled: true`
3. Append the exact policy name to `gating_policies` in `restore.flopack` (see the next section).
4. Run `tools/fmt-flopack okta/workflows/device-compliance/restore.flopack`.
5. Run the checks in **Validation**. Fix every ERROR.
6. Commit, push, and open one PR (see **Pull requests**).

Don't touch `quarantine.flopack` for a guardrail. See **Flopack editing rules**.

### Where `gating_policies` lives

- File `restore.flopack`, flow "Restore if compliant", Assign card named "Gating policies" (`node.data.name`).
- On that card, the input whose `key` is `"gating_policies"` has a `value` with `"type": "string"`, `"collection": true`, and `data` holding a JSON list of policy names, like `["Gatekeeper enabled"]`. Append the new name to that list.
- The card also has an output with the same key. If its `value.data` holds the list too, keep it identical to the input's.
- To find both, search the file for `"gating_policies"`.

### Policies that check the Claude Code standard

- The source of truth is `fleet/lib/macos/scripts/deploy-claude-settings.sh`. Read it to find the file path and every value it writes. Don't copy values from anywhere else.
- Check the file with fleetd's `parse_json` table. It returns one row per leaf value, with these columns:
  - `path`: the file. It's required in the `WHERE` clause.
  - `fullkey`: the key path, joined with `/` and without a leading slash, like `forceLoginMethod` or `permissions/deny/0`.
  - `key`, `parent`, and `value`. `value` is always text, so booleans come back as `'true'` or `'false'`.
- Check every scalar setting and every deny rule the script writes. A partial check lets a Mac with a weakened config pass.
- A missing or invalid file returns 0 rows, and the policy must fail in that case. Count the matching rows and require the exact total:
  `SELECT 1 WHERE (SELECT COUNT(DISTINCT value) FROM parse_json WHERE path = '<file>' AND (<one condition per expected value, joined with OR>)) = <number of conditions>;`
  `COUNT(DISTINCT value)` stops a duplicated rule from standing in for a missing one. It works because every expected value is different.
- Match a scalar on `fullkey` and `value`. Match a deny rule on `value` among `fullkey LIKE 'permissions/deny/%'`, not on a fixed index, so reordering the list doesn't fail the policy.

## Flopack editing rules

- Change only `value.data` of existing inputs, plus the mirrored output described above. Change more only when the request needs new flow logic.
- Never change `checksum`, `meta`, any `id` or `uuid`, connector versions in `address`, `data.configs`, or anything under `display`.
- A value with `"collection": true` must have list `data` (`[]` or `["a", "b"]`) or `null`. It must never be a string, like `""` or `"[\"a\"]"`. Okta's importer fails with a 500 "flo.id is not a function" otherwise. Don't hand-type a list as a string.
- Make targeted edits. Don't regenerate, reorder, or re-serialize the file another way. Run `tools/fmt-flopack <file>` after every edit, because the validator rejects anything that isn't in canonical format.
- Don't add flows. The Workflows plan allows 5 active flows, and helpers count because they must be on to be called. Quarantine uses 3 and Restore uses 2.
- **Don't change `quarantine.flopack` for a new guardrail.** Its API endpoint is Fleet's webhook target, and re-importing it creates a new Invoke URL. Fleet would keep calling the old URL until the webhook secret is updated.

## Fleet YAML rules

- Don't put `$` anywhere in a policy, including its `query`. GitOps expands `$NAME` as an environment variable, and an unset one fails the deploy.
- Don't remove top-level keys, even empty ones like `software:` and `reports:`. GitOps clears whatever a missing key manages.
- Secrets come only from environment variables (`$FLEET_URL`, `$OKTA_WEBHOOK_URL`), which are set as GitHub Actions secrets. Never write a secret value into the repo.
- Don't add `run_script` or other automations to a gating policy. An automatic fix can make the Mac pass before Fleet sends the webhook, so the user is never quarantined.
- Don't change `webhook_settings` or the deploy script for a guardrail unless you're asked to.

## Validation

Run these from the repo root, exactly as written. They're pre-approved in `.claude/settings.json`.

- `tools/validate-flopack okta/workflows/device-compliance/*.flopack`: ERROR lines block the PR. WARN lines don't.
- `python3 -m unittest discover -s tools/tests`

There's no local Fleet check. On the PR, CI runs these again and adds `fleetctl gitops --dry-run`.

## Pull requests

- One guardrail gets one branch (`guardrail/<slug>`, where the slug is short kebab-case) and one PR against `main`.
- Push with `git push -u origin guardrail/<slug>`.
- Fill in every section of `.github/pull_request_template.md`. Pass the body through a quoted heredoc, so backticks and `$` stay literal:

  ```
  gh pr create --title "<plain-English title>" --body-file - <<'EOF'
  ...filled-in template...
  EOF
  ```

- Write the Summary for an IT or security reader who doesn't read SQL or JSON. In plain English, say what changes in Fleet, what changes in Okta, and how the two connect: which policy now gates sign-in, and what happens to a user whose Mac fails it.
- Keep the template's After-merge checklist as it is. It covers importing `restore.flopack` and turning off the old Restore flows. Don't add a step for `quarantine.flopack`.
- Tick a Validation box only if you ran that check and it passed.
- Never push to `main` and never merge. A person reviews and merges, and merging deploys Fleet.

## Questions about a flow

Answer from the flopack JSON, because that's what Okta runs. Use `readme.md` only as a cross-check. If the two disagree, say so and trust the JSON. "The device-compliance flow" means both files in `okta/workflows/device-compliance/`: quarantine first, then restore.

How to read a flopack:

- The file's `data.flos` holds the flows by id. Each flow has a `name` and a `data` object. The paths below are inside a flow.
- `data.methods[]` holds the flow's cards. For each card:
  - `uuid` identifies it.
  - `node.data.name` is the title shown in the Workflows Console.
  - `address` says what kind of card it is. For example, `root:kernel:control:0.0.1:let` is Assign, `...:continueIf` is Continue If, and `root:channels:http:okta:<version>:removeUserFromGroup` is an Okta connector card.
  - `node.model.inputs.data` holds the inputs. A literal value is in `value.data`. An input wired from an earlier card has empty `data`, and the earlier card's `pins` point to it.
- `data.orderings` lists `[from, to]` pairs of card `uuid`s. Start at the card that no pair points to, and follow the pairs to get the execution order. Don't rely on the order of `methods`.
- The start card shows the trigger:
  - `...:http:0.0.1:accept` is an API endpoint.
  - `...:callable` with `data.scheduled: true` is a scheduled flow. The schedule is in `data.cron`.
  - Any other `...:callable` is a helper flow.
- An input with `value.type: "flo"` calls the flow whose id is in its `data`. For Each, List Group Members (streaming), and Call Flow cards work this way.
- A Continue If card stops the flow when its condition fails. Its `message` input says why.

To list every card: `jq -r '.data.flos[] | .name, (.data.methods[] | "  \(.uuid)  \(.node.data.name)  \(.address)")' <file>`

In your answer, give each flow's trigger, then walk its cards in order. Name each card by its title, and say what it does, including any literal inputs that matter. Then say which flow calls which. Don't paste raw JSON.
