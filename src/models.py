"""Shared data shapes and vocabulary for the recommender.

Everything here is plain data with no logic that depends on other modules, so
any part of the system (catalog, scorer, guardrails, agent) can import it
without creating import loops.

Songs travel through the pipeline as dictionaries (one row of songs.csv).
The Song and UserProfile dataclasses are kept for the original Module 3 tests.
"""

from dataclasses import dataclass
from typing import Optional

# Moods that feel alike share a cluster and earn partial credit when scoring.
# The catalog uses the same clusters to search for "similar mood" songs.
MOOD_CLUSTERS = {
    "Calm": {"chill", "relaxed", "peaceful", "focused", "dreamy", "reflective"},
    "Happy": {
        "happy",
        "uplifting",
        "euphoric",
        "celebratory",
        "carefree",
        "playful",
        "whimsical",
        "mischievous",
    },
    "Intense": {
        "intense",
        "angry",
        "aggressive",
        "anxious",
        "rebellious",
        "overwhelmed",
    },
    "Energetic": {"energetic", "confident", "determined", "adventurous"},
    "Romantic": {"romantic", "passionate"},
    "Longing": {"sad", "melancholic", "yearning", "nostalgic"},
    "Moody": {"moody", "mysterious", "uncertain"},
}

# Every mood the system understands.
KNOWN_MOODS = set().union(*MOOD_CLUSTERS.values())


def mood_cluster(mood: str) -> Optional[str]:
    """Return the cluster name for a mood (e.g. 'chill' -> 'Calm'), or None."""
    mood = str(mood).strip().casefold()
    return next((name for name, moods in MOOD_CLUSTERS.items() if mood in moods), None)


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """

    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """

    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
