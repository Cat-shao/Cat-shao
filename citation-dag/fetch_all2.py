import json
import os
import time
import urllib.request
import urllib.error

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
        return True  # genuinely not found (404)
    try:
        d = json.loads(content)
        return "title" in d
    except:
        return False

todo = [i for i in ids if not is_valid(os.path.join(TMPDIR, f"{i}.json"))]
print(f"Total: {len(ids)}, Already done: {len(ids)-len(todo)}, Remaining: {len(todo)}")
import sys; sys.stdout.flush()

if not todo:
    print("Nothing to fetch!")
else:
    print("Initial delay 15s...")
    sys.stdout.flush()
    time.sleep(15)

    consecutive_429 = 0
    for idx, arxiv_id in enumerate(todo):
        url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}?fields=title,references.title,references.externalIds,references.year"
        fpath = os.path.join(TMPDIR, f"{arxiv_id}.json")
        print(f"[{idx+1}/{len(todo)}] {arxiv_id} ... ", end="", flush=True)
        
        success = False
        for retry in range(5):  # more retries
            try:
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'Mozilla/5.0 (research bot)')
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read().decode()
                    with open(fpath, 'w') as f:
                        f.write(data)
                    print("OK")
                    sys.stdout.flush()
                    success = True
                    consecutive_429 = 0
                    break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    with open(fpath, 'w') as f:
                        f.write("not_found")
                    print("404")
                    sys.stdout.flush()
                    success = True
                    consecutive_429 = 0
                    break
                elif e.code == 429:
                    consecutive_429 += 1
                    wait = min(30 + consecutive_429 * 15, 120)
                    print(f"429(wait {wait}s) ", end="", flush=True)
                    time.sleep(wait)
                else:
                    print(f"HTTP{e.code}(wait 30s) ", end="", flush=True)
                    time.sleep(30)
            except Exception as e:
                print(f"Err(wait 20s) ", end="", flush=True)
                time.sleep(20)
        
        if not success:
            with open(fpath, 'w') as f:
                f.write("not_found")
            print("FAILED")
            sys.stdout.flush()
        
        # Adaptive delay
        if idx < len(todo) - 1:
            delay = 5 if consecutive_429 == 0 else 15
            time.sleep(delay)

# Build final JSON
print("\nBuilding final JSON...")
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
        refs.append({
            "arxiv": ref_arxiv if ref_arxiv else None,
            "title": ref_title,
            "year": ref_year
        })
    result[arxiv_id] = {"title": title, "references": refs}

with open(OUTPUT, "w") as f:
    json.dump(result, f, indent=2)

found = sum(1 for v in result.values() if v != "not_found")
not_found = sum(1 for v in result.values() if v == "not_found")
print(f"Wrote {len(result)} entries. Found: {found}, Not found: {not_found}")
