# Update Codemaps

Generate or refresh architecture codemaps for the current project.

**Model:** Use opus for this command — it requires architectural judgment (analyzing code structure, extracting APIs, mapping data flow).

## Workflow

1. **Detect project language** from config files:
   - Python: pyproject.toml, setup.py
   - TypeScript: tsconfig.json, package.json
   - C/C++: CMakeLists.txt, Makefile
   - Go: go.mod
   - Rust: Cargo.toml

2. **Check staleness** of existing codemaps/:
   - If codemaps/ doesn't exist: generate all codemaps from scratch (first run)
   - Read YAML frontmatter from each codemap
   - Run `git diff <source_hash>..HEAD -- <files_covered>` per codemap
   - Report which are stale vs current
   - If none stale: "All codemaps current" and stop

3. **Regenerate stale codemaps:**
   - Read source files in the affected module
   - Extract: module purpose, key classes/functions, public API, dependencies, data flow
   - Write compact codemap (30-50 lines per module)

4. **Write codemaps/** with YAML frontmatter:
   ```yaml
   ---
   generated: YYYY-MM-DDTHH:MM:SSZ
   source_hash: <git rev-parse HEAD>
   files_covered:
     - src/module/*.py
   ---
   ```

5. **Report:** "X/Y codemaps updated, Z still current"

## Codemap Format (per module)

```markdown
# Module: [name]
**Path:** src/myproject/module/
**Purpose:** [1-2 sentences]

## Key Components
- ClassName — responsibility (file.py:line)
- function_name — responsibility (file.py:line)

## Public API
- method(args) → return — description
- signal_name(payload) — when emitted

## Dependencies
- module_a — what it uses

## Data Flow
[1-3 lines: how data enters, transforms, exits]
```

## INDEX.md Format

```markdown
# Project: [name]
**Language:** [Python/TypeScript/C++/etc.]
**Modules:** [count]

| Module | Path | Purpose |
|--------|------|---------|
| workers | src/workers/ | Background job execution |
| models | src/models/ | Data models and validation |
| ...    | ...          | ...                       |
```

## Output
- codemaps/ in project root (git-tracked)
- One file per architectural area (5-10 files typical)
- codemaps/INDEX.md — overview with 1-line per module
