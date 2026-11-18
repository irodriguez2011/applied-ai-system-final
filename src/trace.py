"""TraceLogger: a step-by-step record of what the agent did and why.

Each event is one JSON object per line (JSON Lines) in logs/, for example:

    {"step": 2, "event": "tool_call", "tool": "search_songs", "args": {...}}

The trace answers "why did it recommend that?" after the fact: what the model
decided, which tool ran, what came back, what failed, and whether the app fell
back to the rule-based recommender. Logs stay on this machine (logs/ is in
.gitignore) and never contain the API key, because the LLM client scrubs it
from its error messages before they reach the agent.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG_DIR = "logs"
MAX_TEXT = 2000  # long values are cut so one run's log stays readable


def _short(value: Any) -> Any:
    """Cut long strings so a single event can't flood the log."""
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return value[:MAX_TEXT] + f"... [{len(value) - MAX_TEXT} more characters]"
    return value


class TraceLogger:
    """Collects events in memory and, if given a folder, writes them to a file."""

    def __init__(self, log_dir: Optional[str] = LOG_DIR):
        self.events: List[Dict] = []
        self.path: Optional[Path] = None
        if log_dir is not None:
            folder = Path(log_dir)
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            self.path = folder / f"run-{stamp}.jsonl"

    def log(self, event: str, step: int = 0, **details: Any) -> Dict:
        entry = {"time": datetime.now().isoformat(timespec="seconds"), "step": step, "event": event}
        entry.update({key: _short(value) for key, value in details.items()})
        self.events.append(entry)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, default=str) + "\n")
        return entry

    def of_type(self, event: str) -> List[Dict]:
        """All events with this name, for tests and the evaluator."""
        return [entry for entry in self.events if entry["event"] == event]
