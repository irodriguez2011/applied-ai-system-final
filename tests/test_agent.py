"""Agent tests. MockClient plays the AI and ScriptedIO plays the listener,
so every run is offline, free and the same each time."""

import json

from src.agent import RecommenderAgent, parse_action
from src.catalog import SongCatalog
from src.llm_client import MockClient
from src.tools import Toolbox
from src.trace import TraceLogger
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


def tool(name, **args):
    return json.dumps({"thought": f"call {name}", "tool": name, "args": args})


def final(ids, message="Enjoy!"):
    return json.dumps({"thought": "done", "final": {"song_ids": ids, "message": message}})


def varied_top_ids(k=5):
    """The ids rank_songs will return, trimmed so no artist appears more than twice."""
    toolbox = Toolbox(CATALOG, ScriptedIO())
    ranked = toolbox.run("rank_songs", {"profile": PROFILE, "k": 20}).data["ranked"]
    ids, per_artist = [], {}
    for song in ranked:
        artist = song["artist"].split("&")[0].strip().casefold()
        if per_artist.get(artist, 0) < 2:
            ids.append(song["id"])
            per_artist[artist] = per_artist.get(artist, 0) + 1
    return ids[:k]


def make_agent(replies, answers=(), log_dir=None, max_steps=8):
    io = ScriptedIO(answers)
    llm = MockClient(replies)
    agent = RecommenderAgent(llm, Toolbox(CATALOG, io), TraceLogger(log_dir), max_steps=max_steps)
    return agent, llm, io


# --- parse_action -------------------------------------------------------


def test_parse_accepts_a_tool_call_and_code_fences():
    action, problem = parse_action('```json\n{"tool": "search_songs", "args": {"genre": "r&b"}}\n```')
    assert problem == "" and action["tool"] == "search_songs"


def test_parse_rejects_plain_text():
    action, problem = parse_action("Sure! Here are some songs you might like.")
    assert action is None and "JSON" in problem


# --- Happy path ---------------------------------------------------------


def test_full_loop_ask_rank_check_answer():
    ids = varied_top_ids()
    agent, llm, io = make_agent(
        [
            tool("ask_user", question="Any favorite genre?"),
            tool("rank_songs", profile=PROFILE, k=10),
            tool("check_picks", song_ids=ids),
            final(ids, "Smooth r&b for your night."),
        ],
        answers=["r&b, something chill"],
    )
    result = agent.run("something chill")

    assert not result.used_fallback
    assert [song["id"] for song, _s, _e in result.picks] == ids
    assert result.confidence in {"high", "medium", "low"}
    assert result.message == "Smooth r&b for your night."
    assert io.questions == ["Any favorite genre?"]
    assert result.steps == 4
    # The listener's answer reached the AI on the next step.
    assert "r&b, something chill" in llm.calls[1][1]


def test_scores_and_reasons_come_from_code_not_the_ai():
    ids = varied_top_ids()
    agent, _, _ = make_agent([tool("rank_songs", profile=PROFILE), final(ids)])
    result = agent.run("chill r&b")
    song, score, reasons = result.picks[0]
    assert score > 0 and "energy closeness" in reasons


# --- Recovering from mistakes -------------------------------------------


def test_bad_json_is_reported_back_and_the_agent_recovers():
    ids = varied_top_ids()
    agent, llm, _ = make_agent(["here you go!", tool("rank_songs", profile=PROFILE), final(ids)])
    result = agent.run("chill r&b")
    assert not result.used_fallback
    assert "not a JSON object" in llm.calls[1][1]
    assert agent.trace.of_type("bad_reply")


def test_unknown_tool_error_goes_back_to_the_ai():
    ids = varied_top_ids()
    agent, llm, _ = make_agent(
        [tool("play_song", id=1), tool("rank_songs", profile=PROFILE), final(ids)]
    )
    result = agent.run("chill r&b")
    assert not result.used_fallback
    assert "unknown tool" in llm.calls[1][1]


def test_invented_song_fails_the_self_check_and_the_agent_revises():
    ids = varied_top_ids()
    agent, llm, _ = make_agent(
        [tool("rank_songs", profile=PROFILE), final(ids[:4] + [999]), final(ids)]
    )
    result = agent.run("chill r&b")
    assert not result.used_fallback
    assert 999 not in [song["id"] for song, _s, _e in result.picks]
    assert "self-check failed" in llm.calls[2][1]
    assert agent.trace.of_type("self_check_failed")


def test_final_before_ranking_is_rejected():
    ids = varied_top_ids()
    agent, llm, _ = make_agent([final(ids), tool("rank_songs", profile=PROFILE), final(ids)])
    result = agent.run("chill r&b")
    assert not result.used_fallback
    assert "rank_songs" in llm.calls[1][1]


# --- Fallback -----------------------------------------------------------


def test_ai_failure_falls_back_to_the_rule_based_recommender():
    agent, _, _ = make_agent([])  # the mock has no replies: like Gemini being down
    result = agent.run("chill r&b")
    assert result.used_fallback
    assert "AI unavailable" in result.fallback_reason
    assert len(result.picks) == 5
    assert agent.trace.of_type("fallback")


def test_step_limit_falls_back_and_keeps_the_agents_profile():
    agent, _, _ = make_agent(
        [tool("rank_songs", profile=PROFILE)] + [tool("search_songs", genre="r&b")] * 5,
        max_steps=3,
    )
    result = agent.run("chill r&b")
    assert result.used_fallback
    assert "step limit" in result.fallback_reason
    assert result.steps == 3
    assert agent.trace.of_type("fallback")[0]["used_agent_profile"]


# --- Trace log ----------------------------------------------------------


def test_trace_file_records_every_step(tmp_path):
    ids = varied_top_ids()
    agent, _, _ = make_agent(
        [tool("rank_songs", profile=PROFILE), final(ids)], log_dir=str(tmp_path)
    )
    result = agent.run("chill r&b")
    lines = [json.loads(line) for line in open(result.trace_path, encoding="utf-8")]
    events = [line["event"] for line in lines]
    assert events[0] == "start" and events[-1] == "final"
    assert "tool_call" in events and "tool_result" in events
