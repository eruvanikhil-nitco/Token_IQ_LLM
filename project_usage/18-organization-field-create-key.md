# The Organization field in the create-key form

> **Status: REMOVED.** Field, its dropdown wiring, and the team filter it fed. The
> `OrganizationDropdown` component itself stays, because the key *edit* view still uses it.

## Why it went

Organizations are enterprise-gated. The nav entry was removed in change 12 and the Default
Organization row in Default Team Settings in change 16. This one survived both because it
lives inside the key creation form rather than a settings page.

It could never do anything here. Measured on the running proxy:

```bash
curl -s -H "Authorization: Bearer $MASTER_KEY" http://localhost:4001/organization/list
[]
```

An empty list, so the dropdown had nothing to offer. It was also `disabled` for every role
except Admin, and its only stated job was narrowing the team list, which an empty list
cannot narrow.

## What was removed

From `components/organisms/create_key_button.tsx`:

- the `Organization` `MountedFormField` and its `OrganizationDropdown`
- `changeOrganization`, which cleared team and project whenever the org changed
- the `selectedOrganizationId` state and its reset in the form-reset path
- the org auto-populate branch inside `selectTeam`, which copied `team.organization_id` into
  the form for non-admins
- `organizationId={selectedOrganizationId}` on the `TeamDropdown`, whose prop is optional and
  now simply unset, so the team list is never filtered
- the `useOrganizations` and `OrganizationDropdown` imports

`"organization_id"` stays in the `excludedFields` list passed to `SchemaFormFields`. Without
it the field would come straight back as a raw schema input in the Advanced Settings section,
which is the opposite of the point.

## What was deliberately left

`components/templates/key_edit_view.tsx` still renders an `OrganizationDropdown`. Editing a
key is a different form and was not in scope. It has the same problem and is the obvious next
removal if you want the concept gone entirely.

`useOrganizations` is still used by `VirtualKeysTable`, so the hook is not orphaned.

## The tests were a real contract, and they failed

This is worth recording because it is the good case. `create_key_button.integration.test.tsx`
pins the exact submit payload with `toStrictEqual` across eleven cases, and the fixture
carried `organization_id: undefined`. Removing the field broke ten of them immediately,
before any test was touched. That is the payload contract doing its job rather than a test
that had to be hunted down.

The three dropdown-specific tests (editable for admin, read-only for non-admin, routes a
chosen org into `organization_id`) were replaced with three that assert the new behaviour:

- no organization control renders *even when organizations exist*, which is stronger than
  asserting absence against an empty list
- `organization_id` is absent from the payload, not merely undefined
- a team can still be selected and reaches `team_id`, since the removed field used to filter
  that list

72 tests pass in that file. `ALL_CLOSED_PAYLOAD` and the per-section payload fixtures remain
the real guard: if the field ever comes back, strict equality catches it.

## How to restore

Revert this commit, then rebuild and redeploy the bundle:

```bash
cd ui/litellm-dashboard && npm run build
rm -rf ../../litellm/proxy/_experimental/out/* && cp -r ./out/* ../../litellm/proxy/_experimental/out/ && rm -rf ./out
```
