"""API-based evaluation runner for skill benchmarks.

Uses Claude-as-judge to score responses against challenge rubrics.
Requires ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from eval_rubric import Challenge, ElementScore, EvalResult, score_response
from skill_parser import parse_skill

JUDGE_MODEL = "claude-opus-4-6-20250929"
SUBJECT_MODEL = "claude-opus-4-6-20250929"


@dataclass(frozen=True)
class RunConfig:
    """Configuration for an evaluation run."""

    challenges: list[Challenge]
    skills_dir: Path
    runs_per_challenge: int = 3
    subject_model: str = SUBJECT_MODEL
    judge_model: str = JUDGE_MODEL


def _build_subject_prompt(challenge: Challenge, skill_content: str | None) -> str:
    """Build the prompt sent to the subject model."""
    parts: list[str] = []
    if skill_content:
        parts.append(f"<skill>\n{skill_content}\n</skill>\n")
    parts.append(challenge.prompt)
    return "\n".join(parts)


def _build_judge_prompt(challenge: Challenge, response: str) -> str:
    """Build the prompt for the judge model to score a response."""
    elements_desc = "\n".join(
        f"  - {eid}: {desc}" for eid, desc in challenge.rubric.required_elements.items()
    )
    anti_desc = "\n".join(
        f"  - {aid}: {desc}" for aid, desc in challenge.rubric.anti_patterns.items()
    )

    return f"""You are evaluating an AI response against a rubric. Score each element as present or absent.

## Challenge
{challenge.prompt}

## Response to evaluate
{response}

## Required elements (score each as present/absent with evidence)
{elements_desc}

## Anti-patterns (score each as present/absent with evidence)
{anti_desc}

Respond with ONLY valid JSON in this exact format:
{{
  "elements": {{
    "<element_id>": {{"present": true/false, "evidence": "brief quote or explanation"}},
    ...
  }},
  "anti_patterns": {{
    "<pattern_id>": {{"present": true/false, "evidence": "brief quote or explanation"}},
    ...
  }}
}}"""


def _call_model(client, model: str, prompt: str) -> str:
    """Call the Anthropic API and return the response text."""
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_judge_response(
    challenge: Challenge, judge_text: str
) -> tuple[list[ElementScore], list[ElementScore]]:
    """Parse the judge's JSON response into ElementScores."""
    # Extract JSON from response (handle markdown code blocks)
    text = judge_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])

    data = json.loads(text)

    element_scores: list[ElementScore] = []
    for eid in challenge.rubric.required_elements:
        entry = data.get("elements", {}).get(eid, {})
        element_scores.append(
            ElementScore(
                element_id=eid,
                present=entry.get("present", False),
                evidence=entry.get("evidence", ""),
            )
        )

    anti_scores: list[ElementScore] = []
    for aid in challenge.rubric.anti_patterns:
        entry = data.get("anti_patterns", {}).get(aid, {})
        anti_scores.append(
            ElementScore(
                element_id=aid,
                present=entry.get("present", False),
                evidence=entry.get("evidence", ""),
            )
        )

    return element_scores, anti_scores


def run_single_eval(
    client,
    challenge: Challenge,
    skill_content: str | None,
    config: RunConfig,
) -> EvalResult:
    """Run a single evaluation: subject responds, judge scores."""
    subject_prompt = _build_subject_prompt(challenge, skill_content)
    response = _call_model(client, config.subject_model, subject_prompt)

    judge_prompt = _build_judge_prompt(challenge, response)
    judge_text = _call_model(client, config.judge_model, judge_prompt)

    element_scores, anti_scores = _parse_judge_response(challenge, judge_text)

    return score_response(
        challenge,
        element_scores,
        anti_scores,
        skill_used=challenge.skill,
        raw_response=response,
    )


def run_challenge(
    client,
    challenge: Challenge,
    config: RunConfig,
) -> list[EvalResult]:
    """Run a challenge multiple times and return all results.

    Runs both with and without the skill for A/B comparison.
    """
    results: list[EvalResult] = []

    # Load skill content if specified
    skill_content: str | None = None
    if challenge.skill:
        skill_path = config.skills_dir / challenge.skill / "SKILL.md"
        if skill_path.exists():
            skill = parse_skill(skill_path)
            skill_content = skill.body

    for _ in range(config.runs_per_challenge):
        # Run with skill
        result_with = run_single_eval(client, challenge, skill_content, config)
        results.append(result_with)

        # Run baseline (without skill)
        baseline = run_single_eval(client, challenge, None, config)
        results.append(
            EvalResult(
                challenge_id=baseline.challenge_id,
                skill_used=None,
                element_scores=baseline.element_scores,
                anti_pattern_scores=baseline.anti_pattern_scores,
                total_score=baseline.total_score,
                passed=baseline.passed,
                raw_response=baseline.raw_response,
            )
        )

    return results


def run_evaluation(config: RunConfig) -> list[EvalResult]:
    """Run the full evaluation suite.

    Requires ANTHROPIC_API_KEY environment variable.

    Returns list of all EvalResults across all challenges and runs.
    """
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise ImportError(
            "anthropic package required for evaluation. Install with: "
            "uv pip install -e '.[eval]'"
        ) from e

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)
    all_results: list[EvalResult] = []

    for challenge in config.challenges:
        results = run_challenge(client, challenge, config)
        all_results.extend(results)

    return all_results
