import json, os, time, urllib.request, urllib.error, sys

INPUT = "/home/user/Cat-shao/citation-dag/todo_batch_1.txt"
TMPDIR = "/home/user/Cat-shao/citation-dag/tmp_fetches"
OUTPUT = "/home/user/Cat-shao/citation-dag/depth2_batch1.json"
os.makedirs(TMPDIR, exist_ok=True)

with open(INPUT) as f:
    ids = [line.strip() for line in f if line.strip()]

def is_valid(fpath):
    if not os.path.exists(fpath):
        return False
    with open(fpath) as f:
        content = f.read().strip()
    if content == "not_found":
        return True
    try:
        d = json.loads(content)
        return "title" in d
    except:
        return False

todo = [i for i in ids if not is_valid(os.path.join(TMPDIR, f"{i}.json"))]
print(f"Total: {len(ids)}, Done: {len(ids)-len(todo)}, Remaining: {len(todo)}", flush=True)

if todo:
    print("Waiting 30s before starting (cooldown)...", flush=True)
    time.sleep(30)

    for idx, arxiv_id in enumerate(todo):
        url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}?fields=title,references.title,references.externalIds,references.year"
        fpath = os.path.join(TMPDIR, f"{arxiv_id}.json")
        print(f"[{idx+1}/{len(todo)}] {arxiv_id} ", end="", flush=True)
        
        success = False
        for retry in range(5):
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read().decode()
                    with open(fpath, 'w') as f:
                        f.write(data)
                    print("OK", flush=True)
                    success = True
                    break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    with open(fpath, 'w') as f:
                        f.write("not_found")
                    print("404", flush=True)
                    success = True
                    break
                elif e.code == 429:
                    wait = 30 * (retry + 1)  # 30, 60, 90, 120, 150
                    print(f"429(w{wait}s) ", end="", flush=True)
                    time.sleep(wait)
                else:
                    print(f"H{e.code}(w30s) ", end="", flush=True)
                    time.sleep(30)
            except Exception as e:
                print(f"E(w20s) ", end="", flush=True)
                time.sleep(20)
        
        if not success:
            print("FAIL", flush=True)
            # Don't write not_found for failures - we'll retry next run
        
        if idx < len(todo) - 1:
            time.sleep(15)  # 15 second delay between requests

# Build final JSON
print("\nBuilding JSON...", flush=True)
result = {}
for arxiv_id in ids:
    fpath = os.path.join(TMPDIR, f"{arxiv_id}.json")
    if not os.path.exists(fpath):
        result[arxiv_id] = "not_found"
        continue
    with open(fpath) as f:
        content = f.read().strip()
    if content == "not_found":
        result[arxiv_id] = "not_found"
        continue
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        result[arxiv_id] = "not_found"
        continue
    title = data.get("title", "")
    refs = []
    for ref in (data.get("references") or []):
        ref_title = ref.get("title", "")
        ref_year = ref.get("year")
        ext_ids = ref.get("externalIds") or {}
        ref_arxiv = ext_ids.get("ArXiv")
        refs.append({"arxiv": ref_arxiv if ref_arxiv else None, "title": ref_title, "year": ref_year})
    result[arxiv_id] = {"title": title, "references": refs}

with open(OUTPUT, "w") as f:
    json.dump(result, f, indent=2)

found = sum(1 for v in result.values() if v != "not_found")
nf = sum(1 for v in result.values() if v == "not_found")
print(f"Done! Found: {found}, Not found: {nf}", flush=True)
