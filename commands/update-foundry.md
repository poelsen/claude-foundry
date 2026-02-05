# /update-foundry - Update Claude Foundry Configuration

**Model:** haiku (mechanical)

## Usage

- `/update-foundry` — Check and apply update
- `/update-foundry --check` — Check only
- `/update-foundry --interactive` — Full interactive menu

## Process

1. **Read manifest** (`.claude/setup-manifest.json`): get `repo_url`, `version`
2. **Check latest**: `curl -sL "https://api.github.com/repos/<repo_url>/releases/latest"` → compare `tag_name`
3. **Confirm**: Show current/available versions, release URL. Stop if `--check`.
4. **Download**: Get tarball URL from `.assets[0].browser_download_url`, extract to temp dir
5. **Find Python**: Try `python3`, `python` (if v3), `uv run python3`
6. **Save state**: Read old manifest, list old commands
7. **Apply**: `<python> <temp>/tools/setup.py init <project> --non-interactive` (omit flag if `--interactive`)
8. **Report changes**:
   - Commands changed → "available immediately"
   - Rules changed → "take effect next interaction"
   - Agents changed → "load on demand"
   - Nothing changed → "Version bumped, configuration unchanged"
