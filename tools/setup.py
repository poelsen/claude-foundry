#!/usr/bin/env python3
"""Claude Code per-project setup tool.

Configures a project's .claude/ directory with selected rules, hooks,
agents, skills, plugins, and MCP servers from the claude-foundry repo.

Usage:
    python3 tools/setup.py init [project_dir]
    python3 tools/setup.py update-all
    python3 tools/setup.py check
    python3 tools/setup.py version
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── CLAUDE.md Header ────────────────────────────────────────────────────

CLAUDE_FOUNDRY_MARKER_START = "<!-- claude-foundry -->"
CLAUDE_FOUNDRY_MARKER_END = "<!-- /claude-foundry -->"

CLAUDE_FOUNDRY_HEADER_TEMPLATE = """{marker_start}
## Rules

Read rules in `.claude/rules/` before making changes:
{rules_list}

## Environment

```bash
{env_commands}
```

## Architecture

Read `codemaps/INDEX.md` before modifying unfamiliar modules.
Run `/update-codemaps` after significant structural changes.

## Documentation

Read `docs/` for detailed project documentation (if it exists).
- `docs/ARCHITECTURE.md` — design decisions and patterns
- `docs/DEVELOPMENT.md` — setup and workflow guides
{marker_end}
"""

ENVIRONMENT_SNIPPETS = {
    "python.md": {
        "setup": "uv venv && uv pip install -e .[dev]",
        "test": "uv run pytest",
        "lint": "uv run ruff check src tests",
        "format": "uv run ruff format src tests",
    },
    "rust.md": {
        "setup": "cargo build",
        "test": "cargo test",
        "lint": "cargo clippy",
        "format": "cargo fmt",
    },
    "go.md": {
        "setup": "go mod download",
        "test": "go test ./...",
        "lint": "golangci-lint run",
        "format": "go fmt ./...",
    },
    "nodejs.md": {
        "setup": "npm install",
        "test": "npm test",
        "lint": "npm run lint",
    },
    "react.md": {
        "setup": "npm install",
        "test": "npm test",
        "lint": "npm run lint",
        "dev": "npm run dev",
    },
    "c.md": {
        "setup": "mkdir -p build && cd build && cmake ..",
        "build": "cmake --build build",
        "test": "ctest --test-dir build",
    },
    "cpp.md": {
        "setup": "mkdir -p build && cd build && cmake ..",
        "build": "cmake --build build",
        "test": "ctest --test-dir build",
    },
}

# ── Registry ────────────────────────────────────────────────────────────

BASE_RULES = [
    "coding-style.md", "git-workflow.md", "security.md", "testing.md",
    "architecture.md", "performance.md", "agents.md", "hooks.md", "codemaps.md",
]

MODULAR_RULES = {
    "lang": {
        "python.md": {"detect": [".py"], "config": ["pyproject.toml", "requirements.txt"]},
        "python-qt.md": {"detect": [], "config": [], "dep_keywords": ["PySide6", "PyQt"]},
        "react.md": {"detect": [], "config": [], "dep_keywords": ["react"]},
        "nodejs.md": {"detect": [], "config": ["package.json"]},
        "c.md": {"detect": [".c"], "config": ["CMakeLists.txt"]},
        "c-embedded.md": {"detect": [], "config": [], "manual": True},
        "cpp.md": {"detect": [".cpp", ".cc", ".cxx", ".hpp"]},
        "go.md": {"detect": [".go"], "config": ["go.mod"]},
        "rust.md": {"detect": [".rs"], "config": ["Cargo.toml"]},
        "matlab.md": {"detect": [".m"]},
    },
    "style": {
        "backend.md": {}, "scripts.md": {},
        "library.md": {}, "data-pipeline.md": {},
    },
    "arch": {
        "rest-api.md": {}, "react-app.md": {}, "monolith.md": {},
    },
    "domain": {
        "gui.md": {}, "gui-threading.md": {}, "embedded.md": {}, "dsp-audio.md": {},
    },
    "platform": {
        "github.md": {"detect_dir": [".github"]},
    },
    "security": {
        "enterprise.md": {}, "internal.md": {}, "sandbox.md": {},
    },
}

HOOK_SCRIPTS = {
    "ruff-format.sh": {"langs": ["python.md"], "desc": "Python formatting (ruff)"},
    "prettier-format.sh": {"langs": ["react.md", "nodejs.md"], "desc": "JS/TS formatting (prettier)"},
    "tsc-check.sh": {"langs": ["react.md", "nodejs.md"], "desc": "TypeScript type checking"},
    "mypy-check.sh": {"langs": ["python.md"], "desc": "Python type checking (mypy)"},
    "cargo-check.sh": {"langs": ["rust.md"], "desc": "Rust type checking (cargo check)"},
}

AGENTS_DIR = REPO_ROOT / "agents"
COMMANDS_DIR = REPO_ROOT / "commands"
LEARNED_SKILLS_DIR = REPO_ROOT / "skills" / "learned"

SKILLS = [
    "clickhouse-io", "gui-threading", "python-qt-gui",
]

LSP_PLUGINS = {
    "python.md": ("pyright-lsp", "pyright-langserver"),
    "react.md": ("typescript-lsp", "typescript-language-server"),
    "nodejs.md": ("typescript-lsp", "typescript-language-server"),
    "rust.md": ("rust-analyzer-lsp", "rust-analyzer"),
    "go.md": ("gopls-lsp", "gopls"),
    "c.md": ("clangd-lsp", "clangd"),
    "cpp.md": ("clangd-lsp", "clangd"),
}

WORKFLOW_PLUGINS = [
    ("feature-dev", "7-phase feature workflow"),
    ("pr-review-toolkit", "PR analysis suite"),
    ("code-review", "Automated PR feedback"),
    ("code-simplifier", "Autonomous refactoring"),
]

MCP_SERVERS_FILE = REPO_ROOT / "mcp-configs" / "mcp-servers.json"

# ── Helpers ─────────────────────────────────────────────────────────────


def read_version() -> str:
    """Read version from VERSION file (tarball) or git tag (clone)."""
    version_file = REPO_ROOT / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding='utf-8').strip()
    # Fall back to latest git tag
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "dev"


def toggle_menu(title: str, items: list[str], selected: set[int],
                required_one: bool = False) -> set[int]:
    """Interactive toggle menu. Returns set of selected indices."""
    while True:
        print(f"\n=== {title} ===")
        for i, item in enumerate(items):
            mark = "X" if i in selected else " "
            print(f"  [{mark}] {i + 1}. {item}")
        prompt = "Toggle (space-separated numbers, Enter to confirm): "
        raw = input(prompt).strip()
        if not raw:
            if required_one and not selected:
                print("  ⚠ At least one selection required.")
                continue
            return selected
        for token in raw.split():
            try:
                idx = int(token) - 1
                if 0 <= idx < len(items):
                    selected ^= {idx}
            except ValueError:
                pass


def confirm(msg: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{msg} {suffix} ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def ask_int(msg: str, default: int) -> int:
    raw = input(f"{msg} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def save_manifest(project: Path, manifest: dict) -> None:
    """Save selection manifest for future re-init / update-all."""
    dest = project / ".claude" / "setup-manifest.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, indent=2) + "\n", encoding='utf-8')


def load_manifest(project: Path) -> dict | None:
    """Load saved selection manifest, or None if not present."""
    src = project / ".claude" / "setup-manifest.json"
    if src.exists():
        try:
            return json.loads(src.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def generate_claude_foundry_header(
    deployed_rules: list[str],
    selected_langs: set[str],
) -> str:
    """Generate the claude-foundry header for CLAUDE.md."""
    # Build rules list
    rule_descriptions = {
        # Language/tooling rules
        "python.md": "Python tooling (uv, pytest, ruff)",
        "rust.md": "Rust tooling (cargo, clippy)",
        "go.md": "Go tooling (go mod, golangci-lint)",
        "nodejs.md": "Node.js tooling (npm)",
        "react.md": "React/TypeScript tooling",
        "c.md": "C tooling (CMake, clang)",
        "cpp.md": "C++ tooling (CMake, clang)",
        "matlab.md": "MATLAB tooling",
        # Platform rules
        "github.md": "GitHub workflow (gh CLI, PR conventions)",
        # Base rules
        "coding-style.md": "Code style guidelines",
        "git-workflow.md": "Git workflow and commit conventions",
        "security.md": "Security checks and practices",
        "testing.md": "Testing requirements (TDD, 80% coverage)",
        "architecture.md": "Architecture principles",
        "performance.md": "Performance and model selection",
        "agents.md": "Agent orchestration",
        "codemaps.md": "Codemap system",
        "hooks.md": "Hooks system",
    }

    # Sort rules with tooling rules first (language + platform), then alphabetically
    lang_rules = set(MODULAR_RULES.get("lang", {}).keys())
    platform_rules = set(MODULAR_RULES.get("platform", {}).keys())
    tooling_rules = lang_rules | platform_rules

    tooling_first = sorted(r for r in deployed_rules if r in tooling_rules)
    other_rules = sorted(r for r in deployed_rules if r not in tooling_rules)
    ordered_rules = tooling_first + other_rules

    rules_lines = []
    for rule in ordered_rules:
        desc = rule_descriptions.get(rule, rule.replace(".md", "").replace("-", " ").title())
        rules_lines.append(f"- `{rule}` — {desc}")
    rules_list = "\n".join(rules_lines) if rules_lines else "- (none deployed)"

    # Build environment commands
    env_lines = []
    for lang in sorted(selected_langs):
        if lang in ENVIRONMENT_SNIPPETS:
            snippets = ENVIRONMENT_SNIPPETS[lang]
            if "setup" in snippets:
                env_lines.append(f"{snippets['setup']}  # Setup")
            if "test" in snippets:
                env_lines.append(f"{snippets['test']}  # Tests")
    env_commands = "\n".join(env_lines) if env_lines else "# No language-specific commands configured"

    return CLAUDE_FOUNDRY_HEADER_TEMPLATE.format(
        marker_start=CLAUDE_FOUNDRY_MARKER_START,
        marker_end=CLAUDE_FOUNDRY_MARKER_END,
        rules_list=rules_list,
        env_commands=env_commands,
    )


def has_claude_foundry_header(content: str) -> bool:
    """Check if content has claude-foundry marker."""
    return CLAUDE_FOUNDRY_MARKER_START in content


def update_claude_foundry_header(content: str, new_header: str) -> str:
    """Replace existing claude-foundry header with new one."""
    start_idx = content.find(CLAUDE_FOUNDRY_MARKER_START)
    end_idx = content.find(CLAUDE_FOUNDRY_MARKER_END)

    if start_idx == -1 or end_idx == -1:
        return content

    # Include the end marker in the replacement
    end_idx += len(CLAUDE_FOUNDRY_MARKER_END)

    return content[:start_idx] + new_header.strip() + content[end_idx:]


def prepend_claude_foundry_header(content: str, header: str) -> str:
    """Prepend header to content with blank line separator."""
    return header + "\n" + content


def resolve_project_path(encoded_name: str) -> Path | None:
    """Resolve ~/.claude/projects/ encoded dir name to actual filesystem path.

    The encoding replaces both '/' and '_' with '-', so we greedily
    reconstruct by testing which dashes are directory separators vs underscores.
    """
    parts = encoded_name.lstrip("-").split("-")
    if len(parts) < 2:
        return None
    base = Path("/") / parts[0] / parts[1]  # /home/rudm
    remaining = parts[2:]

    def _find(base: Path, remaining: list[str]) -> Path | None:
        if not remaining:
            return base if base.is_dir() else None
        for take in range(1, len(remaining) + 1):
            # Try underscore join
            candidate = base / "_".join(remaining[:take])
            if candidate.is_dir():
                result = _find(candidate, remaining[take:])
                if result:
                    return result
            # Try hyphen join (for dirs with actual hyphens)
            if take > 1:
                candidate = base / "-".join(remaining[:take])
                if candidate.is_dir():
                    result = _find(candidate, remaining[take:])
                    if result:
                        return result
            # Try single part as-is (no join needed for take==1, already covered by underscore)
            if take == 1:
                candidate = base / remaining[0]
                if candidate.is_dir():
                    result = _find(candidate, remaining[1:])
                    if result:
                        return result
        return None

    return _find(base, remaining)


def discover_projects() -> list[tuple[Path, bool]]:
    """Discover known projects from ~/.claude/projects/.

    Returns list of (project_path, has_setup) tuples.
    """
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.is_dir():
        return []
    results = []
    for d in sorted(projects_dir.iterdir()):
        if not d.is_dir():
            continue
        resolved = resolve_project_path(d.name)
        if resolved and resolved.is_dir():
            has_setup = (resolved / ".claude" / "VERSION").exists()
            results.append((resolved, has_setup))
    return results


# ── Detection ───────────────────────────────────────────────────────────


def scan_extensions(project: Path) -> set[str]:
    """Scan top 3 levels for file extensions."""
    exts: set[str] = set()
    base_depth = len(project.parts)
    for dirpath, dirnames, filenames in os.walk(project):
        depth = len(Path(dirpath).parts) - base_depth
        if depth >= 3:
            dirnames.clear()
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        for f in filenames:
            ext = Path(f).suffix
            if ext:
                exts.add(ext)
    return exts


def detect_languages(project: Path) -> set[str]:
    """Return set of detected lang rule names."""
    exts = scan_extensions(project)
    detected: set[str] = set()

    for rule, meta in MODULAR_RULES["lang"].items():
        if meta.get("manual"):
            continue
        # Extension match
        for ext in meta.get("detect", []):
            if ext in exts:
                detected.add(rule)
        # Config file match
        for cfg in meta.get("config", []):
            if (project / cfg).exists():
                detected.add(rule)

    # Dependency keyword detection (python-qt, react)
    dep_text = _read_dep_files(project)
    for rule, meta in MODULAR_RULES["lang"].items():
        for kw in meta.get("dep_keywords", []):
            if kw.lower() in dep_text.lower():
                detected.add(rule)

    # React vs nodejs disambiguation
    if "react.md" in detected and "nodejs.md" in detected:
        # If react detected via dependency, nodejs is redundant for frontend
        pass  # Keep both, let user deselect

    return detected


def _read_dep_files(project: Path) -> str:
    """Read dependency files for keyword scanning."""
    text = ""
    for name in ["package.json", "pyproject.toml", "requirements.txt"]:
        p = project / name
        if p.exists():
            try:
                text += p.read_text(encoding='utf-8', errors="ignore")
            except OSError:
                pass
    return text


def detect_platform(project: Path) -> set[str]:
    detected: set[str] = set()
    if (project / ".github").is_dir():
        detected.add("github.md")
    else:
        # Check git remote for github.com
        try:
            result = subprocess.run(
                ["git", "-C", str(project), "remote", "-v"],
                capture_output=True, text=True, timeout=5,
            )
            if "github.com" in result.stdout:
                detected.add("github.md")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return detected


# ── Generation ──────────────────────────────────────────────────────────


def generate_settings_json(
    hooks: list[str],
    plugins: list[str],
) -> dict:
    """Build .claude/settings.json content."""
    settings: dict = {}

    # Plugins
    if plugins:
        settings["enabledPlugins"] = {
            f"{p}@claude-plugins-official": True for p in plugins
        }

    # Hooks
    hook_entries: dict[str, list] = {}

    post_hooks = []
    for script in hooks:
        meta = HOOK_SCRIPTS[script]
        # Determine matcher from script name
        if "ruff" in script or "mypy" in script:
            matcher = 'tool == "Edit" && tool_input.file_path matches "\\.py$"'
        elif "prettier" in script:
            matcher = 'tool == "Edit" && tool_input.file_path matches "\\.(ts|tsx|js|jsx)$"'
        elif "tsc" in script:
            matcher = 'tool == "Edit" && tool_input.file_path matches "\\.(ts|tsx)$"'
        elif "cargo" in script:
            matcher = 'tool == "Edit" && tool_input.file_path matches "\\.rs$"'
        else:
            matcher = ""

        post_hooks.append({
            "matcher": matcher,
            "hooks": [{"type": "command", "command": f".claude/hooks/library/{script}"}],
            "description": meta["desc"],
        })

    if post_hooks:
        hook_entries.setdefault("PostToolUse", []).extend(post_hooks)

    if hook_entries:
        settings["hooks"] = hook_entries

    return settings


def generate_claude_md(
    project_name: str,
    deployed_rules: list[str],
    selected_langs: set[str],
) -> str:
    """Generate a new CLAUDE.md with claude-foundry header."""
    header = generate_claude_foundry_header(deployed_rules, selected_langs)
    return f"""# {project_name}

{header}
"""


def copy_rules(project: Path, base: list[str], modular: dict[str, list[str]]) -> None:
    rules_dir = project / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    # Base rules
    for rule in base:
        src = REPO_ROOT / "rules" / rule
        if src.exists():
            shutil.copy2(src, rules_dir / rule)

    # Modular rules (flatten into same dir with category prefix)
    for category, rules in modular.items():
        for rule in rules:
            src = REPO_ROOT / "rule-library" / category / rule
            if src.exists():
                dest_name = f"{category}-{rule}" if rule in base else rule
                # Avoid name collisions with base rules
                if (rules_dir / rule).exists() and rule in base:
                    dest_name = f"{category}-{rule}"
                else:
                    dest_name = rule
                shutil.copy2(src, rules_dir / dest_name)


def copy_agents(project: Path, agents: list[str]) -> None:
    dest = project / ".claude" / "agents"
    dest.mkdir(parents=True, exist_ok=True)
    # Remove stale agents not in current selection
    wanted = set(agents)
    for existing in dest.iterdir():
        if existing.suffix == ".md" and existing.name not in wanted:
            existing.unlink()
    for agent in agents:
        src = AGENTS_DIR / agent
        if src.exists():
            shutil.copy2(src, dest / agent)


def copy_commands(project: Path) -> None:
    """Copy all slash commands to the project."""
    if not COMMANDS_DIR.is_dir():
        return
    dest = project / ".claude" / "commands"
    dest.mkdir(parents=True, exist_ok=True)
    # Remove stale commands not in source
    source_names = {f.name for f in COMMANDS_DIR.iterdir() if f.suffix == ".md"}
    for existing in dest.iterdir():
        if existing.suffix == ".md" and existing.name not in source_names:
            existing.unlink()
    for src in COMMANDS_DIR.iterdir():
        if src.suffix == ".md":
            shutil.copy2(src, dest / src.name)


def discover_learned_categories() -> list[str]:
    """Return sorted list of learned skill category directories."""
    if not LEARNED_SKILLS_DIR.is_dir():
        return []
    return sorted(
        d.name for d in LEARNED_SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def copy_learned_skills(project: Path, categories: list[str]) -> None:
    """Deploy selected learned skill categories to the project."""
    if not categories:
        return
    dest_base = project / ".claude" / "skills" / "learned"
    local_base = project / ".claude" / "skills" / "learned-local"

    for cat in categories:
        src = LEARNED_SKILLS_DIR / cat
        if not src.is_dir():
            continue
        dest = dest_base / cat
        dest.mkdir(parents=True, exist_ok=True)
        for skill_file in src.iterdir():
            if skill_file.suffix == ".md":
                # Warn on conflict with project-local skills
                local_conflict = local_base / cat / skill_file.name
                if local_conflict.exists():
                    print(f"  ⚠ Conflict: {skill_file.name} exists in both learned/ and learned-local/{cat}/")
                shutil.copy2(skill_file, dest / skill_file.name)


def copy_skills(project: Path, skills: list[str]) -> None:
    for skill in skills:
        src = REPO_ROOT / "skills" / skill
        dest = project / ".claude" / "skills" / skill
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)


def copy_hooks(project: Path, hooks: list[str]) -> None:
    if hooks:
        lib_dest = project / ".claude" / "hooks" / "library"
        lib_dest.mkdir(parents=True, exist_ok=True)
        for script in hooks:
            src = REPO_ROOT / "hooks" / "library" / script
            if src.exists():
                dest = lib_dest / script
                shutil.copy2(src, dest)
                dest.chmod(dest.stat().st_mode | 0o111)


def write_mcp_servers(project: Path, servers: list[str]) -> None:
    if not servers or not MCP_SERVERS_FILE.exists():
        return
    all_servers = json.loads(MCP_SERVERS_FILE.read_text(encoding='utf-8'))["mcpServers"]
    selected = {k: v for k, v in all_servers.items() if k in servers}
    # Remove description fields (not valid in .claude.json)
    for srv in selected.values():
        srv.pop("description", None)
    claude_json = project / ".claude.json"
    data = {}
    if claude_json.exists():
        try:
            data = json.loads(claude_json.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            pass
    data.setdefault("mcpServers", {}).update(selected)
    claude_json.write_text(json.dumps(data, indent=2) + "\n", encoding='utf-8')


# ── Commands ────────────────────────────────────────────────────────────


def cmd_version() -> None:
    print(f"claude-foundry version: {read_version()}")


def cmd_check() -> None:
    local = read_version()
    print(f"Local repo version: {local}")
    # Try fetching from GitHub
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-remote", "--tags", "origin"],
            capture_output=True, text=True, timeout=10,
        )
        tags = [
            line.split("refs/tags/")[-1].strip()
            for line in result.stdout.strip().splitlines()
            if "refs/tags/" in line and "^{}" not in line
        ]
        if tags:
            latest = sorted(tags)[-1]
            if latest > local:
                print(f"Latest on GitHub: {latest} — update available")
                print(f"  cd {REPO_ROOT} && git pull && python3 tools/setup.py init")
            else:
                print("Up to date.")
        else:
            print("No tags found on remote. Use git log to check for updates.")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"Could not check remote: {e}")


def cmd_init(project: Path, interactive: bool = True, force: bool = False) -> bool:
    """Initialize or update a project. Returns True on success.

    Args:
        project: Path to the project directory
        interactive: Whether to prompt for choices
        force: Force update even if CLAUDE.md has no marker (with confirmation)
    """
    version = read_version()
    project = project.resolve()
    project_name = project.name

    print(f"Claude Config Setup v{version}")
    print(f"Project: {project}")
    print()

    # ── Pre-checks ──
    version_file = project / ".claude" / "VERSION"
    if version_file.exists() and interactive:
        existing = version_file.read_text(encoding='utf-8').strip()
        if existing == version:
            if not confirm("Already configured with current version. Reconfigure?", default=False):
                return False
        elif existing < version:
            if not confirm(f"Project configured with {existing}, repo is {version}. Update?"):
                return False
        else:
            print(f"Project version ({existing}) is newer than repo ({version}). Aborting.")
            return False

    # ── Load manifest for defaults ──
    manifest = load_manifest(project)

    def _manifest_indices(registry_items: list[str], manifest_key: str,
                          manifest_sub: str | None = None) -> set[int]:
        """Compute pre-selected indices from manifest."""
        if not manifest:
            return set()
        saved = manifest.get(manifest_key, []) if not manifest_sub else \
            manifest.get(manifest_key, {}).get(manifest_sub, [])
        return {i for i, item in enumerate(registry_items) if item in saved}

    # ── 1. Detect languages ──
    print("Scanning project for languages...")
    detected_langs = detect_languages(project)
    detected_platform = detect_platform(project)

    if detected_langs:
        print(f"Detected: {', '.join(sorted(r.replace('.md', '') for r in detected_langs))}")
    else:
        print("No languages auto-detected.")

    # ── 2. Base rules ──
    if manifest:
        base_defaults = _manifest_indices(BASE_RULES, "base_rules")
    else:
        base_defaults = set(range(len(BASE_RULES)))

    if interactive:
        base_selected = toggle_menu("Base Rules (all recommended)", BASE_RULES, base_defaults)
    else:
        base_selected = base_defaults
    selected_base = [BASE_RULES[i] for i in sorted(base_selected)]

    # ── 3. Modular rules ──
    selected_modular: dict[str, list[str]] = {}

    for category in ["lang", "style", "arch", "domain", "platform", "security"]:
        rules = list(MODULAR_RULES[category].keys())
        if not rules:
            continue

        # Defaults: manifest takes precedence, then auto-detection
        if manifest:
            auto = _manifest_indices(rules, "modular_rules", category)
        else:
            auto = set()
            for i, rule in enumerate(rules):
                if category == "lang" and rule in detected_langs:
                    auto.add(i)
                elif category == "platform" and rule in detected_platform:
                    auto.add(i)

        required = category == "security"
        if interactive:
            result = toggle_menu(
                f"Rules: {category}/" + (" (select exactly one)" if required else ""),
                [f"{rule}" for rule in rules],
                auto,
                required_one=required,
            )
        else:
            result = auto
        chosen = [rules[i] for i in sorted(result)]
        if chosen:
            selected_modular[category] = chosen

    # Collect all selected lang rules for hook/plugin auto-detection
    selected_langs = set(selected_modular.get("lang", []))

    # ── 4. Hooks ──
    hook_names = list(HOOK_SCRIPTS.keys())
    if manifest:
        hook_auto = _manifest_indices(hook_names, "hooks")
    else:
        hook_auto = set()
        for i, script in enumerate(hook_names):
            meta = HOOK_SCRIPTS[script]
            if any(lang in selected_langs for lang in meta["langs"]):
                hook_auto.add(i)

    if interactive:
        hook_selected = toggle_menu(
            "Hooks (auto-selected by language)",
            [f"{s} — {HOOK_SCRIPTS[s]['desc']}" for s in hook_names],
            hook_auto,
        )
    else:
        hook_selected = hook_auto
    selected_hooks = [hook_names[i] for i in sorted(hook_selected)]

    # ── 5. Agents ──
    agent_files = sorted(f.name for f in AGENTS_DIR.iterdir() if f.suffix == ".md") if AGENTS_DIR.is_dir() else []
    if manifest:
        agent_auto = _manifest_indices(agent_files, "agents")
    else:
        agent_auto = set()
        for i, af in enumerate(agent_files):
            for lang in selected_langs:
                lang_key = lang.replace(".md", "")
                if f"-{lang_key}." in af or af.startswith(f"{lang_key}."):
                    agent_auto.add(i)
            if any(l in selected_langs for l in ["react.md", "nodejs.md"]):
                if "typescript" in af:
                    agent_auto.add(i)

    if interactive:
        agent_selected = toggle_menu("Agents", agent_files, agent_auto)
    else:
        agent_selected = agent_auto
    selected_agents = [agent_files[i] for i in sorted(agent_selected)]

    # ── 6. Skills ──
    if manifest:
        skill_auto = _manifest_indices(SKILLS, "skills")
    else:
        skill_auto = set()
        for i, skill in enumerate(SKILLS):
            if skill == "gui-threading" and "python-qt.md" in selected_langs:
                skill_auto.add(i)
            if skill == "python-qt-gui" and "python-qt.md" in selected_langs:
                skill_auto.add(i)

    if interactive:
        skill_selected = toggle_menu("Skills", SKILLS, skill_auto)
    else:
        skill_selected = skill_auto
    selected_skills = [SKILLS[i] for i in sorted(skill_selected)]

    # ── 6b. Learned Skills ──
    learned_cats = discover_learned_categories()
    selected_learned: list[str] = []
    if learned_cats:
        if manifest:
            learned_auto = _manifest_indices(learned_cats, "learned_categories")
        else:
            learned_auto = set(range(len(learned_cats)))  # All selected by default

        if interactive:
            learned_selected = toggle_menu(
                "Learned Skills (categories)",
                learned_cats,
                learned_auto,
            )
        else:
            learned_selected = learned_auto
        selected_learned = [learned_cats[i] for i in sorted(learned_selected)]

    # ── 7. Plugins ──
    lsp_plugins: list[tuple[str, str]] = []
    seen_lsp: set[str] = set()
    for lang in selected_langs:
        if lang in LSP_PLUGINS:
            plugin, binary = LSP_PLUGINS[lang]
            if plugin not in seen_lsp:
                lsp_plugins.append((plugin, binary))
                seen_lsp.add(plugin)

    all_plugins = [(p, f"LSP: {b}") for p, b in lsp_plugins] + [(p, d) for p, d in WORKFLOW_PLUGINS]
    plugin_names = [f"{p} — {d}" for p, d in all_plugins]

    if manifest:
        saved_plugins = manifest.get("plugins", [])
        plugin_auto = {i for i, (p, _) in enumerate(all_plugins) if p in saved_plugins}
    else:
        plugin_auto = set(range(len(all_plugins)))

    if interactive:
        plugin_selected = toggle_menu("Plugins", plugin_names, plugin_auto)
    else:
        plugin_selected = plugin_auto
    selected_plugins = [all_plugins[i][0] for i in sorted(plugin_selected)]

    # ── 8. MCP servers ──
    mcp_servers: list[str] = []
    if MCP_SERVERS_FILE.exists():
        all_mcp = json.loads(MCP_SERVERS_FILE.read_text(encoding='utf-8'))["mcpServers"]
        mcp_names = list(all_mcp.keys())
        mcp_descs = [f"{k} — {v.get('description', '')}" for k, v in all_mcp.items()]

        if manifest:
            saved_mcp = manifest.get("mcp_servers", [])
            mcp_auto = {i for i, name in enumerate(mcp_names) if name in saved_mcp}
        else:
            mcp_auto = set()

        if interactive:
            mcp_selected = toggle_menu("MCP Servers (optional)", mcp_descs, mcp_auto)
        else:
            mcp_selected = mcp_auto
        mcp_servers = [mcp_names[i] for i in sorted(mcp_selected)]

    # ── Pre-check CLAUDE.md for non-interactive mode ──
    claude_md = project / "CLAUDE.md"
    force_merge = False
    if not interactive and claude_md.exists():
        existing_content = claude_md.read_text(encoding='utf-8')
        if not has_claude_foundry_header(existing_content):
            if force:
                # Force flag — ask for confirmation before proceeding
                print(f"\n  WARNING: CLAUDE.md exists without claude-foundry marker.")
                print(f"  Force will merge the header into your existing CLAUDE.md.")
                if not confirm("  Proceed with force merge?", default=False):
                    print("  Aborted.")
                    return False
                force_merge = True
            else:
                # Non-interactive and no marker — skip entire project
                print(f"\n  CLAUDE.md exists without claude-foundry marker — skipping project")
                print(f"")
                print(f"  To add the marker, run setup.py init interactively:")
                print(f"    python3 <claude-foundry>/tools/setup.py init {project}")
                print(f"  Or use --force to merge the header (with confirmation).")
                return False

    # ── Generate ──
    print("\nGenerating project configuration...")

    claude_dir = project / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    # VERSION
    (claude_dir / "VERSION").write_text(version + "\n", encoding='utf-8')

    # Rules
    copy_rules(project, selected_base, selected_modular)

    # Agents
    if selected_agents:
        copy_agents(project, selected_agents)

    # Commands
    copy_commands(project)

    # Skills
    if selected_skills:
        copy_skills(project, selected_skills)

    # Learned Skills
    if selected_learned:
        copy_learned_skills(project, selected_learned)

    # Hooks
    copy_hooks(project, selected_hooks)

    # settings.json
    settings = generate_settings_json(selected_hooks, selected_plugins)
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding='utf-8')

    # MCP servers
    if mcp_servers:
        write_mcp_servers(project, mcp_servers)

    # Save manifest
    save_manifest(project, {
        "version": version,
        "config_repo": str(REPO_ROOT),
        "repo_url": "poelsen/claude-foundry",
        "base_rules": selected_base,
        "modular_rules": selected_modular,
        "hooks": selected_hooks,
        "agents": selected_agents,
        "skills": selected_skills,
        "learned_categories": selected_learned,
        "plugins": selected_plugins,
        "mcp_servers": mcp_servers,
    })

    # Compute deployed rules list for CLAUDE.md header
    deployed_rules = selected_base.copy()
    for rules in selected_modular.values():
        deployed_rules.extend(rules)

    # CLAUDE.md
    claude_md = project / "CLAUDE.md"
    header = generate_claude_foundry_header(deployed_rules, selected_langs)

    if claude_md.exists():
        existing_content = claude_md.read_text(encoding='utf-8')
        lines = existing_content.count("\n")
        chars = len(existing_content)

        if has_claude_foundry_header(existing_content):
            # Has marker — update header silently
            updated_content = update_claude_foundry_header(existing_content, header)
            claude_md.write_text(updated_content, encoding='utf-8')
            print(f"  Updated claude-foundry header in CLAUDE.md")
        elif interactive:
            # No marker — offer options
            print(f"\n  CLAUDE.md exists ({lines} lines, {chars} chars)")
            print("  Options:")
            print("    [R] Replace — Generate new CLAUDE.md (saves original as .old)")
            print("    [M] Merge — Prepend claude-foundry header (saves original as .old)")
            print("    [Q] Quit — Abort setup entirely")
            print()
            print("  Note: claude-foundry recommends keeping CLAUDE.md minimal.")
            print("  Move detailed project documentation to docs/ARCHITECTURE.md.")
            print("  The docs/ directory is preferred for project documentation.")
            print()
            choice = input("  Choice [R/M/Q]: ").strip().upper()
            if choice == "Q":
                print("\n  Aborted. No changes made to CLAUDE.md.")
                return False
            elif choice == "R":
                # Save original and replace
                backup = project / "CLAUDE.md.old"
                backup.write_text(existing_content, encoding='utf-8')
                claude_md.write_text(generate_claude_md(project_name, deployed_rules, selected_langs), encoding='utf-8')
                print(f"  Replaced CLAUDE.md (original saved to CLAUDE.md.old)")
            else:  # M or anything else defaults to Merge
                # Save original and prepend header
                backup = project / "CLAUDE.md.old"
                backup.write_text(existing_content, encoding='utf-8')
                merged = prepend_claude_foundry_header(existing_content, header)
                claude_md.write_text(merged, encoding='utf-8')
                print(f"  Merged claude-foundry header into CLAUDE.md (original saved to CLAUDE.md.old)")
        elif force_merge:
            # Force merge — prepend header (confirmed earlier)
            backup = project / "CLAUDE.md.old"
            backup.write_text(existing_content, encoding='utf-8')
            merged = prepend_claude_foundry_header(existing_content, header)
            claude_md.write_text(merged, encoding='utf-8')
            print(f"  Force-merged claude-foundry header into CLAUDE.md (original saved to CLAUDE.md.old)")
        # Note: non-interactive + no marker without force case is handled earlier (skips entire project)
    else:
        claude_md.write_text(generate_claude_md(project_name, deployed_rules, selected_langs), encoding='utf-8')
        print(f"  Created CLAUDE.md")

    # Summary
    print(f"\n✓ Project configured with claude-foundry v{version}")
    print(f"  Rules: {len(selected_base)} base + {sum(len(v) for v in selected_modular.values())} modular")
    print(f"  Hooks: {len(selected_hooks)}")
    cmd_count = len([f for f in (COMMANDS_DIR).iterdir() if f.suffix == ".md"]) if COMMANDS_DIR.is_dir() else 0
    print(f"  Commands: {cmd_count}")
    print(f"  Agents: {len(selected_agents)}")
    print(f"  Skills: {len(selected_skills)}")
    if selected_learned:
        print(f"  Learned: {len(selected_learned)} categories ({', '.join(selected_learned)})")
    print(f"  Plugins: {len(selected_plugins)}")
    print(f"  MCP servers: {len(mcp_servers)}")
    return True


def cmd_update_all(force: bool = False) -> None:
    """Batch update all known projects.

    Args:
        force: Force update even if CLAUDE.md has no marker (with confirmation per project)
    """
    version = read_version()
    print(f"Claude Config v{version} — Update All Projects\n")

    projects = discover_projects()
    if not projects:
        print("No projects found in ~/.claude/projects/")
        return

    # Build display list, auto-select those with existing setup
    labels: list[str] = []
    auto: set[int] = set()
    for i, (path, has_setup) in enumerate(projects):
        manifest = load_manifest(path)
        proj_ver = ""
        if has_setup:
            ver_file = path / ".claude" / "VERSION"
            if ver_file.exists():
                proj_ver = ver_file.read_text(encoding='utf-8').strip()
        status = f"v{proj_ver}" if proj_ver else "not configured"
        has_manifest = " +manifest" if manifest else ""
        labels.append(f"{path}  ({status}{has_manifest})")
        if has_setup:
            auto.add(i)

    selected = toggle_menu("Select projects to update", labels, auto)
    if not selected:
        print("No projects selected.")
        return

    # Process each selected project
    results: dict[str, list[str]] = {"updated": [], "interactive": [], "failed": [], "skipped": []}

    for idx in sorted(selected):
        path, has_setup = projects[idx]
        manifest = load_manifest(path)
        print(f"\n{'=' * 60}")
        print(f"Project: {path}")
        print(f"{'=' * 60}")

        if manifest:
            # Non-interactive update using saved choices
            print("Using saved manifest for non-interactive update...")
            try:
                success = cmd_init(path, interactive=False, force=force)
                if success:
                    results["updated"].append(str(path))
                else:
                    results["skipped"].append(str(path))
            except Exception as e:
                print(f"  ✗ Failed: {e}")
                results["failed"].append(str(path))
        else:
            # Interactive init needed
            print("No manifest found — running interactive setup...")
            try:
                success = cmd_init(path, interactive=True, force=force)
                if success:
                    results["interactive"].append(str(path))
                else:
                    results["skipped"].append(str(path))
            except Exception as e:
                print(f"  ✗ Failed: {e}")
                results["failed"].append(str(path))

    # Summary
    print(f"\n{'=' * 60}")
    print("Update All — Summary")
    print(f"{'=' * 60}")
    if results["updated"]:
        print(f"\n  Updated (non-interactive): {len(results['updated'])}")
        for p in results["updated"]:
            print(f"    ✓ {p}")
    if results["interactive"]:
        print(f"\n  Configured (interactive): {len(results['interactive'])}")
        for p in results["interactive"]:
            print(f"    ✓ {p}")
    if results["skipped"]:
        print(f"\n  Skipped: {len(results['skipped'])}")
        for p in results["skipped"]:
            print(f"    — {p}")
    if results["failed"]:
        print(f"\n  Failed: {len(results['failed'])}")
        for p in results["failed"]:
            print(f"    ✗ {p}")


# ── Main ────────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "version":
        cmd_version()
    elif command == "check":
        cmd_check()
    elif command == "init":
        interactive = "--non-interactive" not in sys.argv
        force = "--force" in sys.argv
        args = [a for a in sys.argv[2:] if a not in ("--non-interactive", "--force")]
        project = Path(args[0]) if args else Path.cwd()
        cmd_init(project, interactive=interactive, force=force)
    elif command == "update-all":
        force = "--force" in sys.argv
        cmd_update_all(force=force)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
