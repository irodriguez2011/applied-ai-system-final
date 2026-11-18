"""Evaluator: run the agent on fixed requests and print a pass/fail table.

    python -m eval.run_eval

Each case has a request, scripted answers for any follow-up questions, and a
"fit" rule (for example, at least 3 of the 5 picks are bachata). A case
passes when the agent:

1. finished on its own (no fallback),
2. recommended only real catalog songs (the self-check passed),
3. stayed within the step limit, and
4. met the case's fit rule.

The same fit rule is also applied to the Module 3 baseline (its fixed lofi
profile), to show where the agent changes the results.

The table and summary line are printed and saved to eval/latest_results.md,
so they can be pasted into the README or model card as text.
"""

import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from src.agent import MAX_STEPS, AgentResult, RecommenderAgent
from src.catalog import SongCatalog
from src.llm_client import LLMClient
from src.main import BASELINE_PROFILE, SONGS_CSV, build_llm
from src.models import mood_cluster
from src.recommender import recommend_songs
from src.tools import Toolbox
from src.trace import LOG_DIR, TraceLogger
from src.user_io import ScriptedIO

RESULTS_PATH = Path(__file__).resolve().parent / "latest_results.md"
# Gemini's free tier allows 15 requests a minute, and a case uses about 5.
# Pausing between cases keeps the run under that limit.
DEFAULT_PAUSE_SECONDS = 20

Songs = List[Dict]


def count(songs: Songs, test: Callable[[Dict], bool]) -> int:
    return sum(1 for song in songs if test(song))


@dataclass
class Case:
    name: str
    request: str
    answers: Sequence[str]
    rule: str  # what "fits" means, in words, for the table
    fits: Callable[[Songs], bool]
    must_ask: bool = False  # vague request: the agent should ask a question


CASES = [
    Case(
        "Study music",
        "something chill to study to",
        ["lofi or r&b", "low energy"],
        "3+ of 5 have a calm mood",
        lambda s: count(s, lambda x: mood_cluster(x["mood"]) == "Calm") >= 3,
    ),
    Case(
        "Party",
        "high energy songs for a party",
        ["reggaeton or afrobeats", "very high"],
        "3+ of 5 have energy 0.7 or more",
        lambda s: count(s, lambda x: x["energy"] >= 0.7) >= 3,
    ),
    Case(
        "Named genre",
        "romantic bachata",
        ["slow to medium", "romantic"],
        "3+ of 5 are bachata",
        lambda s: count(s, lambda x: x["genre"] == "bachata") >= 3,
    ),
    Case(
        "Sad mood",
        "sad songs for a rainy day",
        ["any genre", "low energy"],
        "2+ of 5 have a sad or longing mood",
        lambda s: count(s, lambda x: mood_cluster(x["mood"]) == "Longing") >= 2,
    ),
    Case(
        "Vague request",
        "recommend me some music",
        ["afrobeats, something happy", "medium energy", "no preference"],
        "asks a question; 2+ of 5 are afrobeats",
        lambda s: count(s, lambda x: x["genre"] == "afrobeats") >= 2,
        must_ask=True,
    ),
    Case(
        "Genre not in catalog",
        "polka music for my grandma",
        ["something happy and upbeat", "medium energy", "no preference"],
        "only real songs; 2+ of 5 have a happy mood",
        lambda s: count(s, lambda x: mood_cluster(x["mood"]) == "Happy") >= 2,
    ),
]


@dataclass
class Row:
    case: Case
    passed: bool
    picks: Songs
    confidence: str
    steps: int
    questions: int
    baseline_fits: bool
    notes: List[str] = field(default_factory=list)


def evaluate(
    case: Case, llm: LLMClient, catalog: SongCatalog, baseline: Songs, log_dir: Optional[str]
) -> Row:
    io = ScriptedIO(case.answers)
    agent = RecommenderAgent(llm, Toolbox(catalog, io), TraceLogger(log_dir))
    result: AgentResult = agent.run(case.request)
    picks = [song for song, _score, _reasons in result.picks]

    notes = []
    if result.used_fallback:
        notes.append(f"fell back ({result.fallback_reason[:60]})")
    if result.problems:
        notes.append("self-check: " + "; ".join(result.problems))
    if result.steps > MAX_STEPS:
        notes.append("too many steps")
    fits = case.fits(picks)
    if not fits:
        notes.append("picks don't fit the request")
    if case.must_ask and not io.questions:
        notes.append("didn't ask a question")

    return Row(
        case=case,
        passed=not notes,
        picks=picks,
        confidence=result.confidence,
        steps=result.steps,
        questions=len(io.questions),
        baseline_fits=case.fits(baseline),
        notes=notes,
    )


def run_cases(
    llm: LLMClient,
    cases: Sequence[Case] = CASES,
    log_dir: Optional[str] = LOG_DIR,
    pause_seconds: float = 0,
) -> List[Row]:
    catalog = SongCatalog.from_csv(SONGS_CSV)
    baseline = [song for song, _s, _r in recommend_songs(BASELINE_PROFILE, catalog.all(), k=5)]
    rows = []
    for number, case in enumerate(cases):
        if number and pause_seconds:
            time.sleep(pause_seconds)
        row = evaluate(case, llm, catalog, baseline, log_dir)
        print(f"  {'PASS' if row.passed else 'FAIL'}  {case.name}")
        rows.append(row)
    return rows


def summary_line(rows: List[Row]) -> str:
    passed = sum(row.passed for row in rows)
    high = sum(row.confidence == "high" for row in rows)
    baseline = sum(row.baseline_fits for row in rows)
    line = (
        f"{passed} of {len(rows)} cases passed. "
        f"Confidence was high in {high} of {len(rows)}. "
        f"The Module 3 baseline fit {baseline} of {len(rows)} requests."
    )
    failed = [row for row in rows if not row.passed]
    if failed:
        line += " Struggled with: " + "; ".join(
            f"{row.case.name} ({', '.join(row.notes)})" for row in failed
        ) + "."
    return line


def to_markdown(rows: List[Row]) -> str:
    lines = [
        "| Case | Request | Fit rule | Agent | Confidence | Steps | Questions | Baseline fits? | Top 3 picks |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        top = ", ".join(song["title"] for song in row.picks[:3])
        verdict = "PASS" if row.passed else "FAIL: " + "; ".join(row.notes)
        lines.append(
            f"| {row.case.name} | {row.case.request} | {row.case.rule} | {verdict} | "
            f"{row.confidence} | {row.steps} | {row.questions} | "
            f"{'yes' if row.baseline_fits else 'no'} | {top} |"
        )
    return "\n".join(lines) + "\n\n" + summary_line(rows) + "\n"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Run the VibeMatch agent on fixed test requests")
    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_PAUSE_SECONDS,
        help=f"seconds to wait between cases, to stay under the free-tier rate limit (default {DEFAULT_PAUSE_SECONDS})",
    )
    args = parser.parse_args(argv)
    print(f"Running {len(CASES)} cases with the agent (Gemini), {args.pause:g} s apart...")
    rows = run_cases(build_llm(), pause_seconds=args.pause)
    report = to_markdown(rows)
    RESULTS_PATH.write_text(report, encoding="utf-8")
    print("\n" + report)
    print("Saved to eval/latest_results.md")


if __name__ == "__main__":
    main()
