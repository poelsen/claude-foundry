"""Evaluation runner for skill benchmarks.

Uses Claude-as-judge via the claude CLI to score responses against challenge rubrics.
Requires the claude CLI to be installed and available in PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from eval_rubric import Challenge, ElementScore, EvalResult, score_response
from skill_parser import parse_skill

JUDGE_MODEL = "opus"
SUBJECT_MODEL = "opus"


@dataclass(frozen=True)
class RunConfig:
    """Configuration for an evaluation run."""

    challenges: list[Challenge]
    skills_dir: Path
    runs_per_challenge: int = 3
    subject_model: str = SUBJECT_MODEL
    judge_model: str = JUDGE_MODEL


def _claude_cli(prompt: str, model: str = "opus") -> str:
    """Run a prompt through the claude CLI in non-interactive mode.

    Uses --output-format json for structured output and --permission-mode
    bypassPermissions for non-interactive / CI use.
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError("claude CLI not found in PATH")

    result = subprocess.run(
        [
            claude_bin,
            "--print",
            "--output-format", "json",
            "--model", model,
            "--no-session-persistence",
            "--permission-mode", "bypassPermissions",
            "--tools", "",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")

    # --output-format json wraps the response in a JSON object
    import json as _json
    try:
        data = _json.loads(result.stdout)
        if isinstance(data, dict) and "result" in data:
            return data["result"].strip()
        return result.stdout.strip()
    except _json.JSONDecodeError:
        return result.stdout.strip()


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
    challenge: Challenge,
    skill_content: str | None,
    config: RunConfig,
) -> EvalResult:
    """Run a single evaluation: subject responds, judge scores."""
    subject_prompt = _build_subject_prompt(challenge, skill_content)
    response = _claude_cli(subject_prompt, config.subject_model)

    judge_prompt = _build_judge_prompt(challenge, response)
    judge_text = _claude_cli(judge_prompt, config.judge_model)

    element_scores, anti_scores = _parse_judge_response(challenge, judge_text)

    return score_response(
        challenge,
        element_scores,
        anti_scores,
        skill_used=challenge.skill,
        raw_response=response,
    )


def run_challenge(
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
        result_with = run_single_eval(challenge, skill_content, config)
        results.append(result_with)

        # Run baseline (without skill)
        baseline = run_single_eval(challenge, None, config)
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

    Requires the claude CLI to be installed and available in PATH.

    Returns list of all EvalResults across all challenges and runs.
    """
    if not shutil.which("claude"):
        raise RuntimeError("claude CLI not found in PATH")

    all_results: list[EvalResult] = []

    for challenge in config.challenges:
        results = run_challenge(challenge, config)
        all_results.extend(results)

    return all_results
