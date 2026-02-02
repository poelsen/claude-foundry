# Claude Code Skills

Skills are reusable knowledge modules that provide domain-specific patterns, best practices, and implementation guidance.

## Available Skills

### GUI Development

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| [gui-threading](gui-threading/) | Framework-agnostic GUI threading | Any multithreaded GUI |
| [python-qt-gui](python-qt-gui/) | Python/Qt specific patterns | PySide6/PyQt6 apps |

**Relationship:** `python-qt-gui` extends `gui-threading`. Read the base skill first.

### Specialized Domains

| Skill | Purpose | When to Use |
|-------|---------|-------------|
| [clickhouse-io](clickhouse-io/) | ClickHouse analytics patterns | Data engineering |

## Skill Structure

Each skill directory contains:

```
skill-name/
├── SKILL.md    # Main skill content (required)
└── README.md   # Documentation (optional)
```

### SKILL.md Format

```markdown
---
name: skill-name
description: Brief description for skill discovery
extends: base-skill  # Optional: for extension skills
---

# Skill Title

Skill content with patterns, examples, checklists...
```

## How Skills Work

1. **Activation**: Skills are loaded based on context (project type, file patterns, explicit request)
2. **Content**: Provides patterns, code examples, checklists, anti-patterns
3. **Rules**: Skills often pair with rules files for non-negotiable constraints

## Skill vs Rule

| Aspect | Skill | Rule |
|--------|-------|------|
| Purpose | Guidance, patterns | Constraints, mandates |
| Tone | "Here's how to..." | "You MUST/MUST NOT..." |
| Flexibility | Multiple valid approaches | Non-negotiable |
| Location | `.claude/skills/` | `.claude/rules/` |

## Learned Skills

Patterns extracted from sessions via `/learn`. Organized by category:

```
skills/learned/
├── python/          # Python-specific patterns
├── debugging/       # Debugging techniques
└── <category>/      # Any category
    └── <pattern>.md
```

- **Shared** (`skills/learned/<cat>/`): Deployed to projects via `setup.py`, synced across machines
- **Project-local** (`<project>/.claude/skills/learned-local/<cat>/`): Project-specific, not managed by setup.py

Use `/recall` to list or search learned skills. Use `/learn` to extract new patterns.

Categories are selected during `setup.py init` — projects only get relevant categories.

## Creating New Skills

1. Create directory: `.claude/skills/my-skill/`
2. Create `SKILL.md` with YAML frontmatter
3. Add `README.md` for documentation
4. If it has non-negotiables, create matching rule in `.claude/rules/`

### Extension Skills

For framework-specific implementations:

```yaml
---
name: framework-specific-skill
extends: base-skill
---
```

Start content with: "This skill extends `base-skill`. Read that first."

## GUI Threading Skills

The `gui-threading` and `python-qt-gui` skills are based on:

- **MIT 6.005**: Thread safety strategies
- **KDAB**: Eight Rules of Multithreaded Qt
- **Facebook Flux**: Unidirectional data flow
- **Redux**: Immutable state management
- **Martin Fowler**: Event sourcing patterns

Key patterns:
- UI thread protection (no backend work)
- One-way data flow (Backend → Controller → Model → View)
- Worker job pattern (signals, cancellation)
- Immutable snapshots (frozen dataclass + tuple)
- Debounced event-driven refresh
- Multipane dock layouts

See [gui-threading/README.md](gui-threading/README.md) for details.
