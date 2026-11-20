# Onboarding survey and router

Readers:
- backend: the router;
- frontend: the onboarding screens;
- the pitch owner: the benchmark facts.

Purpose: how the first survey places a user in the skills tree
([skills_tree.md](skills_tree.md)) with few questions.

Status: draft on branch `skills-tree`, 2026-11-20. A reference run on
personas is reported below. The parameters are to tune.

## Idea in one paragraph

- **The questions.** The survey reuses the Flash Eurobarometer 525 (2023)
  questions, so every answer can be compared with Poland and the EU, by age
  and education.
- **The router has no trained model.** We have no microdata. It combines:
  - a Rasch ability estimate from the 5 knowledge items, with a prior mean
    shifted by age and education;
  - static distributions from the Polish EB525 tables;
  - explicit need rules from the behaviour answers.
- **The first item of every node checks the router.** Elo updates take
  over from there.

## The survey: 14 answers, about 3-4 minutes

| # | Question | Source | Used for |
|---|---|---|---|
| 1 | Age band (18-24, 25-39, 40-54, 55+; under 18 maps to 18-24 for benchmarks) | EB525 crosstab | prior mean, needs, benchmarks |
| 2 | Education level (low / medium / high) | EB525 crosstab (ISCED) | prior mean, benchmarks |
| 3 | Who makes money decisions at home (me / with someone / someone else) | EB525 crosstab | needs (F1) |
| 4 | Goal (buffer, first investment, retirement, home, other) | ours | needs |
| 5 | Horizon of that goal (under 3 years, 3-10, over 10) | ours | needs (S4, I2) |
| 6 | Self-rating of financial knowledge | EB525 Q1 | calibration gap at the start |
| 7-11 | Five knowledge items, each followed by "how sure are you?" (1-5) | EB525 Q2-Q6 | ability θ, node mastery, overconfidence |
| 12 | Three behaviour statements on one screen | EB525 Q7_1-3 | needs (F1, S4); EB behaviour score |
| 13 | How long could you live without income | EB525 Q8 | need for S1 |
| 14 | Products held in the last 2 years (multi-select) | EB525 Q9 | needs (F4, S2, L1, L2, I4, I5, I7, D4) |

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

1. **Their EB525 score**, computed exactly as in the report:
   - knowledge 0-5 (one point per correct answer; "don't know" counts as
     wrong);
   - behaviour 0-3 (statements agreed with), rescaled to 0-5;
   - overall 0-10 = knowledge + behaviour × 5/3;
   - bands: low ≤ 5, medium > 5 and < 9, high 9-10.
2. **Benchmarks:** "you vs Poland vs your age group", from the tables below.
3. **The first path:** 3-5 nodes, each with one sentence saying why. The
   sentence comes from the largest term in the priority formula.

## Router algorithm

1. **Prior mean** μ = μ_age + μ_edu (table below). This is additive, which
   assumes no interaction between age and education.
2. **Ability θ:** the EAP estimate on a grid, from a prior N(μ, 1) and the
   Rasch likelihood of the 5 answers.
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
   - Nodes with m ≥ 0.8 are "probably known". They get a 2-item test-out,
     not the full node.
   - Targets are the top 2 non-known E/M nodes by priority. H nodes are
     never first targets.
   - Add every target's unmet prerequisites (m < 0.6), recursively.
   - Safety rule: if n_S1 ≥ 0.6, S1 goes first.
   - Order by prerequisite depth, and cap at 5 nodes.
8. **Correction.** The first item of each node (its prerequisite test)
   updates θ_k. From then on, the two-sided Elo updates both the user and
   the item ratings.

**Need rules (proposal):**

| Survey signal | Nodes | n |
|---|---|---|
| Q8: no savings or under 1 month | S1 | 1.0 |
| Q8: 1-3 months | S1 | 0.6 |
| Q9: consumer loan, or Q7_1 disagree | F4, S2 | 0.8 |
| Q9: mortgage | L2 | 0.8 |
| Q9: no investment product and goal "first investment" | I1, I2, P1 | 0.8, 0.7, 0.6 |
| Q9: holds an investment product | I4, I5, P1 | 0.7 |
| Q9: holds crypto | D4, I7, O1 | 0.8, 0.6, 0.6 |
| Q9: no private pension, age 25-54 | L1 | 0.6 |
| Goal "retirement" | L1 | 0.9 |
| Age 55+ | L3, O1 | 0.8 |
| Age 18-24 | F1, F4, O1 | 0.6 |
| Horizon under 3 years | S4, I2 | 0.7 |
| Q7_2 disagree (does not track expenses) | F1 | 0.8 |
| Q7_3 disagree (no long-term goals) | S4 | 0.8 |
| Someone else makes money decisions | F1 | 0.6 |
| Q1 high self-rating and knowledge score ≤ 2 | D4 | 0.8 |

**Prior means fitted to EB525 vol. C, Poland, weighted.** Each μ is fitted
so that the mean predicted share correct over the 5 items matches the
group's shares (least squares).

| Category | μ |
|---|---|
| Age 18-24 | −0.19 |
| Age 25-39 | −0.11 |
| Age 40-54 | +0.10 |
| Age 55+ | +0.03 |
| Education low | −0.21 |
| Education medium | −0.22 |
| Education high | +0.49 |

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
- The prior is kept because it costs one table lookup. The main value of the
  categories is the benchmarks and the need rules, not the forecast.
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
