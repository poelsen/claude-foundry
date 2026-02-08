#!/usr/bin/env python3
"""Run comprehensive megamind skill benchmarks.

Runs every challenge against every skill mode + baseline.
Produces a detailed comparison report.

Usage (local — uses claude CLI, no API cost):
    python3 tools/run_benchmark.py --local --runs 2
    python3 tools/run_benchmark.py --local --skill megamind-deep --runs 2

Usage (API — requires ANTHROPIC_API_KEY):
    ANTHROPIC_API_KEY=sk-... python3 tools/run_benchmark.py --runs 2
    ANTHROPIC_API_KEY=sk-... python3 tools/run_benchmark.py --save results/baseline.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))

from eval_rubric import Challenge, ElementScore, EvalResult, load_challenges, score_response
from eval_runner import _build_judge_prompt, _build_subject_prompt, _parse_judge_response
from skill_parser import parse_skill

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
CHALLENGES_DIR = REPO_ROOT / "tests" / "challenges"

SUBJECT_MODEL = "claude-opus-4-6-20250929"
JUDGE_MODEL = "claude-opus-4-6-20250929"

ALL_SKILL_MODES = [None, "megamind-deep", "megamind-creative", "megamind-adversarial"]


def label(skill: str | None) -> str:
    return skill or "baseline"


def load_skill_content(skill_name: str) -> str | None:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.exists():
        return None
    return parse_skill(path).body


def run_one(client, challenge: Challenge, skill_name: str | None) -> EvalResult:
    """Run a single challenge with a single skill mode (API backend)."""
    skill_content = load_skill_content(skill_name) if skill_name else None
    subject_prompt = _build_subject_prompt(challenge, skill_content)

    response = client.messages.create(
        model=SUBJECT_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": subject_prompt}],
    ).content[0].text

    judge_prompt = _build_judge_prompt(challenge, response)
    judge_text = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": judge_prompt}],
    ).content[0].text

    element_scores, anti_scores = _parse_judge_response(challenge, judge_text)

    return score_response(
        challenge, element_scores, anti_scores,
        skill_used=skill_name, raw_response=response,
    )


def _claude_cli(prompt: str, model: str = "opus") -> str:
    """Run a prompt through the claude CLI in non-interactive mode."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError("claude CLI not found in PATH")

    result = subprocess.run(
        [
            claude_bin,
            "--print",
            "--model", model,
            "--no-session-persistence",
            "--tools", "",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=1200,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")

    return result.stdout.strip()


def run_one_local(challenge: Challenge, skill_name: str | None) -> EvalResult:
    """Run a single challenge with a single skill mode (local claude CLI)."""
    skill_content = load_skill_content(skill_name) if skill_name else None
    subject_prompt = _build_subject_prompt(challenge, skill_content)

    response = _claude_cli(subject_prompt)

    judge_prompt = _build_judge_prompt(challenge, response)
    judge_text = _claude_cli(judge_prompt)

    element_scores, anti_scores = _parse_judge_response(challenge, judge_text)

    return score_response(
        challenge, element_scores, anti_scores,
        skill_used=skill_name, raw_response=response,
    )


# ── Serialization ──


def results_to_json(
    challenges: list[Challenge],
    all_results: dict[str, dict[str, list[EvalResult]]],
    skill_modes: list[str | None],
) -> dict:
    """Convert results to a JSON-serializable dict."""
    data: dict = {"challenges": {}, "skill_modes": [label(s) for s in skill_modes]}
    for challenge in challenges:
        cdata: dict = {"name": challenge.name, "modes": {}}
        for skill in skill_modes:
            key = label(skill)
            results = all_results.get(challenge.id, {}).get(key, [])
            mode_data: dict = {
                "scores": [r.total_score for r in results],
                "passed": [r.passed for r in results],
                "elements": {},
                "anti_patterns": {},
            }
            for eid in challenge.rubric.required_elements:
                hits = sum(
                    1 for r in results
                    for e in r.element_scores
                    if e.element_id == eid and e.present
                )
                mode_data["elements"][eid] = {"hits": hits, "total": len(results)}
            for aid in challenge.rubric.anti_patterns:
                hits = sum(
                    1 for r in results
                    for a in r.anti_pattern_scores
                    if a.element_id == aid and a.present
                )
                mode_data["anti_patterns"][aid] = {"hits": hits, "total": len(results)}
            cdata["modes"][key] = mode_data
        data["challenges"][challenge.id] = cdata
    return data


def load_saved_results(path: Path) -> dict:
    """Load previously saved benchmark results."""
    return json.loads(path.read_text(encoding="utf-8"))


# ── Reporting ──


def print_header(text: str) -> None:
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}")


def _element_hit_rate(
    results: list[EvalResult], element_id: str, is_anti: bool = False
) -> tuple[int, int]:
    """Return (hits, total) for an element across results."""
    scores_attr = "anti_pattern_scores" if is_anti else "element_scores"
    hits = sum(
        1 for r in results
        for e in getattr(r, scores_attr)
        if e.element_id == element_id and e.present
    )
    return hits, len(results)


def _variance(scores: list[int]) -> float:
    """Compute variance of scores."""
    if len(scores) < 2:
        return 0.0
    avg = sum(scores) / len(scores)
    return sum((s - avg) ** 2 for s in scores) / (len(scores) - 1)


def print_element_grid(
    challenges: list[Challenge],
    all_results: dict[str, dict[str, list[EvalResult]]],
    skill_modes: list[str | None],
) -> None:
    """Print per-element scoring grid for each challenge."""
    for challenge in challenges:
        print_header(f"{challenge.id}: {challenge.name}")
        print(f"  Category: {challenge.category}")
        print(f"  Passing score: {challenge.rubric.passing_score}")
        print()

        modes = [label(s) for s in skill_modes]
        col_width = 16
        header = "  Element".ljust(34) + "".join(m.center(col_width) for m in modes)
        print(header)
        print("  " + "-" * (32 + col_width * len(modes)))

        # Required elements
        for eid in challenge.rubric.required_elements:
            row = f"  + {eid}".ljust(34)
            for skill in skill_modes:
                results = all_results.get(challenge.id, {}).get(label(skill), [])
                if results:
                    hits, total = _element_hit_rate(results, eid)
                    pct = hits / total if total else 0
                    marker = " **" if pct == 0 else ""  # Flag 0% hit rate
                    cell = f"{hits}/{total} ({pct:.0%}){marker}"
                else:
                    cell = "-"
                row += cell.center(col_width)
            print(row)

        # Anti-patterns
        if challenge.rubric.anti_patterns:
            print()
            for aid in challenge.rubric.anti_patterns:
                row = f"  ! {aid}".ljust(34)
                for skill in skill_modes:
                    results = all_results.get(challenge.id, {}).get(label(skill), [])
                    if results:
                        hits, total = _element_hit_rate(results, aid, is_anti=True)
                        pct = hits / total if total else 0
                        marker = " !!" if pct == 1.0 else ""  # Flag 100% anti-pattern
                        cell = f"{hits}/{total} ({pct:.0%}){marker}"
                    else:
                        cell = "-"
                    row += cell.center(col_width)
                print(row)

        # Score + variance
        print()
        row = "  SCORE (avg)".ljust(34)
        for skill in skill_modes:
            results = all_results.get(challenge.id, {}).get(label(skill), [])
            if results:
                scores = [r.total_score for r in results]
                avg = sum(scores) / len(scores)
                var = _variance(scores)
                cell = f"{avg:.1f} (var={var:.1f})"
            else:
                cell = "-"
            row += cell.center(col_width)
        print(row)

        row = "  PASS RATE".ljust(34)
        for skill in skill_modes:
            results = all_results.get(challenge.id, {}).get(label(skill), [])
            if results:
                rate = sum(1 for r in results if r.passed) / len(results)
                cell = f"{rate:.0%}"
            else:
                cell = "-"
            row += cell.center(col_width)
        print(row)
        print()


def print_summary_table(
    challenges: list[Challenge],
    all_results: dict[str, dict[str, list[EvalResult]]],
    skill_modes: list[str | None],
) -> None:
    """Print overall summary comparison table."""
    print_header("OVERALL SUMMARY")

    col_width = 16
    modes = [label(s) for s in skill_modes]
    header = "  Metric".ljust(28) + "".join(m.center(col_width) for m in modes)
    print(header)
    print("  " + "-" * (26 + col_width * len(modes)))

    # Avg score
    row = "  Avg Score".ljust(28)
    for skill in skill_modes:
        scores = [
            r.total_score
            for cid in all_results
            for r in all_results[cid].get(label(skill), [])
        ]
        avg = sum(scores) / len(scores) if scores else 0
        row += f"{avg:.1f}".center(col_width)
    print(row)

    # Variance
    row = "  Score Variance".ljust(28)
    for skill in skill_modes:
        scores = [
            r.total_score
            for cid in all_results
            for r in all_results[cid].get(label(skill), [])
        ]
        var = _variance(scores) if scores else 0
        row += f"{var:.1f}".center(col_width)
    print(row)

    # Pass rate
    row = "  Pass Rate".ljust(28)
    for skill in skill_modes:
        results = [
            r for cid in all_results for r in all_results[cid].get(label(skill), [])
        ]
        rate = sum(1 for r in results if r.passed) / len(results) if results else 0
        row += f"{rate:.0%}".center(col_width)
    print(row)

    # Delta vs baseline
    baseline_scores = [
        r.total_score
        for cid in all_results
        for r in all_results[cid].get("baseline", [])
    ]
    baseline_avg = sum(baseline_scores) / len(baseline_scores) if baseline_scores else 0

    row = "  Delta vs Baseline".ljust(28)
    for skill in skill_modes:
        if skill is None:
            row += "-".center(col_width)
        else:
            scores = [
                r.total_score
                for cid in all_results
                for r in all_results[cid].get(label(skill), [])
            ]
            avg = sum(scores) / len(scores) if scores else 0
            delta = avg - baseline_avg
            sign = "+" if delta >= 0 else ""
            row += f"{sign}{delta:.1f}".center(col_width)
    print(row)

    # Per-challenge breakdown
    print()
    print("  Per-challenge scores:")
    row = "  Challenge".ljust(28) + "".join(m.center(col_width) for m in modes)
    print(row)
    print("  " + "-" * (26 + col_width * len(modes)))

    for challenge in challenges:
        row = f"  {challenge.id}".ljust(28)
        for skill in skill_modes:
            results = all_results.get(challenge.id, {}).get(label(skill), [])
            if results:
                avg = sum(r.total_score for r in results) / len(results)
                row += f"{avg:.1f}".center(col_width)
            else:
                row += "-".center(col_width)
        print(row)

    # Weakness report: elements where any skill scores 0%
    print()
    print_header("WEAKNESS REPORT (0% hit rate elements)")
    found_weakness = False
    for challenge in challenges:
        for skill in skill_modes:
            if skill is None:
                continue
            results = all_results.get(challenge.id, {}).get(label(skill), [])
            if not results:
                continue
            for eid in challenge.rubric.required_elements:
                hits, total = _element_hit_rate(results, eid)
                if hits == 0 and total > 0:
                    print(f"  {label(skill)} on {challenge.id}: {eid} = 0/{total}")
                    found_weakness = True
    if not found_weakness:
        print("  None found!")

    # Anti-pattern report: elements where any skill scores 100%
    print()
    print_header("ANTI-PATTERN ALERT (100% trigger rate)")
    found_alert = False
    for challenge in challenges:
        for skill in skill_modes:
            if skill is None:
                continue
            results = all_results.get(challenge.id, {}).get(label(skill), [])
            if not results:
                continue
            for aid in challenge.rubric.anti_patterns:
                hits, total = _element_hit_rate(results, aid, is_anti=True)
                if hits == total and total > 0:
                    print(f"  {label(skill)} on {challenge.id}: {aid} = {hits}/{total}")
                    found_alert = True
    if not found_alert:
        print("  None found!")

    print()


def print_comparison(current: dict, saved: dict) -> None:
    """Print comparison between current and saved results."""
    print_header("COMPARISON WITH SAVED BASELINE")

    for cid, cdata in current.get("challenges", {}).items():
        saved_cdata = saved.get("challenges", {}).get(cid)
        if not saved_cdata:
            print(f"\n  {cid}: NEW (no saved baseline)")
            continue

        print(f"\n  {cid}: {cdata.get('name', '')}")
        for mode_key, mode_data in cdata.get("modes", {}).items():
            saved_mode = saved_cdata.get("modes", {}).get(mode_key)
            if not saved_mode:
                continue

            cur_scores = mode_data.get("scores", [])
            sav_scores = saved_mode.get("scores", [])
            cur_avg = sum(cur_scores) / len(cur_scores) if cur_scores else 0
            sav_avg = sum(sav_scores) / len(sav_scores) if sav_scores else 0
            delta = cur_avg - sav_avg
            if abs(delta) < 0.01:
                continue

            sign = "+" if delta >= 0 else ""
            print(f"    {mode_key}: {sav_avg:.1f} -> {cur_avg:.1f} ({sign}{delta:.1f})")

            # Element-level diffs
            for eid, edata in mode_data.get("elements", {}).items():
                saved_edata = saved_mode.get("elements", {}).get(eid)
                if not saved_edata:
                    continue
                cur_rate = edata["hits"] / edata["total"] if edata["total"] else 0
                sav_rate = saved_edata["hits"] / saved_edata["total"] if saved_edata["total"] else 0
                if abs(cur_rate - sav_rate) > 0.01:
                    print(f"      {eid}: {sav_rate:.0%} -> {cur_rate:.0%}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run megamind skill benchmarks")
    parser.add_argument("--runs", type=int, default=2, help="Runs per challenge/skill combo")
    parser.add_argument("--challenges", nargs="*", help="Specific challenge IDs to run")
    parser.add_argument("--skill", nargs="*", help="Specific skills to test (always includes baseline)")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--save", type=str, help="Save results to JSON file")
    parser.add_argument("--compare", type=str, help="Compare with saved baseline JSON")
    parser.add_argument("--local", action="store_true", help="Use claude CLI instead of API (no cost)")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers (use with --local)")
    args = parser.parse_args()

    use_local = args.local
    client = None

    if use_local:
        if not shutil.which("claude"):
            print("ERROR: claude CLI not found in PATH")
            sys.exit(1)
        print("Backend: claude CLI (local, no API cost)")
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set (use --local for claude CLI)")
            sys.exit(1)
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        print("Backend: Anthropic API")

    challenges = load_challenges(CHALLENGES_DIR)
    if args.challenges:
        challenges = [c for c in challenges if c.id in args.challenges]

    # Filter skill modes
    skill_modes = list(ALL_SKILL_MODES)
    if args.skill:
        skill_modes = [None]  # Always include baseline
        for s in args.skill:
            if s in ("megamind-deep", "megamind-creative", "megamind-adversarial"):
                skill_modes.append(s)

    total_combos = len(challenges) * len(skill_modes) * args.runs
    total_calls = total_combos * 2
    workers = max(1, args.workers)
    print(f"Running benchmark: {len(challenges)} challenges x {len(skill_modes)} modes x {args.runs} runs")
    print(f"Total calls: {total_calls} | Workers: {workers}")
    print()

    # Build list of all combos
    combos: list[tuple[Challenge, str | None, int]] = []
    for challenge in challenges:
        for skill in skill_modes:
            for run_idx in range(args.runs):
                combos.append((challenge, skill, run_idx))

    # Initialize results structure
    all_results: dict[str, dict[str, list[EvalResult]]] = {}
    for challenge in challenges:
        all_results[challenge.id] = {}
        for skill in skill_modes:
            all_results[challenge.id][label(skill)] = []

    def _run_combo(combo: tuple[Challenge, str | None, int]) -> tuple[str, str, int, EvalResult | None, str]:
        """Run a single combo; returns (cid, key, run_idx, result_or_None, status_msg)."""
        challenge, skill, run_idx = combo
        key = label(skill)
        try:
            if use_local:
                result = run_one_local(challenge, skill)
            else:
                result = run_one(client, challenge, skill)
            status = "PASS" if result.passed else "FAIL"
            return (challenge.id, key, run_idx, result, f"score={result.total_score} {status}")
        except Exception as e:
            return (challenge.id, key, run_idx, None, f"ERROR: {e}")

    start = time.time()
    completed = 0

    if workers == 1:
        # Sequential mode — preserve ordered output
        for combo in combos:
            completed += 1
            challenge, skill, run_idx = combo
            tag = f"[{completed}/{total_combos}]"
            print(f"  {tag} {challenge.id} + {label(skill)} (run {run_idx + 1})...", end=" ", flush=True)
            cid, key, _, result, msg = _run_combo(combo)
            if result:
                all_results[cid][key].append(result)
            print(msg)
    else:
        # Parallel mode
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_run_combo, c): c for c in combos}
            for future in as_completed(futures):
                completed += 1
                cid, key, run_idx, result, msg = future.result()
                if result:
                    all_results[cid][key].append(result)
                tag = f"[{completed}/{total_combos}]"
                print(f"  {tag} {cid} + {key} (run {run_idx + 1})... {msg}")

    elapsed = time.time() - start
    print(f"\nCompleted in {elapsed:.0f}s ({elapsed / 60:.1f}min)")

    # Build JSON data
    json_data = results_to_json(challenges, all_results, skill_modes)

    # Save if requested
    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
        print(f"\nResults saved to {args.save}")

    # Output
    if args.json:
        print(json.dumps(json_data, indent=2))
    else:
        print_element_grid(challenges, all_results, skill_modes)
        print_summary_table(challenges, all_results, skill_modes)

        # Comparison if requested
        if args.compare:
            saved = load_saved_results(Path(args.compare))
            print_comparison(json_data, saved)


if __name__ == "__main__":
    main()
