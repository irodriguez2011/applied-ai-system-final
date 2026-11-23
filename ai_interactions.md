# AI Interactions: Agent Reasoning Traces

This file shows how the VibeMatch agent reasons, step by step, on real runs. It covers the **Agentic Workflow Enhancement** stretch feature: multi-step reasoning with tool calls, a plan, and a decision at each step, with the intermediate reasoning saved.

The interactions here are between **the agent (Gemini) and the system's tools**, not between me and a coding assistant. How I used AI while building the project is in [model_card.md](model_card.md), section 13 "AI Collaboration".

---

## How the traces are recorded

Every run writes a log file to `logs/run-<date>-<time>.jsonl`, one line per event. `TraceLogger` in `src/trace.py` writes it, and `RecommenderAgent` in `src/agent.py` calls it at every step.

| Event | What it records |
| --- | --- |
| `start` | The listener's request and the step limit (8) |
| `llm_reply` | Gemini's raw reply, exactly as it arrived |
| `thought` | Gemini's one-sentence reason for its next action |
| `tool_call` | Which tool Gemini chose and the arguments it sent |
| `tool_result` | Whether the tool worked (`ok`) and any error message |
| `bad_reply` | Gemini's reply wasn't valid JSON or named an unknown tool; the error goes back to Gemini |
| `self_check_failed` / `final_rejected` | The code re-checked Gemini's final picks and rejected them; the problems go back to Gemini |
| `final` | The 5 song ids and the confidence level |
| `fallback` | The agent couldn't finish, so the Module 3 recommender took over |

At each step Gemini can do only one of two things: call one of the 4 allowed tools (`ask_user`, `search_songs`, `rank_songs`, `check_picks`) or give a final answer. The code runs the tool and sends the result back, and Gemini decides the next step.

---

## Trace 1: A clear request

**Request:** "something chill to study to"
**Full log:** [assets/evidence/trace_log_example.jsonl](assets/evidence/trace_log_example.jsonl)

| Step | Gemini's thought (from the log) | Action | Result |
| --- | --- | --- | --- |
| 1 | "I will search for chill songs suitable for studying." | `search_songs` with mood `chill`, max energy 0.4 | ok |
| 2 | "Now I will rank the catalog using a chill and focused taste profile to get the best 5 study songs." | `rank_songs` with genre `lofi`, mood `focused`, energy 0.3, tempo 75, valence 0.5, danceability 0.4, acousticness 0.7 | ok |
| 3 | "I will check the top 5 ranked songs to ensure they form a valid selection without repeat artists." | `check_picks` on songs 44, 41, 39, 12, 6 | ok |
| 4 | "The picks have passed verification, so I can now present the final song recommendations." | Final answer | Accepted, confidence **high** |

**Final picks:** Focus Flow, Library Rain, Midnight Coding, Blue Dream, Enfant.

**What this shows:** the request was clear, so the agent didn't ask a question. Step 2 is where Gemini turned the words "chill to study to" into the 7 numbers the scoring code needs. The code did the scoring and checking; Gemini only chose the steps.

---

## Trace 2: Recovering from a bad reply

**Request:** "something to vibe to while cleaning"
**Full log:** [assets/evidence/trace_log_bad_json_recovery.jsonl](assets/evidence/trace_log_bad_json_recovery.jsonl)

| Step | Gemini's thought (from the log) | Action | Result |
| --- | --- | --- | --- |
| 1 | *(reply rejected)* | Gemini's reply had one extra `}` at the end, so it wasn't valid JSON | `bad_reply`: "reply was not a JSON object". The error was sent back to Gemini. |
| 2 | "Since cleaning requires an upbeat and engaging vibe, I will search for pop and hip-hop songs with an energetic and carefree mood to keep the momentum going." | `search_songs` with genre `pop`, mood `carefree`, min energy 0.6 | ok |
| 3 | "I will rank songs with a pop and carefree profile to get a good batch for cleaning." | `rank_songs` with genre `pop`, mood `carefree`, energy 0.8, tempo 120, valence 0.8, danceability 0.8, acousticness 0.2 | ok |
| 4 | "Now I will check the top 5 ranked songs to ensure they form a valid and diverse playlist." | `check_picks` on songs 38, 24, 22, 17, 1 | ok |
| 5 | "The checks passed for the top 5 ranked songs, so I can now present them to the user." | Final answer | Accepted, confidence **high** |

**Final picks:** Sunrise City, On the Low, Anybody, Bendecido, Believe What I Say.

**What this shows:** the guardrail caught a broken reply instead of crashing. The agent got the error message, tried again, and finished normally. Without the trace, the only visible difference would be that this run took 5 steps instead of 4.

---

## Trace 3: Asking a question about a missing genre

**Request:** "polka music for my grandma" (an evaluation case, so the answer came from `ScriptedIO`: "something happy and upbeat")
**Full log:** [assets/evidence/trace_log_question_polka.jsonl](assets/evidence/trace_log_question_polka.jsonl)

| Step | Gemini's thought (from the log) | Action | Result |
| --- | --- | --- | --- |
| 1 | "Since polka is not in the allowed genre list, I need to ask the listener to choose a closest matching genre like folk, pop, or rock." | `ask_user`: "Since polka isn't in our catalog, would you prefer folk, pop, or rock music for your grandma?" | ok |
| 2 | "I will search for upbeat and happy folk songs since polka is not in the catalog." | `search_songs` with genre `folk`, mood `happy`, min energy 0.6 | ok |
| 3 | "Now that we know the listener wants happy and upbeat folk music, I will rank the catalog using a matching taste profile." | `rank_songs` with genre `folk`, mood `happy`, energy 0.7, tempo 120, valence 0.8, danceability 0.7, acousticness 0.6 | ok |
| 4 | "I will check the top 5 ranked songs for the listener's happy and upbeat request." | `check_picks` on songs 38, 1, 3, 30, 22 | ok |
| 5 | "The song picks passed the check successfully, so I can present the final recommendations to the user." | Final answer | Accepted, confidence **high** |

**Final picks:** Sunrise City, Believe What I Say, Down, Body Go, Anybody.

**What this shows:**

- **Good:** the agent noticed polka isn't in the catalog, said so honestly, and asked a follow-up question instead of guessing.
- **A flaw the trace revealed:** the answer was "something happy and upbeat," but in step 3 Gemini wrote "the listener wants happy and upbeat folk music." Nobody said folk; Gemini assumed it from its own question. The catalog has very few happy folk songs, so the final picks were mostly pop, hip-hop, r&b and afrobeats. In my human evaluation I rated this case "way off." The automatic evaluation still passed it, because the picks were real songs with a happy mood.

---

## What the traces taught me

1. **The plan is followed.** In every trace the agent went ask (if needed) → search → rank → check → final, the order in the system prompt (`prompts/agent_system.md`).
2. **The guardrails work in real runs, not just tests.** Trace 2 shows a broken reply being caught and fixed on the next step.
3. **The confidence label isn't a quality guarantee.** All three runs ended with "high" confidence, which only means the picks scored well against Gemini's profile. Trace 3 shows the profile itself can rest on an assumption.
4. **The traces make the AI's decisions checkable.** Without the `thought` lines I couldn't have seen why the polka picks went wrong.
