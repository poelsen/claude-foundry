"""Tests for per-project foundry cache and skill grouping.

Covers:
- SKILL_GROUPS shape + default contents
- HIDDEN_SKILLS excludes copilot-* from visible menu
- _self_copy_foundry_source populates <project>/.claude/foundry/
- Self-copy is idempotent and skips when already inside target
- Absolute-path messages in copilot install hook
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import setup as setup_py  # noqa: E402


class TestSkillGroupsShape:
    """Verify SKILL_GROUPS constant is well-formed and matches the rest of setup.py."""

    def test_groups_dict_exists(self):
        assert hasattr(setup_py, "SKILL_GROUPS")
        assert isinstance(setup_py.SKILL_GROUPS, dict)

    def test_groups_have_expected_names(self):
        assert "Megamind Reasoning" in setup_py.SKILL_GROUPS
        assert "Project Management" in setup_py.SKILL_GROUPS

    def test_megamind_group_contains_all_4_skills(self):
        members = setup_py.SKILL_GROUPS["Megamind Reasoning"]
        assert set(members) == {
            "megamind-deep", "megamind-creative", "megamind-adversarial", "megamind-financial",
        }

    def test_prj_group_contains_all_6_skills(self):
        members = setup_py.SKILL_GROUPS["Project Management"]
        assert set(members) == {
            "prj-new", "prj-list", "prj-pause", "prj-resume", "prj-done", "prj-delete",
        }

    def test_copilot_is_not_a_group(self):
        """Copilot is gated on MCP selection, not presented as a group."""
        assert "Copilot MCP" not in setup_py.SKILL_GROUPS
        assert "Copilot" not in setup_py.SKILL_GROUPS

    def test_all_group_members_are_in_SKILLS(self):
        for group, members in setup_py.SKILL_GROUPS.items():
            for skill in members:
                assert skill in setup_py.SKILLS, (
                    f"group '{group}' references unknown skill '{skill}'"
                )


class TestHiddenSkills:
    """Verify HIDDEN_SKILLS removes copilot-* from the visible menu."""

    def test_hidden_skills_exists(self):
        assert hasattr(setup_py, "HIDDEN_SKILLS")
        assert isinstance(setup_py.HIDDEN_SKILLS, set)

    def test_all_copilot_skills_are_hidden(self):
        for skill in setup_py.COPILOT_SKILLS:
            assert skill in setup_py.HIDDEN_SKILLS, (
                f"{skill} must be in HIDDEN_SKILLS so it doesn't appear in the menu"
            )

    def test_non_copilot_skills_not_hidden(self):
        non_copilot = ("megamind-deep", "prj-new", "learn", "clickhouse-io")
        for skill in non_copilot:
            assert skill not in setup_py.HIDDEN_SKILLS


class TestFoundrySelfCopy:
    """Verify _self_copy_foundry_source populates .claude/foundry/ atomically."""

    def test_copies_tree_to_claude_foundry(self, tmp_path: Path):
        setup_py._self_copy_foundry_source(tmp_path)
        target = tmp_path / ".claude" / "foundry"
        assert target.is_dir()
        # Key files must be present
        assert (target / "tools" / "setup.py").is_file()
        assert (target / "rules").is_dir()
        assert (target / "skills").is_dir()
        assert (target / "mcp-configs" / "mcp-servers.json").is_file()

    def test_skips_build_artifacts(self, tmp_path: Path):
        setup_py._self_copy_foundry_source(tmp_path)
        target = tmp_path / ".claude" / "foundry"
        # These directories should NOT be copied
        assert not (target / ".git").exists()
        assert not (target / ".venv").exists()
        assert not (target / "__pycache__").exists()
        # node_modules in vscode-copilot-mcp should be pruned
        if (target / "vscode-copilot-mcp").exists():
            assert not (target / "vscode-copilot-mcp" / "node_modules").exists()
            assert not (target / "vscode-copilot-mcp" / "out").exists()

    def test_idempotent(self, tmp_path: Path):
        """Running twice should leave the same result."""
        setup_py._self_copy_foundry_source(tmp_path)
        first_contents = sorted(
            p.relative_to(tmp_path / ".claude" / "foundry")
            for p in (tmp_path / ".claude" / "foundry").rglob("*")
            if p.is_file()
        )
        setup_py._self_copy_foundry_source(tmp_path)
        second_contents = sorted(
            p.relative_to(tmp_path / ".claude" / "foundry")
            for p in (tmp_path / ".claude" / "foundry").rglob("*")
            if p.is_file()
        )
        assert first_contents == second_contents

    def test_no_leftover_staging_or_backup(self, tmp_path: Path):
        setup_py._self_copy_foundry_source(tmp_path)
        claude_dir = tmp_path / ".claude"
        assert not (claude_dir / ".foundry.new").exists()
        assert not (claude_dir / ".foundry.old").exists()

    def test_skips_when_running_inside_target(self, tmp_path: Path, monkeypatch):
        """If REPO_ROOT is already inside <project>/.claude/foundry/, don't copy."""
        # Arrange: stage a fake target and point REPO_ROOT at a subdirectory
        target = tmp_path / ".claude" / "foundry"
        target.mkdir(parents=True)
        (target / "marker.txt").write_text("pre-existing")
        monkeypatch.setattr(setup_py, "REPO_ROOT", target)

        # Act: call the self-copy — should be a no-op, marker preserved
        setup_py._self_copy_foundry_source(tmp_path)

        assert (target / "marker.txt").is_file()
        assert (target / "marker.txt").read_text() == "pre-existing"


class TestCopilotInstallMessagePath:
    """Verify the copilot-install message prints an absolute path."""

    def test_skip_message_uses_absolute_path(self, monkeypatch, capsys):
        monkeypatch.setattr(setup_py, "_copilot_prereqs_missing", lambda: ["code"])
        setup_py._maybe_install_copilot_extension(interactive=False)
        out = capsys.readouterr().out
        # Must contain the absolute path to install-copilot-mcp.sh, not relative
        assert "/tools/install-copilot-mcp.sh" in out
        # No relative path tokens like "./tools" or "tools/install"
        assert "./tools/" not in out
        # Path must be absolute (starts with /)
        for line in out.splitlines():
            if "install-copilot-mcp.sh" in line:
                # Extract the path and check it's absolute
                assert "/install-copilot-mcp.sh" in line
                # Find the path substring
                idx = line.find("/")
                if idx != -1:
                    path_part = line[idx:].strip().split()[0]
                    # Should start with / (absolute)
                    assert path_part.startswith("/"), (
                        f"expected absolute path, got: {path_part}"
                    )

    def test_failure_message_uses_absolute_path(self, monkeypatch, capsys):
        monkeypatch.setattr(setup_py, "_copilot_prereqs_missing", lambda: [])

        def fake_run(cmd, check=True):
            raise setup_py.subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(setup_py.subprocess, "run", fake_run)
        setup_py._maybe_install_copilot_extension(interactive=False)
        out = capsys.readouterr().out
        assert "install-copilot-mcp.sh" in out
        # The re-run hint must be absolute
        assert "bash /" in out


class TestUpdateFoundryScript:
    """Verify update-foundry.sh uses the per-project cache model."""

    SCRIPT = REPO_ROOT / "skills" / "update-foundry" / "scripts" / "update-foundry.sh"

    def test_script_exists_and_parses(self):
        assert self.SCRIPT.is_file()
        import subprocess
        result = subprocess.run(
            ["bash", "-n", str(self.SCRIPT)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"bash syntax error:\n{result.stderr}"

    def test_script_uses_per_project_foundry_dir(self):
        content = self.SCRIPT.read_text(encoding="utf-8")
        assert "FOUNDRY_DIR=" in content
        assert ".claude/foundry" in content

    def test_script_does_atomic_swap(self):
        content = self.SCRIPT.read_text(encoding="utf-8")
        # Should stage in .foundry.new, back up as .foundry.old, swap via mv
        assert ".foundry.new" in content
        assert ".foundry.old" in content

    def test_script_rolls_back_on_setup_failure(self):
        content = self.SCRIPT.read_text(encoding="utf-8")
        assert "rolling back" in content.lower() or "roll back" in content.lower()

    def test_script_does_not_use_mktemp_for_foundry(self):
        """Old behavior was to use mktemp + trap cleanup; new behavior persists."""
        content = self.SCRIPT.read_text(encoding="utf-8")
        # The script should not create a mktemp dir for the foundry tree
        # (it may still use temp for the tarball download, which is fine)
        # Specifically: the old "TMPDIR=$(mktemp -d)" pattern should be gone
        assert "TMPDIR=$(mktemp -d)" not in content

    def test_script_prints_manual_reinit_hint(self):
        content = self.SCRIPT.read_text(encoding="utf-8")
        assert "Manual re-init" in content or "manual re-init" in content.lower()
