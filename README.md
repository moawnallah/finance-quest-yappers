# CrocoCash

Collabothon 2026, Commerzbank challenge. Live at [crococash.xyz](https://crococash.xyz).

**CrocoCash helps adults of every generation learn to invest: a short survey places them on a personal path of
real-data decisions, scored on their reasons, with a guarded AI tutor.**

## Technology stack

Flutter (Dart) for web, iOS and Android from one codebase; Python 3 and FastAPI backend; SQLAlchemy and Alembic
(SQLite, PostgreSQL-ready); deployed on Oracle Virtual Server behind Cloudflare (HTTPS, DDoS protection, CDN); content
as YAML compiled to JSON by our own engines; Blockly-style block programs for hard tasks; AI tutor on Gemma
(gemma4:12b) served by Ollama locally on our machine; BASAL as the decision model that picks the path, with the rule router as fallback; pytest and
flutter test.

## The problem

Many adults know the basics of money but never act on them. In the EU's 2023 financial-literacy survey (Flash
Eurobarometer 525), only 57% of adults in Poland answered the risk-and-return question correctly, and many who
answer wrongly are confident they are right. Savings sit in accounts that lose value to inflation; first investments
are driven by tips and news rather than a rule. Most learning apps teach facts with quizzes, so people finish them
knowing more but deciding no better. Banks such as Commerzbank (mBank in Poland) want customers who invest with
understanding, but cannot give personal advice in an app.

## Our solution

CrocoCash teaches decisions, not definitions.
- **A 3-minute survey places you.** It reuses the five Eurobarometer questions, so you see how you compare with Poland
  and the EU. A transparent router (an ability estimate plus need rules, no black box) builds a personal path of 3 to
  5 missions, each with a reason.
- **Missions on a skills tree** go from budget and emergency fund to bonds, funds and costs, diversification and
  staying calm in a crash.
- **Three levels per mission.** Easy: cards and questions. Medium: "Day X": a real chart cut at a historical date
  (for example February 2022, inflation rising; March 2020, after the crash). You make a choice and pick your reasons;
  only the reasons are graded, then you see what happened. Hard: you build a strategy from blocks and it is tested on
  hundreds of simulated futures.
- **Every learning material is prepared by a human expert.** Cards, quiz questions, Day-X tasks, explanations, and the
  scenarios and tests of the block tasks are written and checked by a person who knows the field, with a source for
  every fact. AI does not generate learning content. It only helps a learner understand content that an expert wrote.
- **A guarded AI tutor** (Kyle the crocodile) gives hints and explanations but never sees the answer before you submit,
  and never names a product or gives advice.
- **Confidence is measured**, so learners see whether "how sure" matches "how right", and the bank sees anonymised
  needs, with consent.

What makes it different: expert-made content rather than AI-generated questions; grading reasons rather than lucky
outcomes; real public data with no hindsight; safety by construction (the model is never given what it must not
reveal).

## The working prototype

Implemented and working today (crococash.xyz):
- onboarding survey with the Poland/EU benchmark and a personal path from the router;
- the skills wheel and tree with 11 missions on the two demo paths (a young adult and a self-directed investor), with
  learning cards, easy questions, quick checks and prerequisite checks;
- two Day-X tasks on real data: I2 (deposit or bond, February 2022; GUS inflation and the NBP rate) and P4 (sell, hold
  or rebalance, March 2020; OECD share price index for Poland);
- two hard block tasks: "Ania's first two years" and "Marek over ten years", scored on obligatory and optional
  scenarios with a result histogram;
- progress with a confidence-vs-score chart, Scales points, daily goal and leagues;
- **the adviser view for the bank**, the centre of the admin panel. It shows which learners are ready for a
  conversation with an adviser and why: for example "ready to talk about index funds: finished I5 and P1, goal
  retirement, horizon over 10 years, confidence 4/5". Signals appear only for learners who consented to share their
  profile (others are counted only in totals), and they name only types of instruments, never a product, since
  the adviser does the suitability check. Charts show how many learners are ready and which product types they
  already hold, by age group, with sorting and filters by topic and age;
- the rest of the admin panel: logs, statistics, errors and user data (learners, question quality, confidence,
  alerts, tutor calls, recommender and event logs, export), plus a study mode for user tests;
- the AI tutor endpoint with a fallback to stored explanations.

In progress / not yet validated:
- the full tutor pipeline on Gemma is wired behind a flag and has been tested with fake model calls; the real-model
  red-team run is pending;
- more missions (32 on the tree) are visible but locked.

## Behind the build

- **Content is data.** Missions, cards, questions and tasks are YAML files. One build (`backend/data/build.py`)
  validates them and compiles them into JSON the API serves. A strict build fails on hindsight words, real names in a
  hidden chart, a missing source or an unlicensed series.
- **Human expert in the loop.** Every card, question, Day-X task, explanation and block-task scenario records its
  author, its reviewer and its sources. The build checks each fact's source against a source register. A task with no
  named reviewer is marked as not live. In production it would not be shown; in this prototype the tasks still
  waiting for review are shown so the demo paths can be played end to end.
- **Three engines, one contract.** Easy, medium and hard engines share one interface (validate, compile, question
  view, score, reveal view) and a small shared kernel; none imports another. The question view never contains answers,
  truth values or weights, so neither the browser nor the tutor model can leak them.
- **Simulation core.** Hard tasks run a household and market simulation month by month; user block programs are
  parsed and interpreted, never executed as code.
- **Router.** A Rasch ability estimate from five items, Polish Eurobarometer benchmarks and explicit need rules; every
  path step carries a reason. BASAL is the primary decision model: for each candidate mission it says whether the
  learner should study it now and how sure it is; the router's path is used whenever BASAL is unsure or unreachable.
  Nothing personal is sent to BASAL.
- **Tutor.** One model call per message, context fetched by the backend, output checked in code (no answer leak, no
  product advice, no invented numbers) before it is shown.
- **Data.** Downloaded once by hand from licensed public sources (GUS, NBP, OECD, Eurostat, Damodaran), one CSV per
  series with a catalogue of source and licence. No live market calls; single-company prices are synthetic and
  labelled.
- **Hosting.** crococash.xyz runs behind Cloudflare. It issues and renews the HTTPS certificates automatically,
  blocks DDoS attacks and serves cached content from the location nearest each visitor. The server's own address
  stays hidden.
- **Built on:** Flutter, FastAPI, Cloudflare, SQLAlchemy/Alembic, PostgreSQL/SQLite, Ollama with Gemma, LiteLLM,
  BASAL, PyYAML, pytest. Everything else (engines, simulator, router, tutor checks, content, app) was written by the
  team during the hackathon.

## Challenges and discoveries

- **Licences, not data, were the bottleneck.** Stock exchange, index and many aggregator prices may not be
  redistributed, and FRED forbids commercial reuse. We switched to the OECD API for share prices, used GUS and NBP
  with attribution, and made single-company charts synthetic and labelled.
- **Hindsight leaks hide in small places.** A Day-X task dated 1 February 2022 would have shown January inflation
  before it was published, so we moved it to 16 February; a learning card that mentioned the 2020 recovery would
  have given away the P4 task, so we changed it to 2008/2009. We added automatic checks for hindsight words and hidden
  names.
- **Grading outcomes rewards luck.** Day-X tasks are graded on reasons only; the outcome is shown, not scored.
- **No microdata for placement.** We built the router from published Eurobarometer tables and explicit rules, kept it
  explainable, and let each mission's first question check the placement.
- **Local models are slow with reasoning on.** Gemma with thinking enabled took about 50 seconds a reply; calling it
  directly with thinking off is needed for an interactive tutor.
- **Advice versus education.** Under MiFID II, presenting an instrument as suitable for a person is advice. The app
  and the bank-side panel therefore name only types of instruments (index fund, bond, deposit), never a product.

## Results and next steps

**Achieved:** a deployed app with two complete demo paths, real-data Day-X tasks, block-based hard tasks, an
explainable router, a guarded tutor and a consent-based adviser view for the bank.

**Validated:** automated tests across the engines, router, tutor checks and the API; router persona tests for the two
demo learners; a security check of the block-code endpoints with hostile inputs; content checked against its sources.

**Most proud of:** a learner is scored on why they decided, on real history, without being able to cheat with
hindsight.

**Limitations:** most of the 32 missions are not written yet; content has no external reviewer yet; the tutor has not
yet passed its red-team run on the real model; router parameters are not tuned on real outcomes.

**Next:** more missions and real-data tasks, the red-team run and tutor caching, tuning the router on first-question
outcomes, connecting the adviser view to the bank's own adviser tools, and a pilot with real learners.

## Repository

```
frontend/          Flutter app (Michał): one codebase for web, iOS and Android
backend/app/       FastAPI app, database models, Alembic migrations in backend/migrations (Mohamed)
backend/content/   missions, cards, questions and tasks as YAML, plus the source register
backend/data/      engines, simulator, data series and the content build (Yurii)
backend/ml/        router and tutor (Mateusz)
docs/              specs and architecture
.env.example       config names only, never real secrets
```

Rules: every push to `main` deploys, so pull before you push and keep `main` working. Don't commit secrets. Add tests
with every change.
