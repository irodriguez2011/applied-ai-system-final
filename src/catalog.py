"""SongCatalog: the one place that knows which songs exist.

GRASP Information Expert: the catalog holds the song data, so it answers
"does this song exist?" and "which songs match these filters?".

The agent's search_songs tool calls SongCatalog.search(), so the agent can only
ever see real songs from data/songs.csv.
"""

import csv
from typing import Dict, Iterable, List, Optional

from src.models import mood_cluster

NUMERIC_FIELDS = ("energy", "tempo_bpm", "valence", "danceability", "acousticness")


def load_songs(csv_path: str) -> List[Dict]:
    """Load song rows from a CSV file and convert numeric fields."""
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        for song in csv.DictReader(csv_file):
            song["id"] = int(song["id"])
            for field in NUMERIC_FIELDS:
                song[field] = float(song[field])
            songs.append(song)
    return songs


class SongCatalog:
    """Holds every song and answers lookups and searches."""

    def __init__(self, songs: Iterable[Dict]):
        self._songs = list(songs)
        self._by_id = {song["id"]: song for song in self._songs}

    @classmethod
    def from_csv(cls, csv_path: str) -> "SongCatalog":
        return cls(load_songs(csv_path))

    def all(self) -> List[Dict]:
        """Every song, in catalog order."""
        return list(self._songs)

    def __len__(self) -> int:
        return len(self._songs)

    def get_by_id(self, song_id: int) -> Optional[Dict]:
        """The song with this id, or None if it does not exist."""
        return self._by_id.get(song_id)

    def genres(self) -> List[str]:
        """Every genre in the catalog, sorted."""
        return sorted({song["genre"].casefold() for song in self._songs})

    def moods(self) -> List[str]:
        """Every mood in the catalog, sorted."""
        return sorted({song["mood"].casefold() for song in self._songs})

    def search(
        self,
        genre: Optional[str] = None,
        mood: Optional[str] = None,
        min_energy: Optional[float] = None,
        max_energy: Optional[float] = None,
        similar_moods: bool = True,
    ) -> List[Dict]:
        """Return songs matching every filter given (filters left as None are ignored).

        genre:         exact genre, case-insensitive ("R&B" matches "r&b").
        mood:          exact mood, or, with similar_moods=True, any mood in the
                       same cluster ("chill" also matches "relaxed", "focused").
        min/max_energy: keep songs whose energy is inside this range (0-1).
        """
        genre = genre.strip().casefold() if genre else None
        mood = mood.strip().casefold() if mood else None
        wanted_cluster = mood_cluster(mood) if (mood and similar_moods) else None

        results = []
        for song in self._songs:
            if genre and song["genre"].casefold() != genre:
                continue
            if mood:
                song_mood = song["mood"].casefold()
                same_cluster = wanted_cluster is not None and mood_cluster(song_mood) == wanted_cluster
                if song_mood != mood and not same_cluster:
                    continue
            if min_energy is not None and song["energy"] < min_energy:
                continue
            if max_energy is not None and song["energy"] > max_energy:
                continue
            results.append(song)
        return results
