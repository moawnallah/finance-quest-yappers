# Onboarding survey and router

Readers:
- backend: the router;
- frontend: the onboarding screens;
- the pitch owner: the benchmark facts.

Purpose: how the first survey places a user in the skills tree
([skills_tree.md](skills_tree.md)) with few questions.

Status: implemented 2026-11-21 in `backend/ml/router` (section
"Implementation"), with the personas as tests. The parameters are to tune
once real first-item outcomes exist.

## Idea in one paragraph

- **The questions.** The survey reuses the Flash Eurobarometer 525 (2023)
  questions, so every answer can be compared with Poland and the EU, and
  with the user's age group.
- **The router has no trained model.** We have no microdata. It combines:
  - a Rasch ability estimate from the 5 knowledge items, with the same
    prior for everyone: placement depends on what you answer, not on who
    you are;
  - static distributions from the Polish EB525 tables;
  - explicit need rules from the behaviour answers.
- **The first item of every node checks the router.** Elo updates take
  over from there.

## The survey: 12 answers, about 3 minutes

| # | Question | Source | Used for |
|---|---|---|---|
| 1 | Age band (18-24, 25-39, 40-54, 55+; under 18 maps to 18-24 for benchmarks) | EB525 crosstab | needs, benchmarks |
| 2 | Who makes money decisions at home (me / with someone / someone else) | EB525 crosstab | needs (F1) |
| 3 | Goal (buffer, first investment, retirement, home, other) | ours | needs |
| 4 | Horizon of that goal (under 3 years, 3-10, over 10) | ours | needs (S4, I2) |
| 5 | Self-rating of financial knowledge | EB525 Q1 | calibration gap at the start |
| 6-10 | Five knowledge items, each followed by "how sure are you?" (1-5) | EB525 Q2-Q6 | ability θ, node mastery, overconfidence |
| 11 | "If you lost your main source of income today, how long could you continue to cover your living expenses, without borrowing any money or moving house?" | EB525 Q8, full wording | need for S1 |
| 12 | Products held in the last 2 years (multi-select) | EB525 Q9 | needs (F4, S2, L1, L2, I4, I5, I7, D4) |

**Removed on 2026-11-20 (your decision):**
- **Education.** The prior it fed added about 1 point of band agreement, and
  ranking a starting level by education reads as profiling.
- **The three behaviour statements (Q7).** About 91-92% of Polish adults
  agree with two of the three, so they say little about a person. They
  only fed the EU overall score and two weak need rules.


**No income question.** Income stays out, as agreed earlier.

**Wording.** The UI is in English, so we use the English master
questionnaire wording of EB525 for Q1-Q9. It is the source of all national
translations, so the benchmarks stay comparable. The exact text is to be
copied from the EB525 report or the questionnaire file in the dataset.

**Sensitive questions (Q8 buffer, Q9 products held).**
- Both are in an official EU survey answered by 26,139 people. They ask for
  bands and product types, never amounts.
- Both are optional and keep the original "Don't know / prefer not to
  answer" option. Skipping sets no need from that question.
- One line under each says why we ask it, for example "So we know whether
  to start with a safety buffer."
- We store the band only. It is used for routing and is never shown to
  anyone else.
- Under 18: skip Q8 and Q9. Benchmarks are for adults only.

## What the user gets back right after the survey

1. **Their EB525 knowledge score**, computed as in the report:
   - 0-5, one point per correct answer; "don't know" counts as wrong;
   - bands: low 0-1, medium 2-3, high 4-5.

   Without Q7 there is no overall 0-10 score.
2. **Benchmarks:** "you vs Poland vs your age group", from the tables below.
3. **The first path:** 3-5 nodes, each with one sentence saying why. The
   sentence comes from the largest term in the priority formula.

## Router algorithm

1. **Prior:** N(0, 1) for everyone. No demographic shift; see "Removed"
   above and check 1 below.
2. **Ability θ:** the EAP estimate on a grid, from the prior and the Rasch
   likelihood of the 5 answers.
   - Item difficulties b:
     - Q3 (inflation) −0.91;
     - Q5 (risk-return) −0.33;
     - Q6 (diversification) −0.17;
     - Q2 (compound interest) +0.67;
     - Q4 (bond prices) +1.54.
   - These are solved so that the mean P(correct) over θ ~ N(0,1) equals
     the Polish share correct.
3. **Per-node ability.**
   - For a node linked to an item: θ_k = θ + 0.5 · (answer − P(correct)).
     The links are Q2 → F3, Q3 → F2, Q4 → I3, Q5 → I1, Q6 → P1.
   - For every other node, θ_k = θ.
4. **Mastery** m_k = σ(θ_k − d_k).
   - Starting difficulty by node level: E −0.5, M +0.5, H +1.5.
   - Elo recalibrates d_k from real attempts.
5. **Needs** n_k:
   - each node starts at 0.2;
   - the rules below raise it;
   - when several rules hit the same node, take the maximum.
6. **Priority:** priority_k = n_k · (1 − m_k) + γ · max(0, c_k − x_k).
   - c_k = (confidence − 1) / 4 on the linked item.
   - x_k = 1 if that item was answered correctly, else 0.
   - γ = 0.3.
   - The interest boost from the Explore wheel (skills_tree.md) adds to
     this later.
7. **Path.**
   - Nodes with m ≥ 0.8 are "probably known". They are offered as a
     **challenge** (see below), not as the full node.
   - Targets are the top 2 non-known E/M nodes by priority. H nodes are
     never first targets.
   - Add every target's unmet prerequisites (m < 0.6), recursively.
   - Safety rule: if n_S1 ≥ 0.6, S1 goes first.
   - Order by prerequisite depth, and cap at 5 nodes.
8. **Correction.** The first item of each node (its prerequisite test)
   updates θ_k. From then on, the two-sided Elo updates both the user and
   the item ratings.

**Challenge (test-out), decided 2026-11-21.**
- **What the user sees:** "Already know this? Take the 2-question challenge
  and skip the node."
  - On nodes the router marks "probably known", the offer is highlighted
    on the path.
  - On any other unlocked node, it is available but not pushed.
- **The challenge:** 2 of the node's own check items, drawn and seeded by
  the easy engine. Both right means the whole node is done. Mastery is set
  to at least 0.8, and the path moves on.
- **One attempt per node.** If it fails, the user does the node normally,
  and the failure lowers θ_k like any first item. One attempt limits lucky
  guesses: two 3-option items pass by chance about 1 time in 9.
- **Logged** as a `reco_events` row of type `test_out`, with `observed`.
  This is the router's cheapest accuracy signal.

**Need rules (proposal):**

| Survey signal | Nodes | n |
|---|---|---|
| Q8: no savings or under 1 month | S1 | 1.0 |
| Q8: 1-3 months | S1 | 0.6 |
| Q9: consumer loan | F4, S2 | 0.8 |
| Q9: mortgage | L2 | 0.8 |
| Q9: no investment product and goal "first investment" | I1, I2, P1 | 0.8, 0.7, 0.6 |
| Q9: holds an investment product | I4, I5, P1 | 0.7 |
| Q9: holds crypto | D4, I7, O1 | 0.8, 0.6, 0.6 |
| Q9: no private pension, age 25-54 | L1 | 0.6 |
| Goal "retirement" | L1 | 0.9 |
| Age 55+ | L3, O1 | 0.8 |
| Age 18-24 | F1, F4, O1 | 0.6 |
| Horizon under 3 years | S4, I2 | 0.7 |
| Someone else makes money decisions | F1 | 0.6 |
| Q1 high self-rating and knowledge score ≤ 2 | D4 | 0.8 |

**Prior means (dropped; kept here as the record behind check 1).**
- Fitted to EB525 vol. C, Poland, weighted.
- Age: 18-24 −0.19; 25-39 −0.11; 40-54 +0.10; 55+ +0.03.
- Education: low −0.21; medium −0.22; high +0.49.
- EB525 also has a "still studying" group, which a version with education
  would have needed for school pupils.

## Checks

**1. Do category priors improve the estimate?** This was a simulation with
20,000 users drawn from the Polish age × education mix (scratch script, seed
0).

| Prior | RMSE of θ | corr | Same tercile band | Off by two bands |
|---|---|---|---|---|
| Flat N(0,1) | 0.742 | 0.710 | 59.6% | 4.4% |
| Age + education | 0.722 | 0.728 | 60.8% | 3.2% |

Reading:
- The gain is small, because the categories explain little of the spread
  (SD of category means 0.34 against 1.0 within).
- The simulation assumes the additive model is true, so the real gain is
  probably smaller.
- Decision (2026-11-20): dropped. One point of band agreement does not
  justify placing people by education. Age stays for benchmarks and need
  rules only.
- Earlier simulation: 3 own items on top of the 5 raise the correlation
  from 0.69 to 0.78. That helps more than any prior.

**2. Reference run on hand-written personas.** The expected paths were
written before the run. The run is a scratch script on the algorithm above.

| Persona | Answers | Path from the router | Expected? |
|---|---|---|---|
| Young adult, 27: under 1 month of savings, no investments, goal "first investment" | Q2, Q3, Q5 right; Q4 and Q6 wrong with confidence 4 | S1 → I2 → I4 → P1 | Yes. I1 counts as known enough because Q5 was right |
| Same, but Q5 also wrong | 2 of 5 | S1 → F1 → F2 → I1 → I4 (cap 5) | Partly: easy nodes at m ≈ 0.55 are pulled in as prerequisites. They should become 2-item test-outs, not full nodes |
| Student, 20: BNPL, does not track expenses, rates themself high | 1 of 5 | F1 → F3 → F4 | Yes. D4 has the same priority as F1 and comes next |
| Self-directed investor, 35: funds and crypto | 5 of 5 | I4 → I5 (10 nodes "probably known") | Yes. I7 is H, so it is never a first target |
| Pre-retiree, 60 | 3 of 5 | O1 → I2 | Partly: L3 (the main need) is H, so it is not a target yet. Show it as the goal of the path |

The run was made before the 2026-11-20 simplification: it used the
age and education prior and the Q7 rules. M2 reruns these personas as
tests on the simplified router.

What the run changed in the design:
- **Prerequisites between m = 0.4 and 0.6 become test-outs** (1 minute),
  not full nodes.
- **The path shows its goal node**, even when the goal is H, for example
  L3 for the pre-retiree.
- **The demo path for the young adult has to include I4**, because P1
  requires I2 and I4 in the tree. Proposal: S1 → I1 → I2 → I4 → P1.
  - Full content (cards, easy, one medium) for S1, I1 and I2.
  - Cards and easy items only for I4 and P1.

These personas become tests once the router is code. Each test asserts the
hand-written path, so a change to rules or parameters that alters a path is
noticed.

## Demo: two personas, one tree

Same content, different entry points and pace. This is how the demo shows
"for all generations and levels".

| Persona | Router output | Content depth |
|---|---|---|
| Young adult, 27: under 1 month of savings, no investments, goal "first investment" | S1 → I1 → I2 → I4 → P1 | Full (cards, easy, medium on real data) for S1, I1, I2; cards and easy for I4 and P1 |
| Self-directed investor, 35: holds funds, 5 of 5 right, high confidence | First path in the reference run: I4 → I5. Ten nodes are marked "probably known" (test-outs). The demo continues to P1 and P4, which are the next targets once I4 and I5 are done | Full for I5 and P4 (March 2020, day X on a real index); I4 and P1 shared with the young adult |

**Shared nodes.** I4 and P1 appear in both paths. The demo can show the same
node reached from two starting points.

**Nodes to write:** S1, I1, I2, I4, I5, P1, P4 (7). One hard task for the
demo: S1 (buffer) or P4 (rebalancing). Yurii picks, based on the engine.

## Replacing the rules with a model later

This is possible once we log real attempts. Until then, the rules are the
better choice: they are explainable to a bank, and they work from the first
user.

- **What a model would predict:** success on the first item of each node
  (the prerequisite test), from the survey answers. That is the router's
  forecast, and real logs measure it directly.
- **Model:** logistic regression per node, or one model with node as a
  feature. It stays explainable through its coefficients (SHAP is not
  needed for a linear model).
- **Comparison:** on held-out users, compare the log loss of the model and
  of the rule router's m_k on the same first items. Replace the rules only
  where the model is better.
- **Data needed:** a few hundred first attempts per node. The earlier
  estimate was about 500 attempts before logistic regression is useful.
- **Synthetic logs:** they can test the pipeline, but they cannot show that
  a model is better. If we generate them from our own rules, the model
  learns our rules back. Label them as synthetic in the pitch.
- **Now:** log the full survey, the router output (m, n, priority, path,
  reasons) and every first attempt from day one. The attempt record in
  task_engines.md already has the fields. Add `router_version`.

## Implementation (backend/ml/router, 2026-11-21)

```python
from router import route
result = route(survey, user_pseudo_id)
```

| Part | File | Notes |
|---|---|---|
| Tree | `router/tree.yaml` | The 32 nodes with title, panel, level and prerequisites. The machine-readable copy of docs/skills_tree.md; a test checks that every node file in `backend/content/nodes` has the same `title` and `after` |
| Benchmarks | `router/benchmarks.yaml` | EB525 vol. C Poland, weighted: items correct, knowledge bands, self-rating "high", buffer under one month; all ages and by age group |
| Algorithm | `router/router.py` | Ability (EAP, flat prior), mastery, needs, priority, path, challenges, goal, `reco_events` rows |

**Survey input:**

```json
{"age_band": "25-39", "decisions": "me", "goal": "first_investment", "horizon": "over_10",
 "self_rating": "quite_high", "buffer": "under_1", "products": ["life_insurance"],
 "knowledge": {"Q2": {"correct": true, "confidence": 3}, "Q4": {"correct": null}}}
```

- `age_band`: `under_18`, `18-24`, `25-39`, `40-54`, `55+`.
- `decisions`: `me`, `with_someone`, `someone_else`.
- `goal`: `buffer`, `first_investment`, `retirement`, `home`, `other`.
- `horizon`: `under_3`, `3_10`, `over_10`.
- `self_rating`: `very_high`, `quite_high`, `average`, `quite_low`,
  `very_low`, `dont_know`.
- `buffer` (Q8): `none`, `under_1`, `1_3`, `3_6`, `6_plus`, or `null` if
  skipped.
- `products` (Q9): any of `pension`, `life_insurance`,
  `non_life_insurance`, `mortgage`, `consumer_loan`, `investment`,
  `crypto`, `none`; or `null` if skipped.
- `knowledge`: Q2-Q6 with `correct` (`true`, `false`, or `null` for "don't
  know", which counts as wrong) and `confidence` 1-5.

**Output:**
- `knowledge_score` (0-5) and `band`;
- `benchmarks` (you vs Poland vs your age group);
- `theta`, `mastery`, `needs`, `priority` per node;
- `path`: up to 5 nodes, each with a reason;
- `challenges`: nodes offered as a 2-question challenge, each with a reason;
- `goal`: a higher-priority node, often H, shown as the path's goal;
- `events`: `reco_events` rows, one `path_issued`, then one per path node
  and one per challenge;
- `router_version`.

**Mastery thresholds for prerequisites:**
- m < 0.4: the prerequisite becomes a full node on the path;
- 0.4-0.6: it becomes a challenge;
- 0.6 or more: it is met;
- 0.8 or more: the node is "probably known", and if it is an ancestor of
  the path it is offered as a challenge.

**Persona results (tests in `backend/ml/tests/test_router.py`):**

| Persona | Path | Challenges | Goal |
|---|---|---|---|
| Young adult (demo): under a month of savings, wants to invest; Q2, Q3 right | S1 → I1 → I2 → I4 → P1 | F1 | - |
| Investor (demo): holds funds, 5 of 5 | I4 → I5 | F1, F3, I1 (+ other known ancestors) | - |
| Student: consumer loan, someone else manages money, 1 of 5 | F4 → S2 | F3, S1 | - |
| Pre-retiree: goal retirement, 3 of 5 | O1 → L1 | S4 | L3 |

**First run vs hand-written expectations.** Two personas differed from
the hand calculation. The hand calculation had used the dropped age and
education prior. With the flat prior:
- the young adult's θ is −0.18, so F2 is met;
- the student's F3 (m 0.43) is a challenge.

The expectations were revised, with the reason in the test file. The demo
paths did not change.

## Demo mode (built 2026-11-21, `router/demo.py`)

The router recommends a path for everyone, but in the demo only some nodes
have content. Two demo paths are defined in `router/demo_paths.yaml`:
- young adult: S1 → I1 → I2 → I4 → P1;
- investor: I4 → I5 → P1 → P4, with P2 offered as a challenge.

**The rule (decided 2026-11-21, option a):**
- **Every node on the recommended path has content:** the user gets it.
  If the path is part of a demo path, the user gets the whole demo path.
  This is the investor case: the router's I4 → I5 becomes I4 → I5 → P1 →
  P4.
- **Otherwise:** "We're sorry: your recommended path would be X > Y > Z,
  but it is not ready yet. Please choose one of the two paths we have
  prepared." Both demo paths are offered. The closest comes first: the
  largest overlap with the recommendation, then the router's priority.
- **The pick is logged** as `path_chosen` with the recommended path. That
  is a label for the next-step model: what people choose when their ideal
  path is missing.

| Persona | Status | Path |
|---|---|---|
| Young adult | ready | young_adult |
| Investor | ready | investor (extended from I4 → I5) |
| Student (F4 → S2) | not ready | picks one of the two |
| Pre-retiree (O1 → L1) | not ready | picks one of the two |

## Shadow decision model: BASAL (experiment, planned 2026-11-21)

**Idea (yours).** Next to the rule router, ask a typed decision model
whether each candidate node is right for this learner. Compare the two,
and keep the algorithm as the base the model falls back to.

**What BASAL is**, from its README (github.com/rkinas/basal, v2.8.1,
read 2026-11-21):
- **Engine.** An inference engine and models for "typed decisions" in
  Polish and English. It returns a probability for each allowed option in
  one forward pass, without generating text, so it cannot answer outside
  the options.
- **Licence:** Apache-2.0.
- **Models:** basal-2.0 mini (1.5B), 4.5B (the recommended start) and max
  (11B), built on Bielik v3. Also experimental basal-omni models.
- **API.** `POST /v1/systemone` with a `state` (text or JSON) and named,
  typed `questions`.
  - Types: `choice`, `noul` (probability of yes), `score`, `multi`; `act`
    and `tool` are experimental.
  - Each answer has a probability per option, the chosen key and a
    `confidence`.
  - The full response format is in its `docs/API.md`, not yet read.
- **Calibration** is reported as ECE on its own benchmark (basal-2.0 4.5B:
  0.060). The README warns that calibration is cautious on unseen tasks.
- **`deferred: true`** exists only for `act` and `tool`, with `max_error`.
  For our yes/no questions we set our own threshold on `confidence`.
- **Hardware.**
  - A GPU (CUDA 12.8) or Apple Silicon (MLX); the README also lists Ollama
    and llama.cpp.
  - Throughput on one H100 with 16 clients: 32 decisions/s for 4.5B.
  - No single-request latency is given, so we measure it on Mo's GPU.

**Set-up: shadow mode.** The router decides every path. BASAL's answers
are only logged as `reco_events` rows of type `shadow_decision`. They never
change what a user sees in the demo.

**One request per user** (illustrative; check the exact fields in
`docs/API.md`):

```json
{
  "state": {
    "age_band": "25-39", "goal": "first investment", "horizon": "10+ years",
    "buffer_months": "under 1", "products": ["life insurance"],
    "self_rating": "quite high",
    "answers": {"Q2": "correct", "Q3": "correct", "Q4": "wrong", "Q5": "correct", "Q6": "wrong"},
    "confidence": {"Q2": 3, "Q3": 4, "Q4": 4, "Q5": 4, "Q6": 4},
    "candidates": [{"node": "S1", "title": "Emergency fund", "level": "E", "router_mastery": 0.66}]
  },
  "questions": {
    "ready_S1": {"type": "noul", "instructions": "Will this learner answer the first check question of 'Emergency fund' correctly?"},
    "start_S1": {"type": "noul", "instructions": "Should this learner study 'Emergency fund' now, given the goal and the gaps?"}
  }
}
```

- `ready_<node>` predicts the same thing as the router's mastery m_k: the
  first item in the node. So the two can be compared on the same outcomes.
- `start_<node>` is the decision itself, compared with the router's path.
- No personal data goes in: bands and answers only, the same rule as for
  the tutor.
- A variant without `router_mastery` in the state tests whether BASAL adds
  anything on its own.

**Fallback rule.** If BASAL's `confidence` is below τ, the algorithm
decides. τ starts at 0.7 and is fitted on data later.

**What we can measure now, on personas** (the 5 from check 2, plus
perturbations; about 30 requests):

| Metric | How | Why it matters |
|---|---|---|
| Agreement with the router | `start_` vs path membership; correlation of `ready_` with m_k | Shows where the two disagree, and those are the cases to read |
| Stability | Shuffle candidates; reword the goal; change fields that should not matter | A decision model must not flip on wording |
| Share below τ | Count | How often the fallback would run |
| Latency and cost | Per request, on Mo's GPU | Whether it fits the onboarding screen |

**What needs real outcomes** (the challenges and first items, from the
hallway test and later users):
- Brier score and log loss of `ready_` vs m_k on the same first items;
- a reliability diagram;
- recalibration of both (Platt or isotonic) on a held-out split.

Replace the rules for a node only where BASAL is better on held-out data.
With about 50 outcomes from the hallway test, this is a first look, not a
result.

**For the pitch:** "We tested an AI decision model against a transparent
baseline. It runs in shadow mode until the data shows it is better
calibrated." This is honest, and it shows AI used as a measured component.

**Resolves the branch:** the persona measurement above.

**Next steps:**
1. Read BASAL's `docs/API.md`.
2. Start `basal-serve` on Mo's GPU with basal-2.0 4.5B.
3. Write the request builder in `backend/ml/router`.

## Facts for the pitch

Source: EB525, volume C, Poland, weighted %. Unweighted n: 18-24 = 98
(margin about ±10 points), 25-39 = 270, 40-54 = 276, 55+ = 359.

| Fact | All | 18-24 | 55+ |
|---|---|---|---|
| Rate their own knowledge "high" (Q1) | 39.6 | 53.6 | 27.3 |
| … among those with a low knowledge score (0-1 correct) | 26.8 | | |
| … among those with a high knowledge score (4-5 correct) | 54.6 | | |
| No emergency savings or under 1 month (Q8) | 30.3 | 41.9 | 31.4 |
| 6 months or more of savings (Q8) | 24.8 | 13.1 | 24.6 |
| Inflation item correct (Q3) | 68.1 | 54.2 | 75.4 |
| Hold an investment product (Q9) | 15.1 | 20.2 | 10.2 |
| Hold crypto (Q9) | 5.8 | 11.5 | 2.8 |
| High overall score, 9-10 (F3) | 14.9 | 6.5 | 17.2 |

Reading for the pitch: the youngest group rates itself highest but has the
weakest safety net and the lowest inflation knowledge. This is why the app
measures confidence next to knowledge, and why the young-adult path starts
with S1.
