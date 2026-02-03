# /recall - Search Learned Skills

Search and surface learned patterns from previous sessions.

**Model:** Use haiku for this command — it's mechanical (glob files, read, display).

## Usage

- `/recall` — List all learned skills
- `/recall <keyword>` — Search by keyword

## Process

### List Mode (no argument)

1. Scan both directories for `.md` files:
   - `.claude/skills/learned/` (shared, deployed from claude_config)
   - `.claude/skills/learned-local/` (project-specific)
2. Group by category (subdirectory name)
3. For each skill, show: category, name, first-line description
4. If none found: "No learned skills found. Use `/learn` to extract patterns from your session."

### Search Mode (with keyword)

1. Scan both directories for `.md` files
2. Read each file and check if the keyword appears in the content (case-insensitive)
3. For matching files:
   - Read the full content
   - Present a summary: problem, solution, when to use
4. If no matches: "No learned skills matching '<keyword>'. Use `/recall` to see all available skills."

## Display Format

```
## Learned Skills

### <category>/
- **<skill-name>** — <first line of Problem section>

### <category>/
- **<skill-name>** — <first line of Problem section>
  [project-local]
```

Mark project-local skills with `[project-local]` to distinguish from shared ones.
