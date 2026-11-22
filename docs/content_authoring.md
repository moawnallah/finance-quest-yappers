# Making content: from scope to a live mission

Readers:
- a bank or partner that would run the content: who does what, and why
  people write it;
- content authors and analysts: how to add a mission or a task;
- the jury: what our prototype did, including where it broke its own rule.

Purpose: why learning content is made by people, the process we propose,
how a new mission or task is added in this repository, and the rules for
real data and for the hard (sandbox) tasks.

Status: 2026-11-22. The process is a proposal. The repository facts are
read from `backend/content` and `backend/data` on main.

## Why an expert, when knowledge is everywhere

- Facts about money are easy to find. Any chat model will explain what a
  bond is.
- What a learner cannot get alone is the choice: which few things are worth
  learning first for their situation, in which order, and which common
  beliefs are wrong. That choice is what the app sells.
- If the missions were generated text, a learner could open Claude or
  ChatGPT and get the same thing for free. The value is a path chosen and
  checked by someone who knows the field, with a source for every fact and
  tasks whose grading has been thought through.
- Checked content is also what lets a bank put its name on the app: every
  fact has a source, and every file has a named reviewer.

## What our prototype did

The app's rule is that AI does not write learning content. In the 48 hours
of the hackathon it did.

| Content | Author field | Reviewer field |
|---|---|---|
| 11 node files (cards and quiz items: F1-F3, S1, I1, I2, I4, I5, P1, P2, P4) | "draft by Claude (AI), 2026-11-20" | none |
| Day-X tasks i2.m1, p4.m1 | "draft by Claude (AI), 2026-11-21" | none |
| Hard tasks p1.h1, p4.h1 | "draft by Claude (AI), 2026-11-21" | "Mateusz, 2026-11-21 (situation, tests and lessons approved)" |
| Licence checklist of the three real series | | signed off by Yurii, 2026-11-21 |

- The arithmetic in the items was rechecked and recorded in each item's
  `checked` field (by Claude, so not an independent check).
- The build marks a file without a reviewer as not live. The server serves
  it anyway, because `SERVE_DRAFTS` defaults to on for the demo
  (`backend/app/config.py`).
- So the pipeline works with AI drafts: the template, the source register,
  the build checks and the reviewer field. The step that is missing is the
  expert review.
- Before real learners see the content: set `SERVE_DRAFTS=0`, and have a
  named expert review every file.

## The process we propose

1. **Scope.** A person responsible for the curriculum agrees with the bank
   what the app covers:
   - the bank's target customers, and the types of products it offers
     (accounts, deposits, bonds, funds, retirement accounts);
   - what the app must not do: name products, or say that something is
     suitable for a person (docs/tutor_agent.md, advice policy).
   The result is the list of missions on the skills tree and, for each
   mission, two to four learning objectives
   ([skills_tree.md](skills_tree.md), `backend/ml/router/tree.yaml`).
2. **Cards.** For each mission, an author writes the cards:
   - one idea per card, in plain words;
   - a number only with a source, linked to an entry in
     `backend/content/sources.yaml`;
   - the common mistake the card corrects.
   Template: `backend/content/nodes/_TEMPLATE_easy.yaml`;
   guide: [easy_engine.md](easy_engine.md).
3. **Quiz items.** Items that test the objectives, each with an
   explanation (`why`) and a record of how its numbers were checked
   (`checked`). Item kinds: single, multi, true/false, numeric, reflection.
4. **Day-X tasks** on real data, by an analyst (section "Real data" below).
5. **Hard tasks** in the sandbox (section "Hard tasks" below).
6. **Review.** A second person checks every fact against its source and
   every task's grading, then fills in `reviewer`. The strict build
   (`python build.py --strict`) fails on hindsight words, real names in a
   hidden chart, a missing source or an unlicensed series.
7. **After launch.** The admin panel's item-quality view shows items that
   are too easy, too hard or confusing; flagged tutor answers point to
   unclear cards. Both go back to the author.

AI may help along the way: draft variants of an item, check arithmetic,
translate. A named person chooses what goes in, checks it and signs it.

## Adding a mission or a task in this repository

A new task of an existing kind is a content file; no code changes
([task_engines.md](task_engines.md)).

1. **The mission.** Add the node to [skills_tree.md](skills_tree.md) and to
   `backend/ml/router/tree.yaml` with its title and prerequisites (`after`).
   A test checks that the node file has the same `title` and `after`.
2. **The node file.** Copy `backend/content/nodes/_TEMPLATE_easy.yaml` to
   `<NODE>.yaml` for cards and quiz items. Day-X tasks go under `tasks:`
   (copy from `_TEMPLATE.yaml`, guide [medium_engine.md](medium_engine.md));
   hard tasks go under `hard:` ([hard_engine.md](hard_engine.md)).
3. **Sources and data.** Each fact links to `backend/content/sources.yaml`.
   A real series needs an entry in `backend/data/series/catalog.yaml`, a
   CSV in `backend/data/series/data/`, a row in `backend/data/SOURCES.md`,
   and the licence checklist in [task_engines.md](task_engines.md).
4. **Build and test.**
   ```bash
   cd backend/data
   python build.py --strict
   python -m pytest tests
   ```
5. **Review.** Fill in `author` and `reviewer`. Only reviewed files are live
   once `SERVE_DRAFTS=0`.
6. **Deploy** through a pull request to `main` (every push to `main`
   deploys).

As soon as the node is in `tree.yaml` and served, the router and BASAL can
put it on a learner's path. This is how the app can grow toward full
personalisation: a bank can add missions for its own product types or
customer groups without new code.

## Real data in Day-X tasks

**What is in the repository.**
- Three real monthly series: GUS consumer prices, the NBP reference rate,
  and the OECD share price index for Poland. Each has its source, licence
  and attribution in `series/catalog.yaml` and `SOURCES.md`.
- Single-company prices are synthetic and labelled as such on screen.
  Prices from the stock exchange or index providers may not be
  redistributed.
- Facts on cards cite published tables (Damodaran's historical returns,
  Eurobarometer 525); those tables are not stored as series.

**Licence check (2026-11-22, Claude).**

| Source | What the terms say | Open |
|---|---|---|
| GUS | stat.gov.pl/copyright: copying and reuse are allowed if the source is given | The page says nothing about commercial use. The DBW terms linked in task_engines.md were not re-read |
| OECD | CC BY 4.0 is the OECD default for content from 1 July 2024; material owned by third parties is excluded | Whether OECD treats the Polish share price index as third-party material |
| NBP | Not read: nbp.pl blocked the automated request | The credit "Source: NBP, www.nbp.pl" matches how NBP credits its own tables |

For the demo, the attribution is in place. Before a commercial launch, the
three open points need a person to check them.

**Why real data.** A fictional chart can be drawn to teach any lesson, so a
learner's choice on it proves little. On a real chart, cut on a real date,
the learner faces what people faced then, and the reveal is believable.

**How an analyst should build a Day-X task.**
1. **Pick the date and show only what was known then.** Mind publication
   lags: January's inflation is published in mid-February, so the I2 task
   is dated 16 February 2022, not 1 February.
2. **Set out the likely futures as seen on that date.** Three or four
   scenarios, with rough probabilities and what each would mean for the
   decision. Take them from forecasts published at the time (the NBP
   projection, the consensus), not from hindsight.
3. **Grade the reasons, never the outcome.** The current tasks already do
   this.
4. **Reveal what happened, placed among those scenarios.** Often what
   happened was one of the less likely ones: on 24 February 2022, eight
   days after the I2 task date, Russia invaded Ukraine. That is itself the lesson. Finance is
   managing risk: you decide before you know, and a good decision is one
   that holds up across the likely futures. A decision that only worked
   because the outcome was guessed right was luck.

Steps 2 and 4 are the target. The two current tasks show the reveal
without a scenario set.

**Revisions are hindsight too.** The charts use final figures. In I2
(16 February 2022) the published January inflation was 9.2%
(preliminary); the chart shows the final 9.4%, published on 15 March. An
analyst should use the figures as published on the task date (data
vintages), or state the revision in the task.

## Hard tasks: the sandbox

**What they are.** The last and hardest step of a mission. The learner
builds a rule for a household from blocks ("every month, if the buffer is
below three months of costs, save 300 first…"). The simulator then runs
the rule month by month. The task assumes time and focus: the app tells the
learner it may take a while, and recommends a large screen.

**Two kinds of tests** ([hard_engine.md](hard_engine.md)):
1. **Obligatory tests.** Named scenarios with a check, for example "job
   loss in month 4: no card debt". If any fails, the plan is not accepted,
   and the learner sees the failing test's month-by-month story.
2. **Optional tests.** Named surprises, each with a probability and a
   metric from 0 to 1. Their probability-weighted share gives the points,
   51 to 100. The metric depends on the task: in P1 (Ania) it is card use
   (1 never needed the card, 0.5 needed it and repaid it, 0 still in
   debt); in P4 (Marek) it is whether the portfolio stayed near its
   target mix.

On top of the tests, 200 random ten-year futures with a fixed seed show
the spread of results, and add no points. In P1 they include random job
losses and shocks, and show in how many futures the rule never needed the
card; in P4 they vary the markets only. Both show a growth index.

**Safety.** A program is parsed into blocks and interpreted. User code is
never executed. Limits: 8,000 characters, 30 blocks, 3 own variables; deep
nesting returns an error (400); runs and submits are rate limited per user
(30 runs and 10 submits a minute).

**Writing a hard task.** The author describes the household
(`household`), the world (`world`: months, market), the block palette, the
obligatory and optional tests, the futures and a reference program that
passes. The reviewer checks that the reference program passes, that a
plausible weak plan fails for the right reason, and that the lesson in the
reveal follows from the tests.

**A possible second use: work-sample tests for hiring.** A bank or fintech
could use the same sandbox to assess candidates for analyst or adviser
roles. The candidate writes a rule for a client situation; it is scored on
fixed tests and futures; reviewers read the program. This would need:
- a task set made for the role, and time limits;
- a separate deployment, with the tutor switched off;
- the same tasks for every candidate, and evidence that scores relate to
  job performance before they inform decisions;
- a legal review first: AI systems used to select or evaluate candidates
  are listed as high-risk in the EU AI Act (Annex III, employment), and
  automated decisions about people fall under GDPR Article 22.
