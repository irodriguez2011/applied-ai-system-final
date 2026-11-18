# Changelog

How VibeMatch grew from the Module 3 recommender (1.0) into the Project 4 applied AI system (2.0). Newest first.

## [Unreleased]: VibeMatch 2.0 (Project 4)

### 2026-11-18: Final docs
- Redrew `diagrams/architecture.mmd` to match the agent as built, embedded it in the README, and added a rendered image, `diagrams/architecture.png`.
- Rewrote `README.md`: summary, how the agent works, scoring, setup with `.env`, run commands, 3 real sample runs, baseline comparison, a guardrail input → behavior → result table, the evaluation, and limitations. Removed starter text and claims that weren't true (an outdated expected-results table, a tie-break rule the code never had, and `Recommender.recommend()` using the scoring code).
- `model_card.md` now covers 2.0 and adds sections 10–13: limitations and biases, possible misuse and prevention, surprises during reliability testing, and AI collaboration.
- Added `diagrams/data_flow.mmd`, a simplified data-flow diagram (also in the README and `docs/design.md`), fixed to match the real code: Gemini chooses the songs, then the code checks them; the fallback also runs after 8 steps.
- README now covers everything the project instructions list: a summary of the original Module 3 project, an explanation of both diagrams, design decisions, a testing summary and a reflection.
- Added `assets/evidence/`: real outputs of agent runs, the baseline, a trace log, the test run and the evaluation, with a README saying which command made each.

### 2026-11-18: Evaluation
- Added `eval/run_eval.py`: runs the agent with real Gemini on 6 fixed requests and scripted answers, applies a fit rule to each, compares with the Module 3 baseline, and prints a pass/fail table and summary line (also saved to `eval/latest_results.md`). Waits 20 seconds between cases to stay under the free tier's 15 requests a minute.
- Results over three runs: 5/6 (rate limit), 5/6 (agent searched too much and ran out of steps), then 6/6 after a prompt fix. The baseline fit 1 of 6 requests.
- `prompts/agent_system.md`: tells the agent to rank the whole catalog instead of searching repeatedly. Steps per case dropped from up to 8 to 3–5.
- `load_dotenv(override=True)`: the project's `.env` now wins over a blank `GEMINI_API_KEY` already set in the terminal, which had made a real run fall back.
- Added the evaluation results, run history and a human evaluation table to `model_card.md`.
- Added `tests/test_eval.py` (4 tests). All 70 tests pass.

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

## [1.0]: VibeMatch 1.0 (Module 3), 2026-11-08
- Content-based recommender: mood (with mood clusters), genre and numeric-closeness scoring, rescaled to 0–100.
- Weight-shift experiment: genre 20 → 10, energy 20 → 40.
- CLI runner, model card, and starter tests.
