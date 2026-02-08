"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --run-eval option for API-based evaluation tests."""
    parser.addoption(
        "--run-eval",
        action="store_true",
        default=False,
        help="Run evaluation tests that require ANTHROPIC_API_KEY",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip eval-marked tests unless --run-eval is passed."""
    if config.getoption("--run-eval"):
        return

    skip_eval = pytest.mark.skip(reason="Need --run-eval option to run")
    for item in items:
        if "eval" in item.keywords:
            item.add_marker(skip_eval)
