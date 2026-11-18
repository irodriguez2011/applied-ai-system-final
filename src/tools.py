"""Toolbox: the only way the AI agent can act on the system.

The LLM never runs code or touches data directly. It asks for a tool by name
with arguments, and the Toolbox decides whether the request is allowed, runs
plain Python, and returns a ToolResult. This is the trust boundary:

- Only the four tools in TOOL_SPECS exist. Any other name is refused.
- Arguments are checked before anything runs.
- Scores and reasons always come from score_song, never from the LLM.
- No tool ever raises. Failures come back as ok=False with an error message,
  so the agent can read what went wrong and try again, and the trace log can
  record it.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.catalog import SongCatalog
from src.guardrails import PickChecker, ProfileValidator
from src.recommender import recommend_songs, score_song
from src.user_io import UserIO

# Limits that keep a run short, cheap and predictable.
MAX_QUESTIONS = 3
DEFAULT_RANK_K = 10
MAX_RANK_K = 20

# Tool descriptions the agent's prompt will show to the LLM.
TOOL_SPECS = {
    "ask_user": {
        "description": "Ask the listener one short follow-up question about their taste.",
        "args": {"question": "text"},
    },
    "search_songs": {
        "description": "Find songs by genre, mood (similar moods included) and energy range. Every filter is optional.",
        "args": {
            "genre": "text, optional",
            "mood": "text, optional",
            "min_energy": "number 0-1, optional",
            "max_energy": "number 0-1, optional",
        },
    },
    "rank_songs": {
        "description": "Score songs against a full taste profile and return the best matches with reasons.",
        "args": {
            "profile": "favorite_genre, favorite_mood, target_energy, target_tempo, "
            "target_valence, target_danceability, target_acousticness",
            "song_ids": "list of ids to rank, optional (default: whole catalog)",
            "k": f"how many to return, optional (default {DEFAULT_RANK_K})",
        },
    },
    "check_picks": {
        "description": "Self-check the final song ids before showing them: real songs, no repeats, variety, confidence.",
        "args": {"song_ids": "list of ids"},
    },
}


@dataclass
class ToolResult:
    """What a tool hands back to the agent.

    ok:    True when the tool did its job.
    data:  the result (JSON-friendly) when ok.
    error: why it failed, written so the agent can fix its request.
    """

    ok: bool
    data: Any = None
    error: str = ""

    def to_dict(self) -> Dict:
        return {"ok": self.ok, "data": self.data, "error": self.error}


def song_summary(song: Dict) -> Dict:
    """The fields the agent needs to reason about a song."""
    return {
        "id": song["id"],
        "title": song["title"],
        "artist": song["artist"],
        "genre": song["genre"],
        "mood": song["mood"],
        "energy": song["energy"],
    }


@dataclass
class _RankState:
    """What the last rank_songs call produced, so check_picks can use real scores."""

    profile: Dict = field(default_factory=dict)
    picks_by_id: Dict[int, tuple] = field(default_factory=dict)


class Toolbox:
    """Runs the agent's tool requests safely."""

    def __init__(
        self,
        catalog: SongCatalog,
        user_io: UserIO,
        validator: Optional[ProfileValidator] = None,
        checker: Optional[PickChecker] = None,
        max_questions: int = MAX_QUESTIONS,
    ):
        self.catalog = catalog
        self.user_io = user_io
        self.validator = validator or ProfileValidator(catalog.genres())
        self.checker = checker or PickChecker(catalog.all())
        self.max_questions = max_questions
        self.questions_asked = 0
        self.last_check = None  # the most recent CheckResult, for the final output
        self.last_checked_picks: List[tuple] = []  # the (song, score, reasons) it checked
        self._rank = _RankState()
        self._tools: Dict[str, Callable[..., ToolResult]] = {
            "ask_user": self.ask_user,
            "search_songs": self.search_songs,
            "rank_songs": self.rank_songs,
            "check_picks": self.check_picks,
        }

    @property
    def last_profile(self) -> Dict:
        """The validated profile from the last successful rank_songs call ({} if none)."""
        return dict(self._rank.profile)

    # --- Entry point -----------------------------------------------------

    def run(self, name: str, args: Optional[Dict] = None) -> ToolResult:
        """Run a tool by name. Never raises: every failure becomes ok=False."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(False, error=f"unknown tool '{name}'. Allowed: {', '.join(self._tools)}")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return ToolResult(False, error="tool arguments must be an object")
        try:
            return tool(**args)
        except TypeError as exc:
            return ToolResult(False, error=f"bad arguments for {name}: {exc}")
        except Exception as exc:  # last line of defense: report, don't crash
            return ToolResult(False, error=f"{name} failed: {type(exc).__name__}: {exc}")

    # --- Tools -----------------------------------------------------------

    def ask_user(self, question: str = "") -> ToolResult:
        question = str(question).strip()
        if not question:
            return ToolResult(False, error="question is empty")
        if self.questions_asked >= self.max_questions:
            return ToolResult(
                False,
                error=f"question limit reached ({self.max_questions}); rank with what you know",
            )
        self.questions_asked += 1
        answer = self.user_io.ask(question).strip()
        return ToolResult(True, data={"answer": answer or "(no answer)"})

    def search_songs(
        self,
        genre: Optional[str] = None,
        mood: Optional[str] = None,
        min_energy: Optional[float] = None,
        max_energy: Optional[float] = None,
    ) -> ToolResult:
        for name, value in (("min_energy", min_energy), ("max_energy", max_energy)):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                return ToolResult(False, error=f"{name} must be a number from 0 to 1, got {value!r}")
        if min_energy is not None and max_energy is not None and min_energy > max_energy:
            return ToolResult(False, error="min_energy is larger than max_energy")

        songs = self.catalog.search(genre=genre, mood=mood, min_energy=min_energy, max_energy=max_energy)
        data = {"count": len(songs), "songs": [song_summary(s) for s in songs]}
        if not songs:
            data["hint"] = f"no matches; known genres: {', '.join(self.catalog.genres())}"
        return ToolResult(True, data=data)

    def rank_songs(
        self,
        profile: Optional[Dict] = None,
        song_ids: Optional[List[int]] = None,
        k: int = DEFAULT_RANK_K,
    ) -> ToolResult:
        validation = self.validator.validate(profile)
        if not validation.ok:
            return ToolResult(False, error="invalid profile: " + "; ".join(validation.errors))

        if song_ids is None:
            candidates = self.catalog.all()
        else:
            if not isinstance(song_ids, list) or not song_ids:
                return ToolResult(False, error="song_ids must be a non-empty list")
            unknown = [i for i in song_ids if self.catalog.get_by_id(i) is None]
            if unknown:
                return ToolResult(False, error=f"unknown song ids: {unknown}")
            candidates = [self.catalog.get_by_id(i) for i in dict.fromkeys(song_ids)]

        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= MAX_RANK_K:
            return ToolResult(False, error=f"k must be a whole number from 1 to {MAX_RANK_K}")

        picks = recommend_songs(validation.profile, candidates, k=k)
        self._rank = _RankState(validation.profile, {pick[0]["id"]: pick for pick in picks})

        ranked = [
            dict(song_summary(song), score=round(score, 2), reasons=explanation)
            for song, score, explanation in picks
        ]
        return ToolResult(True, data={"ranked": ranked, "warnings": validation.warnings})

    def check_picks(self, song_ids: Optional[List[int]] = None) -> ToolResult:
        if not isinstance(song_ids, list) or not song_ids:
            return ToolResult(False, error="song_ids must be a non-empty list")
        if not self._rank.profile:
            return ToolResult(False, error="call rank_songs before check_picks")

        picks = []
        for song_id in song_ids:
            if song_id in self._rank.picks_by_id:
                picks.append(self._rank.picks_by_id[song_id])
                continue
            song = self.catalog.get_by_id(song_id) if isinstance(song_id, int) else None
            if song is None:
                # Not a real song: pass it on so PickChecker reports it.
                picks.append(({"id": song_id, "title": None, "artist": ""}, 0.0, ""))
                continue
            # Real song the agent picked without ranking it: score it now, in code.
            score, reasons = score_song(self._rank.profile, song)
            picks.append((song, score, "; ".join(reasons)))

        result = self.checker.check(picks)
        self.last_check = result
        self.last_checked_picks = picks
        return ToolResult(
            True,
            data={"passed": result.ok, "problems": result.problems, "confidence": result.confidence},
        )
