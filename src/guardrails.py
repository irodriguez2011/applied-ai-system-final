"""Guardrails: checks that run no matter what the AI agent decides.

Two guardrails live here:

- ProfileValidator runs BEFORE ranking. It checks the taste profile the agent
  built (from the user's answers) and rejects impossible values.
- PickChecker runs AFTER ranking. It checks the recommendations themselves:
  every song must be real, there must be no repeats, there must be some
  variety, and it reports how confident the result is.

Both are plain Python with fixed rules, so they work the same way whether the
profile came from a person, the Gemini agent, or a test.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from src.models import KNOWN_MOODS

# --- ProfileValidator --------------------------------------------------------

# Every key a profile needs before it can be scored.
REQUIRED_KEYS = (
    "favorite_genre",
    "favorite_mood",
    "target_energy",
    "target_tempo",
    "target_valence",
    "target_danceability",
    "target_acousticness",
)

# Features measured on a 0-1 scale.
UNIT_RANGE_KEYS = (
    "target_energy",
    "target_valence",
    "target_danceability",
    "target_acousticness",
)

# A sensible tempo range in beats per minute.
MIN_TEMPO_BPM = 40
MAX_TEMPO_BPM = 220


@dataclass
class ValidationResult:
    """Outcome of validating a profile.

    ok:       True when the profile is safe to score.
    errors:   problems that block scoring (the agent must fix them).
    warnings: problems that still allow scoring but should be shown.
    profile:  a cleaned copy (labels trimmed and lower-cased, numbers as floats).
    """

    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    profile: Dict = field(default_factory=dict)


class ProfileValidator:
    """Checks a taste profile before any song is scored."""

    def __init__(self, known_genres: Iterable[str], known_moods: Iterable[str] = KNOWN_MOODS):
        self.known_genres = {str(g).strip().casefold() for g in known_genres}
        self.known_moods = {str(m).strip().casefold() for m in known_moods}

    def validate(self, profile: Dict) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []
        cleaned: Dict = {}

        if not isinstance(profile, dict):
            return ValidationResult(ok=False, errors=["profile must be a dictionary"])

        missing = [key for key in REQUIRED_KEYS if key not in profile]
        if missing:
            errors.append(f"missing keys: {', '.join(missing)}")

        # Labels: must be text; unknown values are allowed but flagged.
        for key, known, label in (
            ("favorite_genre", self.known_genres, "genre"),
            ("favorite_mood", self.known_moods, "mood"),
        ):
            if key not in profile:
                continue
            value = profile[key]
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{key} must be non-empty text")
                continue
            value = value.strip().casefold()
            cleaned[key] = value
            if value not in known:
                warnings.append(
                    f"unknown {label} '{value}': no song will earn {label} points"
                )

        # Numbers: must be numeric and inside their allowed range.
        for key in UNIT_RANGE_KEYS + ("target_tempo",):
            if key not in profile:
                continue
            value = profile[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"{key} must be a number, got {value!r}")
                continue
            value = float(value)
            low, high = (
                (MIN_TEMPO_BPM, MAX_TEMPO_BPM) if key == "target_tempo" else (0.0, 1.0)
            )
            if not low <= value <= high:
                errors.append(f"{key} must be between {low:g} and {high:g}, got {value:g}")
                continue
            cleaned[key] = value

        # Keep any extra keys (for example allow-lists added later) unchanged.
        for key, value in profile.items():
            cleaned.setdefault(key, value)

        return ValidationResult(ok=not errors, errors=errors, warnings=warnings, profile=cleaned)


# --- PickChecker -------------------------------------------------------------

# Confidence is based on the best score in the list (scores are out of 100).
HIGH_CONFIDENCE_SCORE = 80
MEDIUM_CONFIDENCE_SCORE = 60

# Variety rule: the same lead artist may appear at most this many times.
MAX_SONGS_PER_ARTIST = 2

# One recommendation as returned by recommend_songs: (song, score, explanation).
Pick = Tuple[Dict, float, str]


@dataclass
class CheckResult:
    """Outcome of checking a list of recommendations.

    ok:         True when every rule passed.
    problems:   rule failures the agent should fix (for example, by re-ranking).
    confidence: "high", "medium" or "low", based on the top score.
    """

    ok: bool
    problems: List[str] = field(default_factory=list)
    confidence: str = "low"


def lead_artist(artist: str) -> str:
    """Return the first listed artist, e.g. 'Romeo Santos & Daddy Yankee' -> 'romeo santos'."""
    return str(artist).split("&")[0].strip().casefold()


class PickChecker:
    """Self-check that runs on the recommendations before they are shown."""

    def __init__(self, songs: Iterable[Dict], max_per_artist: int = MAX_SONGS_PER_ARTIST):
        self.songs_by_id = {int(song["id"]): song for song in songs}
        self.max_per_artist = max_per_artist

    def check(self, picks: List[Pick]) -> CheckResult:
        problems: List[str] = []

        if not picks:
            return CheckResult(ok=False, problems=["no recommendations to check"])

        # 1. No made-up songs: each pick must match a real catalog entry.
        for song, _score, _explanation in picks:
            song_id = song.get("id")
            real = self.songs_by_id.get(song_id) if isinstance(song_id, int) else None
            if real is None or real["title"] != song.get("title"):
                problems.append(f"not in catalog: {song.get('title')!r} (id {song_id!r})")

        # 2. No duplicates.
        ids = [song.get("id") for song, _score, _explanation in picks]
        duplicates = sorted({i for i in ids if ids.count(i) > 1}, key=str)
        if duplicates:
            problems.append(f"duplicate songs: ids {duplicates}")

        # 3. Variety: no lead artist more than max_per_artist times.
        counts: Dict[str, int] = {}
        for song, _score, _explanation in picks:
            name = lead_artist(song.get("artist", ""))
            counts[name] = counts.get(name, 0) + 1
        for name, count in counts.items():
            if count > self.max_per_artist:
                problems.append(
                    f"too repetitive: {count} songs by {name} (max {self.max_per_artist})"
                )

        top_score = max(score for _song, score, _explanation in picks)
        if top_score >= HIGH_CONFIDENCE_SCORE:
            confidence = "high"
        elif top_score >= MEDIUM_CONFIDENCE_SCORE:
            confidence = "medium"
        else:
            confidence = "low"

        return CheckResult(ok=not problems, problems=problems, confidence=confidence)
