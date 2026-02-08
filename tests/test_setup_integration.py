"""Integration tests for setup.py cmd_init with CLAUDE.md handling."""

from __future__ import annotations

import sys
from pathlib import Path
from io import StringIO

import pytest

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from setup import (
    CLAUDE_FOUNDRY_MARKER_START,
    CLAUDE_FOUNDRY_MARKER_END,
    cmd_init,
    has_claude_foundry_header,
    load_manifest,
    save_manifest,
)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory."""
    project = tmp_path / "test-project"
    project.mkdir()
    return project


class TestNewProject:
    """Tests for initializing a new project without existing CLAUDE.md."""

    def test_creates_claude_md_non_interactive(self, temp_project):
        """New project should get CLAUDE.md created in non-interactive mode."""
        result = cmd_init(temp_project, interactive=False)

        assert result is True
        claude_md = temp_project / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert has_claude_foundry_header(content)
        assert "test-project" in content

    def test_claude_md_has_rules_section(self, temp_project):
        """New CLAUDE.md should list deployed rules."""
        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        assert ".claude/rules/" in content
        assert "## Rules" in content

    def test_claude_md_has_environment_section(self, temp_project):
        """New CLAUDE.md should have environment section."""
        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        assert "## Environment" in content

    def test_claude_md_has_architecture_section(self, temp_project):
        """New CLAUDE.md should have architecture section."""
        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        assert "codemaps/INDEX.md" in content
        assert "/update-codemaps" in content


class TestExistingClaudeMdWithMarker:
    """Tests for projects with existing CLAUDE.md that has marker."""

    def test_updates_header_silently_non_interactive(self, temp_project):
        """Existing CLAUDE.md with marker should be updated silently."""
        # Create existing CLAUDE.md with marker
        old_content = f"""# test-project

{CLAUDE_FOUNDRY_MARKER_START}
## Rules
Old rules list
{CLAUDE_FOUNDRY_MARKER_END}

## Custom Section
My custom content
"""
        (temp_project / "CLAUDE.md").write_text(old_content)

        result = cmd_init(temp_project, interactive=False)

        assert result is True

        new_content = (temp_project / "CLAUDE.md").read_text()
        # Header should be updated
        assert "Old rules list" not in new_content
        # Custom section should be preserved
        assert "## Custom Section" in new_content
        assert "My custom content" in new_content
        # No backup should be created for marker updates
        assert not (temp_project / "CLAUDE.md.old").exists()

    def test_preserves_content_before_header(self, temp_project):
        """Content before header should be preserved."""
        old_content = f"""# My Project Title

Some intro text here.

{CLAUDE_FOUNDRY_MARKER_START}
Old header content
{CLAUDE_FOUNDRY_MARKER_END}

After header
"""
        (temp_project / "CLAUDE.md").write_text(old_content)

        cmd_init(temp_project, interactive=False)

        new_content = (temp_project / "CLAUDE.md").read_text()
        assert "# My Project Title" in new_content
        assert "Some intro text here." in new_content
        assert "After header" in new_content


class TestExistingClaudeMdWithoutMarker:
    """Tests for projects with existing CLAUDE.md without marker."""

    def test_non_interactive_skips_without_marker(self, temp_project):
        """Non-interactive mode should skip entire project without marker."""
        old_content = """# My Project

Existing content without marker
"""
        (temp_project / "CLAUDE.md").write_text(old_content)

        result = cmd_init(temp_project, interactive=False)

        assert result is False
        # CLAUDE.md should be unchanged
        assert (temp_project / "CLAUDE.md").read_text() == old_content
        # No backup created
        assert not (temp_project / "CLAUDE.md.old").exists()


class TestRulesInHeader:
    """Tests for rules list in generated header."""

    def test_python_rules_detected(self, temp_project):
        """Python project should have Python rules in header."""
        # Create pyproject.toml to trigger Python detection
        (temp_project / "pyproject.toml").write_text("[project]\nname = 'test'")

        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        assert "`python.md`" in content

    def test_base_rules_in_header(self, temp_project):
        """Base rules should appear in header."""
        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        # At least some base rules should be listed
        assert "`coding-style.md`" in content or "`security.md`" in content

    def test_rust_project_has_cargo_commands(self, temp_project):
        """Rust project should have cargo commands in environment."""
        (temp_project / "Cargo.toml").write_text('[package]\nname = "test"')

        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        assert "cargo" in content


class TestManifestTracking:
    """Tests for manifest and re-initialization."""

    def test_reinit_preserves_custom_content(self, temp_project):
        """Re-init should preserve custom content after header."""
        # First init
        cmd_init(temp_project, interactive=False)

        # Add custom content after header
        content = (temp_project / "CLAUDE.md").read_text()
        content += "\n## My Custom Section\n\nCustom stuff here\n"
        (temp_project / "CLAUDE.md").write_text(content)

        # Second init (should update header, keep custom)
        cmd_init(temp_project, interactive=False)

        new_content = (temp_project / "CLAUDE.md").read_text()
        assert "## My Custom Section" in new_content
        assert "Custom stuff here" in new_content

    def test_manifest_created(self, temp_project):
        """Manifest should be created after init."""
        cmd_init(temp_project, interactive=False)

        manifest = load_manifest(temp_project)
        assert manifest is not None
        assert "version" in manifest
        assert "base_rules" in manifest

    def test_reinit_with_manifest(self, temp_project):
        """Re-init with manifest should use saved selections."""
        # First init creates manifest
        cmd_init(temp_project, interactive=False)

        # Modify manifest to have specific selections
        manifest = load_manifest(temp_project)
        manifest["base_rules"] = ["coding-style.md"]
        save_manifest(temp_project, manifest)

        # Re-init should use manifest
        cmd_init(temp_project, interactive=False)

        # Should still succeed
        assert (temp_project / "CLAUDE.md").exists()


class TestContextLoadConfigurations:
    """Tests for context load of different project configurations."""

    def test_empty_project_minimal_claude_md(self, temp_project):
        """Empty project should have minimal CLAUDE.md."""
        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        # Should be reasonably sized
        assert len(content) < 4000
        assert content.count("\n") < 100

    def test_python_project_claude_md_size(self, temp_project):
        """Python project CLAUDE.md should be appropriately sized."""
        (temp_project / "pyproject.toml").write_text("[project]\nname = 'test'")
        (temp_project / "src").mkdir()
        (temp_project / "src" / "main.py").write_text("# Python file")

        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        assert len(content) < 5000

    def test_multi_language_project(self, temp_project):
        """Multi-language project should have combined env commands."""
        (temp_project / "pyproject.toml").write_text("[project]\nname = 'test'")
        (temp_project / "Cargo.toml").write_text('[package]\nname = "test"')

        cmd_init(temp_project, interactive=False)

        content = (temp_project / "CLAUDE.md").read_text()
        # Should have commands for both
        assert "uv" in content or "cargo" in content


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_claude_md_file_skipped(self, temp_project):
        """Empty CLAUDE.md without marker should skip entire project."""
        (temp_project / "CLAUDE.md").write_text("")

        result = cmd_init(temp_project, interactive=False)

        assert result is False
        # Empty file stays empty (skipped)
        assert (temp_project / "CLAUDE.md").read_text() == ""

    def test_whitespace_only_claude_md(self, temp_project):
        """Whitespace-only CLAUDE.md should skip entire project."""
        (temp_project / "CLAUDE.md").write_text("   \n\n   \n")

        result = cmd_init(temp_project, interactive=False)

        assert result is False

    def test_unicode_in_claude_md(self, temp_project):
        """Unicode in existing CLAUDE.md should be preserved."""
        old_content = f"""# Projekt

{CLAUDE_FOUNDRY_MARKER_START}
header
{CLAUDE_FOUNDRY_MARKER_END}

## Über das Projekt

日本語のドキュメント
"""
        (temp_project / "CLAUDE.md").write_text(old_content)

        cmd_init(temp_project, interactive=False)

        new_content = (temp_project / "CLAUDE.md").read_text()
        assert "Über das Projekt" in new_content
        assert "日本語のドキュメント" in new_content

    def test_large_existing_claude_md(self, temp_project):
        """Large existing CLAUDE.md should be handled."""
        # Create a large CLAUDE.md (10KB)
        large_content = f"""# Large Project

{CLAUDE_FOUNDRY_MARKER_START}
header
{CLAUDE_FOUNDRY_MARKER_END}

""" + "A" * 10000 + "\n## End"
        (temp_project / "CLAUDE.md").write_text(large_content)

        cmd_init(temp_project, interactive=False)

        new_content = (temp_project / "CLAUDE.md").read_text()
        assert "## End" in new_content
        # Content should be preserved
        assert "A" * 100 in new_content


class TestVersionFile:
    """Tests for VERSION file handling."""

    def test_version_file_created(self, temp_project):
        """VERSION file should be created in .claude/."""
        cmd_init(temp_project, interactive=False)

        version_file = temp_project / ".claude" / "VERSION"
        assert version_file.exists()
        assert version_file.read_text().strip()

    def test_rules_copied(self, temp_project):
        """Rules should be copied to .claude/rules/."""
        cmd_init(temp_project, interactive=False)

        rules_dir = temp_project / ".claude" / "rules"
        assert rules_dir.is_dir()
        # Should have at least some rules
        rules = list(rules_dir.glob("*.md"))
        assert len(rules) > 0


class TestGitHubPlatformDetection:
    """Tests for GitHub platform detection."""

    def test_github_dir_detected(self, temp_project):
        """Projects with .github/ should get github.md rule."""
        (temp_project / ".github").mkdir()
        (temp_project / ".github" / "workflows").mkdir()

        cmd_init(temp_project, interactive=False)

        # Check if github.md was copied
        rules_dir = temp_project / ".claude" / "rules"
        github_rule = rules_dir / "github.md"
        assert github_rule.exists()
