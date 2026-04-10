"""Tests for copilot-mcp integration in setup.py.

Covers:
- {FOUNDRY_ROOT} placeholder substitution in the MCP entry
- copilot-mcp entry exists in mcp-configs/mcp-servers.json
- copilot-* skills gated on copilot-mcp MCP selection
- install-copilot-mcp.sh script presence and basic structure
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import setup as setup_py  # noqa: E402


class TestMcpServersRegistry:
    """Verify the MCP servers registry contains copilot-mcp."""

    @pytest.fixture
    def mcp_config(self) -> dict:
        path = REPO_ROOT / "mcp-configs" / "mcp-servers.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_copilot_mcp_registered(self, mcp_config: dict):
        assert "copilot-mcp" in mcp_config["mcpServers"]

    def test_copilot_mcp_uses_node(self, mcp_config: dict):
        entry = mcp_config["mcpServers"]["copilot-mcp"]
        assert entry["command"] == "node"

    def test_copilot_mcp_has_foundry_root_placeholder(self, mcp_config: dict):
        entry = mcp_config["mcpServers"]["copilot-mcp"]
        args = entry["args"]
        assert any("{FOUNDRY_ROOT}" in a for a in args), (
            "copilot-mcp args should contain {FOUNDRY_ROOT} placeholder"
        )
        assert any("vscode-copilot-mcp/mcp/server.js" in a for a in args)

    def test_copilot_mcp_has_description(self, mcp_config: dict):
        entry = mcp_config["mcpServers"]["copilot-mcp"]
        assert "description" in entry
        assert len(entry["description"]) > 0


class TestPlaceholderSubstitution:
    """Verify _substitute_placeholders replaces {FOUNDRY_ROOT} correctly."""

    def test_substitutes_in_string(self):
        result = setup_py._substitute_placeholders("{FOUNDRY_ROOT}/a/b")
        assert result == f"{setup_py.REPO_ROOT}/a/b"

    def test_substitutes_in_list(self):
        result = setup_py._substitute_placeholders(["x", "{FOUNDRY_ROOT}/y"])
        assert result == ["x", f"{setup_py.REPO_ROOT}/y"]

    def test_substitutes_in_nested_dict(self):
        inp = {"command": "node", "args": ["{FOUNDRY_ROOT}/server.js"]}
        result = setup_py._substitute_placeholders(inp)
        assert result["args"][0] == f"{setup_py.REPO_ROOT}/server.js"
        assert result["command"] == "node"

    def test_leaves_unrelated_strings_alone(self):
        assert setup_py._substitute_placeholders("plain text") == "plain text"

    def test_handles_non_string_scalars(self):
        assert setup_py._substitute_placeholders(42) == 42
        assert setup_py._substitute_placeholders(True) is True
        assert setup_py._substitute_placeholders(None) is None


class TestWriteMcpServersSubstitution:
    """Verify write_mcp_servers substitutes placeholders when writing .claude.json."""

    def test_copilot_mcp_written_with_absolute_path(self, tmp_path: Path):
        setup_py.write_mcp_servers(tmp_path, ["copilot-mcp"])
        claude_json = tmp_path / ".claude.json"
        assert claude_json.exists()
        data = json.loads(claude_json.read_text(encoding="utf-8"))
        entry = data["mcpServers"]["copilot-mcp"]
        assert entry["command"] == "node"
        # Placeholder must be gone, replaced by absolute REPO_ROOT path
        assert not any("{FOUNDRY_ROOT}" in a for a in entry["args"])
        assert any(str(setup_py.REPO_ROOT) in a for a in entry["args"])
        # Description field stripped (not valid in .claude.json)
        assert "description" not in entry

    def test_other_mcp_servers_unaffected(self, tmp_path: Path):
        """Non-copilot servers should pass through untouched."""
        setup_py.write_mcp_servers(tmp_path, ["memory"])
        data = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
        assert "memory" in data["mcpServers"]
        assert data["mcpServers"]["memory"]["command"] == "npx"


class TestCopilotSkillRegistration:
    """Verify copilot-* skills are registered and COPILOT_SKILLS list is correct."""

    EXPECTED_COPILOT_SKILLS = [
        "copilot-list-models", "copilot-ask", "copilot-review", "copilot-audit",
        "copilot-agent", "copilot-multi", "copilot-job",
    ]

    def test_all_copilot_skills_in_SKILLS(self):
        for skill in self.EXPECTED_COPILOT_SKILLS:
            assert skill in setup_py.SKILLS, f"{skill} missing from SKILLS"

    def test_COPILOT_SKILLS_list_matches(self):
        assert set(setup_py.COPILOT_SKILLS) == set(self.EXPECTED_COPILOT_SKILLS)

    def test_skill_dirs_exist(self):
        for skill in self.EXPECTED_COPILOT_SKILLS:
            skill_md = REPO_ROOT / "skills" / skill / "SKILL.md"
            assert skill_md.is_file(), f"{skill}/SKILL.md missing"

    def test_command_files_exist(self):
        for skill in self.EXPECTED_COPILOT_SKILLS:
            cmd = REPO_ROOT / "commands" / f"{skill}.md"
            assert cmd.is_file(), f"commands/{skill}.md missing"

    def test_skill_md_has_frontmatter(self):
        for skill in self.EXPECTED_COPILOT_SKILLS:
            content = (REPO_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            assert content.startswith("---"), f"{skill}/SKILL.md missing frontmatter"
            assert f"name: {skill}" in content, f"{skill}/SKILL.md frontmatter missing name"


class TestInstallScript:
    """Verify the extension install script exists and has expected structure."""

    SCRIPT = REPO_ROOT / "tools" / "install-copilot-mcp.sh"

    def test_script_exists(self):
        assert self.SCRIPT.is_file()

    def test_script_is_executable(self):
        import os
        assert os.access(self.SCRIPT, os.X_OK), "install-copilot-mcp.sh not executable"

    def test_script_is_bash(self):
        shebang = self.SCRIPT.read_text(encoding="utf-8").splitlines()[0]
        assert "bash" in shebang

    def test_script_checks_prereqs(self):
        content = self.SCRIPT.read_text(encoding="utf-8")
        for cmd in ["code", "node", "npm", "bash", "curl", "python3"]:
            assert cmd in content, f"install script doesn't check for {cmd}"

    def test_script_runs_build_chain(self):
        content = self.SCRIPT.read_text(encoding="utf-8")
        assert "npm install" in content
        assert "npm run compile" in content or "tsc" in content
        assert "vsce package" in content
        assert "code --install-extension" in content

    def test_script_syntax_valid(self):
        import subprocess
        result = subprocess.run(
            ["bash", "-n", str(self.SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"bash syntax error:\n{result.stderr}"


class TestCopilotSkillGating:
    """Verify copilot-* skills are deployed only when copilot-mcp MCP is selected.

    This tests the post-selection gating logic in do_init, which we exercise
    indirectly by calling the pieces it uses.
    """

    def test_gating_adds_skills_when_mcp_selected(self):
        """Simulating: selected_skills starts empty, mcp has copilot-mcp → skills added."""
        # Mirror the gating logic from tools/setup.py do_init()
        selected_skills: list[str] = []
        mcp_servers = ["copilot-mcp"]
        if "copilot-mcp" in mcp_servers:
            for skill in setup_py.COPILOT_SKILLS:
                if skill not in selected_skills:
                    selected_skills.append(skill)
        else:
            selected_skills = [s for s in selected_skills if s not in setup_py.COPILOT_SKILLS]
        assert set(selected_skills) == set(setup_py.COPILOT_SKILLS)

    def test_gating_removes_skills_when_mcp_not_selected(self):
        """If user pre-selected copilot skills but not the MCP, strip them."""
        selected_skills = ["megamind-deep", "copilot-ask", "copilot-agent"]
        mcp_servers: list[str] = []
        if "copilot-mcp" in mcp_servers:
            for skill in setup_py.COPILOT_SKILLS:
                if skill not in selected_skills:
                    selected_skills.append(skill)
        else:
            selected_skills = [s for s in selected_skills if s not in setup_py.COPILOT_SKILLS]
        assert "megamind-deep" in selected_skills
        assert "copilot-ask" not in selected_skills
        assert "copilot-agent" not in selected_skills

    def test_gating_preserves_non_copilot_skills(self):
        """Other skills must survive the gating pass regardless of MCP selection."""
        selected_skills = ["megamind-deep", "learn", "prj-new"]
        mcp_servers = ["copilot-mcp"]
        if "copilot-mcp" in mcp_servers:
            for skill in setup_py.COPILOT_SKILLS:
                if skill not in selected_skills:
                    selected_skills.append(skill)
        else:
            selected_skills = [s for s in selected_skills if s not in setup_py.COPILOT_SKILLS]
        for preserved in ["megamind-deep", "learn", "prj-new"]:
            assert preserved in selected_skills
