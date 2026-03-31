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
        return True
    try:
        d = json.loads(content)
        return "title" in d
    except:
        return False

# Determine what needs fetching
todo = [i for i in ids if not is_valid(os.path.join(TMPDIR, f"{i}.json"))]
print(f"Total: {len(ids)}, Already done: {len(ids)-len(todo)}, Remaining: {len(todo)}")

if not todo:
    print("Nothing to fetch!")
else:
    print("Initial delay 10s...")
    time.sleep(10)

    for idx, arxiv_id in enumerate(todo):
        url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{arxiv_id}?fields=title,references.title,references.externalIds,references.year"
        fpath = os.path.join(TMPDIR, f"{arxiv_id}.json")
        print(f"[{idx+1}/{len(todo)}] {arxiv_id} ... ", end="", flush=True)
        
        success = False
        for retry in range(3):
            try:
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'Mozilla/5.0 (research bot)')
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read().decode()
                    with open(fpath, 'w') as f:
                        f.write(data)
                    print("OK")
                    success = True
                    break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    with open(fpath, 'w') as f:
                        f.write("not_found")
                    print("404")
                    success = True
                    break
                elif e.code == 429:
                    print(f"429 (retry {retry+1}/3, wait 60s) ", end="", flush=True)
                    time.sleep(60)
                else:
                    print(f"HTTP {e.code} (retry {retry+1}/3, wait 60s) ", end="", flush=True)
                    time.sleep(60)
            except Exception as e:
                print(f"Error: {e} (retry {retry+1}/3, wait 30s) ", end="", flush=True)
                time.sleep(30)
        
        if not success:
            with open(fpath, 'w') as f:
                f.write("not_found")
            print("FAILED")
        
        # Delay between requests
        if idx < len(todo) - 1:
            time.sleep(5)

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

print(f"Wrote {len(result)} entries to {OUTPUT}")
found = sum(1 for v in result.values() if v != "not_found")
not_found = sum(1 for v in result.values() if v == "not_found")
print(f"Found: {found}, Not found: {not_found}")
