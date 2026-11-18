"""Command line runner for VibeMatch 2.0.

    python -m src.main                      # the AI agent (default): it may ask you questions
    python -m src.main --request "chill r&b for studying"   # skip the first question
    python -m src.main --baseline           # the original Module 3 recommender, for comparison

The agent needs GEMINI_API_KEY in .env. Without it (or if Gemini is down),
the run still finishes: the rule-based recommender answers and says so.
"""

import argparse
from typing import Optional

from src.agent import AgentResult, RecommenderAgent
from src.catalog import SongCatalog
from src.llm_client import LLMClient, LLMError, UnavailableClient, load_gemini_client
from src.recommender import load_songs, recommend_songs
from src.tools import Toolbox
from src.trace import LOG_DIR, TraceLogger
from src.user_io import ConsoleIO, UserIO

SONGS_CSV = "data/songs.csv"
FIRST_QUESTION = "What are you in the mood for? (for example: chill r&b to study to)"
DEFAULT_REQUEST = "recommend me some music"

# The fixed profile Module 3 always used. --baseline keeps it, so the two
# versions can be compared side by side.
BASELINE_PROFILE = {
    "favorite_genre": "lofi",
    "favorite_mood": "chill",
    "target_energy": 0.4,
    "target_tempo": 78,
    "target_valence": 0.58,
    "target_danceability": 0.60,
    "target_acousticness": 0.78,
}


def print_picks(picks) -> None:
    print("=" * 60)
    for rank, (song, score, explanation) in enumerate(picks, start=1):
        print(f"{rank}. {song['title']} - {song['artist']} ({song['genre']}, {song['mood']})")
        print(f"   Final score: {score:.2f} / 100")
        print("   Reasons:")
        for reason in explanation.split("; "):
            print(f"   - {reason}")
        print("-" * 60)


def run_baseline() -> None:
    """Module 3: one fixed profile, no questions, no AI."""
    songs = load_songs(SONGS_CSV)
    print(f"Loaded songs: {len(songs)}")
    print("Mode: baseline (Module 3 rule-based recommender, fixed lofi profile)")
    recommendations = recommend_songs(BASELINE_PROFILE, songs, k=5)
    print(f"\nTop {len(recommendations)} recommendations")
    print_picks(recommendations)


def run_agent(
    request: Optional[str],
    llm: LLMClient,
    user_io: UserIO,
    log_dir: Optional[str] = LOG_DIR,
) -> AgentResult:
    """VibeMatch 2.0: the agent builds your profile from the conversation."""
    if not request:
        request = user_io.ask(FIRST_QUESTION) or DEFAULT_REQUEST

    catalog = SongCatalog.from_csv(SONGS_CSV)
    agent = RecommenderAgent(llm, Toolbox(catalog, user_io), TraceLogger(log_dir))
    print("\nThinking...")
    result = agent.run(request)

    if result.used_fallback:
        print(f"\nNote: {result.message}")
        print(f"Reason: {result.fallback_reason}")
    elif result.message:
        print(f"\n{result.message}")

    print(f"\nTop {len(result.picks)} recommendations")
    print_picks(result.picks)
    print(f"Confidence: {result.confidence}  |  Agent steps: {result.steps}")
    if result.problems:
        print("Self-check notes: " + "; ".join(result.problems))
    if result.trace_path:
        print(f"Step-by-step log: {result.trace_path}")
    return result


def build_llm() -> LLMClient:
    """Gemini if it can be set up; otherwise a client that makes the agent fall back."""
    try:
        return load_gemini_client()
    except LLMError as exc:
        return UnavailableClient(str(exc))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="VibeMatch 2.0 music recommender")
    parser.add_argument("--baseline", action="store_true", help="run the original Module 3 recommender")
    parser.add_argument("--request", help="what you're in the mood for (skips the first question)")
    args = parser.parse_args(argv)

    if args.baseline:
        run_baseline()
    else:
        run_agent(args.request, build_llm(), ConsoleIO())


if __name__ == "__main__":
    main()
