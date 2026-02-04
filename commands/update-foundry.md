# /update-foundry - Update Claude Foundry Configuration

Check for new releases and apply updates to the current project.

**Model:** Use haiku for this command — it's mechanical (fetch, compare, run script).

## Usage

- `/update-foundry` — Check for update and apply if available
- `/update-foundry --check` — Only check, don't apply
- `/update-foundry --interactive` — Apply with full interactive selection menu

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

### 5. Detect Python

Find a working Python 3 command. Try in order:

```bash
command -v python3 && python3 --version
```

If not found, try `python` and verify it's Python 3:

```bash
command -v python && python --version 2>&1 | grep -q "Python 3"
```

If not found, try uv:

```bash
command -v uv && uv run python3 --version
```

If none work: "Python 3 is required to apply updates. Install Python 3 or uv, then retry." and stop.

Use the first working command (`python3`, `python`, or `uv run python3`) as `PYTHON_CMD` below.

### 6. Save old state and apply update

Before running setup.py:
1. Read `.claude/setup-manifest.json` and save its content as `old_manifest`
2. List files in `.claude/commands/` and save as `old_commands`

Run setup.py from the extracted tarball:

```bash
<PYTHON_CMD> <temp_dir>/tools/setup.py init <project_dir> --non-interactive
```

If `--interactive` was passed, omit `--non-interactive`.

### 7. Clean up and report changes

Remove the temp directory. Report the version change (old → new).

Then compare old state with new state:

1. Read the new `.claude/setup-manifest.json` as `new_manifest`
2. List files in `.claude/commands/` as `new_commands`

**Compare and warn:**

**Commands** (compare `old_commands` vs `new_commands` file lists):
- If commands were added or removed: "Commands changed (<list>). New commands are available immediately."

**Rules** (compare `base_rules` and `modular_rules` fields):
- If rules changed: "Rules updated (<list>). They take effect on next interaction."

**Agents** (compare `agents` field):
- If agents changed: "Agents updated (<list>). They load on demand."

**Skills/hooks/plugins** (compare remaining fields):
- If changed: "Skills/hooks/plugins updated (<list>)."

If nothing changed besides version: "Version bumped, configuration unchanged."
