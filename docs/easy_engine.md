# Easy engine: implementation guide

Readers:
- backend (Mohamed): loading nodes, the API, scoring and prerequisite tests;
- frontend (Michał): the JSON to render;
- ML (Mateusz): the answer secrets for the tutor's leak check;
- content authors: writing cards and items.

The spec is [task_engines.md](task_engines.md), "Easy engine". This file
describes the code in `backend/data/easy/`. Status: 2026-11-20, owner Yurii.
The medium engine has its own guide: [medium_engine.md](medium_engine.md).

## What is implemented

| Part | Implemented |
|---|---|
| Item kinds | `single`, `multi`, `true_false`, `numeric`, `reflection` (all five from the spec) |
| Cards | checked and served with their links resolved from `backend/content/sources.yaml` |
| Prerequisite test | 2-3 check items from the node's `after` nodes, the same for a given seed |
| Test-out | 2 of the node's own check items, for nodes the router marks "probably known" ([onboarding_router.md](onboarding_router.md), "Path") |
| Completion | easy part: prerequisite test passed, or the items average at least 0.8; whole node: also one medium task ≥ 0.6 |
| Confidence | 1-5 on every scored item, stored and not scored (none on reflections) |

Scores:

| Kind | Response | Score |
|---|---|---|
| `single` | option index (0-based) | 1 or 0 |
| `multi` | list of option indexes | (correct picks − wrong picks) / number of correct options, clipped to 0-1 |
| `true_false` | true / false | 1 or 0 |
| `numeric` | a number | 1 within the tolerance band, then down to 0 at three bands |
| `reflection` | option index | not scored; the reveal has feedback for each option |

## Files

```
backend/content/nodes/<NODE>.yaml        node files: cards, items (and medium tasks); see _TEMPLATE_easy.yaml
backend/content/sources.yaml             source register (Mateusz); card links and item sources point here
backend/data/common.py                   helpers shared with the medium engine (texts, tolerance rule, ...)
backend/data/easy/
  kinds.py      ITEM_KINDS: one small class per kind
  node.py       validate -> compile; node_view / question_view / reveal_view; score; prerequisite test
  build.py      command line and QA report
backend/data/schemas/easy.schema.json    contract for the output
backend/data/output/easy.json            built nodes (committed)
backend/data/output/easy_qa.md           QA report of the last build
```

## Build

```bash
cd backend/data
python -m easy.build --strict     # exit 1 if any node has an error
python -m pytest tests
```

Read `output/easy_qa.md` after every build. It has one row per node, with
the number of cards, items and check items, and the size of the
prerequisite pool. Missing prerequisite nodes (for example F2, which has no
file yet) are warnings. A node with an error is left out, with all its
cards and items.

## Backend

```python
from easy import (load_nodes, node_view, question_view, reveal_view, score, secrets,
                  prerequisite_test, prerequisite_passed, test_out, easy_done, node_done, AttemptError)

nodes = load_nodes()                                   # {node_id: record}, from output/easy.json
items = {i["id"]: i for n in nodes.values() for i in n["items"]}

# GET /nodes/{id}: cards and items without answers
node_view(nodes["I4"], lang="en")

# POST /answers {task_id, response, confidence}
try:
    result = score(items["i4.e1"], response=1, confidence=4)
except AttemptError as e:       # wrong response type, index out of range, confidence not 1-5
    ...                         # -> 400 with the message
return {**result, "reveal": reveal_view(items["i4.e1"], lang="en")}

# Prerequisite test for node P1: item ids. Use the user id as the seed, so a reload shows the same test.
prerequisite_test(nodes, "P1", seed=user_id)           # e.g. ['i4.e1', 'i2.e1', 'i4.e2']
test_out(nodes, "I4", seed=user_id)                    # 2 own check items when the router marks I4 "probably known"
prerequisite_passed([1.0, 1.0, 1.0])                   # every drawn item scored 1 (prerequisite test or test-out)
easy_done(prerequisite_scores, item_scores)            # the completion rule for the easy part
node_done(easy_part_done, medium_scores)               # the whole node: easy done and one medium task >= 0.6
```

`score()` returns the attempt-record fields:

```json
{"task_id": "i4.e1", "content_version": 1, "level": "easy",
 "response": {"value": 1}, "confidence": 4, "p": 0.75,
 "score_estimate": null, "score_reasons": null, "score": 1.0}
```

`score_estimate` and `score_reasons` are always null for easy items. They
are there so both engines return the same attempt-record columns. For a
reflection, `score`, `confidence` and `p` are null too.

Other rules:
- `node["live"]` is false until a reviewer has signed the node off.
- Item difficulty (starting Elo) is in each item record. Updating it from
  attempts belongs to the learner model.

**Tutor.** `secrets(item)` returns
`{"strings": [correct option texts], "numbers": [numeric answers]}`. That
is the shape of `ContextProvider.task_secrets()` in `backend/ml/tutor`, so
the backend can return it directly.

## Frontend

`node_view` (trimmed):

```json
{
  "node": "I4", "panel": "INSTRUMENTS", "title": "One stock vs an index", "after": ["I1"], "status": "draft",
  "cards": [{
    "id": "i4.c1", "title": "One company or a basket", "body": "An index is a basket of ...", "example": "...",
    "links": [{"id": "eb525_pl", "title": "Flash Eurobarometer 525 ...", "publisher": "European Commission",
               "url": "https://data.europa.eu/data/datasets/s2953_fl525_eng"}]
  }],
  "items": [{
    "id": "i4.e1", "node": "I4", "level": "easy", "kind": "single", "content_version": 1, "scored": true,
    "q": "Why can one company's shares fall to zero while a broad index rarely does?",
    "options": ["Indexes are protected by the state", "For an index to reach zero, all its companies would have to fail at once", "The stock exchange fixes index prices"],
    "confidence": {"min": 1, "max": 5}
  }]
}
```

A numeric item, before and after the answer:

```json
{"id": "s1.e2", "kind": "numeric", "q": "Ania's essential costs are 4,800 PLN a month. ...",
 "unit": "PLN", "input": {"min": 0, "max": 30000, "step": 100}, "confidence": {"min": 1, "max": 5}}

{"answer": 14400, "unit": "PLN", "tolerance": {"kind": "absolute", "band": 100},
 "why": "4,800 PLN x 3 months = 14,400 PLN. ...", "sources": []}
```

How to render:
- **Responses.** `single` and `reflection`: one option, sent as its index.
  `multi`: several options, sent as a list of indexes. `true_false`: two
  buttons, sent as a boolean. `numeric`: a slider from `input` if given,
  else a number field.
- **Confidence.** Ask for it only when the item has `confidence`. Scored
  items have it; reflections don't.
- **Reveal.** Show `why`. Highlight `answer`: an index, a list of indexes,
  a boolean or a number. For a reflection, show the `feedback` entry of
  the option the user picked.
- **Cards.** Show each link by its `title` and `publisher`, opening `url`.
- **Texts** come back as plain strings in the requested `lang`, falling
  back to English.

## Content authors

Copy the blocks you need from `backend/content/nodes/_TEMPLATE_easy.yaml`.
Rules the build enforces:
- **IDs.** Cards are `<node>.c<n>` and items `<node>.e<n>`, with the node
  in lower case. IDs are unique across all nodes.
- **Answers fit the kind.**
  - `single`: an option index.
  - `multi`: a non-empty list of distinct indexes.
  - `true_false`: true or false.
  - `numeric`: a number, a `unit` and a `tolerance`.
  - `reflection`: no answer, and one `feedback` per option.
- **Options.** 2-6 per item.
- **`why`.** Required on every scored item.
- **Reflections** can't be check items.
- **Cards.** At most 80 words. 1-2 links is a warning, not an error. Links
  and item `sources` must exist in `sources.yaml`. A source whose licence
  is still `to_check` gives a warning.
- **`valid_until`** must not be in the past. Use it when a card or item
  states a limit, rate or tax rule, as I2 does with the BFG limit.
- **Check items.** Mark the items you want to test this node's skill in
  later nodes with `check: true`, at least 2 per node.

## Developers: adding a kind (e.g. matching or ranking)

Write one class in `easy/kinds.py` with the same methods as the others,
then add it to `ITEM_KINDS`:

| Method | Returns |
|---|---|
| `validate(item, report)` | nothing; reports problems |
| `public(item)` | fields for the question (never the answer) |
| `reveal(item)` | fields for the reveal |
| `check(item, response)` | None, or a message for an invalid response |
| `score(item, response)` | 0..1, or None if the kind is not scored |
| `secrets(item)` | `{"strings": [...], "numbers": [...]}` |

Then add the kind to the `enum` in `schemas/easy.schema.json` and add a
test in `backend/data/tests/test_easy.py`.

## Choices not fixed by the spec (please review)

1. **Answer indexes are 0-based**, as in today's `roadmap.json`.
2. **Prerequisite test.**
   - Items are spread round-robin over the prerequisite nodes.
   - The default is 3 items, or fewer if the pool is smaller.
   - The draw is seeded by user id and node, so a reload shows the same
     test.
   - Prerequisite nodes without a file are skipped.
3. **Completion.** The 0.8 average covers whichever scored items the
   backend passes in. The backend decides whether unanswered items count
   as 0.
4. **`checked`** (the fact-check note on cards) stays in `meta`. It is
   never sent to the app.
5. **Card checks.** The 1-2 links rule and a missing `example` are
   warnings, so drafts build; more than 80 words is an error.
6. **`numeric.input`** (min, max, step) is optional and only drives the
   slider. It must contain the answer.
7. **Test-out.** It uses 2 of the node's own check items, and is passed
   like the prerequisite test: every item scores 1. The router spec doesn't
   say what happens after a passed test-out, so the backend decides,
   presumably marking the easy part done.
8. **Item IDs are `<node>.e<n>`** (the spec's `f4.e1`). skills_tree.md says
   reused `roadmap.json` questions keep their IDs (e.g. `bonds.b1.q1`),
   which would fail this rule. We decided not to reuse them, because that
   content was made up for testing. If that changes, the rule needs an
   exception.
