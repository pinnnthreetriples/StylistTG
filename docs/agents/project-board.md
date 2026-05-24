# Project Board Workflow

StylistTG uses GitHub Projects as the source of truth for agent-ready work.

- Project: https://github.com/users/pinnnthreetriples/projects/1
- Repository: https://github.com/pinnnthreetriples/StylistTG
- Primary work item: GitHub Issue linked to one Pull Request when possible.

## Operating Rules

Use the board before starting GitHub issue, pull request, or implementation work.

1. Check whether an issue/card already exists.
2. Work from a specified issue whenever possible.
3. Keep the issue, branch, pull request, and board card aligned.
4. Record verification results in the pull request before moving work to review.
5. Treat `Done` as a real terminal state: merged PR, closed issue, or explicit no-code closure.

Do not use chat history as the only source of truth for active work. Important decisions, scope changes, and follow-up tasks belong in issues, pull requests, or project status updates.

## Status Contract

| Status | Meaning | Entry requirement | Exit requirement |
| --- | --- | --- | --- |
| `Todo` | Ready to start. | Issue has goal, scope, acceptance criteria, verification, and safety constraints. | Someone starts work and records owner/branch/intent. |
| `In Progress` | Actively being worked on. | Assignee, agent, or branch is known. | PR opens, or work is paused with a comment explaining state. |
| `Review` | PR is open and needs review/CI. | PR links the issue and includes verification notes. | PR merges, is closed, or requires follow-up issue. |
| `Done` | Completed or intentionally closed. | PR merged, issue closed, or no-code resolution documented. | No further action. |

Agents must not move cards to `Done` just because local work is complete.

## Required Fields

Use these fields on every meaningful board item.

| Field | Values | Use |
| --- | --- | --- |
| `Priority` | `P0`, `P1`, `P2`, `P3` | Urgency and ordering. |
| `Type` | `security`, `bug`, `feature`, `refactor`, `docs`, `deps`, `chore` | Kind of work. |
| `Area` | `backend`, `frontend`, `infra`, `security`, `docs`, `repo` | Primary ownership area. |

Priority guidance:

- `P0`: active security exposure, data loss, production blocker, or live-operation safety issue.
- `P1`: important security work, blocker for planned delivery, or high-risk regression.
- `P2`: normal planned work.
- `P3`: cleanup, polish, low-risk maintenance.

## Agent-Ready Issue Shape

Every issue intended for an AI coding agent should include:

- Goal: one concrete outcome.
- Scope: files, modules, workflows, or behavior that may change.
- Out of scope: adjacent work the agent must not touch.
- Acceptance criteria: observable pass/fail bullets.
- Verification: exact commands or checks to run.
- Safety constraints: secrets, live TDLib, destructive commands, package installs, deploys, or external side effects.

Large work should be split into smaller issues or sub-issues. Prefer one issue to one branch to one pull request.

## Pull Request Requirements

Every PR should include:

- Linked issue, using `Closes #123` when the PR fully resolves it.
- Short summary of what changed.
- Verification commands that were run and their results.
- Commands/checks that were not run, with a reason.
- Risk notes for security, workspace isolation, migrations, TDLib/live behavior, queues, and deployment impact when relevant.

Move the linked card to `Review` only after the PR is open and has verification notes.

## Agent Session Protocol

Agents must follow this sequence when working on board items. Full details and API commands are in `.mex/patterns/board-workflow.md`.

### Session start

1. Identify the target issue (from user instruction or by querying `Todo` items with `ready-for-agent`).
2. Fetch the project item ID using the lookup query below.
3. Move the item to `In Progress` using the status mutation below.
4. Comment on the issue with branch name, intent, and scope.

### During work

- Reference `#<issue-number>` in commits and PR title.
- Comment on the issue if scope changes or blockers appear.

### Session end — PR opened

1. Add verification results to the PR body.
2. Link the issue with `Closes #N`.
3. Move the item to `Review`.

### Session end — no PR

1. Comment on the issue: current state, branch, what was done, what remains.
2. Leave the item in `In Progress`. Do not move back to `Todo` unless work is abandoned.

### Session end — task fully complete

1. Move to `Done` only after the PR is merged and the issue is closed.

## GraphQL Mutations Reference

### Lookup: fetch project item ID for an issue

```powershell
gh api graphql -f query='
  query($login:String!, $projectNumber:Int!) {
    user(login:$login) {
      projectV2(number:$projectNumber) {
        id
        items(first:50) {
          nodes {
            id
            content {
              ... on Issue { number }
              ... on PullRequest { number }
            }
          }
        }
        field(name:"Status") {
          ... on ProjectV2SingleSelectField {
            id
            options { id name }
          }
        }
      }
    }
  }
' -f login='pinnnthreetriples' -F projectNumber=1
```

From the response, extract `projectId`, `itemId` (matching target issue number), `fieldId` (Status field), and `optionId` (desired status).

### Mutation: update item status

```powershell
gh api graphql -f query='
  mutation($projectId:ID!, $itemId:ID!, $fieldId:ID!, $optionId:String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $projectId
      itemId: $itemId
      fieldId: $fieldId
      value: { singleSelectOptionId: $optionId }
    }) {
      clientMutationId
    }
  }
' -f projectId='<PROJECT_ID>' -f itemId='<ITEM_ID>' -f fieldId='<FIELD_ID>' -f optionId='<OPTION_ID>'
```

Always fetch IDs dynamically at session start. Do not hardcode across sessions. Verify the mutation took effect by re-querying.

## Safe Automation Expectations

The project has GitHub Project workflows enabled for item add/close, linked PRs, and merged PRs. Agents should still verify status after actions because automations may lag.

Suggested checks:

```powershell
gh issue view <number> --repo pinnnthreetriples/StylistTG
gh pr view <number> --repo pinnnthreetriples/StylistTG
gh api graphql -f query='query($login:String!, $number:Int!) { user(login:$login) { projectV2(number:$number) { items(first:20) { totalCount nodes { content { ... on Issue { number title state url } ... on PullRequest { number title state url } } } } } } }' -f login='pinnnthreetriples' -F number=1
```

## Updating Board Items By API

Use GitHub CLI or the GitHub connector when available. Confirm token scope includes `project` or `read:project` before relying on Project v2 APIs.

Useful field names:

- `Status`
- `Priority`
- `Type`
- `Area`

When using GraphQL, look up field and option IDs instead of hard-coding stale IDs unless you just fetched them in the same session.

## Handoff Rules

Before ending or handing off active board work:

1. Comment on the issue or PR with current state.
2. Include branch name, commands run, failures, and next action.
3. Leave the board status truthful.
4. Create follow-up issues for discovered work that is outside the current scope.

For long or complex work, use the project handoff skill/process and link the handoff from the issue or PR.

## Source Practices

This workflow follows GitHub's recommended project practices: keep a single source of truth, use issue/PR structure, use metadata fields, and rely on automation where it reduces manual status drift.
