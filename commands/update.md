# /update - Update Claude Foundry Configuration

Check for new releases and apply updates to the current project.

## Usage

- `/update` — Check for update and apply if available
- `/update --check` — Only check, don't apply
- `/update --interactive` — Apply with full interactive selection menu

## Process

### 1. Read manifest

Read `.claude/setup-manifest.json` to get:
- `repo_url` (e.g. `poelsen/claude-foundry`) — the GitHub repo to check
- `version` — currently installed version

If no manifest found: "No setup-manifest.json found. Run `setup.py init` first."

### 2. Check for updates

Fetch the latest release from GitHub:

```bash
curl -sL "https://api.github.com/repos/<repo_url>/releases/latest"
```

Extract the `tag_name` field. Compare with installed version.

If up to date: "Already on latest version (X)." and stop.

### 3. Confirm update

Show the user:
- Current version
- Available version
- Release notes URL

Ask for confirmation before proceeding. If `--check` was passed, stop here.

### 4. Download and extract

Download the release tarball:

```bash
curl -sL "https://api.github.com/repos/<repo_url>/releases/latest" | jq -r '.assets[0].browser_download_url'
```

Download to a temp directory and extract.

### 5. Apply update

Run setup.py from the extracted tarball:

```bash
python3 <temp_dir>/tools/setup.py init <project_dir> --non-interactive
```

If `--interactive` was passed, omit `--non-interactive`.

### 6. Clean up

Remove the temp directory. Report what changed (old version → new version).
