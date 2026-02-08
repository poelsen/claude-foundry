"""Evaluation rubrics and scoring for skill benchmarks.

Defines the data structures for challenge problems, scoring rubrics,
and evaluation results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Rubric:
    """Scoring rubric for a challenge problem."""

    required_elements: dict[str, str]  # id -> description
    anti_patterns: dict[str, str]  # id -> description
    passing_score: int


@dataclass(frozen=True)
class Challenge:
    """A challenge problem for evaluating skill effectiveness."""

    id: str
    name: str
    category: str
    prompt: str
    rubric: Rubric
    skill: str | None = None  # Target skill to test (None = baseline)


@dataclass(frozen=True)
class ElementScore:
    """Score for a single rubric element."""

    element_id: str
    present: bool
    evidence: str = ""


@dataclass(frozen=True)
class EvalResult:
    """Result of evaluating a response against a rubric."""

    challenge_id: str
    skill_used: str | None
    element_scores: tuple[ElementScore, ...]
    anti_pattern_scores: tuple[ElementScore, ...]
    total_score: int
    passed: bool
    raw_response: str = ""


def load_challenge(path: Path) -> Challenge:
    """Load a challenge from a YAML file.

    Args:
        path: Path to the challenge YAML file.

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If required fields are missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"Challenge file not found: {path}")

    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise ValueError(f"Challenge file must be a YAML mapping: {path}")

    for required in ("id", "name", "category", "prompt", "rubric"):
        if required not in data:
            raise ValueError(f"Missing required field '{required}' in {path}")

    rubric_data = data["rubric"]
    for required in ("required_elements", "passing_score"):
        if required not in rubric_data:
            raise ValueError(f"Missing required rubric field '{required}' in {path}")

    rubric = Rubric(
        required_elements=rubric_data["required_elements"],
        anti_patterns=rubric_data.get("anti_patterns", {}),
        passing_score=rubric_data["passing_score"],
    )

    return Challenge(
        id=data["id"],
        name=data["name"],
        category=data["category"],
        prompt=data["prompt"],
        rubric=rubric,
        skill=data.get("skill"),
    )


def load_challenges(directory: Path) -> list[Challenge]:
    """Load all challenge YAML files from a directory."""
    if not directory.is_dir():
        return []

    challenges: list[Challenge] = []
    for path in sorted(directory.glob("*.yaml")):
        challenges.append(load_challenge(path))
    return challenges


def score_response(
    challenge: Challenge,
    element_scores: list[ElementScore],
    anti_pattern_scores: list[ElementScore],
    skill_used: str | None = None,
    raw_response: str = "",
) -> EvalResult:
    """Score a response against a challenge rubric.

    Points: +1 for each required element present, -1 for each anti-pattern present.
    """
    score = sum(1 for e in element_scores if e.present)
    score -= sum(1 for a in anti_pattern_scores if a.present)

    return EvalResult(
        challenge_id=challenge.id,
        skill_used=skill_used,
        element_scores=tuple(element_scores),
        anti_pattern_scores=tuple(anti_pattern_scores),
        total_score=score,
        passed=score >= challenge.rubric.passing_score,
        raw_response=raw_response,
    )
