"""Evaluator tests: offline, so they check the scoring of cases, not Gemini."""

import json

from eval import run_eval
from src.catalog import SongCatalog
from src.llm_client import MockClient, UnavailableClient
from src.tools import Toolbox
from src.user_io import ScriptedIO

CATALOG = SongCatalog.from_csv("data/songs.csv")
BACHATA_IDS = [s["id"] for s in CATALOG.search(genre="bachata")]
BACHATA_CASE = next(case for case in run_eval.CASES if case.name == "Named genre")

PROFILE = {
    "favorite_genre": "bachata",
    "favorite_mood": "romantic",
    "target_energy": 0.55,
    "target_tempo": 125,
    "target_valence": 0.6,
    "target_danceability": 0.75,
    "target_acousticness": 0.4,
}


def test_every_case_has_a_request_and_rule():
    assert len(run_eval.CASES) == 6
    assert all(case.request and case.rule for case in run_eval.CASES)


def varied_bachata_ids(k=5):
    """The top bachata picks, with at most 2 songs per artist."""
    ranked = Toolbox(CATALOG, ScriptedIO()).run(
        "rank_songs", {"profile": PROFILE, "song_ids": BACHATA_IDS, "k": 7}
    ).data["ranked"]
    ids, per_artist = [], {}
    for song in ranked:
        artist = song["artist"].split("&")[0].strip().casefold()
        if per_artist.get(artist, 0) < 2:
            ids.append(song["id"])
            per_artist[artist] = per_artist.get(artist, 0) + 1
    return ids[:k]


def test_a_good_agent_run_passes():
    replies = [
        json.dumps({"tool": "rank_songs", "args": {"profile": PROFILE, "song_ids": BACHATA_IDS, "k": 5}}),
        json.dumps({"final": {"song_ids": varied_bachata_ids(), "message": "ok"}}),
    ]
    rows = run_eval.run_cases(MockClient(replies), [BACHATA_CASE], log_dir=None)
    assert rows[0].passed, rows[0].notes
    assert not rows[0].baseline_fits  # the fixed lofi profile gives no bachata


def test_fallback_counts_as_a_failure_with_a_reason():
    rows = run_eval.run_cases(UnavailableClient("no key"), [BACHATA_CASE], log_dir=None)
    assert not rows[0].passed
    assert any("fell back" in note for note in rows[0].notes)


def test_report_has_a_table_and_a_summary_line():
    rows = run_eval.run_cases(UnavailableClient("no key"), run_eval.CASES[:2], log_dir=None)
    report = run_eval.to_markdown(rows)
    assert report.startswith("| Case |")
    assert "0 of 2 cases passed" in report
    assert "Struggled with:" in report
