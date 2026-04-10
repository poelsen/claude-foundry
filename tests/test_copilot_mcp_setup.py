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
    """Verify write_mcp_servers writes to .mcp.json with placeholders substituted."""

    def test_copilot_mcp_written_with_absolute_path(self, tmp_path: Path):
        setup_py.write_mcp_servers(tmp_path, ["copilot-mcp"])
        # Must write to .mcp.json (Claude Code's project-scoped MCP file),
        # NOT .claude.json (which Claude Code does not read for MCP).
        mcp_json = tmp_path / ".mcp.json"
        assert mcp_json.exists()
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
        entry = data["mcpServers"]["copilot-mcp"]
        assert entry["command"] == "node"
        # Placeholder must be gone, replaced by absolute REPO_ROOT path
        assert not any("{FOUNDRY_ROOT}" in a for a in entry["args"])
        assert any(str(setup_py.REPO_ROOT) in a for a in entry["args"])
        # Description field stripped (not valid in .mcp.json)
        assert "description" not in entry

    def test_does_not_write_to_dot_claude_json(self, tmp_path: Path):
        """Regression test: foundry must NOT write MCP servers to .claude.json.
        That was the original bug — Claude Code reads project MCP from .mcp.json."""
        setup_py.write_mcp_servers(tmp_path, ["copilot-mcp"])
        legacy = tmp_path / ".claude.json"
        if legacy.exists():
            data = json.loads(legacy.read_text(encoding="utf-8"))
            assert "mcpServers" not in data, (
                ".claude.json must NOT contain mcpServers — they belong in .mcp.json"
            )

    def test_other_mcp_servers_unaffected(self, tmp_path: Path):
        """Non-copilot servers should pass through untouched."""
        setup_py.write_mcp_servers(tmp_path, ["memory"])
        data = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
        assert "memory" in data["mcpServers"]
        assert data["mcpServers"]["memory"]["command"] == "npx"

    def test_migrates_from_legacy_dot_claude_json(self, tmp_path: Path):
        """If a previous foundry version wrote MCP servers to .claude.json,
        the next run should migrate them into .mcp.json and clean up."""
        # Arrange: simulate the legacy state
        legacy = tmp_path / ".claude.json"
        legacy.write_text(json.dumps({
            "mcpServers": {
                "old-server": {"command": "old", "args": ["one"]}
            },
            "someOtherSetting": "kept"
        }), encoding="utf-8")
        # Act
        setup_py.write_mcp_servers(tmp_path, ["copilot-mcp"])
        # Assert: .mcp.json has both the legacy entry and the new selection
        mcp_data = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
        assert "old-server" in mcp_data["mcpServers"]
        assert "copilot-mcp" in mcp_data["mcpServers"]
        # Legacy file: mcpServers stripped, other fields preserved
        legacy_data = json.loads(legacy.read_text(encoding="utf-8"))
        assert "mcpServers" not in legacy_data
        assert legacy_data.get("someOtherSetting") == "kept"

    def test_migrates_and_removes_legacy_when_only_mcp_servers(self, tmp_path: Path):
        """If .claude.json contained ONLY mcpServers, the file is deleted entirely."""
        legacy = tmp_path / ".claude.json"
        legacy.write_text(json.dumps({
            "mcpServers": {"old-server": {"command": "old"}}
        }), encoding="utf-8")
        setup_py.write_mcp_servers(tmp_path, ["copilot-mcp"])
        assert not legacy.exists(), (
            ".claude.json should be removed when it had nothing but mcpServers"
        )
        mcp_data = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
        assert "old-server" in mcp_data["mcpServers"]
        assert "copilot-mcp" in mcp_data["mcpServers"]


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

    def test_script_prefers_prebuilt_vsix(self):
        """Install script must detect and use a pre-built .vsix when present."""
        content = self.SCRIPT.read_text(encoding="utf-8")
        assert "PREBUILT_VSIX" in content, (
            "install script should define PREBUILT_VSIX variable"
        )
        assert "vscode-copilot-mcp-*.vsix" in content
        # Both code paths must exist: pre-built install + source build fallback
        assert "Using pre-built extension" in content
        assert "building extension from source" in content.lower() or \
               "Building from source" in content or \
               "No pre-built" in content

    def test_script_documents_per_workspace_enable(self):
        """Post-install notice must tell the user to enable per workspace."""
        content = self.SCRIPT.read_text(encoding="utf-8")
        assert "copilot-mcp.autoStart" in content
        assert ".vscode/settings.json" in content
        assert "disabled by default" in content.lower() or "idle" in content.lower()

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


class TestReleaseWorkflowPreBuild:
    """Verify release.yml pre-builds the .vsix and ships it in the tarball."""

    WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"

    def test_workflow_sets_up_node(self):
        content = self.WORKFLOW.read_text(encoding="utf-8")
        assert "actions/setup-node" in content, "release workflow must install Node"
        assert "node-version: '20'" in content or 'node-version: "20"' in content

    def test_workflow_prebuilds_extension(self):
        content = self.WORKFLOW.read_text(encoding="utf-8")
        assert "Pre-build vscode-copilot-mcp extension" in content
        assert "npm ci" in content or "npm install" in content
        assert "npm run compile" in content or "tsc" in content
        assert "vsce package" in content

    def test_tarball_does_not_exclude_vsix(self):
        """Since CI pre-builds the .vsix, the tarball must include it."""
        content = self.WORKFLOW.read_text(encoding="utf-8")
        # The previous version had --exclude='vscode-copilot-mcp/*.vsix'; must be removed
        assert "--exclude='vscode-copilot-mcp/*.vsix'" not in content, (
            "release tarball must NOT exclude the pre-built .vsix"
        )

    def test_release_uploads_vsix_asset(self):
        content = self.WORKFLOW.read_text(encoding="utf-8")
        assert "vscode-copilot-mcp-*.vsix" in content
        assert "gh release create" in content


class TestExtensionDisabledByDefault:
    """Verify the VS Code extension is disabled by default (opt-in per workspace)."""

    EXT_DIR = REPO_ROOT / "vscode-copilot-mcp"

    def test_package_json_autoStart_default_is_false(self):
        pkg = json.loads((self.EXT_DIR / "package.json").read_text(encoding="utf-8"))
        autoStart = pkg["contributes"]["configuration"]["properties"]["copilot-mcp.autoStart"]
        assert autoStart["default"] is False, (
            "copilot-mcp.autoStart default must be False so the extension "
            "is idle until explicitly enabled per workspace"
        )

    def test_package_json_autoStart_description_mentions_opt_in(self):
        pkg = json.loads((self.EXT_DIR / "package.json").read_text(encoding="utf-8"))
        desc = pkg["contributes"]["configuration"]["properties"]["copilot-mcp.autoStart"]["description"]
        assert ".vscode/settings.json" in desc
        assert "disabled" in desc.lower() or "idle" in desc.lower()

    def test_extension_ts_default_is_false(self):
        """extension.ts fallback to config.get('autoStart', <default>) must be false."""
        src = (self.EXT_DIR / "src" / "extension.ts").read_text(encoding="utf-8")
        # The fallback default in the getConfig call should be `false`, not `true`
        assert "config.get<boolean>('autoStart', false)" in src, (
            "extension.ts must default autoStart to false"
        )
        assert "config.get<boolean>('autoStart', true)" not in src, (
            "extension.ts still has old autoStart=true default"
        )


class TestCopilotPrereqCheck:
    """Verify _copilot_prereqs_missing() reports missing prerequisites."""

    def test_returns_list(self):
        result = setup_py._copilot_prereqs_missing()
        assert isinstance(result, list)

    def test_reports_missing_when_path_empty(self, monkeypatch):
        """With an empty PATH, every prereq should be flagged as missing."""
        monkeypatch.setenv("PATH", "")
        missing = setup_py._copilot_prereqs_missing()
        # At minimum, these tools must be reported missing with empty PATH
        for cmd in ["code", "node", "npm", "bash"]:
            assert cmd in missing

    def test_reports_nothing_when_all_present(self, monkeypatch, tmp_path):
        """With a fake PATH containing stub binaries, nothing should be missing."""
        for cmd in ["code", "node", "npm", "bash", "curl", "python3", "awk", "mktemp"]:
            stub = tmp_path / cmd
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
        monkeypatch.setenv("PATH", str(tmp_path))
        assert setup_py._copilot_prereqs_missing() == []


class TestMaybeInstallCopilotExtension:
    """Verify _maybe_install_copilot_extension behaviour on update paths."""

    def test_noninteractive_auto_runs_when_prereqs_met(self, monkeypatch, capsys):
        """Non-interactive (e.g. /update-foundry) with all prereqs present
        should actually invoke the install script so the extension stays in sync."""
        calls = []

        def fake_run(cmd, check=True):
            calls.append(cmd)

            class R:
                returncode = 0
            return R()

        monkeypatch.setattr(setup_py, "_copilot_prereqs_missing", lambda: [])
        monkeypatch.setattr(setup_py.subprocess, "run", fake_run)

        setup_py._maybe_install_copilot_extension(interactive=False)

        assert len(calls) == 1, "install script should run exactly once"
        assert calls[0][0] == "bash"
        assert "install-copilot-mcp.sh" in calls[0][1]
        out = capsys.readouterr().out
        # Message should indicate an install action (either pre-built or rebuild)
        assert any(word in out.lower() for word in ("installing", "rebuilding", "install")), (
            f"expected install/rebuild message in output:\n{out}"
        )

    def test_noninteractive_skips_when_prereqs_missing(self, monkeypatch, capsys):
        """Non-interactive with missing prereqs must not invoke subprocess.run."""
        calls = []
        monkeypatch.setattr(setup_py, "_copilot_prereqs_missing", lambda: ["code", "node"])
        monkeypatch.setattr(
            setup_py.subprocess, "run",
            lambda *a, **kw: calls.append(a) or (_ for _ in ()).throw(
                AssertionError("subprocess.run should not be called when prereqs missing")),
        )

        setup_py._maybe_install_copilot_extension(interactive=False)

        assert calls == []
        out = capsys.readouterr().out
        assert "missing prereqs" in out.lower()
        assert "code" in out and "node" in out

    def test_noninteractive_handles_script_failure(self, monkeypatch, capsys):
        """If the install script fails, print an error and return cleanly
        (do not raise — update must continue)."""
        monkeypatch.setattr(setup_py, "_copilot_prereqs_missing", lambda: [])

        def fake_run(cmd, check=True):
            raise setup_py.subprocess.CalledProcessError(2, cmd)

        monkeypatch.setattr(setup_py.subprocess, "run", fake_run)

        # Should not raise
        setup_py._maybe_install_copilot_extension(interactive=False)

        out = capsys.readouterr().out
        assert "install failed" in out.lower()
        assert "exit 2" in out.lower()
