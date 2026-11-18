from src.catalog import SongCatalog
from src.recommender import recommend_songs

CATALOG = SongCatalog.from_csv("data/songs.csv")


def test_catalog_loads_every_song_with_numbers():
    assert len(CATALOG) == 47
    song = CATALOG.get_by_id(1)
    assert song["title"] == "Believe What I Say"
    assert isinstance(song["energy"], float)


def test_unknown_id_returns_none():
    assert CATALOG.get_by_id(999) is None


def test_search_by_genre_is_case_insensitive():
    results = CATALOG.search(genre="  R&B ")
    assert len(results) == 11
    assert all(song["genre"] == "r&b" for song in results)


def test_search_by_mood_includes_similar_moods():
    exact = CATALOG.search(mood="chill", similar_moods=False)
    similar = CATALOG.search(mood="chill")
    assert all(song["mood"] == "chill" for song in exact)
    assert len(similar) > len(exact)
    assert any(song["mood"] == "focused" for song in similar)


def test_search_by_energy_range():
    results = CATALOG.search(min_energy=0.3, max_energy=0.5)
    assert results
    assert all(0.3 <= song["energy"] <= 0.5 for song in results)


def test_filters_combine():
    results = CATALOG.search(genre="reggaeton", min_energy=0.8)
    assert all(song["genre"] == "reggaeton" and song["energy"] >= 0.8 for song in results)


def test_no_match_returns_empty_list():
    assert CATALOG.search(genre="polka") == []


def test_genres_lists_each_genre_once():
    genres = CATALOG.genres()
    assert len(genres) == len(set(genres)) == 13
    assert "bachata" in genres


def test_refactor_keeps_scores_the_same():
    """main.py's lofi profile must still give the same top 5 as before the split."""
    profile = {
        "favorite_genre": "lofi",
        "favorite_mood": "chill",
        "target_energy": 0.4,
        "target_tempo": 78,
        "target_valence": 0.58,
        "target_danceability": 0.60,
        "target_acousticness": 0.78,
    }
    top = recommend_songs(profile, CATALOG.all(), k=5)
    assert [(song["title"], round(score, 2)) for song, score, _ in top] == [
        ("Midnight Coding", 98.50),
        ("Library Rain", 97.12),
        ("Focus Flow", 86.20),
        ("Pink Dolphin Sunset", 85.57),
        ("Spacewalk Thoughts", 82.95),
    ]
