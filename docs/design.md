# VibeMatch 2.0: System Design

**Status:** in progress. Parts marked *Existing* or **Built** exist in code; the rest are planned. `diagrams/architecture.mmd` shows only what is built, and is updated as each part ships.

**Base project:** VibeMatch 1.0, the Module 3 Music Recommender Simulation. It scores every song in `data/songs.csv` against a fixed taste profile and prints the top 5 with reasons.

**What 2.0 adds:** a multi-step AI agent that plans its own steps (ask about your taste, search songs, rank them, check its own picks), plus a reliability layer (guardrails, fallback, logging, and an evaluation script).

---

## 1. Integration rule

The project requires the AI feature to be part of the main application and to change how the system behaves. It cannot be a standalone script or AI text printed next to the old answer. This design meets that rule as follows:

- `python -m src.main` runs the **agent by default**. The old rule-based recommender runs only as a **fallback** (AI unavailable) or with `--baseline` for comparison.
- The agent's decisions **change the results**: the profile it builds decides which songs are ranked, a follow-up question can change the profile, and a failed self-check makes it re-rank.
- Explanations come from the **real scoring reasons** returned by `score_song`, not from text the LLM makes up.

## 2. Components

| # | Component | File | Job | Status |
|---|---|---|---|---|
| 1 | `Song`, `UserProfile` | `src/models.py` | Hold song and listener data, plus the shared mood clusters | **Built** (Nov 18, moved out of `recommender.py`) |
| 2 | `SongCatalog` | `src/catalog.py` | Load `songs.csv`, search songs, look up a song by id | **Built** (Nov 18) |
| 3 | `Scorer` | `src/recommender.py` | Score one song against a profile, with reasons | Existing `score_song` |
| 4 | `Recommender` | `src/recommender.py` | Rank candidates, return the top *k* | Existing `recommend_songs` |
| 5 | `ProfileValidator` | `src/guardrails.py` | Check the profile: values in 0–1, sensible BPM, known genres and moods | **Built** (Nov 18) |
| 6 | `PickChecker` | `src/guardrails.py` | Self-check picks: songs exist, enough variety, confidence level | **Built** (Nov 18) |
| 7 | `LLMClient` → `GeminiClient`, `MockClient` | `src/llm_client.py` | Talk to the AI, or a fake AI for tests | New |
| 8 | `Toolbox` | `src/tools.py` | List the tools the agent may call and run them | New |
| 9 | `RecommenderAgent` | `src/agent.py` | Run the loop: plan → ask → search → rank → check → revise | New (AI feature) |
| 10 | `UserIO` → `ConsoleIO`, `ScriptedIO` | `src/user_io.py` | Ask the human questions, live or scripted for tests | New (human-in-the-loop) |
| 11 | `TraceLogger` | `src/trace.py` | Record every step to a log file | New (logging) |
| 12 | Evaluator | `eval/run_eval.py` | Run fixed requests, print a pass/fail summary | New (testing) |
| 13 | CLI | `src/main.py` | Build the objects and start a run | Existing, to update |

### Agent tools

| Tool | What it does | Built from |
|---|---|---|
| `ask_user(question)` | Asks the user a follow-up question | `UserIO` |
| `search_songs(filters)` | Finds candidate songs by genre, mood or energy range | `SongCatalog` |
| `rank_songs(profile)` | Scores and ranks songs with reasons | `Recommender` + `Scorer` |
| `check_picks(song_ids, profile)` | Checks the picks before output | `PickChecker` |

## 3. GRASP principles

| Principle | Meaning | Where it is applied |
|---|---|---|
| Information Expert | Give a job to whoever has the data | `SongCatalog` answers "does this song exist?"; `Scorer` owns the weights and computes scores |
| Creator | Whoever owns or uses objects creates them | `SongCatalog` creates `Song` objects; `main.py` creates the agent and its parts |
| Controller | One class receives requests and coordinates | `RecommenderAgent` directs the work but never scores or searches itself |
| Low Coupling | Parts depend on each other as little as possible | The agent reaches code only through `Toolbox`; swapping the AI provider changes one file |
| High Cohesion | Each class does one focused job | Validation, checking, logging and scoring each live in their own class |
| Polymorphism | Same interface, different behavior | `GeminiClient` / `MockClient` and `ConsoleIO` / `ScriptedIO` are interchangeable |
| Pure Fabrication | Helper classes that are not real-world objects | `Toolbox`, `TraceLogger`, `ProfileValidator`, `PickChecker` |
| Indirection | A middleman between two parts | `Toolbox` sits between the LLM and Python functions; the LLM asks by name, the Toolbox decides |
| Protected Variations | Shield the system from parts likely to change or fail | `LLMClient` hides the AI provider; the fallback keeps the app working if the AI is down |

## 3b. SOLID principles

GRASP decides which class owns each job; SOLID keeps those classes easy to change and test. The AI (Gemini) is one component behind an interface, so the same rules apply.

| Principle | Meaning | Where it is applied | Status |
|---|---|---|---|
| Single Responsibility | Each class has one reason to change | `ProfileValidator` and `PickChecker` each do one job. Step 2 split `recommender.py`: data shapes and mood clusters in `models.py`, loading and search in `catalog.py`, and only scoring and ranking left in `recommender.py` | **Built** |
| Open/Closed | Add features without editing working code | New agent tools are registered in `Toolbox` without changing the agent; weights and mood clusters are named constants | Planned |
| Liskov Substitution | A subclass can replace its parent safely | `MockClient` and `GeminiClient` both return text (empty text on failure), so the agent behaves the same with either | Planned |
| Interface Segregation | Small, focused interfaces | `LLMClient` has one method (`complete`); `UserIO` has one (`ask`) | Planned |
| Dependency Inversion | Depend on abstractions; pass dependencies in | `ProfileValidator` receives the genre list and `PickChecker` receives the songs. The agent will receive its LLM client, catalog and user I/O, so tests can pass a mock | Partly built |

## 4. Data flow

Main path, top to bottom: request → agent → toolbox → validator → rank → self-check → output. Dotted lines are side paths: going back to the agent, the fallback, and testing. Every tool result returns to the agent, which plans the next step.

```mermaid
flowchart TD
    U(["User request<br/>'chill r&b for studying'"]) --> AG
    subgraph AGENT["RecommenderAgent (Controller)"]
        AG["Plan next step<br/>LLM: Gemini or Mock"] -- "tool call" --> TB["Toolbox<br/>results go back to the agent"]
    end
    TB --> ASK["ask_user"]
    ASK <--> H(["Human answers"])
    TB --> SEARCH["search_songs<br/>SongCatalog"]
    TB --> V{"ProfileValidator<br/>guardrail"}
    V -- valid --> RANK["rank_songs<br/>Recommender + Scorer"]
    V -. invalid .-> AG
    RANK --> C{"check_picks<br/>PickChecker"}
    C -. "fails: retry" .-> AG
    C -- passes --> O(["Top 5 + reasons + confidence"])
    AG -. "AI unavailable" .-> F["Fallback:<br/>rule-based recommender"]
    F --> O
    AG --> LOG[("Trace log")]
    EV["pytest + Evaluator<br/>MockClient, ScriptedIO"] -. tests .-> AGENT
```

## 5. Where humans and testing check the AI

| Checkpoint | Type | What it checks |
|---|---|---|
| `ask_user` | Human | The user confirms their taste before ranking |
| `ProfileValidator` | Guardrail | The AI built a valid profile |
| `PickChecker` | Self-check | Picks are real songs, varied, and confident enough |
| Trace log | Human review | Every decision can be read afterward |
| pytest + `MockClient` | Testing | Tools and guardrails work, with no API calls |
| Evaluator | Testing | The full agent on fixed requests, with a pass/fail summary |

## 6. Limits on the agent

- About 8 steps and 3 questions per run.
- Every recommended song must exist in `songs.csv`.
- If the LLM is unavailable (no key, network error, rate limit), the app runs the rule-based recommender and says so.

## 7. Evidence that the feature changes behavior

The README will show the same request run with `--baseline` and with the agent, side by side. The outputs should differ because the agent builds the profile from the conversation and can re-rank after its self-check.
