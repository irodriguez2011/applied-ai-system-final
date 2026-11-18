"""RecommenderAgent: the multi-step AI agent.

Each step, the LLM reads the request and everything that has happened so far,
then picks ONE action: call a tool, or give a final answer. The loop is:

    ask the user -> search songs -> rank songs -> check picks -> revise -> answer

Reliability rules the code enforces (not the LLM):

- Only Toolbox tools can run. Scores and reasons come from score_song.
- A final answer is accepted only if check_picks passes on those exact ids.
  If it fails, the problems go back to the LLM and it must revise.
- At most MAX_STEPS LLM replies. Bad JSON or a bad tool call uses up a step
  but does not crash the run; the error goes back to the LLM.
- If the LLM fails (no key, network, rate limit) or runs out of steps, the
  rule-based recommender from Module 3 answers instead, and the result says so.
- Every step goes to the TraceLogger.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.guardrails import Pick
from src.llm_client import LLMClient, LLMError
from src.recommender import recommend_songs
from src.tools import TOOL_SPECS, Toolbox
from src.trace import TraceLogger

MAX_STEPS = 8
NUM_PICKS = 5
MAX_RESULT_CHARS = 6000  # how much of each tool result the LLM sees again
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "agent_system.md"

# Used by the fallback only when the agent never built a valid profile.
DEFAULT_PROFILE = {
    "favorite_genre": "pop",
    "favorite_mood": "happy",
    "target_energy": 0.6,
    "target_tempo": 105,
    "target_valence": 0.65,
    "target_danceability": 0.65,
    "target_acousticness": 0.3,
}


@dataclass
class AgentResult:
    """What the app shows the listener."""

    picks: List[Pick]
    confidence: str
    message: str
    used_fallback: bool = False
    fallback_reason: str = ""
    steps: int = 0
    problems: List[str] = field(default_factory=list)
    trace_path: Optional[str] = None


def parse_action(text: str) -> Tuple[Optional[Dict], str]:
    """Turn the LLM's reply into an action dict. Returns (action, problem)."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        action = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        try:
            action = json.loads(text[start : end + 1]) if start != -1 else None
        except json.JSONDecodeError:
            action = None
    if not isinstance(action, dict):
        return None, "reply was not a JSON object"
    if "final" in action:
        final = action["final"]
        if not isinstance(final, dict) or not isinstance(final.get("song_ids"), list):
            return None, "final must be an object with a song_ids list"
        return action, ""
    if not isinstance(action.get("tool"), str):
        return None, "reply needs either a 'tool' name or a 'final' answer"
    if not isinstance(action.get("args", {}), dict):
        return None, "args must be an object"
    return action, ""


class RecommenderAgent:
    def __init__(
        self,
        llm: LLMClient,
        toolbox: Toolbox,
        trace: Optional[TraceLogger] = None,
        max_steps: int = MAX_STEPS,
    ):
        self.llm = llm
        self.toolbox = toolbox
        self.trace = trace or TraceLogger(log_dir=None)
        self.max_steps = max_steps
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        tools = "\n".join(
            f"- `{name}`: {spec['description']} Args: {json.dumps(spec['args'])}"
            for name, spec in TOOL_SPECS.items()
        )
        return PROMPT_PATH.read_text(encoding="utf-8").format(
            tools=tools,
            genres=", ".join(self.toolbox.catalog.genres()),
            moods=", ".join(self.toolbox.catalog.moods()),
            max_steps=self.max_steps,
            max_questions=self.toolbox.max_questions,
        )

    # --- The loop --------------------------------------------------------

    def run(self, request: str) -> AgentResult:
        self.trace.log("start", request=request, max_steps=self.max_steps)
        history: List[Dict] = []

        for step in range(1, self.max_steps + 1):
            prompt = self._user_prompt(request, history, step)
            try:
                reply = self.llm.complete(self.system_prompt, prompt)
            except LLMError as exc:
                return self._fallback(f"AI unavailable: {exc}", step - 1)
            self.trace.log("llm_reply", step, text=reply)

            action, problem = parse_action(reply)
            if problem:
                self.trace.log("bad_reply", step, problem=problem)
                history.append({"step": step, "error": problem})
                continue
            self.trace.log("thought", step, thought=action.get("thought", ""))

            if "final" in action:
                result, feedback = self._try_finish(action["final"], step)
                if result:
                    return result
                history.append({"step": step, "final_rejected": feedback})
                continue

            name, args = action["tool"], action.get("args", {})
            self.trace.log("tool_call", step, tool=name, args=args)
            outcome = self.toolbox.run(name, args)
            self.trace.log("tool_result", step, tool=name, ok=outcome.ok, error=outcome.error)
            history.append({"step": step, "tool": name, "args": args, "result": outcome.to_dict()})

        return self._fallback(f"step limit reached ({self.max_steps} steps)", self.max_steps)

    def _user_prompt(self, request: str, history: List[Dict], step: int) -> str:
        lines = [f"Listener's request: {request}", "", f"This is reply {step} of {self.max_steps}."]
        if history:
            lines += ["", "What has happened so far:"]
            for entry in history:
                text = json.dumps(entry, default=str)
                if len(text) > MAX_RESULT_CHARS:
                    text = text[:MAX_RESULT_CHARS] + " ...(cut)"
                lines.append(text)
        lines += ["", "Reply with one JSON object."]
        return "\n".join(lines)

    # --- Finishing -------------------------------------------------------

    def _try_finish(self, final: Dict, step: int) -> Tuple[Optional[AgentResult], str]:
        """Accept the final answer only if the code's self-check passes."""
        ids = final["song_ids"]
        if not 1 <= len(ids) <= NUM_PICKS:
            feedback = f"give between 1 and {NUM_PICKS} song ids, got {len(ids)}"
            self.trace.log("final_rejected", step, reason=feedback)
            return None, feedback

        check = self.toolbox.run("check_picks", {"song_ids": ids})
        if not check.ok:
            self.trace.log("final_rejected", step, reason=check.error)
            return None, check.error
        if not check.data["passed"]:
            feedback = "self-check failed: " + "; ".join(check.data["problems"]) + ". Fix and try again."
            self.trace.log("self_check_failed", step, problems=check.data["problems"])
            return None, feedback

        self.trace.log("final", step, song_ids=ids, confidence=check.data["confidence"])
        return (
            AgentResult(
                picks=list(self.toolbox.last_checked_picks),
                confidence=check.data["confidence"],
                message=str(final.get("message", "")).strip(),
                steps=step,
                trace_path=str(self.trace.path) if self.trace.path else None,
            ),
            "",
        )

    def _fallback(self, reason: str, steps: int) -> AgentResult:
        """Module 3's rule-based recommender answers when the agent can't."""
        profile = self.toolbox.last_profile or DEFAULT_PROFILE
        picks = recommend_songs(profile, self.toolbox.catalog.all(), k=NUM_PICKS)
        check = self.toolbox.checker.check(picks)
        self.trace.log(
            "fallback",
            steps,
            reason=reason,
            used_agent_profile=bool(self.toolbox.last_profile),
            song_ids=[song["id"] for song, _s, _e in picks],
        )
        return AgentResult(
            picks=picks,
            confidence=check.confidence,
            message="The AI agent couldn't finish, so these come from the rule-based recommender.",
            used_fallback=True,
            fallback_reason=reason,
            steps=steps,
            problems=check.problems,
            trace_path=str(self.trace.path) if self.trace.path else None,
        )
