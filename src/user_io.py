"""UserIO: how the agent talks to the human (human-in-the-loop).

ConsoleIO asks a real person at the keyboard. ScriptedIO replays fixed answers,
so tests and the evaluator can run the agent with no one typing.
Both have the same one-method interface, so the agent works with either.
"""

from typing import Iterable, List


class UserIO:
    """Interface: ask the user a question and return their answer as text."""

    def ask(self, question: str) -> str:
        raise NotImplementedError


class ConsoleIO(UserIO):
    """Asks a real person in the terminal."""

    def ask(self, question: str) -> str:
        try:
            return input(f"\n{question}\n> ").strip()
        except EOFError:
            # Input was closed (for example, piped input ran out): treat as no answer.
            return ""


class ScriptedIO(UserIO):
    """Replays prepared answers in order. Returns "" once they run out."""

    def __init__(self, answers: Iterable[str] = ()):
        self._answers = list(answers)
        self.questions: List[str] = []  # every question asked, for tests to inspect

    def ask(self, question: str) -> str:
        self.questions.append(question)
        if self._answers:
            return self._answers.pop(0)
        return ""
