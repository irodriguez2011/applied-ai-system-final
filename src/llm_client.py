"""LLM clients: the one place the app talks to a language model.

Every client has one method, complete(system_prompt, user_prompt) -> str.
The agent only knows that method, so it works the same with any client:

- GeminiClient calls the real Gemini API.
- MockClient replays prepared replies, so tests and the evaluator run
  offline, for free, and give the same result every time.

When a call fails, the client raises LLMError with a short reason instead of
returning an empty string. The agent catches it, writes the reason to the
trace log, and falls back to the rule-based recommender. A clear reason makes
failures easy to explain; a silent empty string would hide them.

Run `python -m src.llm_client` to check the Gemini connection. It prints only
"works" or "doesn't work" and a reason. It never prints the API key.
"""

import os
from typing import Iterable, List, Optional, Tuple

DEFAULT_MODEL = "gemini-3.5-flash-lite"  # pinned: a "latest" alias can change behavior without warning
DEFAULT_TEMPERATURE = 0.2  # low: we want steady, repeatable tool choices
DEFAULT_TIMEOUT_SECONDS = 30
KEY_NAME = "GEMINI_API_KEY"
RETRY_ATTEMPTS = 3  # retry busy (503) or rate-limited (429) calls before giving up


class LLMError(Exception):
    """The model could not give a usable reply. The message says why."""


class LLMClient:
    """Interface: send a system prompt and a user prompt, get text back."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class MockClient(LLMClient):
    """Replays prepared replies in order. Raises LLMError once they run out.

    Running out on purpose is how tests check the fallback path.
    """

    def __init__(self, replies: Iterable[str] = ()):
        self._replies = list(replies)
        self.calls: List[Tuple[str, str]] = []  # every (system, user) prompt sent

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        if not self._replies:
            raise LLMError("mock client has no replies left")
        return self._replies.pop(0)


class GeminiClient(LLMClient):
    """Calls Gemini and asks for a JSON reply."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        api_key = (api_key if api_key is not None else os.getenv(KEY_NAME, "")).strip()
        if not api_key or api_key == "your_api_key_here":
            raise LLMError(f"{KEY_NAME} is not set. Copy .env.example to .env and add your key.")

        # Imported here so tests and --baseline runs don't need the package loaded.
        from google import genai
        from google.genai import types

        self._types = types
        self._key = api_key  # kept only so error messages can be scrubbed of it
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=timeout_seconds * 1000,  # milliseconds
                retry_options=types.HttpRetryOptions(
                    attempts=RETRY_ATTEMPTS, initial_delay=1.0, http_status_codes=[429, 500, 503]
                ),
            ),
        )
        self.model_name = model_name
        self.temperature = float(temperature)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        config = self._types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self.temperature,
            response_mime_type="application/json",
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=config,
            )
            text = response.text  # can be None, for example when a safety filter blocks it
        except Exception as exc:
            raise LLMError(self._scrub(f"Gemini call failed: {type(exc).__name__}: {exc}")) from None

        if not text or not text.strip():
            raise LLMError("Gemini returned an empty reply")
        return text

    def _scrub(self, message: str) -> str:
        """Never let the API key reach a log or the screen."""
        return message.replace(self._key, "[hidden]") if self._key else message


def load_gemini_client(**kwargs) -> GeminiClient:
    """Load .env (if present) and build a GeminiClient. Raises LLMError if it can't."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass  # fine: the key can still come from the real environment
    return GeminiClient(**kwargs)


def check_connection() -> Tuple[bool, str]:
    """Send one tiny request. Returns (works, reason). Never includes the key."""
    try:
        client = load_gemini_client()
        client.complete('Reply with the JSON {"ok": true} and nothing else.', "ping")
    except LLMError as exc:
        return False, str(exc)
    return True, f"model {DEFAULT_MODEL} replied"


if __name__ == "__main__":
    works, reason = check_connection()
    status = "works" if works else "doesn't work"
    print(f"Gemini: {status} ({reason})")
