# Build & Publish `token-iq-migrations`

This runbook covers building and publishing a new version of the `token-iq-migrations` PyPI package. For use by litellm engineers only.

## Prerequisites

- All `schema.prisma` files are in sync (see [migration_runbook.md](./migration_runbook.md) Step 0)
- Migration has been generated and committed
- You are in the `token-iq-migrations/` directory

## Step 1: Bump the Version

### Option A: Automatic Version Bump (Recommended)

Use commitizen to automatically bump the version across all files:

```bash
cd token-iq-migrations
cz bump --increment patch
```

This will automatically:
- Bump the version in `pyproject.toml` (both `[project].version` and `[tool.commitizen].version`)
- Update the version in `../pyproject.toml` (root)
- Create a git commit with the version bump

Then skip to Step 3 (Clean Old Artifacts).

### Option B: Manual Version Bump

Update the version in `pyproject.toml`:

```bash
cd token-iq-migrations

# Check current version
grep 'version' pyproject.toml
```

Edit `pyproject.toml` and bump the version (both `[project].version` and `[tool.commitizen].version`).

#### Step 2: Update Version in the Root Package Metadata (Manual Only)

After bumping the version in `token-iq-migrations/pyproject.toml`, you **must** also update the version reference in the root `pyproject.toml`:

| File | Line to update |
|------|---------------|
| `pyproject.toml` (root) | `token-iq-migrations==X.Y.Z` in `[project.optional-dependencies].proxy` |

```bash
# From the repo root — replace OLD with NEW version
sed -i '' 's/token-iq-migrations==OLD/token-iq-migrations==NEW/' pyproject.toml
```

> **Do NOT skip this step.** The main `litellm` package pins the extras version — if you don't update these, users will install the old version.

## Step 3: Clean Old Artifacts

```bash
rm -rf dist/ build/ *.egg-info
```

## Step 4: Build the Package

```bash
uv build
```

This creates `.tar.gz` and `.whl` files in the `dist/` directory.

Verify the build output:

```bash
ls -la dist/
```

## Step 5: Upload to PyPI

```bash
uv tool run --from 'twine==6.2.0' twine upload dist/*
```

You will be prompted for your PyPI API token:

```
Enter your API token: pypi-...
```

> Use `__token__` as the username and your PyPI API token as the password.

## Quick Reference (Copy-Paste)

```bash
cd token-iq-migrations
rm -rf dist/ build/ *.egg-info
uv build
uv tool run --from 'twine==6.2.0' twine upload dist/*
```

---

## Do you want to build and publish a new `token-iq-migrations` package? (y/n)

If **yes**, run the following commands in order:

```bash
cd token-iq-migrations
rm -rf dist/ build/ *.egg-info
uv build
uv tool run --from 'twine==6.2.0' twine upload dist/*
```

When `twine upload` runs, enter your PyPI credentials:
- **Username:** `__token__`
- **Password:** *(paste your PyPI API key)*

If **no**, you're done — no package publish needed.
