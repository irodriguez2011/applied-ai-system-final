"""Scoring and ranking: how well each song fits a taste profile.

This module only scores and ranks. Song data and lookups live in
src/catalog.py; shared data shapes and mood clusters live in src/models.py.
load_songs, Song, UserProfile, MOOD_CLUSTERS and KNOWN_MOODS are re-exported
here so older imports (main.py, the Module 3 tests) keep working.
"""

from typing import Dict, List, Tuple

from src.catalog import load_songs  # noqa: F401  (re-exported)
from src.models import KNOWN_MOODS, MOOD_CLUSTERS, Song, UserProfile, mood_cluster  # noqa: F401

# --- Experiment: weight shift -------------------------------------------
# Original weights: genre 20, energy 20 (max score 100).
# Experiment: halve genre (20 -> 10) and double energy (20 -> 40).
# To undo, set GENRE_POINTS = 20 and ENERGY_WEIGHT = 20.
MOOD_POINTS = 30
MOOD_CLUSTER_POINTS = 15
GENRE_POINTS = 10
ENERGY_WEIGHT = 40
VALENCE_WEIGHT = 10
DANCEABILITY_WEIGHT = 8
ACOUSTICNESS_WEIGHT = 7
TEMPO_WEIGHT = 5

# Highest possible raw score. With the experiment weights this is 110,
# so scores are rescaled to stay on a 0-100 scale.
MAX_RAW_SCORE = (
    MOOD_POINTS
    + GENRE_POINTS
    + ENERGY_WEIGHT
    + VALENCE_WEIGHT
    + DANCEABILITY_WEIGHT
    + ACOUSTICNESS_WEIGHT
    + TEMPO_WEIGHT
)


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """

    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        # TODO: Implement recommendation logic
        return self.songs[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        # TODO: Implement explanation logic
        return "Explanation placeholder"


def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song against the user's preferences and explain the points."""
    score = 0.0
    reasons = []
    favorite_mood = str(user_prefs["favorite_mood"]).strip().casefold()
    song_mood = str(song["mood"]).strip().casefold()

    if song_mood == favorite_mood:
        score += MOOD_POINTS
        reasons.append(f"mood match: {song['mood']} (+{MOOD_POINTS} points)")
    else:
        favorite_cluster = mood_cluster(favorite_mood)
        song_cluster = mood_cluster(song_mood)
        if favorite_cluster is not None and favorite_cluster == song_cluster:
            score += MOOD_CLUSTER_POINTS
            reasons.append(
                f"mood cluster match: {favorite_cluster} (+{MOOD_CLUSTER_POINTS} points)"
            )

    favorite_genre = str(user_prefs["favorite_genre"]).strip().casefold()
    song_genre = str(song["genre"]).strip().casefold()
    if song_genre == favorite_genre:
        score += GENRE_POINTS
        reasons.append(f"genre match: {song['genre']} (+{GENRE_POINTS} points)")

    numeric_features = (
        ("energy", "target_energy", ENERGY_WEIGHT, 1),
        ("valence", "target_valence", VALENCE_WEIGHT, 1),
        ("danceability", "target_danceability", DANCEABILITY_WEIGHT, 1),
        ("acousticness", "target_acousticness", ACOUSTICNESS_WEIGHT, 1),
        ("tempo_bpm", "target_tempo", TEMPO_WEIGHT, 120),
    )
    for song_key, target_key, weight, scale in numeric_features:
        song_value = float(song[song_key])
        target_value = float(user_prefs[target_key])
        closeness = max(0.0, 1.0 - abs(song_value - target_value) / scale)
        points = closeness * weight
        score += points
        feature_name = "tempo" if song_key == "tempo_bpm" else song_key
        reasons.append(f"{feature_name} closeness: {points:.2f}/{weight} points")

    # Rescale so the final score is always out of 100, whatever the weights.
    final_score = score / MAX_RAW_SCORE * 100
    return final_score, reasons


def recommend_songs(
    user_prefs: Dict, songs: List[Dict], k: int = 5
) -> List[Tuple[Dict, float, str]]:
    """Return the top k songs ranked by preference score."""
    scored_songs = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        explanation = "; ".join(reasons)
        scored_songs.append((song, score, explanation))

    return sorted(scored_songs, key=lambda result: result[1], reverse=True)[:k]
