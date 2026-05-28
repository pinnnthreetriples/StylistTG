---
name: board-workflow
description: Agent session protocol for GitHub Project board status transitions.
edges:
  - .mex/ROUTER.md
  - docs/agents/project-board.md
last_updated: 2026-05-28
---

# Board Workflow Pattern

Agents working on StylistTG Development board items must follow this protocol.

Board: https://github.com/users/pinnnthreetriples/projects/1
Repository: pinnnthreetriples/StylistTG (GitHub)

## Session Start

1. **Identify the target issue.** If given an issue number, fetch it. If picking work, query the board for `Todo` items with `ready-for-agent` label.
2. **Fetch board metadata.** Run the lookup query to get the project item ID for the issue.
3. **Move to In Progress.** Run the status mutation with the In Progress option ID.
4. **Comment on the issue.** Post a short comment: branch name, intent, scope.

## During Work

- Keep issue comments current if scope changes or blockers appear.
- Reference the issue number in commit messages and PR title.

## Session End — PR opened

1. Verify tests/lint pass and add verification notes to the PR body.
2. Link the issue with `Closes #N` in the PR body.
3. **Move to Review.** Run the status mutation with the Review option ID.

## Session End — No PR

1. Comment on the issue: current state, branch, what was done, what remains.
2. **Leave In Progress.** Do not move back to Todo unless the work is abandoned.
3. Create follow-up issues for out-of-scope discoveries.

## Session End — Task fully done (merged, no-code closure)

1. **Move to Done.** Run the status mutation with the Done option ID.
2. Only do this when the PR is merged and the issue is closed.

## API Reference

### Lookup: find project item ID for an issue

```powershell
gh api graphql -f query='
  query($login:String!, $projectNumber:Int!, $issueNumber:Int!) {
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
' -f login='pinnnthreetriples' -F projectNumber=1 -F issueNumber=0
```

From the response, extract:
- `projectId`: the project's `id` field
- `itemId`: the `id` of the node whose `content.number` matches the target issue
- `fieldId`: the Status field `id`
- `optionId`: the `id` of the desired status option (Todo, In Progress, Review, Done)

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

### Verify: confirm status after mutation

Re-run the lookup query and check that the item's Status field matches the expected value.

### Set Priority, Type, or Area

Use the same mutation pattern with the appropriate field ID and option ID. Field names: `Priority`, `Type`, `Area`.

## Rules

- Always fetch IDs dynamically. Do not hardcode field or option IDs across sessions.
- Verify the mutation took effect before reporting success.
- Do not move to Done unless the PR is merged and issue is closed.
- If the gh token lacks `project` scope, report the error and proceed with code work without board updates.
