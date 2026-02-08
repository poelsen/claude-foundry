"""Report generation for skill evaluation results.

Produces terminal, JSON, and markdown reports from evaluation results.
"""

from __future__ import annotations

import json

from eval_rubric import EvalResult


def _group_by_challenge(results: list[EvalResult]) -> dict[str, list[EvalResult]]:
    """Group results by challenge ID."""
    groups: dict[str, list[EvalResult]] = {}
    for r in results:
        groups.setdefault(r.challenge_id, []).append(r)
    return groups


def _split_by_skill(results: list[EvalResult]) -> tuple[list[EvalResult], list[EvalResult]]:
    """Split results into (with_skill, baseline)."""
    with_skill = [r for r in results if r.skill_used is not None]
    baseline = [r for r in results if r.skill_used is None]
    return with_skill, baseline


def _avg_score(results: list[EvalResult]) -> float:
    """Average score across results."""
    if not results:
        return 0.0
    return sum(r.total_score for r in results) / len(results)


def _pass_rate(results: list[EvalResult]) -> float:
    """Pass rate as fraction (0.0-1.0)."""
    if not results:
        return 0.0
    return sum(1 for r in results if r.passed) / len(results)


def terminal_report(results: list[EvalResult]) -> str:
    """Generate a human-readable terminal report."""
    if not results:
        return "No results to report."

    lines: list[str] = ["", "=== Skill Evaluation Report ===", ""]

    groups = _group_by_challenge(results)
    for challenge_id, challenge_results in sorted(groups.items()):
        with_skill, baseline = _split_by_skill(challenge_results)

        lines.append(f"--- {challenge_id} ---")

        if with_skill:
            skill_name = with_skill[0].skill_used or "unknown"
            avg = _avg_score(with_skill)
            rate = _pass_rate(with_skill)
            lines.append(f"  With {skill_name}: avg={avg:.1f} pass={rate:.0%} (n={len(with_skill)})")

        if baseline:
            avg = _avg_score(baseline)
            rate = _pass_rate(baseline)
            lines.append(f"  Baseline:       avg={avg:.1f} pass={rate:.0%} (n={len(baseline)})")

        if with_skill and baseline:
            delta = _avg_score(with_skill) - _avg_score(baseline)
            direction = "+" if delta >= 0 else ""
            lines.append(f"  Delta:          {direction}{delta:.1f}")

        lines.append("")

    # Summary
    all_with_skill, all_baseline = _split_by_skill(results)
    lines.append("=== Summary ===")
    if all_with_skill:
        lines.append(f"  With skill: avg={_avg_score(all_with_skill):.1f} pass={_pass_rate(all_with_skill):.0%}")
    if all_baseline:
        lines.append(f"  Baseline:   avg={_avg_score(all_baseline):.1f} pass={_pass_rate(all_baseline):.0%}")
    lines.append("")

    return "\n".join(lines)


def json_report(results: list[EvalResult]) -> str:
    """Generate a JSON report."""
    data = {
        "results": [_result_to_dict(r) for r in results],
        "summary": _summary(results),
    }
    return json.dumps(data, indent=2)


def markdown_report(results: list[EvalResult]) -> str:
    """Generate a markdown report."""
    if not results:
        return "# Skill Evaluation Report\n\nNo results.\n"

    lines: list[str] = ["# Skill Evaluation Report", ""]

    groups = _group_by_challenge(results)

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Challenge | Skill | Avg Score | Pass Rate | Baseline Avg | Baseline Pass | Delta |")
    lines.append("|-----------|-------|-----------|-----------|--------------|---------------|-------|")

    for challenge_id, challenge_results in sorted(groups.items()):
        with_skill, baseline = _split_by_skill(challenge_results)
        skill_name = with_skill[0].skill_used if with_skill else "-"
        s_avg = f"{_avg_score(with_skill):.1f}" if with_skill else "-"
        s_rate = f"{_pass_rate(with_skill):.0%}" if with_skill else "-"
        b_avg = f"{_avg_score(baseline):.1f}" if baseline else "-"
        b_rate = f"{_pass_rate(baseline):.0%}" if baseline else "-"
        delta = ""
        if with_skill and baseline:
            d = _avg_score(with_skill) - _avg_score(baseline)
            delta = f"{'+' if d >= 0 else ''}{d:.1f}"
        lines.append(f"| {challenge_id} | {skill_name} | {s_avg} | {s_rate} | {b_avg} | {b_rate} | {delta} |")

    lines.append("")

    # Detail sections
    lines.append("## Details")
    lines.append("")
    for challenge_id, challenge_results in sorted(groups.items()):
        lines.append(f"### {challenge_id}")
        lines.append("")
        for r in challenge_results:
            label = r.skill_used or "baseline"
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"**{label}** ({status}, score={r.total_score})")
            for e in r.element_scores:
                mark = "+" if e.present else "-"
                lines.append(f"  {mark} {e.element_id}: {e.evidence}")
            for a in r.anti_pattern_scores:
                if a.present:
                    lines.append(f"  ! {a.element_id}: {a.evidence}")
            lines.append("")

    return "\n".join(lines)


def _result_to_dict(result: EvalResult) -> dict:
    """Convert EvalResult to a JSON-serializable dict."""
    return {
        "challenge_id": result.challenge_id,
        "skill_used": result.skill_used,
        "total_score": result.total_score,
        "passed": result.passed,
        "elements": [
            {"id": e.element_id, "present": e.present, "evidence": e.evidence}
            for e in result.element_scores
        ],
        "anti_patterns": [
            {"id": a.element_id, "present": a.present, "evidence": a.evidence}
            for a in result.anti_pattern_scores
        ],
    }


def _summary(results: list[EvalResult]) -> dict:
    """Generate summary statistics."""
    with_skill, baseline = _split_by_skill(results)
    return {
        "total_results": len(results),
        "with_skill": {
            "count": len(with_skill),
            "avg_score": round(_avg_score(with_skill), 2),
            "pass_rate": round(_pass_rate(with_skill), 2),
        },
        "baseline": {
            "count": len(baseline),
            "avg_score": round(_avg_score(baseline), 2),
            "pass_rate": round(_pass_rate(baseline), 2),
        },
    }
