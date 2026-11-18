from src.catalog import SongCatalog
from src.tools import TOOL_SPECS, Toolbox
from src.user_io import ScriptedIO

CATALOG = SongCatalog.from_csv("data/songs.csv")

PROFILE = {
    "favorite_genre": "r&b",
    "favorite_mood": "chill",
    "target_energy": 0.4,
    "target_tempo": 90,
    "target_valence": 0.5,
    "target_danceability": 0.6,
    "target_acousticness": 0.4,
}


def make_toolbox(answers=()):
    io = ScriptedIO(answers)
    return Toolbox(CATALOG, io), io


# --- run(): the trust boundary ---------------------------------------------


def test_tool_specs_match_the_tools():
    toolbox, _ = make_toolbox()
    assert set(TOOL_SPECS) == set(toolbox._tools)


def test_unknown_tool_is_refused_not_crashed():
    toolbox, _ = make_toolbox()
    result = toolbox.run("delete_all_songs", {})
    assert not result.ok
    assert "unknown tool" in result.error


def test_bad_argument_name_is_reported():
    toolbox, _ = make_toolbox()
    result = toolbox.run("search_songs", {"artist": "Drake"})
    assert not result.ok
    assert "bad arguments" in result.error


def test_arguments_must_be_an_object():
    toolbox, _ = make_toolbox()
    assert not toolbox.run("search_songs", "r&b").ok


# --- ask_user -----------------------------------------------------------


def test_ask_user_returns_the_answer():
    toolbox, io = make_toolbox(["something chill for studying"])
    result = toolbox.run("ask_user", {"question": "What are you in the mood for?"})
    assert result.ok
    assert result.data["answer"] == "something chill for studying"
    assert io.questions == ["What are you in the mood for?"]


def test_ask_user_stops_at_the_question_limit():
    toolbox, _ = make_toolbox(["a", "b", "c", "d"])
    for _ in range(3):
        assert toolbox.run("ask_user", {"question": "?"}).ok
    result = toolbox.run("ask_user", {"question": "one more?"})
    assert not result.ok
    assert "question limit" in result.error


def test_silent_user_gets_a_placeholder_answer():
    toolbox, _ = make_toolbox([])
    result = toolbox.run("ask_user", {"question": "Favorite genre?"})
    assert result.ok
    assert result.data["answer"] == "(no answer)"


# --- search_songs -------------------------------------------------------


def test_search_returns_only_real_songs():
    toolbox, _ = make_toolbox()
    result = toolbox.run("search_songs", {"genre": "bachata"})
    assert result.ok
    assert result.data["count"] == 7
    assert all(CATALOG.get_by_id(song["id"]) for song in result.data["songs"])


def test_search_with_no_match_gives_a_hint():
    toolbox, _ = make_toolbox()
    result = toolbox.run("search_songs", {"genre": "polka"})
    assert result.ok
    assert result.data["count"] == 0
    assert "known genres" in result.data["hint"]


def test_search_rejects_bad_energy():
    toolbox, _ = make_toolbox()
    assert not toolbox.run("search_songs", {"min_energy": 2}).ok
    assert not toolbox.run("search_songs", {"min_energy": 0.8, "max_energy": 0.2}).ok


# --- rank_songs ---------------------------------------------------------


def test_rank_returns_scores_and_reasons_from_code():
    toolbox, _ = make_toolbox()
    result = toolbox.run("rank_songs", {"profile": PROFILE, "k": 5})
    assert result.ok
    ranked = result.data["ranked"]
    assert len(ranked) == 5
    assert ranked[0]["score"] >= ranked[-1]["score"]
    assert "energy closeness" in ranked[0]["reasons"]


def test_rank_blocks_an_invalid_profile():
    toolbox, _ = make_toolbox()
    result = toolbox.run("rank_songs", {"profile": dict(PROFILE, target_energy=7)})
    assert not result.ok
    assert "invalid profile" in result.error


def test_rank_rejects_made_up_song_ids():
    toolbox, _ = make_toolbox()
    result = toolbox.run("rank_songs", {"profile": PROFILE, "song_ids": [1, 999]})
    assert not result.ok
    assert "999" in result.error


def test_rank_only_the_given_candidates():
    toolbox, _ = make_toolbox()
    ids = [s["id"] for s in CATALOG.search(genre="reggaeton")]
    result = toolbox.run("rank_songs", {"profile": PROFILE, "song_ids": ids, "k": 3})
    assert result.ok
    assert all(song["genre"] == "reggaeton" for song in result.data["ranked"])


# --- check_picks --------------------------------------------------------


def test_check_requires_ranking_first():
    toolbox, _ = make_toolbox()
    result = toolbox.run("check_picks", {"song_ids": [1, 2]})
    assert not result.ok
    assert "rank_songs" in result.error


def test_check_passes_real_ranked_picks():
    toolbox, _ = make_toolbox()
    ranked = toolbox.run("rank_songs", {"profile": PROFILE, "k": 5}).data["ranked"]
    result = toolbox.run("check_picks", {"song_ids": [s["id"] for s in ranked]})
    assert result.ok
    assert result.data["passed"], result.data["problems"]
    assert result.data["confidence"] in {"high", "medium", "low"}


def test_check_catches_an_invented_song():
    toolbox, _ = make_toolbox()
    ranked = toolbox.run("rank_songs", {"profile": PROFILE, "k": 4}).data["ranked"]
    result = toolbox.run("check_picks", {"song_ids": [s["id"] for s in ranked] + [999]})
    assert result.ok  # the check itself ran
    assert not result.data["passed"]
    assert any("not in catalog" in p for p in result.data["problems"])


def test_check_scores_a_real_but_unranked_song_in_code():
    toolbox, _ = make_toolbox()
    toolbox.run("rank_songs", {"profile": PROFILE, "k": 3})
    result = toolbox.run("check_picks", {"song_ids": [46]})  # ranked list did not include it
    assert result.ok
    song, score, _ = toolbox.last_checked_picks[0]
    assert song["id"] == 46 and score > 0
