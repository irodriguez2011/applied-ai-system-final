# Changelog

How VibeMatch grew from the Module 3 recommender (1.0) into the Project 4 applied AI system (2.0). Newest first.

## [Unreleased]: VibeMatch 2.0 (Project 4)

### 2026-11-18: Agent is the default in main.py
- `python -m src.main` now asks what you're in the mood for and runs the agent. `--request "..."` skips that first question.
- `python -m src.main --baseline` runs the original Module 3 recommender with its fixed lofi profile, for side-by-side comparison.
- Output now shows the agent's message, confidence, number of steps, and the path to the step-by-step log. A fallback run says so and gives the reason.
- Added `UnavailableClient`: if Gemini can't be set up (for example, no key), the agent falls back instead of crashing.
- Added `tests/test_main.py` (4 tests). All 66 tests pass.

### 2026-11-18: Agent and trace log
- Added `src/agent.py` with `RecommenderAgent`. Each step, Gemini picks one action (a tool call or a final answer) as JSON.
  - A final answer is accepted only if `check_picks` passes on those exact ids; otherwise the problems go back to Gemini to revise.
  - Bad JSON or a bad tool call uses a step but doesn't crash; the error goes back to Gemini.
  - At most 8 steps. If Gemini fails or runs out of steps, the Module 3 recommender answers instead, using the agent's profile if it built one.
- Added `prompts/agent_system.md`, the agent's instructions, with the tools, genres and moods filled in from code.
- Added `src/trace.py`: every step is written as JSON Lines to `logs/`.
- `GeminiClient` now retries busy (503) or rate-limited (429) calls up to 3 times, after a live run hit a 503.
- Added `tests/test_agent.py` (11 tests). All 62 tests pass.
- First live runs: "dance at a party" finished in 5 steps with high confidence; "recommend me some music" asked one question, then finished in 5 steps.

### 2026-11-18: LLM client
- Added `src/llm_client.py`:
  - `GeminiClient` calls `gemini-3.5-flash-lite` (a pinned version, since the `latest` alias was not available and can change without warning), asks for a JSON reply, uses a low temperature (0.2) and a 30-second timeout.
  - `MockClient` replays prepared replies, so tests run offline and free.
  - Any failure (no key, network error, empty reply) raises `LLMError` with a reason. Module 5's BugHound returned an empty string instead, which hid why it failed.
  - Error messages never contain the API key.
  - `python -m src.llm_client` checks the connection and prints only "works" or "doesn't work".
- Added `tests/test_llm_client.py` (8 tests, no network). All 51 tests pass.

### 2026-11-18: Toolbox and user I/O
- Added `src/user_io.py`: `ConsoleIO` asks a real person; `ScriptedIO` replays fixed answers for tests.
- Added `src/tools.py`: the `Toolbox` runs the agent's 4 tools (`ask_user`, `search_songs`, `rank_songs`, `check_picks`).
  - Unknown tools and bad arguments are refused with a clear error instead of crashing.
  - At most 3 questions per run.
  - `rank_songs` runs `ProfileValidator` first; scores and reasons always come from `score_song`, never from the AI.
  - `check_picks` runs `PickChecker` on the final song ids.
- Added `tests/test_tools.py` (18 tests). All 43 tests pass.
- Added a spec parts 4–5 map to `docs/design.md`.

### 2026-11-18: Song catalog split
- Added `src/models.py` for shared data shapes and mood clusters.
- Added `src/catalog.py` with `SongCatalog`: load `songs.csv`, look up a song by id, and search by genre, mood or energy range.
- `src/recommender.py` now only scores and ranks. Old imports still work.
- Added `tests/test_catalog.py`. All 25 tests pass.

### 2026-11-18: Guardrails
- Added `src/guardrails.py`:
  - `ProfileValidator` checks a taste profile before ranking: required keys, 0–1 ranges, tempo 40–220 BPM. Unknown genres and moods are warnings.
  - `PickChecker` checks the picks after ranking: songs must exist in the catalog, no duplicates, at most 2 songs per lead artist. It also reports a confidence level.
- Added `tests/test_guardrails.py` (14 tests).

### 2026-11-17: Setup and design
- Added `requirements.txt` (`google-genai`, `python-dotenv`, `pytest`), `.env.example`, and `.gitignore` rules for `.env` and `logs/`.
- Added `docs/design.md`: the agent design, components, GRASP and SOLID tables, and data flow.
- Added `diagrams/architecture.mmd` (Mermaid) showing the system as it is built today.

### 2026-11-17: New catalog
- Rebuilt `data/songs.csv` with 47 songs: 37 real songs (hip-hop, R&B, reggaeton, afrobeats, bachata) and 10 made-up contrast songs.
- Updated the README and model card numbers to match the new catalog.

### Planned
- `eval/run_eval.py`

## [1.0]: VibeMatch 1.0 (Module 3), 2026-11-08
- Content-based recommender: mood (with mood clusters), genre and numeric-closeness scoring, rescaled to 0–100.
- Weight-shift experiment: genre 20 → 10, energy 20 → 40.
- CLI runner, model card, and starter tests.
