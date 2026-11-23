# Execution evidence

Real outputs saved on Nov 18, 2026, so the system's behavior can be checked without a video or screenshots. Each file came from the command next to it, run from the project folder. Gemini's wording and picks vary a little between runs; the scores always come from the code.

| File | Command | What it shows |
| --- | --- | --- |
| [agent_study.txt](agent_study.txt) | `python -m src.main --request "something chill to study to"` | A clear request: the agent ranks and checks without asking a question |
| [agent_party.txt](agent_party.txt) | `python -m src.main --request "high energy songs for a party"` | A different mood gives completely different songs |
| [agent_vague_with_question.txt](agent_vague_with_question.txt) | `python -m src.main`, then typing *recommend me some music* and *afrobeats, something happy* | A vague request: the agent asks a follow-up question before ranking |
| [baseline.txt](baseline.txt) | `python -m src.main --baseline` | The original Module 3 recommender: the same lofi list every time |
| [trace_log_example.jsonl](trace_log_example.jsonl) | Written automatically by the study run above | The step-by-step log: Gemini's reason for each step, each tool call and result, and the final songs |
| [trace_log_bad_json_recovery.jsonl](trace_log_bad_json_recovery.jsonl) | Written automatically by `python -m src.main --request "something to vibe to while cleaning"` | Gemini sent a broken reply; the guardrail caught it and the agent recovered on the next step |
| [trace_log_question_polka.jsonl](trace_log_question_polka.jsonl) | Written automatically by `python -m eval.run_eval` (polka case) | The agent noticed polka isn't in the catalog and asked a follow-up question |
| [pytest_output.txt](pytest_output.txt) | `python -m pytest -v` | All 70 automated tests passing, by name |
| [eval_results.md](eval_results.md) | `python -m eval.run_eval` | The evaluation: 6 of 6 requests passed; the baseline fit 1 of 6 |

In `agent_vague_with_question.txt`, the two typed answers were added back by hand. The answers were piped into the program for this capture, and piped input isn't echoed to the screen. Everything else is exactly what the program printed.
