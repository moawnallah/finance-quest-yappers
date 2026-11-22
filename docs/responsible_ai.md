# Responsible use of AI

Readers:
- a bank's product, compliance and data-protection people;
- the jury;
- the team, as the checklist for a full product.

Purpose: where the app uses AI, the rules each use follows today, and how
it should work in a full product: client privacy, monitoring BASAL,
controlling the tutor, and a personalised version linked to a bank
account.

Status: 2026-11-22. "Today" lines are read from the code on main.
"Full product" lines are proposals and have not been built.

## Where AI is used

| Use | Model | What it may do | If it fails |
|---|---|---|---|
| Tutor (Kyle) | Gemma 4 12B in Ollama, on our own machine | explain, hint, rephrase; one model call per message, no tools | the stored explanation written for that card or task |
| Path choice | BASAL (typed decisions) | choose the path from the router's candidates, within guards | the rule router's path |
| Content drafts | Claude, at build time | drafted the prototype's content ([content_authoring.md](content_authoring.md)) | not applicable: a person must review before it goes live |

AI does not grade: the engines score answers with fixed rules. It does not
recommend products: the app has none to recommend.

## Rules the app follows today

1. **The model is not given what it must not reveal.** Before an answer
   is submitted, the app has no correct answer, truth value or weight (the
   question view never contains them), so it cannot pass one to the tutor.
   In production the tutor accepts the context the app sends; the checked
   pipeline builds the context on the server instead (`tutor/context.py`).
2. **No investment advice.** Two parts of the law matter here:
   - Delegated Regulation 2017/565, Art. 9: a personal recommendation is a
     recommendation, presented as suitable for the person or based on
     their circumstances, to take a particular step concerning a
     particular financial instrument.
   - Recital 15: generic advice about a type of financial instrument is
     not investment advice; but a firm that presents it as suitable for
     the person, when it is not, may breach its duty to act in the
     client's best interest.
   This is a summary, not legal advice; a bank's compliance team decides
   the line. Our own, stricter policy: the app may
   encourage investing at the level of types (shares, funds, bonds), never
   names a company, fund, ticker or provider, and never says that
   something suits this person.
   - In production (`TUTOR_PIPELINE` off) the tutor's instructions forbid
     recommending products or predicting prices, and a complete reply that
     matches an advice pattern is replaced by the stored explanation
     (`app/tutor_api.py`). In the stream, text can show briefly before that
     check.
   - The checked pipeline answers advice and injection questions with a
     fixed template before any model call (`tutor/rules.py`), uses the
     `tutor-v2` prompt, and runs the advice check on every model answer
     (`tutor/checks.py`). Red-team results: "Controlling the tutor"
     below.
3. **Every AI output has a fallback.** In the pipeline, every model answer
   goes through four checks (invented numbers, advice, citations, form),
   plus an answer-leak check when it concerns a task; a failed check shows
   the stored explanation. The pipeline is not yet on in production. BASAL
   decides only when it is confident, and the router decides otherwise.
4. **Every AI decision is logged.** `llm_events` for the tutor (masked
   text, checks failed, fallback, latency), `reco_events` of type
   `path_decision` for BASAL.
5. **Kill switches.** `TUTOR_ENABLED=false` stops model calls; the app
   still works, with stored explanations. Answers already in the one-day
   cache are still served (to clear them: `DELETE /admin/tutor-cache`). `BASAL_MODE=shadow` returns path
   choice to the router. Both are environment variables; neither needs a
   deploy.

## Client privacy

**Today.**
- Email addresses, phone numbers, IBANs and PESEL numbers in a learner's
  messages and chat history are masked before they reach the model and
  before they are stored (since 2026-11-22 also in the original tutor
  path). The task context fields (question, chosen answer, explanation)
  are task content and are not masked. Masking catches these patterns
  only; it does not prove that a message is impersonal.
- The model runs on our own machine. Cloud model roles are off
  (`CLOUD_ROLES_ENABLED=false`), and a request with user data never goes to
  a cloud role.
- BASAL gets the survey answers as bands (age group, goal, horizon,
  experience, self-rating) and the quiz answers, no identity.
- Admin views show a pseudonymous id (a hash of the user id).
- The bank-side views show an individual learner only if that learner
  shared their profile (`PUT /me/consent`). Everyone else appears only in
  aggregates, and a group of fewer than 5 people is hidden.
- Guests are stateless: nothing about a guest is stored on the server.

**Not built yet.**
- Retention: the design keeps flagged masked text for 30 days, but no job
  deletes it.
- Access and deletion on request (GDPR Articles 15 and 17): only study
  participants can be deleted today.
- The pseudonymous id is an unkeyed hash; a keyed hash (HMAC with a secret)
  would stop anyone who knows a user id from finding that user's rows.
- A data protection impact assessment (GDPR Article 35) before launch.

**Full product.**
- Collect only what a feature uses, and write down why for each field.
- Keep learning data and marketing apart. Using learning data to market
  products needs its own consent, which the customer can withdraw.
- Run the models inside the bank's environment, so customer data does not
  leave it.
- Log every access to individual data (who, when, why), and grant it by
  role.
- Set a retention period per table, and delete on schedule.

## Monitoring BASAL

Each onboarding writes one `path_decision` row: who decided (BASAL or the
rules), why the fallback ran, BASAL's answer and confidence per node, its
latency, the router's path and the final path. Monitoring reads these rows.

**Drift: is BASAL still behaving as it did?**

| Signal | What a change means |
|---|---|
| Share of paths decided by BASAL, and the fallback reasons, per day | more `low_confidence`: the inputs moved away from what the model knows; more `unreachable`: an operations problem |
| Distribution of BASAL's confidence, and the share below τ | the model became less sure, after a model update or a change in who signs up |
| Agreement with the router (overlap of the two paths) | a sudden change with the same inputs points to the model; with new inputs, to the population |
| Mix of inputs: age band, goal, knowledge band | a new audience (for example, after a campaign) for which neither model was checked |
| Latency p95 against the 3 s timeout | capacity |

Thresholds come from the first week of data, used as the baseline.

**Feedback: are BASAL's choices good?**
- **Outcomes per path step:** success on the first question of the mission,
  mission completed, return within 7 days, change in confidence. The
  decision log in [admin_and_profile.md](admin_and_profile.md) has these
  fields.
- **A/B test.** Assign each new learner to BASAL or the router by a hash of
  the pseudonymous id, and log the arm in `path_decision`. Today
  `BASAL_MODE` applies to everyone; per-learner assignment is a small
  change in `app/path_decider.py`. Fix the metric, the sample size and the
  decision rule before looking at results.
- **Calibration:** compare BASAL's `ready_` probabilities with first-question
  outcomes (Brier score, reliability diagram), and recalibrate if needed.
- **People read the disagreements.** Take a weekly sample of paths where
  BASAL and the router disagree, and read them against the learner's
  answers.
- **Model updates.** Run a new BASAL version in shadow mode first, compare
  it on logged states, then switch. The model name is logged in every row.
- **Rollback:** `BASAL_MODE=shadow`.

## Controlling the tutor

**Today.**
- One model call per message, with no tools: the tutor can answer, and it
  cannot act.
- Production runs the original path: the app sends the context; the tutor
  is guarded by its instructions and an advice pattern on its complete
  replies. The pipeline, where the backend fetches the context and every
  model answer is checked (rule 3), is built and switched by
  `TUTOR_PIPELINE`.
- The pipeline passed its red-team run on the real model, run by Mohamed
  on a local API: every advice and injection prompt got the template, and
  no check failed ([tutor_agent.md](tutor_agent.md), section 3, has the
  numbers).
- Flagged answers are listed in the admin panel, and a reviewer labels them
  (`review_label`).
- Limits: 8 messages a minute and 80 a day per account (guests per IP).
  The minute counter and the guests' daily counter live in each of the two
  worker processes.
  Above them the learner gets a short message and the GPU is spared.

**Full product.**
- Re-run the red-team set before every prompt or model change, and ship only
  if it passes the agreed criteria.
- Watch the share of failed checks, the fallback rate and learner ratings
  per day, with alerts.
- A person reviews a weekly sample of answers.
- Incident: a flagged piece of advice switches the affected mode off; then
  fix, re-run the red team, and switch it back on.
- If the tutor ever gets tools (for example, reading the learner's account
  data), each tool reads only, is allowlisted, is limited to that user's
  data, and its result is checked like any other output.

## A personalised version, linked to a bank account

**What it adds.** With the customer's consent, the app reads their real
figures: balance, regular income, savings. Then:
- the path starts from the real buffer, not from a survey answer;
- a Day-X task can replay the customer's own last year;
- a hard task can start from the customer's own household.

**Where the line stays.**
- It remains education at the level of types. Once the app presents a
  product as suitable for this customer, it is investment advice, with a
  suitability assessment (Delegated Regulation 2017/565, Art. 54). At that
  point the app hands over to a licensed adviser.
- The adviser panel shows needs at the level of types, and only for
  customers who agreed.
- The data stays in the bank; the models run in the bank's environment.
- Separate consents for linking the account and for being contacted by an
  adviser, each one revocable.
