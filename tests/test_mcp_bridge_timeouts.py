"""Regression tests for per-endpoint timeout budgets in mcp/server.js.

Background: the original mcp/server.js had a hardcoded 300000ms
(5 minute) AbortController on every fetch call, shared between fast
endpoints (/models, /jobs, /sessions) and slow ones (/agent, /chat).
Because the extension's src/server.ts cancels the in-flight
vscode.lm.sendRequest on HTTP client disconnect, this 5-minute ceiling
silently killed long-running /agent jobs (e.g. 21-minute megamind-financial
deep analyses) mid-iteration, losing all accumulated progress.

Fix: mcpRequest() now accepts a timeoutMs parameter. /agent runs with
a 2-hour budget, /chat with 15 minutes, and the default for other
endpoints stays at 5 minutes as a safety net against hung connections.

───────────────────────────────────────────────────────────────────────
WHY PYTHON FOR A JS TEST?
───────────────────────────────────────────────────────────────────────
These are *static* assertions against server.js source text, run from
the existing pytest suite. This is a STOPGAP — the preferred place for
behavioral tests of mcpRequest() is alongside mcp/server.js with
`node --test`, exercising the actual fetch + AbortController flow
(mock fetch to hang, call mcpRequest with a 100ms timeout, assert it
rejects within ~100ms). Adding a Node test runner to mcp/ is a larger
chore tracked separately; until then, static regex checks catch the
one revert scenario we hit (hardcoded 300000) without requiring new
infrastructure.

Static regex tests have known failure modes — they pin implementation
(not behavior), they're brittle to refactors (e.g. AbortSignal.timeout
instead of setTimeout), and they can pass while the code is broken
(e.g. if `signal: controller.signal` is deleted from the fetch options,
the timeout becomes dead code). We guard against the most concerning
exploit explicitly via test_fetch_uses_controller_signal below, but
the suite remains a coarse safety net, not a substitute for behavioral
tests.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SERVER_JS = REPO_ROOT / "vscode-copilot-mcp" / "mcp" / "server.js"


@pytest.fixture(scope="module")
def server_source() -> str:
    assert SERVER_JS.is_file(), f"{SERVER_JS} not found"
    return SERVER_JS.read_text(encoding="utf-8")


class TestTimeoutConstants:
    """The per-endpoint timeout budgets must be declared as named constants."""

    def test_default_timeout_constant_declared(self, server_source: str):
        assert re.search(r"const\s+DEFAULT_TIMEOUT_MS\s*=", server_source), (
            "DEFAULT_TIMEOUT_MS constant missing from server.js"
        )

    def test_chat_timeout_constant_declared(self, server_source: str):
        assert re.search(r"const\s+CHAT_TIMEOUT_MS\s*=", server_source), (
            "CHAT_TIMEOUT_MS constant missing from server.js"
        )

    def test_agent_timeout_constant_declared(self, server_source: str):
        assert re.search(r"const\s+AGENT_TIMEOUT_MS\s*=", server_source), (
            "AGENT_TIMEOUT_MS constant missing from server.js"
        )

    # Arithmetic expressions in the constant declarations: allow digits,
    # arithmetic operators, parentheses, and whitespace. Broad enough for
    # any reasonable edit (e.g. "2 * 60 * 60 * 1000 - 1" or "(2 + 1) * 60 * 1000")
    # but narrow enough to keep the eval() restricted to pure arithmetic.
    _ARITH_RE = r"([0-9*+\-/\s()]+)"

    @staticmethod
    def _parse_const(source: str, name: str) -> int:
        m = re.search(rf"const\s+{name}\s*=\s*{TestTimeoutConstants._ARITH_RE};", source)
        if not m:
            pytest.fail(f"could not parse {name} declaration in server.js")
        expression = m.group(1).strip()
        # eval is safe here: the regex restricts input to arithmetic on digits;
        # the __builtins__={} scope blocks attribute access and name lookups.
        return eval(expression, {"__builtins__": {}}, {})

    def test_agent_timeout_is_at_least_30_minutes(self, server_source: str):
        """Regression guard: /agent must have a budget > 30 min.

        The original bug (issue #38, foundry release 2026.04.10.x) was a
        5-minute hardcoded ceiling at mcp/server.js:65 that killed a
        21-minute megamind-financial deep analysis job on iteration 27.
        Any value below 30 minutes is likely a revert of the fix.
        """
        value = self._parse_const(server_source, "AGENT_TIMEOUT_MS")
        assert value >= 30 * 60 * 1000, (
            f"AGENT_TIMEOUT_MS must be >= 30 minutes (got {value}ms / "
            f"{value / 1000 / 60:.1f} minutes) — the original bug was 5 minutes; "
            f"long-running /copilot-agent jobs will be killed mid-iteration"
        )

    def test_chat_timeout_is_at_least_10_minutes(self, server_source: str):
        value = self._parse_const(server_source, "CHAT_TIMEOUT_MS")
        assert value >= 10 * 60 * 1000, (
            f"CHAT_TIMEOUT_MS must be >= 10 minutes (got {value}ms)"
        )


class TestMcpRequestSignature:
    """mcpRequest() must accept a per-call timeout parameter AND actually use it."""

    def test_mcprequest_accepts_timeout_parameter(self, server_source: str):
        assert re.search(
            r"async\s+function\s+mcpRequest\s*\([^)]*timeoutMs[^)]*\)",
            server_source,
        ), (
            "mcpRequest signature must include a timeoutMs parameter"
        )

    def test_setTimeout_uses_parameter_not_hardcoded(self, server_source: str):
        """The setTimeout call must reference timeoutMs, not a literal number."""
        assert re.search(
            r"setTimeout\([^,]+,\s*timeoutMs\s*\)",
            server_source,
        ), (
            "setTimeout in mcpRequest should use the timeoutMs parameter, "
            "not a hardcoded value"
        )

    def test_fetch_uses_controller_signal(self, server_source: str):
        """Regression guard: the AbortController signal must be passed to fetch().

        If someone deletes `signal: controller.signal` from the fetch options,
        the AbortController's abort() call becomes dead code — all the other
        timeout tests pass, but the timeout has zero effect on the actual
        request, and the original bug is silently reintroduced.

        This test is deliberately SCOPED to the mcpRequest fetch call (not
        checkAlive's /health fetch) by matching on the ${baseUrl}${path}
        URL template string that's unique to mcpRequest. An earlier,
        file-wide check would pass if someone deleted only the mcpRequest
        signal while leaving checkAlive's intact — exactly the exploit
        this test must prevent.
        """
        # Match the mcpRequest fetch call: `await fetch(\`${baseUrl}${path}\`, {...});`
        # The options object body is captured so we can check it for `signal`.
        m = re.search(
            r"await\s+fetch\(\s*`\$\{baseUrl\}\$\{path\}`\s*,\s*\{([^{}]*)\}",
            server_source,
            re.DOTALL,
        )
        assert m, (
            "mcpRequest's fetch call not found — either the URL template changed "
            "(update the regex) or the fetch call was removed (the request helper "
            "is broken)"
        )
        fetch_options = m.group(1)
        assert "signal: controller.signal" in fetch_options, (
            "mcpRequest's fetch() must pass { signal: controller.signal } in its "
            "options — without it, the AbortController has NO EFFECT on the request "
            "and all timeout logic is DEAD CODE (the ORIGINAL BUG reintroduced).\n\n"
            f"fetch options seen:\n  {fetch_options.strip()}"
        )

    def test_no_hardcoded_300000_in_mcprequest(self, server_source: str):
        """Regression guard: the original bug was setTimeout(..., 300000).

        Allow 300000 to appear in DEFAULT_TIMEOUT_MS derivation (e.g. as
        5 * 60 * 1000), but forbid it as a literal inside setTimeout().
        """
        for line in server_source.splitlines():
            if "setTimeout" in line and "timeoutMs" not in line and "2000" not in line:
                # 2000 is the /health check, which legitimately uses a
                # hardcoded short value
                assert "300000" not in line, (
                    f"Regression: setTimeout with hardcoded 300000 found:\n  {line.strip()}"
                )


class TestCallsiteBudgets:
    """Long-running endpoints must pass the extended timeout budgets."""

    @staticmethod
    def _all_callsite_windows(server_source: str, path: str) -> list[str]:
        """Return the 20-line window after EVERY mcpRequest("<path>"...) call.

        The original test only checked the first occurrence of each path,
        which would miss a new variant endpoint that forgot to pass the
        long timeout budget. This scans all of them.
        """
        lines = server_source.splitlines()
        # Match both double and backtick string literals just in case
        patterns = [
            f'mcpRequest("{path}"',
            f"mcpRequest('{path}'",
            f"mcpRequest(`{path}`",
        ]
        windows: list[str] = []
        for i, line in enumerate(lines):
            if any(p in line for p in patterns):
                windows.append("\n".join(lines[i:i + 20]))
        return windows

    def test_agent_callsite_uses_agent_timeout(self, server_source: str):
        """Every mcpRequest('/agent'...) call must pass AGENT_TIMEOUT_MS.

        Scans ALL callsites, not just the first — a new /agent variant
        endpoint that forgets the long timeout would reintroduce the bug
        for that specific tool while all other checks pass.
        """
        windows = self._all_callsite_windows(server_source, "/agent")
        assert len(windows) >= 1, "no mcpRequest('/agent') callsite found"
        bad = [w for w in windows if "AGENT_TIMEOUT_MS" not in w]
        assert not bad, (
            f"{len(bad)}/{len(windows)} mcpRequest('/agent') callsite(s) missing "
            f"AGENT_TIMEOUT_MS argument — long-running agent jobs will be killed by "
            f"the default 5-minute timeout.\n\nOffending window:\n{bad[0] if bad else ''}"
        )

    def test_chat_callsite_uses_chat_timeout(self, server_source: str):
        windows = self._all_callsite_windows(server_source, "/chat")
        assert len(windows) >= 1, "no mcpRequest('/chat') callsite found"
        bad = [w for w in windows if "CHAT_TIMEOUT_MS" not in w]
        assert not bad, (
            f"{len(bad)}/{len(windows)} mcpRequest('/chat') callsite(s) missing "
            f"CHAT_TIMEOUT_MS argument"
        )


class TestExtensionVersionBumped:
    """The .vsix version must be bumped for /update-foundry to reinstall."""

    def test_package_json_version_greater_than_0_1_0(self):
        import json
        pkg = json.loads(
            (REPO_ROOT / "vscode-copilot-mcp" / "package.json").read_text(encoding="utf-8")
        )
        version = pkg["version"]
        # Parse semver major.minor.patch
        parts = version.split(".")
        assert len(parts) == 3, f"expected semver, got {version}"
        major, minor, patch = (int(p) for p in parts)
        # Must be > 0.1.0 — the version that shipped with the broken timeout
        assert (major, minor, patch) > (0, 1, 0), (
            f"package.json version must be > 0.1.0 (got {version}) so the next "
            f"/update-foundry rebuilds + reinstalls the extension with the fix"
        )
