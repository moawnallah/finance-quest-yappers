"""Validates content/slices/*.json + wheel.json + eu_benchmark.json, then writes roadmap.json.

Run: python3 content/validate_content.py        (exit code 1 on any error)
Rules: unique ids, ids prefixed with their slice, 'after' points to real nodes in the same slice,
no cycles, answer index in range, feedback count = options count, URLs valid, no renumbering
of ids already published (checked against content/published_ids.txt).
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
errors = []

def err(msg):
    errors.append(msg)

wheel = json.load(open(os.path.join(HERE, "wheel.json")))
slices = {}
for key in wheel["order"]:
    p = os.path.join(HERE, "slices", f"{key}.json")
    if not os.path.exists(p):
        err(f"wheel.json lists '{key}' but slices/{key}.json is missing"); continue
    slices[key] = json.load(open(p))
for f in os.listdir(os.path.join(HERE, "slices")):
    if f.endswith(".json") and f[:-5] not in wheel["order"]:
        err(f"slices/{f} exists but is not listed in wheel.json order")

seen = {}
url_re = re.compile(r"^https?://[^\s]+$")
for key, s in slices.items():
    if s.get("key") != key:
        err(f"{key}: 'key' field is '{s.get('key')}'")
    if not 1 <= s.get("risk", 0) <= 5:
        err(f"{key}: risk must be 1-5")
    node_ids = {n["id"] for n in s["nodes"]}
    graph = {}
    for n in s["nodes"]:
        nid = n["id"]
        if not nid.startswith(key + "."):
            err(f"{nid}: node id must start with '{key}.'")
        if nid in seen: err(f"duplicate id {nid} (also in {seen[nid]})")
        seen[nid] = key
        graph[nid] = n.get("after", [])
        for a in graph[nid]:
            if a not in node_ids:
                err(f"{nid}: after '{a}' is not a node in {key}")
        if not n["questions"] and not n.get("retired"):
            err(f"{nid}: has no questions")
        for q in n["questions"]:
            qid = q["id"]
            if not qid.startswith(nid + "."):
                err(f"{qid}: question id must start with '{nid}.'")
            if qid in seen: err(f"duplicate id {qid}")
            seen[qid] = key
            opts = q.get("options", [])
            if len(opts) < 2: err(f"{qid}: needs at least 2 options")
            if "answer" in q and not (isinstance(q["answer"], int) and 0 <= q["answer"] < len(opts)):
                err(f"{qid}: answer index out of range")
            if "answer" in q and not q.get("why"):
                err(f"{qid}: scored question needs 'why'")
            if "feedback" in q and len(q["feedback"]) != len(opts):
                err(f"{qid}: feedback count must equal options count")
            if "answer" in q and "feedback" in q:
                err(f"{qid}: use either 'answer' (scored) or 'feedback' (behaviour), not both")
            for u in q.get("sources", []):
                if not url_re.match(u): err(f"{qid}: bad source url {u}")
    # cycle check (DFS)
    state = {}
    def visit(v, path):
        if state.get(v) == 1: err(f"{key}: cycle {' -> '.join(path + [v])}"); return
        if state.get(v) == 2: return
        state[v] = 1
        for w in graph.get(v, []): visit(w, path + [v])
        state[v] = 2
    for v in graph: visit(v, [])

bench = json.load(open(os.path.join(HERE, "eu_benchmark.json")))
for q in bench["quiz"]:
    if q["id"] in seen: err(f"benchmark id {q['id']} collides with roadmap")
    seen[q["id"]] = "eu_benchmark"
    if not 0 <= q["answer"] < len(q["options"]): err(f"{q['id']}: answer index out of range")

# published ids must never disappear (retire instead of delete/renumber)
pub_path = os.path.join(HERE, "published_ids.txt")
if os.path.exists(pub_path):
    published = {l.strip() for l in open(pub_path) if l.strip()}
    missing = sorted(published - set(seen))
    for m in missing:
        err(f"published id '{m}' disappeared: mark it \"retired\": true instead of deleting or renumbering")

if errors:
    print(f"FAILED: {len(errors)} problem(s)")
    for e in errors: print(" -", e)
    sys.exit(1)

# all good: write combined roadmap.json for the seed script and record published ids
combined = {"content_version": wheel["content_version"], "order": wheel["order"], "slices": slices}
json.dump(combined, open(os.path.join(HERE, "roadmap.json"), "w"), indent=2, ensure_ascii=False)
open(pub_path, "w").write("\n".join(sorted(seen)) + "\n")
nq = sum(len(n["questions"]) for s in slices.values() for n in s["nodes"])
print(f"OK: {len(slices)} slices, {sum(len(s['nodes']) for s in slices.values())} nodes, {nq} questions + {len(bench['quiz'])} benchmark. roadmap.json rebuilt.")
