from src.guardrails import PickChecker, ProfileValidator
from src.recommender import load_songs, recommend_songs

SONGS = load_songs("data/songs.csv")
GENRES = {song["genre"] for song in SONGS}


def good_profile(**changes):
    profile = {
        "favorite_genre": "r&b",
        "favorite_mood": "romantic",
        "target_energy": 0.6,
        "target_tempo": 100,
        "target_valence": 0.6,
        "target_danceability": 0.8,
        "target_acousticness": 0.2,
    }
    profile.update(changes)
    return profile


# --- ProfileValidator --------------------------------------------------------


def test_valid_profile_passes_with_no_warnings():
    result = ProfileValidator(GENRES).validate(good_profile())
    assert result.ok
    assert result.errors == []
    assert result.warnings == []


def test_labels_are_trimmed_and_lowercased():
    result = ProfileValidator(GENRES).validate(
        good_profile(favorite_genre="  R&B ", favorite_mood="Romantic")
    )
    assert result.ok
    assert result.profile["favorite_genre"] == "r&b"
    assert result.profile["favorite_mood"] == "romantic"


def test_energy_out_of_range_is_rejected():
    result = ProfileValidator(GENRES).validate(good_profile(target_energy=1.5))
    assert not result.ok
    assert any("target_energy" in error for error in result.errors)


def test_impossible_tempo_is_rejected():
    result = ProfileValidator(GENRES).validate(good_profile(target_tempo=-100))
    assert not result.ok
    assert any("target_tempo" in error for error in result.errors)


def test_text_instead_of_number_is_rejected():
    result = ProfileValidator(GENRES).validate(good_profile(target_valence="high"))
    assert not result.ok
    assert any("target_valence" in error for error in result.errors)


def test_missing_key_is_rejected():
    profile = good_profile()
    del profile["target_danceability"]
    result = ProfileValidator(GENRES).validate(profile)
    assert not result.ok
    assert any("target_danceability" in error for error in result.errors)


def test_unknown_genre_and_mood_are_warnings_not_errors():
    result = ProfileValidator(GENRES).validate(
        good_profile(favorite_genre="polka", favorite_mood="hungry")
    )
    assert result.ok
    assert len(result.warnings) == 2


# --- PickChecker -------------------------------------------------------------


def test_real_recommendations_pass_with_high_confidence():
    picks = recommend_songs(good_profile(), SONGS, k=5)
    result = PickChecker(SONGS).check(picks)
    assert result.ok, result.problems
    assert result.confidence == "high"


def test_made_up_song_is_caught():
    picks = recommend_songs(good_profile(), SONGS, k=5)
    fake = {"id": 999, "title": "Song That Does Not Exist", "artist": "Nobody"}
    result = PickChecker(SONGS).check(picks[:4] + [(fake, 90.0, "made up")])
    assert not result.ok
    assert any("not in catalog" in problem for problem in result.problems)


def test_wrong_title_for_a_real_id_is_caught():
    picks = recommend_songs(good_profile(), SONGS, k=5)
    song, score, why = picks[0]
    renamed = dict(song, title="Invented Remix")
    result = PickChecker(SONGS).check([(renamed, score, why)] + picks[1:])
    assert not result.ok


def test_duplicate_song_is_caught():
    picks = recommend_songs(good_profile(), SONGS, k=5)
    result = PickChecker(SONGS).check(picks[:4] + [picks[0]])
    assert not result.ok
    assert any("duplicate" in problem for problem in result.problems)


def test_too_many_songs_by_one_artist_is_caught():
    burna_boy = [song for song in SONGS if song["artist"] == "Burna Boy"][:3]
    picks = [(song, 80.0, "") for song in burna_boy]
    result = PickChecker(SONGS).check(picks)
    assert not result.ok
    assert any("too repetitive" in problem for problem in result.problems)


def test_weak_top_score_means_low_confidence():
    picks = [(song, 17.0, "") for song in SONGS[:5]]
    result = PickChecker(SONGS).check(picks)
    assert result.confidence == "low"


def test_empty_list_fails():
    assert not PickChecker(SONGS).check([]).ok
