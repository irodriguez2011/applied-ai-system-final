"""main.py tests: the agent is the default path, and --baseline still works."""

import json

from src import main
from src.catalog import SongCatalog
from src.llm_client import MockClient, UnavailableClient
from src.tools import Toolbox
from src.user_io import ScriptedIO

PROFILE = {
    "favorite_genre": "bachata",
    "favorite_mood": "romantic",
    "target_energy": 0.55,
    "target_tempo": 125,
    "target_valence": 0.6,
    "target_danceability": 0.75,
    "target_acousticness": 0.4,
}


def test_baseline_prints_the_module_3_results(capsys):
    main.main(["--baseline"])
    out = capsys.readouterr().out
    assert "Mode: baseline" in out
    assert "1. Midnight Coding" in out and "98.50" in out


def test_agent_asks_first_question_when_no_request_given(capsys):
    io = ScriptedIO(["romantic bachata"])
    llm = MockClient([])  # AI down: still must finish
    result = main.run_agent(None, llm, io, log_dir=None)
    assert io.questions == [main.FIRST_QUESTION]
    assert "romantic bachata" in llm.calls[0][1]
    assert result.used_fallback


def varied_ids(k=5):
    """Top-ranked ids for PROFILE, one per artist, so the self-check passes."""
    ranked = Toolbox(SongCatalog.from_csv(main.SONGS_CSV), ScriptedIO()).run(
        "rank_songs", {"profile": PROFILE, "k": 20}
    ).data["ranked"]
    ids, seen = [], set()
    for song in ranked:
        if song["artist"] not in seen:
            ids.append(song["id"])
            seen.add(song["artist"])
    return ids[:k]


def test_agent_output_shows_picks_and_confidence(capsys):
    llm = MockClient(
        [
            json.dumps({"thought": "rank", "tool": "rank_songs", "args": {"profile": PROFILE, "k": 10}}),
            json.dumps({"thought": "done", "final": {"song_ids": varied_ids(), "message": "Bachata night!"}}),
        ]
    )
    result = main.run_agent("romantic bachata", llm, ScriptedIO(), log_dir=None)
    out = capsys.readouterr().out
    assert not result.used_fallback
    assert "Bachata night!" in out
    assert "Confidence:" in out and "Final score:" in out


def test_missing_key_still_gives_recommendations(capsys):
    result = main.run_agent(
        "chill r&b", UnavailableClient("GEMINI_API_KEY is not set"), ScriptedIO(), log_dir=None
    )
    out = capsys.readouterr().out
    assert result.used_fallback and len(result.picks) == 5
    assert "GEMINI_API_KEY is not set" in out
