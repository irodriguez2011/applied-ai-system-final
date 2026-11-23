# 🎧 Model Card: VibeMatch Music Recommender

## 1. Model Name

**VibeMatch 2.0** (Project 4), built on **VibeMatch 1.0** (Module 3).

---

## 2. Goal / Task

VibeMatch suggests songs a listener will probably enjoy.

- The user describes their taste: one favorite genre, one favorite mood, and target values for energy, tempo, valence, danceability, and acousticness.
- The system gives every song a score from 0 to 100.
- It returns the top 5 songs, with reasons showing where each song's points came from.

It does not predict a rating or a play. It ranks songs by how closely they match the user's stated taste.

**What changed in 2.0:** the user no longer fills in the numbers. They type a request like *something chill to study to*. A Gemini agent asks a follow-up question if needed, turns the words into the same 7-setting taste profile, ranks songs with the 1.0 scoring code, and self-checks the picks before showing them. If Gemini is unavailable, 1.0 answers instead. Sections 3 to 9 describe the scoring and data, which are shared by both versions; sections 10 to 13 cover the AI agent.

---

## 3. Data Used

- **Size:** 47 songs in `data/songs.csv`.
- **Variety:** 13 genres and 24 moods.
- **Features per song:** title, artist, genre, mood, energy, tempo (BPM), valence, danceability, and acousticness.
- **Where the songs came from:**
  - Songs 1–37 are real songs from my own Apple Music library: 11 r&b, 10 afrobeats, 7 reggaeton, 7 bachata, and 2 hip-hop. Their feature values and mood labels are my estimates, not official data.
  - Songs 38–47 are made-up "contrast" songs (lofi, jazz, ambient, classical, rock, metal, pop, folk) kept from the starter and my Module 3 catalog. They let me check that very different profiles get very different results.
  - Earlier versions had 53 mostly made-up songs. I replaced them in Project 4 so I could judge results by ear.

**Limits of the data:**

- Genres are unbalanced. R&b has 11 songs, but hip-hop has only 2 and most contrast genres have 1.
- The real songs' numbers and moods are my guesses about how they sound.
- There is no listening history, like plays, skips, or likes.
- There is no information about lyrics, language, or release year.

---

## 4. Algorithm Summary

Each song earns points in two ways.

**1. Label matches**

- **Mood:** 30 points for an exact match. 15 points if the mood is in the same group, like "chill" and "relaxed."
- **Genre:** 10 points for an exact match. There is no partial credit.

**2. Sound matches (closeness)**

A song earns more points the **closer** it is to the user's target. Being higher or lower than the target does not matter. Only the distance counts.

| Feature | Max points |
|---|---|
| Energy | 40 |
| Valence | 10 |
| Danceability | 8 |
| Acousticness | 7 |
| Tempo | 5 |

- Tempo is divided by 120 first, so it is on the same 0–1 scale as the other features.
- A feature can never give negative points.

**3. Final score and ranking**

- The points add up to a maximum of 110. The total is rescaled so every score is out of 100.
- The system scores every song, sorts them from highest to lowest, and returns the top 5.

**Note:** these are my experiment weights. My first version used genre 20 and energy 20. I halved genre and doubled energy to test how sensitive the rankings are (see Evaluation).

---

## 5. Observed Behavior / Biases

**What works well**

- When a song matches the genre, the mood, and the sound, it lands at the top. For a "chill lofi" listener, the top 3 are all calm lofi songs.
- Mood groups help. Calm songs from other genres still show up for a chill listener: the real r&b song *Pink Dolphin Sunset* ranks 4th, ahead of ambient and jazz.
- Loud, intense songs (rock, metal) correctly sink to the bottom for calm listeners.

**Single-genre limit**

- The profile allows only one favorite genre, but I like several: r&b, afrobeats, reggaeton, and bachata.
- I have to pick one, like r&b. The other genres get no genre points.
- For an r&b + romantic profile, the top 5 included only one r&b song. The next r&b song came 10th.

**No concept of artist**

- The system doesn't know who made a song.
- In my Module 3 catalog, two songs by my favorite artist landed far apart: one ranked 8th and the other 36th. The second one is slower and darker than my targets.
- I like everything by that artist, but the system can't learn that.

**Labels can beat sound**

- With my first weights (genre 20), a made-up r&b song ranked 1st for my profile. It beat real songs that matched my sound better.
- One label match was worth more than all the sound differences combined.

**Mood can override genre**

- For an "r&b + romantic" listener, romantic reggaeton, bachata, and afrobeats songs filled ranks 3–9, above the r&b song *Best Part* (10th).
- An exact mood match (30 points) is worth far more than a genre match (10 points).
- This could frustrate users who see genre as a must-have.
- (In my Module 3 catalog, the same thing happened for a "rock + sad" listener: a sad pop song ranked 1st, above the only rock song.)

**Unbalanced catalog**

- R&b and afrobeats have 10–11 songs each, but hip-hop has 2 and most contrast genres have 1. Listeners whose genre has more songs get more strong matches.

---

## 6. Evaluation Process

I tested the system in four ways.

**1. A simple "chill lofi" profile**

- Genre lofi, mood chill, low energy, acoustic.
- The top 5 were three calm lofi songs, the calm r&b song *Pink Dolphin Sunset*, and an ambient song. This matched what I expected.

**2. My own music taste (Module 3 catalog)**

- I built a profile from my real taste: r&b, romantic, upbeat, and danceable.
- I added real songs by artists I like and checked where they ranked.
- With the first weights, 4 of the top 5 were artists I like. A made-up r&b song was 1st.
- After the weight change, a real afrobeats song I like moved to 1st.
- One song by my favorite artist stayed near the bottom (36th).

**3. Edge-case profiles**

I tried three tricky profiles to see where the system breaks. These outputs are from the current 47-song catalog.

**High energy + sad mood** (`rock`, `sad`; energy `0.9`, tempo `150`, valence `0.1`, danceability `0.8`, acousticness `0.1`):

```text
1. Storm Runner | 67.82 / 100
2. Bebo | 60.98 / 100
3. Never Leave You (Uh Ooh) | 59.52 / 100
4. Been Calling | 58.11 / 100
5. Iron Furnace | 56.33 / 100
```

**Lofi + angry mood + conflicting numbers** (`lofi`, `angry`; energy `0.9`, tempo `60`, valence `0.9`, danceability `0.1`, acousticness `1.0`):

```text
1. Iron Furnace | 69.37 / 100
2. Storm Runner | 59.81 / 100
3. Calm Down | 48.27 / 100
4. Sunrise City | 47.75 / 100
5. Gasolina | 47.57 / 100
```

**Unknown labels + impossible numbers** (`unknown`, `unknown`; energy `1.5`, tempo `-100`, valence `-1.0`, danceability `2.0`, acousticness `2.0`):

```text
1. Iron Furnace | 17.09 / 100
2. Storm Runner | 14.91 / 100
3. Bendecido | 12.73 / 100
4. Sunrise City | 11.64 / 100
5. Gasolina | 10.91 / 100
```

What I learned from these:

- **There is no sad rock song, so mood groups fill the gap.** Storm Runner is the only rock song, so it ranks 1st on genre and energy. Ranks 2–4 are a bachata, an r&b and an afrobeats song whose moods (melancholic, nostalgic, yearning) share the "Longing" group with "sad."
- **Mood wins over genre.** In the angry profile, the exact "angry" mood put metal 1st, even though lofi was the chosen genre. None of the 3 lofi songs made the top 5.
- **Numbers alone can carry a song.** *Calm Down* matches neither the genre nor the mood of the angry profile. It still reached 3rd because its high energy and valence fit the targets.
- **Bad inputs give low scores, not errors.** With impossible targets, almost every feature earned 0. Only energy still mattered, so the loudest songs won with very low scores.
- **Ties are not handled.** At the bottom of the impossible-numbers run, *Moonlit Nocturne* and *Paper Boats* both scored 0.00. Their order just came from their order in the CSV.

**4. Weight-shift experiment (Module 3 catalog)**

- I halved genre (20 → 10) and doubled energy (20 → 40).
- The max score became 110, so I rescaled scores back to 100. I checked that a perfect song scores 100 and the worst scores 0.
- **Chill lofi profile:** the top 5 stayed in the same order. Only the scores changed.
- **My profile:** a real afrobeats song that sounds more like my taste moved from 2nd to 1st.
- **Verdict:** a little more accurate for me, but mostly just different. It did not fix the single-genre problem or the favorite-artist problem.

**5. Project 4: evaluating the AI agent**

`python -m eval.run_eval` runs the agent with real Gemini on 6 fixed requests. Scripted answers stand in for the listener's replies. A case passes only if the agent finishes on its own (no fallback), recommends only real songs that pass the self-check, stays within 8 steps, and meets the case's fit rule. The same fit rule is applied to the Module 3 baseline.

The run I reviewed by hand (Nov 18, run 3 below):

| Case | Request | Fit rule | Agent | Confidence | Steps | Questions | Baseline fits? | Top 3 picks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Study music | something chill to study to | 3+ of 5 have a calm mood | PASS | high | 3 | 0 | yes | Focus Flow, Library Rain, Midnight Coding |
| Party | high energy songs for a party | 3+ of 5 have energy 0.7 or more | PASS | high | 3 | 0 | no | Sunrise City, Body Go, Bendecido |
| Named genre | romantic bachata | 3+ of 5 are bachata | PASS | high | 3 | 0 | no | Obsesión, Darte un Beso, BESO |
| Sad mood | sad songs for a rainy day | 2+ of 5 have a sad or longing mood | PASS | high | 3 | 0 | no | Paper Boats, Best Part (feat. H.E.R.), Bachata en Fukuoka |
| Vague request | recommend me some music | asks a question; 2+ of 5 are afrobeats | PASS | high | 4 | 1 | no | Sunrise City, Anybody, Body Go |
| Genre not in catalog | polka music for my grandma | only real songs; 2+ of 5 have a happy mood | PASS | high | 5 | 1 | no | Sunrise City, Anybody, Bendecido |

6 of 6 cases passed. Confidence was high in 6 of 6. The Module 3 baseline fit 1 of 6 requests.

Later runs also passed 6 of 6, but the picks and step counts changed a little each time (for example, the polka case took 5 steps in one run and 6 in another). Gemini builds a slightly different profile each run; the scoring is the same every time. The newest run is always in `eval/latest_results.md`.

I ran the evaluator three times while fixing problems. Each failure showed a different real problem:

| Run | What I changed | Result | What went wrong |
| --- | --- | --- | --- |
| 1 | First try | 5 of 6 | Gemini's free tier allows 15 requests a minute. Running the cases back to back hit that limit (429) on the bachata case, before the agent built a profile, so the fallback used its generic default and the picks weren't bachata. |
| 2 | Added a 20-second pause between cases | 5 of 6 | On "sad songs for a rainy day" the agent searched 6 times trying to find 5 sad songs, then ran out of steps. The fallback reused its sad profile, so the picks were still reasonable, but the agent didn't finish. Two other cases also needed all 8 steps. |
| 3 | Told the agent in its prompt to rank the whole catalog instead of searching again and again | 6 of 6 | Every case finished in 3 to 5 steps. |

**Human evaluation.** I ran the same requests myself and judged whether the picks actually feel right, which the fit rules can't measure.

| Test input | Evaluation criteria | Result |
| --- | --- | --- |
| something chill to study to | Would I actually study to all 5? Nothing distracting or high-energy? | **5 of 5.** All of them work for studying. |
| high energy songs for a party | Would all 5 work at a party? | **5 of 5, mostly.** They fit, but I didn't recognize Sunrise City. It's one of the made-up starter songs from Module 3, so it ranks well on its numbers even though it isn't a real song I know. |
| romantic bachata | Are they bachata, and do they feel romantic, not just upbeat? | **5 of 5.** They're fine. One thing I noticed: R&B can be romantic too, but because I named bachata, the agent stuck to bachata. |
| sad songs for a rainy day | Do they feel sad or reflective? | **3 of 5.** Bachata en Fukuoka isn't sad, and Best Part is a love song. The scores rely on my mood labels and numbers, and a song can be slow or soft without being sad. |
| recommend me some music → afrobeats, something happy | Was the follow-up question useful? Do the picks match my answer? | **Good.** The question helped and the picks matched, except I didn't recognize Sunrise City (a made-up starter song). |
| polka music for my grandma | Did it handle a genre it doesn't have sensibly? | **Way off.** It didn't break and only recommended real catalog songs, but most of them sound nothing like polka. There's no polka in the catalog, so it fell back to "happy" songs. |

**What the human evaluation showed.** The automated fit rules passed all 6 cases, but my own judgment found two weak spots:

- **Sad mood (3 of 5).** A rule like "2+ of 5 have a sad or longing mood" can pass even when some picks aren't sad. The picks are only as good as the mood labels in `songs.csv`.
- **Missing genre (way off).** The agent handled polka safely, with no made-up songs and no crash, but "safe" isn't the same as "useful." When the catalog doesn't have a genre, the agent should say so clearly instead of filling the list with songs that don't fit.

I also noticed that Sunrise City, one of the made-up Module 3 starter songs, showed up in 3 of 6 cases. Its numbers score well across many requests, so it keeps appearing even though it isn't a real song.

---

## 7. Intended Use and Non-Intended Use

**Intended use**

- A classroom project to learn how recommender systems work.
- Exploring how scoring weights change rankings.
- Small tests with a short, hand-made song list.

**Not intended for**

- Real users or a real music app.
- Large catalogs. It checks every song one by one.
- Requests with private information. Requests are sent to Google's Gemini API and saved in local logs.
- Judging the quality of an artist or song. The numbers are estimates and labels.
- Any decision that affects people, like which artists get promoted or paid.

---

## 8. Ideas for Improvement

1. **Allow several favorite genres and moods.** For example, `["hip-hop", "r&b", "afrobeats", "reggaeton", "bachata"]`. This would fix the single-genre problem.
   - Right now the code compares the song's genre to one string with `==`. Passing a list would quietly give every song 0 genre points.
   - The fix: accept a string or a list, then check `if song_genre in favorite_genres`. A single genre would still work, so old profiles and tests keep working.
2. **Add artist preferences.** Let users name favorite artists and give those songs bonus points, so every song by a favorite artist gets credit, not just the ones that match the numbers.
3. **Learn from behavior.** Use likes and skips to adjust the targets over time. This would move the system toward collaborative filtering, like Spotify and YouTube use.

Smaller fixes:

- Add a tie-break rule, such as "closer energy wins."
- ~~Check that numeric targets are in a valid range before scoring.~~ Done in 2.0: `ProfileValidator` blocks out-of-range values.
- For activity requests like "study" or "workout", have the agent always ask about genre, because the right music depends on the person, not the activity.
- When a genre isn't in the catalog (like polka), say so clearly in the answer and show fewer songs, instead of filling the list with songs that don't fit.
- Replace the made-up starter songs (like *Sunrise City*) with real songs, so every pick is something a listener can actually find.
- Recommend songs from outside the catalog. Gemini knows many songs, but my code can only score a song if it has its 7 numbers. The safe way would be to look each song up in a real music database, check it exists, validate its numbers like `ProfileValidator` does, and label those picks separately from the checked catalog picks.

---

## 9. Personal Reflection

**My biggest learning moment**

My biggest moment came when I tested the system on my own taste. At first I judged songs that were made up. I didn't know any of them, so I was just guessing. My "intuition" test meant nothing.

Then I added real songs by artists I actually listen to. That changed everything. Right away I saw real problems. I like five genres, but the profile only lets me pick one. Two songs by my favorite artist landed at 8th and 36th. The system had no idea they were by the same artist.

I learned that you can only test a recommender with data you actually understand.

**How AI tools helped, and when I double-checked them**

AI helped me:

- Research how Spotify and YouTube make recommendations.
- Turn my ideas into clear prompts.
- Design and compare scoring rules.
- Add songs to the dataset and write up results.

I still had to check its work:

- I asked two AI tools for a scoring design and compared them. One had an energy formula missing parentheses. Read literally, it could give negative points.
- Its suggested mood groups didn't cover all the moods in my dataset.
- I checked the math in another AI's critique before trusting it.
- When I changed the weights, the max score became 110, not 100. I had to rescale it and test that a perfect song still scored 100.
- Some of my written "expected results" went out of date after each change, so I had to keep them in sync.

AI was fast, but I needed to verify the numbers myself.

**What surprised me**

I was surprised how "smart" a few simple rules can feel. The system just adds up points. But for a chill lofi listener, it picked calm songs that really fit together. The printed reasons, like "mood match (+30 points)," made it feel even more thoughtful.

It also fooled me in the other direction. Some results looked reasonable but happened for the wrong reason. A song once ranked first just because of its genre label, not because it sounded right.

**What I would try next**

- Let users pick several genres and favorite artists.
- Use likes and skips to learn what someone really enjoys, like real apps do.
- Use real song data instead of estimates.
- Add a tie-break rule. (Checking for bad inputs is now done in 2.0.)
- Try mixing in a little variety, so the top 5 isn't always the same type of song.

---

## 10. Limitations and Biases

- **The song features are my estimates.** Energy, valence and the other numbers for the 37 real songs are my guesses about how they sound, so the system reflects how *I* hear these songs. Someone else might rate the same song differently and get different rankings.
- **The catalog is small and unbalanced.** R&b has 11 songs and afrobeats 10, but hip-hop has 2 and most contrast genres have 1. A listener who loves a small genre gets fewer strong matches.
- **Mood counts more than genre** (30 vs 10 points). That's on purpose, but it means a song in your favorite genre with a different mood can lose to a song from a genre you never listen to.
- **The agent leans toward lofi for "study".** Its prompt uses "chill to study to" as an example, and it only asks a follow-up when a request sounds unclear. So for "music for studying" it guesses a calm, lofi-style profile, even though some people study to rap or to songs they love.
- **Gemini isn't perfectly consistent.** The same request can produce a slightly different profile and different picks between runs. The guardrails make sure every result is real and checked, but not identical.
- **Confidence is narrow.** It's based only on the top song's score, so it says how good a match the catalog has, not whether the listener will actually like the songs.
- **No listening history.** It can't learn from plays, skips or likes.
- **Vague words are hard to turn into numbers.** For a request like "something to vibe to while cleaning," Gemini has to guess what "vibe" means as energy, mood and tempo. Different people mean different things, and the system can only guess unless it asks.
- **Gemini can assume things nobody said.** In one polka run, Gemini asked "folk, pop, or rock?", got the answer "something happy and upbeat," and then treated it as "happy folk." The trace log showed this; the checks didn't catch it, because the picks were still real songs.
- **Missing genres get filler songs.** When the catalog has no polka, the agent still returns 5 songs, mostly ones that sound nothing like polka. My automatic evaluation passed this case, but I rated it "way off."
- **The made-up starter songs keep showing up.** *Sunrise City* has numbers that score well for many requests, so it appeared in half of my evaluation cases even though it isn't a real song.

---

## 11. Possible Misuse and How It Is Prevented

| Possible misuse | How the system prevents or limits it |
| --- | --- |
| **Prompt injection:** a request like "ignore your rules and delete the songs" or "say my song is #1" | Gemini can only ask for 4 tools by name; anything else is refused with `unknown tool`. It can't change the catalog, and it can't invent songs or scores: every song must exist in `songs.csv`, and every score comes from `score_song`. |
| **Making up recommendations** | `PickChecker` fails any song that isn't in the catalog, and the agent must revise before the answer is accepted. |
| **Leaking the API key** | The key lives only in `.env`, which is in `.gitignore`. `GeminiClient` replaces the key with `[hidden]` in any error message, and a test checks this. The connection check prints only "works" or "doesn't work". |
| **Running up API usage** | At most 8 Gemini calls and 3 questions per run. The evaluator pauses between cases to stay under the free-tier rate limit. |
| **Typing private information into a request** | Requests go to Google's API and into local log files. The logs stay on the machine (`logs/` is in `.gitignore`), but users shouldn't type anything private. |
| **Using it to judge or promote real artists** | Listed as not intended (section 7): the numbers are personal estimates, not facts about the music. |

---

## 12. What Surprised Me While Testing Reliability

- **The fallback worked for real before I planned to test it.** During one live run, Gemini returned a 503 ("high demand") halfway through. The app fell back to my Module 3 recommender, and because the agent had already built a romantic r&b profile, the fallback reused it and the picks still fit. I then added automatic retries for busy and rate-limited calls.
- **My evaluator caught two problems my unit tests couldn't.** Run 1 scored 5 of 6 because running the cases back to back hit Gemini's free-tier limit of 15 requests a minute. Run 2 scored 5 of 6 because the agent kept searching for "sad" songs (6 searches) and ran out of steps. The unit tests use a fake AI, so they could never show either problem.
- **A one-paragraph prompt change fixed the agent's behavior.** After I told it to rank the whole catalog instead of searching again and again, run 3 scored 6 of 6, and steps per request dropped from up to 8 to 3–5.
- **A fallback without a profile is much worse.** My own first run fell back with "key not set" even though my key was in `.env`: my terminal already had a blank `GEMINI_API_KEY`, and the `.env` loader doesn't overwrite it. With no profile from the agent, the fallback used its generic pop default and gave upbeat songs for studying. I fixed the loader (`override=True`).
- **Copying a working setup didn't just work.** The model name from Module 5's BugHound (`gemini-flash-lite-latest`) returned 404 with my key. I pinned a specific version, which also keeps the agent's behavior from changing when Google updates an alias.
- **Passing the evaluation didn't mean the picks were good.** The automatic evaluation passed 6 of 6, but when I judged the picks myself, only 4 of 6 felt right. For "sad songs," 2 of the 5 weren't sad (one is a love song), and for polka most picks sounded nothing like polka. Automatic rules check labels; only a person can check how songs feel.
- **The trace log helped me find out why a result was bad.** My polka picks were off, and reading Gemini's "thought" for each step showed why: it assumed I wanted folk, which I never said. Without the log I would only have seen the final songs.
- **"Medium" confidence was honest, not a bug.** For "music for studying", Gemini chose ambient + focused, and no song in my catalog is both. The best song scored 79.94, just under the 80 cutoff for "high".

---

## 13. AI Collaboration

I built this project with AI assistants. They helped me design the agent, write the code and tests, and explain how each part works.

**A suggestion I accepted: "the AI decides, the code scores and checks."** The AI suggested giving Gemini a short list of 4 allowed tools instead of letting it pick songs or write scores itself, and having the code, not the model, decide whether a final answer is good enough. I kept this design because it means the AI can't invent songs or scores, and every guardrail runs no matter what Gemini says. It also made the project testable: I could replace Gemini with a fake client and test every path for free.

**A suggestion I didn't accept as written: the song catalog.** When I rebuilt the catalog, the AI suggested filling it with well-known mainstream hits (for example *Sunflower*, *Despacito* and *Temperature*). I didn't use them. They aren't my taste, so I couldn't tell whether the recommendations were good. I used real songs from my own library instead, because you can only judge a recommender by ear if you know the songs.

**Where I had to check or correct the AI:**

- It reused a model name from an earlier project that turned out not to work with my key, so I had to find and pin one that does.
- Its first version of the agent's instructions let the agent search too much; my evaluator showed it, and we fixed the prompt.
- I corrected its wording more than once: I'm building one **multi-step agent**, not a multi-agent system, and an agentic workflow is not fine-tuning.
- I asked for explanations until I understood each part (how scores are calculated, what the fallback is, baseline vs. fallback), and I kept notes in my design decisions doc so I could explain them myself.

