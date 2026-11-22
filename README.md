# CrocoCash

Collabothon 2026, Commerzbank challenge "Finance Quest". Live at [crococash.xyz](https://crococash.xyz).

**CrocoCash helps adults of every generation learn to invest: a short survey places them on a personal path of
real-life decisions on real data, scored on their reasons, with a guarded AI tutor.**

## Technology stack

Flutter (Dart) for web, iOS and Android from one codebase; Python 3, FastAPI and Uvicorn; SQLAlchemy and Alembic on
SQLite (PostgreSQL-ready); one Oracle VPS behind Caddy and Cloudflare Tunnel; content as YAML compiled to JSON by our
own engines; a Blockly-style block language for hard tasks; AI tutor on Gemma 4 12B in Ollama on our own machine;
BASAL, a typed decision model, choosing the learning path, with our rule router as fallback; pytest and flutter test.

## The problem

In the EU's 2023 financial-literacy survey (Flash Eurobarometer 525), 57% of adults in Poland answered the
risk-and-return question correctly, but only 15% hold an investment product; 27% of those who got at most one of
five questions right rated their own knowledge as high. Banks such as Commerzbank (mBank in Poland) want customers who
invest with understanding, and an app that teaches has to stay clear of personal investment advice.

**Target learner:** a self-directed investor, an adult of any age who has some savings and wants to invest them
without an adviser. The survey (age group, goal, horizon, experience, self-rated knowledge) sets the path, so a young
adult building a safety buffer and someone close to retirement start from different missions.

**Learning objective of the demo mission** (P4, "Rebalancing and discipline in a crash"): set a rebalancing rule before
a crash, and keep it when prices fall. The demo paths and missions are explained in
[demo missions](docs/demo_missions.md).

## Our solution

CrocoCash teaches decisions on real situations, and ends each path with a push to take the first step: start
investing your own money, at the level of types (index fund, bond, deposit), never a named product.
- **A 3-minute survey places you** on a path of at least 3 missions, each with a reason, and shows how you compare
  with Poland and the EU. BASAL picks the path when it is confident; otherwise our transparent rule router does
  ([how](docs/onboarding_router.md)).
- **Three task levels** ([how the levels work](docs/task_engines.md)):
  - Easy: cards and questions.
  - Medium, "Day X": a historical chart. You choose and pick your reasons; only the
    reasons are graded, then you see what happened.
  - Hard: you build a rule from blocks for a household over years, and it is tested on fixed scenarios and 200
    simulated futures ([hard tasks](docs/hard_engine.md)).
- **Content and review.** In the full product an expert chooses what is worth learning and signs
  every card and task. In this prototype the content was drafted with AI and is marked so; expert review is the next
  step ([content process](docs/content_authoring.md)).
- **A guarded AI tutor** (Kyle the crocodile) gives hints and explanations and is instructed not to recommend
  products; the task screen shares a task's answer with it only after you submit ([tutor](docs/tutor_agent.md),
  [responsible AI](docs/responsible_ai.md)).
- **Confidence is measured**, so learners see whether "how sure" matches "how right".
- **An adviser view for the bank** shows which learners are ready to talk about which type of product, only for
  learners who agreed to share their profile.

What makes it different: the reasons for a decision are graded, so a lucky outcome earns nothing; a hard task tests a
rule on 200 possible futures; decisions on historical charts; a path that adapts to the learner; and
a design where people choose the content and AI explains it.

## The working prototype

Implemented and working today (crococash.xyz):
- the onboarding survey, the Poland/EU benchmark and a personal path;
- the skills wheel and tree with 11 missions available and two demo paths, "Start safe, then invest" (young adult)
  and "Costs, mixing and discipline" (self-directed investor);
- one complete mission, P4: cards, a Day-X task (March 2020) and a hard task (a 60/40 portfolio over ten years);
- a second Day-X task (I2, February 2022) and a second hard task (P1, a first budget and buffer);
- progress with a confidence-vs-score chart, Emeralds points, daily goal and leagues;
- the adviser view for the bank and the admin panel (learners, question quality, tutor metrics, flagged answers,
  logs, export, study mode);
- the AI tutor, with masking, per-user limits, an answer cache and a fallback to stored explanations.

Built and tested, not yet in production: a stricter tutor pipeline with checks on every model answer. It passed its
red-team run on a local setup; we switch it on after a test environment run ([details](docs/tutor_agent.md)).

## Behind the build

- **Content is data.** Missions, cards, questions and tasks are YAML files with an author, a reviewer and sources.
  A strict build fails on hindsight words, hidden names, a missing source or an unlicensed series. A new
  task of an existing kind needs no new code ([adding a task](docs/content_authoring.md)).
- **Three engines, one contract.** Easy, medium and hard engines share one interface. The question view omits the
  answer ([engines](docs/task_engines.md): [easy](docs/easy_engine.md), [medium](docs/medium_engine.md),
  [hard](docs/hard_engine.md)).
- **Simulation core.** Hard tasks run a household and market simulation month by month. Block programs are parsed and
  interpreted, never executed as code ([market simulation](docs/market_sim.md),
  [household and blocks](docs/hard_engine.md)).
- **Router and BASAL.** The router combines a Rasch ability estimate, Polish Eurobarometer benchmarks and explicit need
  rules. BASAL decides within guards (the goal step first, at least 3 steps) and only when confident; every decision
  is logged ([router and BASAL](docs/onboarding_router.md)).
- **Tutor.** At most one model call per message, no tools. Email addresses, phone numbers, IBANs and PESEL numbers in
  messages are masked before the model ([tutor](docs/tutor_agent.md)).
- **Data.** Three real monthly series from GUS, NBP and the OECD, each with its source and licence; single-company
  prices are synthetic and labelled. Whoever writes a new task downloads the data and checks its licence before it
  goes in ([sources and licences](backend/data/SOURCES.md), [licence checklist](docs/task_engines.md),
  [real data in tasks](docs/content_authoring.md)).
- **Written by the team during the hackathon:** the engines, the simulator, the block language, the router and path
  decider, the tutor pipeline, the admin and adviser panels, and the app; the tools we built on are listed under
  "Technology stack".

## Challenges and discoveries

- **Licences were the bottleneck.** Stock exchange and many aggregator prices may not be redistributed. We took share
  prices from the OECD, used GUS and NBP with attribution, and made single-company charts synthetic.
- **Hindsight leaks hide in small places.** Publication dates, a card that gave away a task, revised statistics. We
  moved dates, rewrote cards and added build checks; one known gap, revised figures, is documented
  ([real data](docs/content_authoring.md)).
- **Grading outcomes rewards luck.** Day-X tasks are graded on reasons only.
- **A decision model needs guards.** BASAL sometimes changed its decision when only something irrelevant changed, so
  it chooses within fixed guards and the router decides whenever it is unsure.
- **Testing our own guardrails was harder than building them.** The checks that keep the tutor from giving advice
  or leaking answers passed a red-team run on a local setup, but in production the stream can show text before the
  final check, and the stricter pipeline fell back to stored explanations too often to switch on before the demo
  ([tutor](docs/tutor_agent.md)).
- **Local models are slow with reasoning on.** Gemma took about 50 seconds a reply with thinking on, and a few seconds
  with it off.
- **Advice versus education.** Recommending a particular product as suitable for a person is investment advice under
  MiFID II. Our policy is stricter: the app names only types of instruments ([responsible AI](docs/responsible_ai.md)).

## Results and next steps

**Achieved:** a deployed app with two demo paths and one complete mission, real-data Day-X tasks, block-based hard
tasks, path choice by BASAL with a rule fallback, a guarded tutor, and a consent-based adviser view for the bank.

**Validated:** automated tests across the engines, router, tutor checks and the API; a red-team run of the tutor
pipeline and a 60-profile run of BASAL, both by Mohamed on local setups; a security check of the block-code endpoints
with hostile inputs; the licence checklist for the real data. Numbers and caveats: [tutor](docs/tutor_agent.md),
[BASAL](docs/onboarding_router.md).

**Most proud of:** a learner is scored on why they decided, on historical charts.

**Limitations:** most of the 32 missions are not written yet; the content awaits expert review; the tutor's guardrails
are tested only on a local setup, and the stricter pipeline is not in production; BASAL is not yet compared with the
router on real outcomes; there is no study with learners and no load test yet ([full
list](docs/limitations_and_next_steps.md)).

**Next:** expert review and new missions for the bank's own product types; the stricter tutor in production; an A/B
test of BASAL against the router; a pilot with real learners; a load test; a personalised version linked to the bank
account, with consent.

## Further reading

- [docs/README.md](docs/README.md): index of all specs.
- [docs/demo_missions.md](docs/demo_missions.md): the two demo paths and what each mission teaches.
- [docs/content_authoring.md](docs/content_authoring.md): why experts make the content, adding a task, real data, the
  sandbox.
- [docs/responsible_ai.md](docs/responsible_ai.md): where AI is used, privacy, monitoring BASAL, controlling the tutor.
- [docs/limitations_and_next_steps.md](docs/limitations_and_next_steps.md): limitations, fixes before the deadline,
  next steps and scaling.
- [docs/onboarding_router.md](docs/onboarding_router.md): the survey, the router, BASAL and its measurements.
- [docs/tutor_agent.md](docs/tutor_agent.md): the tutor, its checks and its red-team results.

## Repository

```
frontend/          Flutter app: one codebase for web, iOS and Android
backend/app/       FastAPI app, database models, Alembic migrations in backend/migrations
backend/content/   missions, cards, questions and tasks as YAML, plus the source register
backend/data/      engines, simulator, data series and the content build
backend/ml/        router, BASAL client and tutor pipeline
docs/              specs; start at docs/README.md
```

## Team

- **Mohamed Awnallah:** backend and API, deployment, admin and adviser panels, BASAL as the path decider, the block
  workspace.
- **Mateusz Gonera:** machine learning: the onboarding router, the BASAL client, the tutor pipeline and its checks;
  research and documentation.
- **Yurii Zaika:** data series and licences, the task engines and the content build.
- **Michał Bielicki:** the Flutter app.
- **Paulina:** design.
- **Artur Melnychenko:** supervision, and an audit of the code against the docs.

**Use of AI.** We used Claude (Anthropic) as a coding assistant for code and documentation, and to draft the
learning content; each content file says so.
